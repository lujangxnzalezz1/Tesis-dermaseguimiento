from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import obtener_usuario_actual
from core.tiempo import ahora
from models.paciente import ConsentimientoPaciente, Paciente
from models.usuario import Usuario
from schemas.paciente import (
    PacienteActualizar, PacienteEliminar, PacienteRegistro, PacienteRespuesta,
)
from services import auditoria_service as audit

router = APIRouter(prefix="/pacientes", tags=["Pacientes"])

CAMPOS_AUDITADOS = ["cedula", "nombre", "apellido", "fecha_nacimiento", "sexo", "telefono",
                    "antecedentes_medicos", "observaciones", "activo", "version"]


def obtener_paciente_propio(db: Session, usuario: Usuario, paciente_id: int, *, incluir_inactivos: bool = False) -> Paciente:
    """Devuelve el paciente SOLO si pertenece al dermatólogo logueado. Si no existe o es de otro,
    la respuesta es la misma (404) para no revelar la existencia de pacientes ajenos."""
    q = db.query(Paciente).filter(Paciente.id == paciente_id, Paciente.dermatologo_id == usuario.id)
    if not incluir_inactivos:
        q = q.filter(Paciente.activo.is_(True))
    paciente = q.first()
    if not paciente:
        raise HTTPException(404, "No encontramos a ese paciente en tu lista de pacientes.")
    return paciente


def consentimiento_vigente(db: Session, paciente_id: int) -> Optional[ConsentimientoPaciente]:
    return (
        db.query(ConsentimientoPaciente)
        .filter(ConsentimientoPaciente.paciente_id == paciente_id, ConsentimientoPaciente.revocado_en.is_(None))
        .order_by(ConsentimientoPaciente.id.desc())
        .first()
    )


def _respuesta(db: Session, p: Paciente) -> PacienteRespuesta:
    r = PacienteRespuesta.model_validate(p)
    r.tiene_consentimiento = consentimiento_vigente(db, p.id) is not None
    return r


