import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
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
from models.usuario import ROL_DERMATOLOGO, Sesion, TokenRestablecimiento, Usuario
from schemas.usuario import (
    CambiarPassword, Restablecer, SolicitudRestablecer, Token, UsuarioRegistro, UsuarioRespuesta,
)
from services import auditoria_service as audit
from services import email_service
from services.suscripcion_service import asegurar_suscripcion

router = APIRouter(tags=["Autenticación"])

MSG_CREDENCIALES = "Correo o contraseña incorrectos. Revisá los datos e intentá de nuevo."


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


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
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    asegurar_suscripcion(db, nuevo)
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
        TokenRestablecimiento.usuario_id == usuario.id, TokenRestablecimiento.usado_en.is_(None)
    ).update({"usado_en": ahora()})
    token = secrets.token_urlsafe(32)  # generador criptográficamente seguro
    db.add(TokenRestablecimiento(
        usuario_id=usuario.id, token_hash=_hash_token(token),
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
    fila = db.query(TokenRestablecimiento).filter(TokenRestablecimiento.token_hash == _hash_token(datos.token)).first()
    ahora_ = ahora()
    if not fila or fila.usado_en is not None or fila.expira_en <= ahora_:
        audit.registrar(db, request, None, "auth", "restablecer_contrasena", resultado="fallo", detalle="token inválido, usado o vencido")
        raise HTTPException(400, "El enlace no es válido o ya venció. Pedí uno nuevo desde «Olvidé mi contraseña».")
    usuario = db.get(Usuario, fila.usuario_id)
    if not usuario or not usuario.activo:
        raise HTTPException(400, "El enlace no es válido o ya venció. Pedí uno nuevo desde «Olvidé mi contraseña».")

    fila.usado_en = ahora_  # un solo uso
    usuario.password_hash = hash_password(datos.password)
    usuario.password_cambiada_en = ahora_
    usuario.fecha_modificacion = ahora_
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    revocar_sesiones_de_usuario(db, usuario.id)
    db.commit()
    audit.registrar(db, request, usuario, "auth", "restablecer_contrasena")
    return {"mensaje": "Tu contraseña se restableció. Ya podés iniciar sesión con la nueva."}
