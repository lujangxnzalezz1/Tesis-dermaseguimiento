"""Webhook de pagos (real) y página de checkout de la pasarela sandbox (solo desarrollo)."""
import json
import logging
import uuid
from decimal import Decimal
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from models.suscripcion import PAGO_APROBADO, PAGO_CANCELADO, PAGO_PENDIENTE, PAGO_RECHAZADO, Pago
from core.tiempo import ahora
from services.letras import formato_monto
from services import auditoria_service as audit
from services import pasarela
from services.suscripcion_service import aplicar_pago_aprobado

log = logging.getLogger("pagos")
router = APIRouter(tags=["Pasarela de pago"])

ESTADOS_FINALES = {"aprobado": PAGO_APROBADO, "rechazado": PAGO_RECHAZADO, "cancelado": PAGO_CANCELADO}


@router.post("/webhooks/pago")
async def webhook_pago(request: Request, db: Session = Depends(get_db)):
    """Recibe el resultado de la transacción desde la pasarela. Valida la firma HMAC y la antigüedad,
    verifica que monto y moneda coincidan, y es IDEMPOTENTE: un mismo pago no se procesa dos veces."""
    cuerpo = await request.body()
    try:
        pasarela.verificar_firma(cuerpo, request.headers.get("X-Pasarela-Timestamp"), request.headers.get("X-Pasarela-Firma"))
    except pasarela.ErrorFirma as e:
        audit.registrar(db, request, None, "pagos", "webhook", resultado="fallo", detalle=f"firma rechazada: {e}")
        raise HTTPException(401, "Notificación rechazada: no se pudo verificar su autenticidad.")
    try:
        evento = json.loads(cuerpo)
        referencia, estado, evento_id = str(evento["referencia"]), str(evento["estado"]), str(evento["evento_id"])
    except Exception:
        raise HTTPException(400, "La notificación no tiene el formato esperado.")

    pago = db.query(Pago).filter(Pago.referencia_externa == referencia).with_for_update().first()
    if not pago:
        audit.registrar(db, request, None, "pagos", "webhook", resultado="fallo", detalle=f"referencia desconocida {referencia}")
        raise HTTPException(404, "Operación de pago desconocida.")

    if estado == "pendiente":
        return {"procesado": False, "motivo": "sin cambios (pendiente)"}
    if estado not in ESTADOS_FINALES:
        raise HTTPException(400, "Estado de pago no reconocido.")

    if pago.estado != PAGO_PENDIENTE:
        # Reintentos/duplicados de la pasarela: se responde 200 sin volver a procesar
        conflicto = ESTADOS_FINALES[estado] != pago.estado
        audit.registrar(db, request, None, "pagos", "webhook_duplicado", entidad="pago", entidad_id=pago.id,
                        resultado="fallo" if conflicto else "exito",
                        detalle="evento en conflicto con el estado final ya registrado" if conflicto else "evento repetido ignorado")
        return {"procesado": False, "motivo": "duplicado"}

    try:
        monto_ok = Decimal(str(evento.get("monto"))) == Decimal(pago.monto) and str(evento.get("moneda")) == pago.moneda
    except Exception:
        monto_ok = False
    if not monto_ok:
        audit.registrar(db, request, None, "pagos", "webhook", entidad="pago", entidad_id=pago.id, resultado="fallo",
                        detalle="el monto o la moneda no coinciden con la operación")
        raise HTTPException(400, "El monto informado no coincide con la operación.")

    pago.estado = ESTADOS_FINALES[estado]
    pago.ultimo_evento_id = evento_id
    pago.forma_pago = str(evento.get("forma_pago") or "") or None
    pago.actualizado_en = ahora()
    db.flush()
    if pago.estado == PAGO_APROBADO:
        aplicar_pago_aprobado(db, pago)
    else:
        db.commit()
    audit.registrar(db, request, None, "pagos", f"pago_{pago.estado}", entidad="pago", entidad_id=pago.id, usuario_id=pago.usuario_id,
                    despues={"referencia": referencia, "monto": str(pago.monto)})
    return {"procesado": True, "estado": pago.estado}


