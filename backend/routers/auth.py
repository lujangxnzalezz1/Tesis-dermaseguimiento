from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    obtener_usuario_actual,
)
from models.usuario import Usuario
from schemas.usuario import UsuarioRegistro, UsuarioRespuesta, Token

router = APIRouter(tags=["Autenticación"])


@router.post("/registro", response_model=UsuarioRespuesta)
def registrar_usuario(datos: UsuarioRegistro, db: Session = Depends(get_db)):
    existente = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ese correo ya está registrado")

    nuevo_usuario = Usuario(
        email=datos.email,
        password_hash=hash_password(datos.password),
        nombre=datos.nombre,
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == form_data.username).first()

    if not usuario or not verify_password(form_data.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )

    access_token = create_access_token(data={"sub": usuario.email, "rol": usuario.rol})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/perfil", response_model=UsuarioRespuesta)
def obtener_perfil(usuario_actual: Usuario = Depends(obtener_usuario_actual)):
    return usuario_actual
