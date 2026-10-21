import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.ratelimit import dependencia as limite
from core.security import hash_password, obtener_usuario_actual, revocar_sesiones_de_usuario, verify_password
from core.tiempo import ahora
from models.paciente import Paciente
from models.usuario import ConsentimientoUsuario, TokenRestablecimiento, Usuario
from schemas.usuario import AceptarPolitica, EliminarCuenta
from services import auditoria_service as audit

router = APIRouter(tags=["Privacidad"])


def _contacto() -> str:
    """Si no se configuró CONTACTO_PRIVACIDAD (.env), se indica el canal dentro de la app."""
    return settings.CONTACTO_PRIVACIDAD or "la opción «Mi cuenta» de la app o el administrador del sistema"


def texto_politica() -> dict:
    return {
        "version": settings.POLITICA_VERSION,
        "titulo": "Política de Privacidad de DermaSeguimiento",
        "secciones": [
            {"titulo": "Qué datos recopilamos",
             "texto": "De los profesionales: nombre, correo electrónico, contraseña (almacenada solo como hash) y registros de uso. "
                      "De los pacientes, cargados por el dermatólogo: cédula, nombre, apellido, fecha de nacimiento, sexo, teléfono, "
                      "antecedentes médicos, observaciones y fotografías clínicas del rostro con sus métricas de color."},
            {"titulo": "Para qué los usamos",
             "texto": "Exclusivamente para el seguimiento fotográfico dermatológico: alinear imágenes, medir cambios de color de la piel "
                      "y mostrar la evolución al profesional. No se usan para otros fines distintos a los declarados al paciente. "
                      "Los resultados son informativos y de apoyo; la interpretación clínica corresponde únicamente al profesional habilitado."},
            {"titulo": "Quién es responsable del tratamiento", "texto": f"{settings.RESPONSABLE_TRATAMIENTO}. Contacto: {_contacto()}."},
            {"titulo": "Por cuánto tiempo los conservamos",
             "texto": f"Mientras la cuenta del profesional esté activa y hasta {settings.RETENCION_DATOS_ANIOS} años después de la última "
                      "consulta, salvo obligación legal o de auditoría. Las bajas de pacientes son lógicas: el historial se conserva "
                      "con acceso restringido."},
            {"titulo": "Con quién los compartimos",
             "texto": "No vendemos ni compartimos datos con terceros. Solo intervienen proveedores técnicos necesarios (alojamiento, "
                      "correo electrónico y pasarela de pago, que recibe únicamente datos del pago del profesional, nunca datos clínicos)."},
            {"titulo": "Medidas de seguridad",
             "texto": "Contraseñas con hash bcrypt, sesiones con vencimiento y cierre por inactividad, permisos verificados en el servidor, "
                      "imágenes clínicas sin acceso público y guardadas con nombres aleatorios, comunicaciones cifradas (HTTPS) en producción "
                      "y bitácora de auditoría de las operaciones."},
            {"titulo": "Tus derechos",
             "texto": "Podés pedir acceso, actualización, corrección o eliminación de tus datos escribiendo a "
                      f"{_contacto()}. Podés retirar tu consentimiento y dar de baja tu cuenta en cualquier momento desde "
                      "«Mi cuenta» en la app: tus datos personales se anonimizan y se cierran tus sesiones. Los registros que deban conservarse por razones legales, contractuales o de auditoría "
                      "no pueden eliminarse."},
            {"titulo": "Consentimiento del paciente",
             "texto": "Antes de registrar a un paciente o sus fotos, el profesional debe obtener su consentimiento informado. El sistema "
                      "guarda quién lo registró, la fecha y hora, la versión de esta política y la finalidad autorizada, y permite revocarlo."},
        ],
    }


@router.get("/politica-privacidad")
def politica_privacidad():
    return texto_politica()


@router.post("/aceptar-politica")
def aceptar_politica(datos: AceptarPolitica, request: Request, db: Session = Depends(get_db),
                     usuario: Usuario = Depends(obtener_usuario_actual)):
    """Aceptación de una versión nueva de la política (la app la pide al ingresar si cambió)."""
    from routers.auth import registrar_consentimiento  # importación diferida: evita un ciclo entre routers

    if datos.version != settings.POLITICA_VERSION:
        raise HTTPException(409, "La política cambió mientras la leías. Volvé a abrirla para ver la versión vigente.")
    anterior = usuario.politica_aceptada_version
    registrar_consentimiento(db, request, usuario)
    db.commit()
    audit.registrar(db, request, usuario, "privacidad", "aceptar_politica", entidad="usuario", entidad_id=usuario.id,
                    antes={"version": anterior},
                    despues={"version": settings.POLITICA_VERSION, "finalidad": settings.FINALIDAD_CONSENTIMIENTO_USUARIO})
    return {"mensaje": "Gracias. Registramos tu aceptación de la Política de Privacidad.", "version": settings.POLITICA_VERSION}


