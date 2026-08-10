from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import obtener_usuario_actual
from models.usuario import Usuario
from models.paciente import Paciente
from schemas.paciente import PacienteRegistro, PacienteRespuesta

router = APIRouter(prefix="/pacientes", tags=["Pacientes"])


@router.get("/buscar/{cedula}")
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


@router.post("", response_model=PacienteRespuesta)
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


@router.get("", response_model=list[PacienteRespuesta])
def listar_pacientes(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Lista los pacientes registrados por el dermatólogo logueado."""
    pacientes = (
        db.query(Paciente).filter(Paciente.dermatologo_id == usuario_actual.id).all()
    )
    return pacientes
