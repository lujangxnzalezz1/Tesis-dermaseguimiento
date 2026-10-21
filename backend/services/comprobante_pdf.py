import io
import logging
import os
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from core.config import settings
from models.suscripcion import Comprobante
from services.letras import formato_monto

log = logging.getLogger("comprobantes")


def _logo(pdf, w, h) -> bool:
    """Logo del emisor arriba a la derecha, si EMISOR_LOGO_RUTA apunta a una imagen válida."""
    ruta = settings.EMISOR_LOGO_RUTA
    if not ruta or not os.path.isfile(ruta):
        return False
    try:
        imagen = ImageReader(ruta)
        ancho, alto = imagen.getSize()
        alto_mm = 18 * mm
        ancho_mm = min(50 * mm, alto_mm * ancho / alto)
        pdf.drawImage(imagen, w - 20 * mm - ancho_mm, h - 15 * mm - alto_mm, width=ancho_mm, height=alto_mm,
                      preserveAspectRatio=True, mask="auto")
        return True
    except Exception:  # un logo dañado no impide emitir el recibo
        log.warning("No se pudo dibujar el logo del emisor (%s)", ruta)
        return False


def generar_pdf(c: Comprobante, reimpreso: bool = False) -> bytes:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    _logo(pdf, w, h)
    y = h - 25 * mm
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, y, "RECIBO ELECTRÓNICO DE PAGO")
    y -= 8 * mm
    pdf.setFont("Helvetica", 10)
    estado = c.estado.upper() + (" (REIMPRESIÓN)" if reimpreso else "")
    pdf.drawString(20 * mm, y, f"N.º {c.numero}    Estado: {estado}")
    y -= 6 * mm
    pdf.drawString(20 * mm, y, f"Fecha y hora de emisión (servidor, UTC): {c.fecha_emision:%Y-%m-%d %H:%M:%S}")
    if reimpreso and c.reimpreso_en:
        y -= 5 * mm
        pdf.drawString(20 * mm, y, f"Reimpresión n.º {max(1, (c.reimpresiones or 1) - 1)} del {c.reimpreso_en:%Y-%m-%d %H:%M:%S}")

    def bloque(titulo, lineas):
        nonlocal y
        y -= 10 * mm
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(20 * mm, y, titulo)
        pdf.setFont("Helvetica", 10)
        for linea in lineas:
            y -= 5.5 * mm
            pdf.drawString(24 * mm, y, linea[:110])

    bloque("Emisor", [c.emisor_nombre, f"RUC: {c.emisor_ruc or 'No aplica'}", f"Correo: {c.emisor_email or '-'}"])
    bloque("Pagador", [c.pagador_nombre, f"RUC / CI: {c.pagador_documento or 'No informado'}",
                       f"Teléfono: {c.pagador_telefono or 'No informado'}", f"Correo: {c.pagador_email}"])
    bloque("Detalle", [f"Concepto: {c.concepto}", f"Referencia de la transacción: {c.referencia}",
                       f"Período: {c.periodo or 'No aplica'}"])

    # Desglose: el precio ya incluye el IVA (10 %), por eso el IVA es total / 11
    total = Decimal(c.monto)
    credito = Decimal(c.credito or 0)
    subtotal = Decimal(c.subtotal) if c.subtotal is not None else total + credito
    iva = Decimal(c.iva) if c.iva is not None else (total / 11).quantize(Decimal("1") if c.moneda == "PYG" else Decimal("0.01"))
    importe = [f"Subtotal: {formato_monto(subtotal, c.moneda)}"]
    if credito:
        importe.append(f"Crédito por tiempo no usado aplicado: - {formato_monto(credito, c.moneda)}")
    importe += [f"Total recibido: {formato_monto(total, c.moneda)}", f"IVA 10 % incluido: {formato_monto(iva, c.moneda)}",
                f"En letras: {c.monto_letras}", f"Forma de pago: {c.forma_pago}"]
    bloque("Importe", importe)
    if c.estado == "anulado":
        bloque("ANULADO", [f"Anulado el {c.anulado_en:%Y-%m-%d %H:%M:%S}", f"Motivo: {c.motivo_anulacion or '-'}"])
    y -= 14 * mm
    pdf.setFont("Helvetica-Oblique", 8.5)
    texto = c.leyenda
    while texto:
        pdf.drawString(20 * mm, y, texto[:120])
        texto = texto[120:]
        y -= 4.5 * mm
    pdf.showPage()
    pdf.save()
    return buf.getvalue()
