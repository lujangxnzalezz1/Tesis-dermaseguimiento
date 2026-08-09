from datetime import datetime, date, timedelta
from typing import Optional

import cv2
import numpy as np
import base64
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Date, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

from procesamiento_imagenes import procesar_par_de_imagenes

# ---------- Configuración de la base de datos ----------
DATABASE_URL = "postgresql://lujan.gonzalez@localhost:5432/dermaseguimiento"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------- Modelo de Usuario ----------
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    rol = Column(String, default="dermatologo")
    fecha_creacion = Column(DateTime, default=datetime.utcnow)


# ---------- Modelo de Paciente (RF-04) ----------
class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, index=True)
    cedula = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    fecha_nacimiento = Column(Date, nullable=True)
    sexo = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    antecedentes_medicos = Column(String, nullable=True)
    observaciones = Column(String, nullable=True)
    dermatologo_id = Column(Integer, nullable=False)  # quién lo registró
    fecha_creacion = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# ---------- Seguridad ----------
SECRET_KEY = "cambiar-esto-por-una-clave-secreta-real-antes-de-produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def obtener_usuario_actual(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Usuario:
    """Dependencia reutilizable: valida el token y devuelve el usuario logueado.
    Cualquier endpoint que la use queda protegido automáticamente."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


# ---------- Esquemas: Usuario ----------
class UsuarioRegistro(BaseModel):
    email: str
    password: str
    nombre: str


class UsuarioRespuesta(BaseModel):
    id: int
    email: str
    nombre: str
    rol: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


# ---------- Esquemas: Paciente ----------
class PacienteRegistro(BaseModel):
    cedula: str
    nombre: str
    apellido: str
    fecha_nacimiento: Optional[date] = None
    sexo: Optional[str] = None
    telefono: Optional[str] = None
    antecedentes_medicos: Optional[str] = None
    observaciones: Optional[str] = None


class PacienteRespuesta(BaseModel):
    id: int
    cedula: str
    nombre: str
    apellido: str
    fecha_nacimiento: Optional[date]
    sexo: Optional[str]
    telefono: Optional[str]
    antecedentes_medicos: Optional[str]
    observaciones: Optional[str]

    class Config:
        from_attributes = True


# ---------- App ----------
app = FastAPI(title="DermaSeguimiento API")


@app.get("/")
def read_root():
    return {"mensaje": "API de DermaSeguimiento funcionando correctamente"}


@app.get("/test-db")
def test_db_connection():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version();"))
        version = result.fetchone()[0]
    return {"conexion": "exitosa", "version_postgresql": version}


@app.post("/registro", response_model=UsuarioRespuesta)
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


@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == form_data.username).first()

    if not usuario or not verify_password(form_data.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )

    access_token = create_access_token(data={"sub": usuario.email, "rol": usuario.rol})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/perfil", response_model=UsuarioRespuesta)
def obtener_perfil(usuario_actual: Usuario = Depends(obtener_usuario_actual)):
    return usuario_actual


# ---------- Endpoints de Pacientes (RF-04) ----------
@app.get("/pacientes/buscar/{cedula}")
def buscar_paciente_por_cedula(
    cedula: str,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Primer paso del flujo RF-04: el dermatólogo ingresa la cédula
    y el sistema le dice si el paciente ya existe o no."""
    paciente = db.query(Paciente).filter(Paciente.cedula == cedula).first()
    if paciente:
        return {"existe": True, "paciente": PacienteRespuesta.model_validate(paciente)}
    return {"existe": False, "paciente": None}


@app.post("/pacientes", response_model=PacienteRespuesta)
def registrar_paciente(
    datos: PacienteRegistro,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    existente = db.query(Paciente).filter(Paciente.cedula == datos.cedula).first()
    if existente:
        raise HTTPException(
            status_code=400, detail="Ya existe un paciente registrado con esa cédula"
        )

    nuevo_paciente = Paciente(
        cedula=datos.cedula,
        nombre=datos.nombre,
        apellido=datos.apellido,
        fecha_nacimiento=datos.fecha_nacimiento,
        sexo=datos.sexo,
        telefono=datos.telefono,
        antecedentes_medicos=datos.antecedentes_medicos,
        observaciones=datos.observaciones,
        dermatologo_id=usuario_actual.id,
    )
    db.add(nuevo_paciente)
    db.commit()
    db.refresh(nuevo_paciente)
    return nuevo_paciente


@app.get("/pacientes", response_model=list[PacienteRespuesta])
def listar_pacientes(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Lista los pacientes registrados por el dermatólogo logueado."""
    pacientes = (
        db.query(Paciente).filter(Paciente.dermatologo_id == usuario_actual.id).all()
    )
    return pacientes


def _leer_imagen_desde_upload(archivo: UploadFile) -> np.ndarray:
    """Convierte un archivo subido (UploadFile) en una imagen que OpenCV
    pueda procesar (formato BGR, el que usa OpenCV internamente)."""
    contenido = archivo.file.read()
    arreglo_bytes = np.frombuffer(contenido, np.uint8)
    imagen = cv2.imdecode(arreglo_bytes, cv2.IMREAD_COLOR)
    return imagen


def _imagen_a_base64(imagen: np.ndarray) -> str:
    """Convierte una imagen de OpenCV a texto base64, para poder
    devolverla dentro de una respuesta JSON."""
    _, buffer = cv2.imencode(".jpg", imagen)
    return base64.b64encode(buffer).decode("utf-8")


@app.post("/procesar-seguimiento")
def procesar_seguimiento(
    imagen_referencia: UploadFile = File(...),
    imagen_nueva: UploadFile = File(...),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """RF-09, RF-10, RF-11: recibe dos fotografías (la de referencia y la
    nueva captura de seguimiento), detecta los puntos anatómicos faciales
    y alinea geométricamente la nueva imagen con la de referencia."""

    ref_bgr = _leer_imagen_desde_upload(imagen_referencia)
    nueva_bgr = _leer_imagen_desde_upload(imagen_nueva)

    if ref_bgr is None or nueva_bgr is None:
        raise HTTPException(status_code=400, detail="No se pudo leer una de las imágenes enviadas.")

    resultado = procesar_par_de_imagenes(ref_bgr, nueva_bgr)

    if not resultado["exito"]:
        raise HTTPException(status_code=422, detail=resultado["error"])

    imagen_base64 = _imagen_a_base64(resultado["imagen_alineada"])

    return {
        "mensaje": "Imagen alineada correctamente",
        "landmarks_detectados_referencia": resultado["cantidad_landmarks_referencia"],
        "landmarks_detectados_nueva": resultado["cantidad_landmarks_nueva"],
        "imagen_alineada_base64": imagen_base64,
    }