# ----------------------------------------------------------------- pasarela sandbox (simula al proveedor externo)

def _pagina(titulo: str, cuerpo: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(titulo)}</title>
<style>body{{font-family:-apple-system,Segoe UI,sans-serif;background:#f3f6f7;margin:0;padding:24px;color:#1D3D47}}
.c{{max-width:420px;margin:0 auto;background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 10px #0002}}
button{{width:100%;padding:14px;margin-top:10px;border:0;border-radius:8px;font-size:16px;font-weight:600;color:#fff;cursor:pointer}}
.ok{{background:#2e7d32}}.no{{background:#c62828}}.ca{{background:#757575}}.pe{{background:#ef6c00}}
small{{color:#666}}</style></head><body><div class="c">{cuerpo}</div></body></html>""")


if settings.PASARELA == "sandbox":

    @router.get("/pasarela-sandbox/checkout/{referencia}", response_class=HTMLResponse, include_in_schema=False)
    def checkout_sandbox(referencia: str, db: Session = Depends(get_db)):
        pago = db.query(Pago).filter(Pago.referencia_externa == referencia).first()
        if not pago or pago.proveedor != "sandbox":
            return _pagina("Pago no encontrado", "<h2>Operación no encontrada</h2><p>El enlace de pago no es válido.</p>")
        if pago.estado != PAGO_PENDIENTE:
            return _pagina("Pago finalizado", f"<h2>Esta operación ya fue {escape(pago.estado)}</h2><p>Podés volver a la app.</p>")
        return _pagina("Pasarela de pruebas", f"""
<h2>Pasarela de pruebas (sandbox)</h2><p><b>{escape(formato_monto(pago.monto, pago.moneda))}</b><br><small>Ref. {escape(referencia)}</small></p>
<small>Entorno de prueba: no se realiza ningún cobro real. El resultado se informa al sistema con un webhook firmado.</small>
<form method="post" action="/pasarela-sandbox/decidir"><input type="hidden" name="referencia" value="{escape(referencia)}">
<button class="ok" name="decision" value="aprobado">Pagar (aprobar)</button>
<button class="no" name="decision" value="rechazado">Simular tarjeta rechazada</button>
<button class="ca" name="decision" value="cancelado">Cancelar pago</button>
<button class="pe" name="decision" value="pendiente">Dejar pendiente</button></form>""")

    @router.post("/pasarela-sandbox/decidir", response_class=HTMLResponse, include_in_schema=False)
    def decidir_sandbox(referencia: str = Form(...), decision: str = Form(...), db: Session = Depends(get_db)):
        pago = db.query(Pago).filter(Pago.referencia_externa == referencia, Pago.proveedor == "sandbox").first()
        if not pago or decision not in ("aprobado", "rechazado", "cancelado", "pendiente"):
            return _pagina("Error", "<h2>Solicitud no válida</h2>")
        evento = {
            "evento_id": uuid.uuid4().hex, "referencia": referencia, "estado": decision, "monto": str(pago.monto),
            "moneda": pago.moneda, "forma_pago": "Tarjeta de crédito (sandbox)",
        }
        codigo = pasarela.enviar_webhook(evento)
        if codigo >= 400:
            return _pagina("Error", "<h2>No pudimos avisar al comercio</h2><p>Intentá de nuevo en unos minutos.</p>")
        textos = {"aprobado": "¡Pago aprobado!", "rechazado": "Pago rechazado", "cancelado": "Pago cancelado", "pendiente": "Pago pendiente"}
        volver = settings.CORS_ORIGINS.split(",")[0].strip()
        enlace = f'<p><a href="{escape(volver)}/suscripcion">Volver a la aplicación (versión web)</a></p>' if volver else ""
        return _pagina("Resultado", f"<h2>{textos[decision]}</h2><p>Ya podés cerrar esta ventana y volver a la aplicación.</p>{enlace}")
