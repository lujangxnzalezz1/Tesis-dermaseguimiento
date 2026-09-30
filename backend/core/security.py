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


def obtener_usuario_actual(
    sesion: Sesion = Depends(obtener_sesion_actual), db: Session = Depends(get_db)
) -> Usuario:
    """Dependencia reutilizable: valida el token y devuelve el usuario logueado.
    Cualquier endpoint que la use queda protegido automáticamente."""
    usuario = db.query(Usuario).filter(Usuario.id == sesion.usuario_id).first()
    if usuario is None or not usuario.activo:
        raise _no_autenticado("Tu cuenta no está activa. Contactá al administrador.")
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


def ip_cliente(request: Request) -> Optional[str]:
    return request.client.host if request.client else None