def anonimizar_usuario(db: Session, usuario: Usuario, motivo: str) -> None:
    """Inactiva la cuenta y reemplaza los datos personales del profesional (sin commit).

    Se CONSERVAN, con el id interno del usuario:
    - la bitácora de auditoría: es inmutable y es la evidencia de quién hizo qué (RNF-12); la ley
      permite conservar datos para cumplir obligaciones legales y de rendición de cuentas;
    - suscripciones, pagos y comprobantes: son registros contables y tributarios que deben
      conservarse por el plazo que fija la normativa tributaria;
    - las fichas clínicas de sus pacientes: son historia clínica (no son datos del profesional) y
      tienen su propio plazo de conservación; se desactivan y el script de retención
      (scripts/retencion_datos.py) las anonimiza cuando vence RETENCION_DATOS_ANIOS."""
    ahora_ = ahora()
    usuario.activo = False
    usuario.fecha_inactivacion = ahora_
    usuario.fecha_modificacion = ahora_
    usuario.motivo_inactivacion = motivo[:300]
    usuario.email = f"eliminado-{usuario.id}@anonimizado.invalid"
    usuario.nombre = "Usuario eliminado"
    usuario.password_hash = hash_password(secrets.token_urlsafe(32))  # nadie conoce la contraseña nueva
    usuario.email_verificado = False
    usuario.anonimizado_en = ahora_
    usuario.consentimiento_revocado_en = usuario.consentimiento_revocado_en or ahora_
    db.query(ConsentimientoUsuario).filter(
        ConsentimientoUsuario.usuario_id == usuario.id, ConsentimientoUsuario.revocado_en.is_(None)
    ).update({"revocado_en": ahora_}, synchronize_session=False)
    db.query(TokenRestablecimiento).filter(
        TokenRestablecimiento.usuario_id == usuario.id, TokenRestablecimiento.usado_en.is_(None)
    ).update({"usado_en": ahora_}, synchronize_session=False)
    revocar_sesiones_de_usuario(db, usuario.id)


@router.post("/cuenta/eliminar", dependencies=[Depends(limite("eliminar_cuenta", 5, 60))])
def eliminar_mi_cuenta(datos: EliminarCuenta, request: Request, db: Session = Depends(get_db),
                       usuario: Usuario = Depends(obtener_usuario_actual)):
    """Retiro del consentimiento y baja de la cuenta por el propio titular (derecho de supresión).
    Se confirma con la contraseña. No se puede deshacer."""
    if not datos.confirmar:
        raise HTTPException(400, "Confirmá que querés dar de baja tu cuenta. Esta acción no se puede deshacer.")
    if not verify_password(datos.password, usuario.password_hash):
        audit.registrar_fallo(db, request, usuario, "privacidad", "eliminar_cuenta", "contraseña incorrecta")
        raise HTTPException(400, "La contraseña no es correcta. Revisala e intentá de nuevo.")
    if usuario.rol == "admin" and db.query(Usuario).filter(Usuario.rol == "admin", Usuario.activo.is_(True)).count() <= 1:
        raise HTTPException(409, "Sos el único administrador activo. Asigná otro administrador antes de dar de baja tu cuenta.")

    email_anterior = usuario.email
    anonimizar_usuario(db, usuario, "Baja y retiro del consentimiento solicitados por el titular"
                       + (f": {datos.motivo}" if datos.motivo else ""))
    pacientes = db.query(Paciente).filter(Paciente.dermatologo_id == usuario.id, Paciente.activo.is_(True)).all()
    for p in pacientes:  # borrado lógico: la historia clínica se conserva con acceso restringido
        p.activo = False
        p.eliminado_en = ahora()
        p.eliminado_por = usuario.id
        p.motivo_eliminacion = "Baja de la cuenta del profesional"
    db.commit()
    audit.registrar(db, request, None, "privacidad", "eliminar_cuenta", usuario_id=usuario.id, email=email_anterior,
                    entidad="usuario", entidad_id=usuario.id, despues={"pacientes_desactivados": len(pacientes)},
                    detalle=datos.motivo)
    return {"mensaje": "Tu cuenta fue dada de baja y tus datos personales se anonimizaron. Se cerraron todas tus sesiones."}
