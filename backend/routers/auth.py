import hashlib
import secrets
from datetime import timedelta

from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from core.captcha import verificar_captcha
from core.config import settings
from core.database import get_db
from core.politica_password import descripcion_politica
from core.ratelimit import dependencia as limite
from core.security import (
    crear_sesion, hash_password, obtener_sesion_actual, obtener_usuario_actual, revocar_sesiones_de_usuario,
    verify_password,
)
from core.tiempo import ahora
from models.usuario import ROL_DERMATOLOGO, TOKEN_RESTABLECER, TOKEN_VERIFICAR, Sesion, TokenRestablecimiento, Usuario
from schemas.usuario import (
    CambiarPassword, Restablecer, SolicitudReenvio, SolicitudRestablecer, Token, UsuarioRegistro, UsuarioRespuesta,
)
from services import auditoria_service as audit
from services import email_service
from services.suscripcion_service import asegurar_suscripcion

router = APIRouter(tags=["Autenticación"])

MSG_CREDENCIALES = "Correo o contraseña incorrectos. Revisá los datos e intentá de nuevo."
MSG_NO_VERIFICADO = ("Todavía no confirmaste tu correo. Abrí el enlace que te enviamos al registrarte "
                     "o pedí uno nuevo con «Reenviar correo de confirmación».")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _enviar_verificacion(db: Session, usuario: Usuario) -> None:
    """Invalida enlaces anteriores y envía uno nuevo de un solo uso para confirmar el correo."""
    db.query(TokenRestablecimiento).filter(
        TokenRestablecimiento.usuario_id == usuario.id, TokenRestablecimiento.tipo == TOKEN_VERIFICAR,
        TokenRestablecimiento.usado_en.is_(None),
    ).update({"usado_en": ahora()})
    token = secrets.token_urlsafe(32)
    db.add(TokenRestablecimiento(
        usuario_id=usuario.id, token_hash=_hash_token(token), tipo=TOKEN_VERIFICAR,
        expira_en=ahora() + timedelta(hours=settings.VERIFICACION_EMAIL_HORAS),
    ))
    db.commit()
    email_service.enviar(db, usuario.email, "verificar_email", {
        "nombre": usuario.nombre, "enlace": f"{settings.BASE_URL}/verificar-correo?token={token}",
        "horas": settings.VERIFICACION_EMAIL_HORAS,
    })


