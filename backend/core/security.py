import ipaddress
import uuid
from datetime import timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.tiempo import ahora
from models.usuario import Sesion, Usuario

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


def crear_sesion(db: Session, usuario: Usuario, ip: Optional[str]) -> str:
    """Registra una sesión en la base y devuelve el JWT que la representa."""
    ahora_ = ahora()
    expira = ahora_ + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = uuid.uuid4().hex
    db.add(Sesion(id=jti, usuario_id=usuario.id, creada_en=ahora_, ultimo_uso=ahora_, expira_en=expira, ip=ip))
    usuario.ultimo_acceso = ahora_
    db.commit()
    payload = {"sub": str(usuario.id), "jti": jti, "rol": usuario.rol, "exp": expira}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def revocar_sesiones_de_usuario(db: Session, usuario_id: int) -> None:
    db.query(Sesion).filter(Sesion.usuario_id == usuario_id, Sesion.revocada.is_(False)).update(
        {"revocada": True}, synchronize_session=False
    )


def _no_autenticado(mensaje: str) -> HTTPException:
    return HTTPException(status_code=401, detail=mensaje, headers={"WWW-Authenticate": "Bearer"})


def _decodificar(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise _no_autenticado("Tu sesión no es válida o expiró. Iniciá sesión de nuevo.")


def obtener_sesion_actual(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Sesion:
    payload = _decodificar(token)
    jti = payload.get("jti")
    sesion = db.query(Sesion).filter(Sesion.id == jti).first() if jti else None
    if sesion is None or sesion.revocada:
        raise _no_autenticado("Tu sesión fue cerrada. Iniciá sesión de nuevo.")
    ahora_ = ahora()
    if sesion.expira_en <= ahora_:
        raise _no_autenticado("Tu sesión expiró. Iniciá sesión de nuevo.")
    if ahora_ - sesion.ultimo_uso > timedelta(minutes=settings.INACTIVITY_TIMEOUT_MINUTES):
        sesion.revocada = True
        db.commit()
        raise _no_autenticado("Tu sesión se cerró por inactividad. Iniciá sesión de nuevo.")
    if ahora_ - sesion.ultimo_uso > timedelta(seconds=30):
        sesion.ultimo_uso = ahora_
        db.commit()
    return sesion


# Rutas que siguen disponibles con la contraseña vencida o la política pendiente de aceptar:
# justamente las que permiten resolverlo (además de /logout, que no pide el usuario).
RUTAS_SIN_BLOQUEO = {"/perfil", "/cambiar-contrasena", "/aceptar-politica", "/cuenta/eliminar"}

MSG_PASSWORD_VENCIDA = ("Tu contraseña venció. Por seguridad, cambiala desde «Mi cuenta» para seguir usando el sistema.")
MSG_POLITICA_PENDIENTE = ("Actualizamos la Política de Privacidad. Leela y aceptala para seguir usando el sistema.")


def password_vencida(usuario: Usuario) -> bool:
    from core.politica_password import politica_vigente  # importación diferida: evita un ciclo

    dias = politica_vigente()["max_dias_vigencia"]
    return bool(dias and usuario.password_cambiada_en and ahora() - usuario.password_cambiada_en > timedelta(days=dias))


def politica_pendiente(usuario: Usuario) -> bool:
    return usuario.politica_aceptada_version != settings.POLITICA_VERSION


def obtener_usuario_actual(
    request: Request, sesion: Sesion = Depends(obtener_sesion_actual), db: Session = Depends(get_db)
) -> Usuario:
    """Dependencia reutilizable: valida el token y devuelve el usuario logueado.
    Cualquier endpoint que la use queda protegido automáticamente. Si la contraseña venció o hay
    una versión nueva de la política sin aceptar, se bloquea todo salvo lo necesario para resolverlo."""
    usuario = db.query(Usuario).filter(Usuario.id == sesion.usuario_id).first()
    if usuario is None or not usuario.activo:
        raise _no_autenticado("Tu cuenta no está activa. Contactá al administrador.")
    if request.url.path not in RUTAS_SIN_BLOQUEO:
        if password_vencida(usuario):
            raise HTTPException(status_code=403, detail=MSG_PASSWORD_VENCIDA, headers={"X-Motivo": "password_vencida"})
        # Las cuentas sin ninguna versión registrada (anteriores al registro del consentimiento o creadas
        # por script) reciben el aviso al ingresar, pero el bloqueo aplica a quien aceptó una versión anterior.
        if usuario.politica_aceptada_version is not None and politica_pendiente(usuario):
            raise HTTPException(status_code=403, detail=MSG_POLITICA_PENDIENTE, headers={"X-Motivo": "politica_pendiente"})
    return usuario


def requiere_rol(*roles: str):
    """Autorización por rol validada SIEMPRE en el backend (punto 8)."""

    def _dep(usuario: Usuario = Depends(obtener_usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(
                status_code=403,
                detail="No tenés permiso para realizar esta acción con tu perfil de usuario.",
            )
        return usuario

    return _dep


def _redes_de_confianza() -> list:
    redes = []
    for parte in settings.TRUSTED_PROXIES.split(","):
        parte = parte.strip()
        if parte:
            try:
                redes.append(ipaddress.ip_network(parte, strict=False))
            except ValueError:
                pass  # una entrada mal escrita no debe tumbar el servidor; simplemente no se confía en ella
    return redes


def _es_de_confianza(ip: Optional[str], redes: list) -> bool:
    try:
        direccion = ipaddress.ip_address(ip)
    except (TypeError, ValueError):
        return False
    return any(direccion in red for red in redes)


def ip_cliente(request: Request) -> Optional[str]:
    """IP real del cliente. Las cabeceras X-Forwarded-For / X-Real-IP las puede escribir cualquiera,
    así que solo se leen cuando la conexión llega desde un proxy listado en TRUSTED_PROXIES."""
    directa = request.client.host if request.client else None
    redes = _redes_de_confianza()
    if not redes or not _es_de_confianza(directa, redes):
        return directa
    reenviadas = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    # Se recorre de derecha a izquierda: la primera IP que no es un proxy propio es la del cliente
    for ip in reversed(reenviadas):
        if not _es_de_confianza(ip, redes):
            return ip
    real = request.headers.get("x-real-ip", "").strip()
    return real or (reenviadas[0] if reenviadas else directa)