@router.get("/buscar/{cedula}")
def buscar_paciente_por_cedula(
    cedula: str, db: Session = Depends(get_db), usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Primer paso del flujo RF-04: el dermatólogo ingresa la cédula y el sistema le dice si el
    paciente ya está en SU lista. Nunca se consultan pacientes de otros profesionales."""
    cedula = "".join(c for c in cedula if c.isalnum())
    paciente = (
        db.query(Paciente)
        .filter(Paciente.cedula == cedula, Paciente.dermatologo_id == usuario_actual.id, Paciente.activo.is_(True))
        .first()
    )
    if paciente:
        return {"existe": True, "paciente": _respuesta(db, paciente)}
    return {"existe": False, "paciente": None}


@router.post("", response_model=PacienteRespuesta, status_code=201)
def registrar_paciente(
    datos: PacienteRegistro, request: Request, db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    if not datos.consentimiento.acepta:
        raise HTTPException(
            400,
            "Para registrar al paciente necesitás su consentimiento informado. Explicale para qué se usan sus fotos "
            "y marcá la casilla de consentimiento.",
        )
    existente = (
        db.query(Paciente)
        .filter(Paciente.cedula == datos.cedula, Paciente.dermatologo_id == usuario_actual.id)
        .first()
    )
    if existente:
        detalle = ("Ese paciente estaba dado de baja. Contactá al administrador si necesitás recuperarlo."
                   if not existente.activo else "Ya tenés un paciente registrado con esa cédula. Buscalo por su número.")
        raise HTTPException(409, detalle)

    nuevo = Paciente(
        cedula=datos.cedula, nombre=datos.nombre, apellido=datos.apellido, fecha_nacimiento=datos.fecha_nacimiento,
        sexo=datos.sexo, telefono=datos.telefono, antecedentes_medicos=datos.antecedentes_medicos,
        observaciones=datos.observaciones, dermatologo_id=usuario_actual.id,
    )
    db.add(nuevo)
    db.flush()
    db.add(ConsentimientoPaciente(
        paciente_id=nuevo.id, registrado_por=usuario_actual.id, version_politica=settings.POLITICA_VERSION,
        finalidad=datos.consentimiento.finalidad,
    ))
    db.commit()
    db.refresh(nuevo)
    audit.registrar(db, request, usuario_actual, "pacientes", "crear", entidad="paciente", entidad_id=nuevo.id,
                    despues=audit.instantanea(nuevo, CAMPOS_AUDITADOS))
    audit.registrar(db, request, usuario_actual, "pacientes", "consentimiento_otorgado", entidad="paciente", entidad_id=nuevo.id,
                    despues={"version_politica": settings.POLITICA_VERSION, "finalidad": datos.consentimiento.finalidad})
    return _respuesta(db, nuevo)


@router.get("")
def listar_pacientes(
    q: Optional[str] = Query(None, max_length=80, description="Busca por cédula, nombre o apellido"),
    estado: str = Query("activos", pattern="^(activos|inactivos|todos)$"),
    creado_desde: Optional[date] = None,
    creado_hasta: Optional[date] = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Lista SOLO los pacientes del dermatólogo logueado, con filtros y paginación."""
    consulta = db.query(Paciente).filter(Paciente.dermatologo_id == usuario_actual.id)
    if estado == "activos":
        consulta = consulta.filter(Paciente.activo.is_(True))
    elif estado == "inactivos":
        consulta = consulta.filter(Paciente.activo.is_(False))
    if q:
        patron = f"%{q.strip()}%"
        consulta = consulta.filter(or_(Paciente.cedula.ilike(patron), Paciente.nombre.ilike(patron), Paciente.apellido.ilike(patron)))
    if creado_desde:
        consulta = consulta.filter(Paciente.fecha_creacion >= datetime.combine(creado_desde, datetime.min.time()))
    if creado_hasta:
        consulta = consulta.filter(Paciente.fecha_creacion < datetime.combine(creado_hasta, datetime.min.time()) + timedelta(days=1))
    total = consulta.count()
    filas = consulta.order_by(Paciente.apellido, Paciente.nombre).offset((pagina - 1) * tamano).limit(tamano).all()
    return {"items": [_respuesta(db, p) for p in filas], "total": total, "pagina": pagina, "tamano": tamano}


@router.get("/{paciente_id}", response_model=PacienteRespuesta)
def obtener_paciente(paciente_id: int, db: Session = Depends(get_db), usuario_actual: Usuario = Depends(obtener_usuario_actual)):
    return _respuesta(db, obtener_paciente_propio(db, usuario_actual, paciente_id))


@router.patch("/{paciente_id}", response_model=PacienteRespuesta)
def actualizar_paciente(
    paciente_id: int, datos: PacienteActualizar, request: Request, db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Edición con bloqueo optimista (punto 30): si alguien modificó la ficha mientras la editabas, se rechaza
    en lugar de sobrescribir en silencio."""
    paciente = obtener_paciente_propio(db, usuario_actual, paciente_id)
    if paciente.version != datos.version:
        raise HTTPException(
            409,
            "Esta ficha fue modificada por otra persona o desde otro dispositivo mientras la editabas. "
            "Volvé a abrirla para ver los cambios y repetí tu edición.",
        )
    antes = audit.instantanea(paciente, CAMPOS_AUDITADOS)
    cambios = datos.model_dump(exclude_unset=True, exclude={"version"})
    # UPDATE atómico condicionado a la versión: si dos personas guardan a la vez, solo una gana.
    filas = (
        db.query(Paciente)
        .filter(Paciente.id == paciente.id, Paciente.version == datos.version)
        .update({**cambios, "version": datos.version + 1, "fecha_modificacion": ahora()}, synchronize_session=False)
    )
    if filas == 0:
        db.rollback()
        raise HTTPException(
            409,
            "Esta ficha fue modificada por otra persona o desde otro dispositivo mientras la editabas. "
            "Volvé a abrirla para ver los cambios y repetí tu edición.",
        )
    db.commit()
    db.refresh(paciente)
    audit.registrar(db, request, usuario_actual, "pacientes", "modificar", entidad="paciente", entidad_id=paciente.id,
                    antes=antes, despues=audit.instantanea(paciente, CAMPOS_AUDITADOS))
    return _respuesta(db, paciente)


@router.delete("/{paciente_id}")
def dar_de_baja_paciente(
    paciente_id: int, datos: PacienteEliminar, request: Request, db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Borrado LÓGICO: la ficha y sus seguimientos se conservan por su valor histórico (punto 20)."""
    if not datos.confirmar:
        raise HTTPException(400, "Confirmá la baja del paciente para continuar. Esta acción lo oculta de tus listas.")
    paciente = obtener_paciente_propio(db, usuario_actual, paciente_id)
    antes = audit.instantanea(paciente, CAMPOS_AUDITADOS)
    paciente.activo = False
    paciente.eliminado_en = ahora()
    paciente.eliminado_por = usuario_actual.id
    paciente.motivo_eliminacion = datos.motivo
    paciente.version += 1
    db.commit()
    audit.registrar(db, request, usuario_actual, "pacientes", "baja_logica", entidad="paciente", entidad_id=paciente.id,
                    antes=antes, despues=audit.instantanea(paciente, CAMPOS_AUDITADOS), detalle=datos.motivo)
    return {"mensaje": "El paciente se dio de baja. Su historial se conserva y puede recuperarlo el administrador."}


@router.post("/{paciente_id}/consentimiento/revocar")
def revocar_consentimiento(
    paciente_id: int, request: Request, db: Session = Depends(get_db), usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    paciente = obtener_paciente_propio(db, usuario_actual, paciente_id)
    vigente = consentimiento_vigente(db, paciente.id)
    if not vigente:
        raise HTTPException(409, "Este paciente no tiene un consentimiento vigente.")
    vigente.revocado_en = ahora()
    db.commit()
    audit.registrar(db, request, usuario_actual, "pacientes", "consentimiento_revocado", entidad="paciente", entidad_id=paciente.id)
    return {"mensaje": "Se registró la revocación. No se podrán procesar nuevas fotos hasta obtener un nuevo consentimiento."}


@router.post("/{paciente_id}/consentimiento")
def renovar_consentimiento(
    paciente_id: int, request: Request, db: Session = Depends(get_db), usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    paciente = obtener_paciente_propio(db, usuario_actual, paciente_id)
    if consentimiento_vigente(db, paciente.id):
        raise HTTPException(409, "Este paciente ya tiene un consentimiento vigente.")
    db.add(ConsentimientoPaciente(
        paciente_id=paciente.id, registrado_por=usuario_actual.id, version_politica=settings.POLITICA_VERSION,
        finalidad="Registro de fotografías clínicas y análisis de la evolución de la piel con fines de seguimiento médico.",
    ))
    db.commit()
    audit.registrar(db, request, usuario_actual, "pacientes", "consentimiento_otorgado", entidad="paciente", entidad_id=paciente.id)
    return {"mensaje": "Consentimiento registrado."}