def _pagina(titulo: str, mensaje: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(titulo)}</title>
<style>body{{font-family:-apple-system,Segoe UI,sans-serif;background:#f3f6f7;margin:0;padding:24px;color:#1D3D47}}
.c{{max-width:420px;margin:40px auto;background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 10px #0002}}</style>
</head><body><div class="c"><h2>{escape(titulo)}</h2><p>{escape(mensaje)}</p></div></body></html>""")


@router.get("/politica-contrasenas")
def politica_contrasenas():
    """Texto de la política vigente (la app lo muestra en el formulario)."""
    return {
        "descripcion": descripcion_politica(),
        "longitud_minima": settings.PASSWORD_MIN_LENGTH,
        "requiere_mayuscula": settings.PASSWORD_REQUIRE_UPPER,
        "requiere_minuscula": settings.PASSWORD_REQUIRE_LOWER,
        "requiere_numero": settings.PASSWORD_REQUIRE_DIGIT,
        "requiere_especial": settings.PASSWORD_REQUIRE_SPECIAL,
    }


@router.post("/registro", response_model=UsuarioRespuesta, status_code=201, dependencies=[Depends(limite("registro"))])
def registrar_usuario(datos: UsuarioRegistro, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    verificar_captcha(datos.captcha_token, ip)

    if db.query(Usuario).filter(Usuario.email == datos.email).first():
        audit.registrar(db, request, None, "auth", "registro", resultado="fallo", email=datos.email, detalle="correo ya registrado")
        raise HTTPException(409, "Ese correo ya está registrado. Iniciá sesión o recuperá tu contraseña.")

    ahora_ = ahora()
    nuevo = Usuario(
        email=datos.email, password_hash=hash_password(datos.password), nombre=datos.nombre, rol=ROL_DERMATOLOGO,
        password_cambiada_en=ahora_, politica_aceptada_version=settings.POLITICA_VERSION, politica_aceptada_en=ahora_,
        email_verificado=not settings.VERIFICAR_EMAIL_REGISTRO,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    asegurar_suscripcion(db, nuevo)
    if not nuevo.email_verificado:
        _enviar_verificacion(db, nuevo)
    audit.registrar(db, request, nuevo, "auth", "registro", entidad="usuario", entidad_id=nuevo.id,
                    despues={"email": nuevo.email, "rol": nuevo.rol, "politica": settings.POLITICA_VERSION})
    return nuevo


@router.post("/login", response_model=Token, dependencies=[Depends(limite("login"))])
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username.strip().lower()
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    ahora_ = ahora()

    if usuario and usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora_:
        minutos = int((usuario.bloqueado_hasta - ahora_).total_seconds() // 60) + 1
        audit.registrar(db, request, usuario, "auth", "login", resultado="fallo", detalle="cuenta bloqueada temporalmente")
        raise HTTPException(429, f"Demasiados intentos fallidos. Por seguridad, esperá {minutos} minuto(s) y volvé a intentar.")

    hash_a_verificar = usuario.password_hash if usuario else hash_password("contraseña-inexistente")
    correcta = verify_password(form_data.password, hash_a_verificar)

    if not usuario or not correcta:
        if usuario:
            usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
            if usuario.intentos_fallidos >= settings.LOGIN_MAX_ATTEMPTS:
                usuario.bloqueado_hasta = ahora_ + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
                usuario.intentos_fallidos = 0
            db.commit()
        audit.registrar(db, request, usuario, "auth", "login", resultado="fallo", email=email, detalle="credenciales incorrectas")
        raise HTTPException(401, MSG_CREDENCIALES)

    if not usuario.activo:
        audit.registrar(db, request, usuario, "auth", "login", resultado="fallo", detalle="usuario inactivo")
        raise HTTPException(403, "Tu cuenta está inactiva. Contactá al administrador para reactivarla.")

    if not usuario.email_verificado:
        audit.registrar(db, request, usuario, "auth", "login", resultado="fallo", detalle="correo sin confirmar")
        raise HTTPException(403, MSG_NO_VERIFICADO)

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    token = crear_sesion(db, usuario, request.client.host if request.client else None)
    vencida = bool(
        settings.PASSWORD_MAX_AGE_DAYS
        and usuario.password_cambiada_en
        and ahora_ - usuario.password_cambiada_en > timedelta(days=settings.PASSWORD_MAX_AGE_DAYS)
    )
    audit.registrar(db, request, usuario, "auth", "login")
    return {"access_token": token, "token_type": "bearer", "password_vencida": vencida}


@router.post("/logout")
def logout(request: Request, sesion: Sesion = Depends(obtener_sesion_actual), db: Session = Depends(get_db)):
    """Invalida el token en el servidor: ya no sirve aunque alguien lo conserve."""
    sesion.revocada = True
    db.commit()
    audit.registrar(db, request, None, "auth", "logout", usuario_id=sesion.usuario_id)
    return {"mensaje": "Sesión cerrada correctamente."}


@router.get("/verificar-correo", response_class=HTMLResponse, include_in_schema=True)
def verificar_correo(request: Request, token: str = Query(..., min_length=20, max_length=200), db: Session = Depends(get_db)):
    """Enlace que llega por correo: confirma que la dirección existe y pertenece a quien se registró."""
    fila = (
        db.query(TokenRestablecimiento)
        .filter(TokenRestablecimiento.token_hash == _hash_token(token), TokenRestablecimiento.tipo == TOKEN_VERIFICAR)
        .first()
    )
    ahora_ = ahora()
    if not fila or fila.usado_en is not None or fila.expira_en <= ahora_:
        audit.registrar(db, request, None, "auth", "verificar_correo", resultado="fallo", detalle="enlace inválido, usado o vencido")
        return _pagina("El enlace no es válido", "Puede que ya lo hayas usado o que haya vencido. Pedí uno nuevo desde la app con "
                       "«Reenviar correo de confirmación».")
    usuario = db.get(Usuario, fila.usuario_id)
    fila.usado_en = ahora_
    usuario.email_verificado = True
    usuario.email_verificado_en = ahora_
    db.commit()
    audit.registrar(db, request, usuario, "auth", "verificar_correo")
    return _pagina("¡Correo confirmado!", "Tu cuenta ya está activa. Volvé a la app e iniciá sesión.")


@router.post("/reenviar-verificacion", dependencies=[Depends(limite("reenviar", 5, 60))])
def reenviar_verificacion(datos: SolicitudReenvio, request: Request, db: Session = Depends(get_db)):
    """Respuesta siempre igual para no revelar qué correos están registrados."""
    usuario = db.query(Usuario).filter(Usuario.email == datos.email.lower()).first()
    if usuario and usuario.activo and not usuario.email_verificado:
        _enviar_verificacion(db, usuario)
        audit.registrar(db, request, usuario, "auth", "reenviar_verificacion")
    return {"mensaje": "Si la cuenta existe y falta confirmarla, te enviamos un nuevo enlace. Revisá tu bandeja de entrada y el correo no deseado."}


@router.get("/perfil", response_model=UsuarioRespuesta)
def obtener_perfil(usuario_actual: Usuario = Depends(obtener_usuario_actual)):
    return usuario_actual


@router.post("/cambiar-contrasena")
def cambiar_contrasena(
    datos: CambiarPassword, request: Request, sesion: Sesion = Depends(obtener_sesion_actual),
    usuario: Usuario = Depends(obtener_usuario_actual), db: Session = Depends(get_db),
):
    if not verify_password(datos.password_actual, usuario.password_hash):
        audit.registrar_fallo(db, request, usuario, "auth", "cambiar_contrasena", "contraseña actual incorrecta")
        raise HTTPException(400, "La contraseña actual no es correcta. Revisala e intentá de nuevo.")
    usuario.password_hash = hash_password(datos.password)
    usuario.password_cambiada_en = ahora()
    usuario.fecha_modificacion = ahora()
    db.query(Sesion).filter(Sesion.usuario_id == usuario.id, Sesion.id != sesion.id).update({"revocada": True})
    db.commit()
    audit.registrar(db, request, usuario, "auth", "cambiar_contrasena")
    return {"mensaje": "Tu contraseña se actualizó. Cerramos tus otras sesiones abiertas."}


@router.post("/recuperar-contrasena", dependencies=[Depends(limite("recuperar", 5, 60))])
def recuperar_contrasena(datos: SolicitudRestablecer, request: Request, db: Session = Depends(get_db)):
    """Paso 1: envía un enlace de un solo uso. La respuesta es siempre la misma para no revelar qué correos existen."""
    respuesta = {"mensaje": "Si el correo está registrado, te enviamos un enlace para restablecer tu contraseña. Revisá tu bandeja de entrada."}
    email = datos.email.lower()
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not usuario.activo:
        audit.registrar(db, request, None, "auth", "recuperar_contrasena", resultado="fallo", email=email, detalle="correo inexistente o inactivo")
        return respuesta

    db.query(TokenRestablecimiento).filter(
        TokenRestablecimiento.usuario_id == usuario.id, TokenRestablecimiento.tipo == TOKEN_RESTABLECER,
        TokenRestablecimiento.usado_en.is_(None),
    ).update({"usado_en": ahora()})
    token = secrets.token_urlsafe(32)  # generador criptográficamente seguro
    db.add(TokenRestablecimiento(
        usuario_id=usuario.id, token_hash=_hash_token(token), tipo=TOKEN_RESTABLECER,
        expira_en=ahora() + timedelta(minutes=settings.RESET_TOKEN_MINUTES),
    ))
    db.commit()
    enlace = f"{settings.FRONTEND_URL}?token={token}"
    email_service.enviar(db, usuario.email, "restablecer_password", {
        "nombre": usuario.nombre, "enlace": enlace, "minutos": settings.RESET_TOKEN_MINUTES,
    })
    audit.registrar(db, request, usuario, "auth", "recuperar_contrasena")
    return respuesta


@router.post("/restablecer-contrasena", dependencies=[Depends(limite("restablecer", 10, 60))])
def restablecer_contrasena(datos: Restablecer, request: Request, db: Session = Depends(get_db)):
    """Paso 2: el usuario define su nueva contraseña con el token recibido por correo."""
    fila = (
        db.query(TokenRestablecimiento)
        .filter(TokenRestablecimiento.token_hash == _hash_token(datos.token), TokenRestablecimiento.tipo == TOKEN_RESTABLECER)
        .first()
    )
    ahora_ = ahora()
    if not fila or fila.usado_en is not None or fila.expira_en <= ahora_:
        audit.registrar(db, request, None, "auth", "restablecer_contrasena", resultado="fallo", detalle="token inválido, usado o vencido")
        raise HTTPException(400, "El enlace no es válido o ya venció. Pedí uno nuevo desde «Olvidé mi contraseña».")
    usuario = db.get(Usuario, fila.usuario_id)
    if not usuario or not usuario.activo:
        raise HTTPException(400, "El enlace no es válido o ya venció. Pedí uno nuevo desde «Olvidé mi contraseña».")

    fila.usado_en = ahora_  # un solo uso
    if not usuario.email_verificado:  # abrir un enlace enviado al correo también prueba que es suyo
        usuario.email_verificado, usuario.email_verificado_en = True, ahora_
    usuario.password_hash = hash_password(datos.password)
    usuario.password_cambiada_en = ahora_
    usuario.fecha_modificacion = ahora_
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    revocar_sesiones_de_usuario(db, usuario.id)
    db.commit()
    audit.registrar(db, request, usuario, "auth", "restablecer_contrasena")
    return {"mensaje": "Tu contraseña se restableció. Ya podés iniciar sesión con la nueva."}
