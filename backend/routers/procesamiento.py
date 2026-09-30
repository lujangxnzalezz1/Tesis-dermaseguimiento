import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Optional

import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import obtener_usuario_actual
from core.tiempo import ahora
from models.paciente import Paciente
from models.seguimiento import Seguimiento
from models.usuario import Usuario
from routers.pacientes import consentimiento_vigente, obtener_paciente_propio
from schemas.seguimiento import SeguimientoRespuesta
from services import almacenamiento as alm
from services import auditoria_service as audit
from services.analisis_colorimetrico import analizar_color
from services.calidad_captura import evaluar_captura
from services.procesamiento_imagenes import procesar_par_de_imagenes
from services.suscripcion_service import exigir_acceso_avanzado

router = APIRouter(tags=["Procesamiento de imágenes"])
log = logging.getLogger("procesamiento")


def _linea_base(db: Session, paciente_id: int) -> Optional[Seguimiento]:
    return db.query(Seguimiento).filter(Seguimiento.paciente_id == paciente_id).order_by(Seguimiento.fecha.asc(), Seguimiento.id.asc()).first()


def _imagen_linea_base(db: Session, paciente_id: int):
    base = _linea_base(db, paciente_id)
    if base is None:
        return None
    ruta = alm.ruta_absoluta(base.ruta_imagen_referencia)
    return cv2.imread(ruta) if os.path.exists(ruta) else None


def _a_respuesta(s: Seguimiento) -> SeguimientoRespuesta:
    return SeguimientoRespuesta(
        id=s.id, paciente_id=s.paciente_id, fecha=s.fecha,
        landmarks_referencia=s.landmarks_referencia, landmarks_nueva=s.landmarks_nueva,
        url_imagen_referencia=f"/archivos/{s.ruta_imagen_referencia}",
        url_imagen_nueva=f"/archivos/{s.ruta_imagen_nueva}",
        url_imagen_alineada=f"/archivos/{s.ruta_imagen_alineada}",
        delta_e_promedio=s.delta_e_promedio,
        l_referencia=s.l_referencia, a_referencia=s.a_referencia, b_referencia=s.b_referencia,
        l_nueva=s.l_nueva, a_nueva=s.a_nueva, b_nueva=s.b_nueva,
        url_mapa_calor=f"/archivos/{s.ruta_mapa_calor}",
        tiempo_procesamiento_ms=s.tiempo_procesamiento_ms,
    )


@router.post("/procesar-seguimiento", response_model=SeguimientoRespuesta, status_code=201)
def procesar_seguimiento(
    request: Request,
    paciente_id: int = Form(...),
    imagen_referencia: Optional[UploadFile] = File(None),
    imagen_nueva: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """RF-09, RF-10, RF-11, RF-12: alinea la nueva captura con la de referencia y analiza el cambio de
    color de piel en CIE L*a*b*. Requiere suscripción con procesamiento, paciente propio y consentimiento."""
    exigir_acceso_avanzado(db, usuario_actual)
    paciente = obtener_paciente_propio(db, usuario_actual, paciente_id)
    if not consentimiento_vigente(db, paciente.id):
        raise HTTPException(
            409,
            "Este paciente no tiene un consentimiento informado vigente. Registralo desde su ficha antes de procesar nuevas fotos.",
        )

    if imagen_referencia is not None:
        ref_bgr, hash_ref = alm.leer_imagen_validada(imagen_referencia, "imagen de referencia")
    else:
        # Sin foto de referencia: se usa la de la primera consulta del paciente (línea de base)
        ref_bgr = _imagen_linea_base(db, paciente.id)
        if ref_bgr is None:
            raise HTTPException(400, "Es la primera consulta de este paciente: elegí también una foto de referencia.")
        hash_ref = None
    nueva_bgr, hash_nueva = alm.leer_imagen_validada(imagen_nueva, "nueva captura")
    if hash_ref == hash_nueva:
        raise HTTPException(400, "Elegiste la misma foto como referencia y como nueva captura. Seleccioná dos fotos distintas.")

    inicio = time.perf_counter()
    try:
        resultado = procesar_par_de_imagenes(ref_bgr, nueva_bgr)
        if not resultado["exito"]:
            audit.registrar_fallo(db, request, usuario_actual, "seguimientos", "procesar", resultado["error"],
                                  entidad="paciente", entidad_id=paciente.id)
            raise HTTPException(422, resultado["error"])
        analisis = analizar_color(ref_bgr, resultado["imagen_alineada"], resultado["puntos_referencia"])
        if not analisis["exito"]:
            audit.registrar_fallo(db, request, usuario_actual, "seguimientos", "procesar", analisis["error"],
                                  entidad="paciente", entidad_id=paciente.id)
            raise HTTPException(422, analisis["error"])
    except HTTPException:
        raise
    except Exception:
        log.exception("Falló el procesamiento de imágenes")
        raise HTTPException(500, "No pudimos procesar las fotos. Probá con otras imágenes; si sigue fallando, avisá al soporte.")
    tiempo_ms = int((time.perf_counter() - inicio) * 1000)

    claves = {k: alm.nueva_clave() for k in ("ref", "nueva", "alineada", "mapa")}
    try:
        alm.guardar_imagen(ref_bgr, claves["ref"])
        alm.guardar_imagen(nueva_bgr, claves["nueva"])
        alm.guardar_imagen(resultado["imagen_alineada"], claves["alineada"])
        alm.guardar_imagen(analisis["mapa_calor"], claves["mapa"])
        seg = Seguimiento(
            paciente_id=paciente.id, usuario_id=usuario_actual.id, fecha=ahora(),
            ruta_imagen_referencia=claves["ref"], ruta_imagen_nueva=claves["nueva"],
            ruta_imagen_alineada=claves["alineada"], ruta_mapa_calor=claves["mapa"],
            landmarks_referencia=resultado["cantidad_landmarks_referencia"], landmarks_nueva=resultado["cantidad_landmarks_nueva"],
            delta_e_promedio=analisis["delta_e_promedio"],
            l_referencia=analisis["l_referencia"], a_referencia=analisis["a_referencia"], b_referencia=analisis["b_referencia"],
            l_nueva=analisis["l_nueva"], a_nueva=analisis["a_nueva"], b_nueva=analisis["b_nueva"],
            tiempo_procesamiento_ms=tiempo_ms,
        )
        db.add(seg)
        db.commit()
        db.refresh(seg)
    except Exception:
        # Nada queda a medias: se deshace la base y se borran las imágenes ya escritas (RNF-16)
        db.rollback()
        alm.borrar_silencioso(list(claves.values()))
        log.exception("No se pudo guardar el seguimiento")
        raise HTTPException(500, "No pudimos guardar el seguimiento y no se realizó ningún cambio. Intentá de nuevo.")

    excedido = tiempo_ms > settings.TIEMPO_MAXIMO_PROCESAMIENTO_SEGUNDOS * 1000
    audit.registrar(db, request, usuario_actual, "seguimientos", "procesar", entidad="seguimiento", entidad_id=seg.id,
                    despues={"paciente_id": paciente.id, "delta_e": round(seg.delta_e_promedio, 3), "tiempo_ms": tiempo_ms},
                    detalle=f"Superó el máximo de {settings.TIEMPO_MAXIMO_PROCESAMIENTO_SEGUNDOS}s (RNF-06)" if excedido else None)
    return _a_respuesta(seg)


@router.get("/pacientes/{paciente_id}/seguimientos", response_model=list[SeguimientoRespuesta])
def listar_seguimientos(
    paciente_id: int,
    response: Response,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """Historial de un paciente PROPIO, del más reciente al más antiguo, con filtro por fechas y paginación."""
    paciente = obtener_paciente_propio(db, usuario_actual, paciente_id, incluir_inactivos=True)
    q = db.query(Seguimiento).filter(Seguimiento.paciente_id == paciente.id)
    if desde:
        q = q.filter(Seguimiento.fecha >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        q = q.filter(Seguimiento.fecha < datetime.combine(hasta, datetime.min.time()) + timedelta(days=1))
    response.headers["X-Total-Count"] = str(q.count())
    filas = q.order_by(Seguimiento.fecha.desc()).offset((pagina - 1) * tamano).limit(tamano).all()
    return [_a_respuesta(s) for s in filas]


@router.get("/archivos/{clave:path}")
def descargar_archivo(clave: str, db: Session = Depends(get_db), usuario_actual: Usuario = Depends(obtener_usuario_actual)):
    """Las imágenes clínicas ya no son públicas: solo las ve el dermatólogo dueño del paciente."""
    seg = (
        db.query(Seguimiento)
        .join(Paciente, Paciente.id == Seguimiento.paciente_id)
        .filter(
            Paciente.dermatologo_id == usuario_actual.id,
            or_(
                Seguimiento.ruta_imagen_referencia == clave, Seguimiento.ruta_imagen_nueva == clave,
                Seguimiento.ruta_imagen_alineada == clave, Seguimiento.ruta_mapa_calor == clave,
            ),
        )
        .first()
    )
    if not seg:
        raise HTTPException(404, "No encontramos esa imagen o no tenés permiso para verla.")
    destino = alm.ruta_absoluta(clave)
    return FileResponse(destino, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.get("/pacientes/{paciente_id}/referencia")
def referencia_del_paciente(paciente_id: int, db: Session = Depends(get_db), usuario_actual: Usuario = Depends(obtener_usuario_actual)):
    """Foto de la primera consulta: la app la muestra semitransparente sobre la cámara (guía de captura, RF-03)."""
    paciente = obtener_paciente_propio(db, usuario_actual, paciente_id, incluir_inactivos=True)
    base = _linea_base(db, paciente.id)
    if base is None:
        return {"existe": False, "url": None, "fecha": None}
    return {"existe": True, "url": f"/archivos/{base.ruta_imagen_referencia}", "fecha": base.fecha}


@router.post("/verificar-captura")
def verificar_captura(
    imagen: UploadFile = File(...),
    paciente_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
):
    """RF-03: revisa la foto recién tomada (rostro, distancia, centrado, inclinación, giro, luz, nitidez) y,
    si el paciente ya tiene consultas, la compara con su foto de referencia. No guarda nada."""
    img, _ = alm.leer_imagen_validada(imagen, "foto")
    referencia = None
    if paciente_id is not None:
        paciente = obtener_paciente_propio(db, usuario_actual, paciente_id)
        referencia = _imagen_linea_base(db, paciente.id)
    return evaluar_captura(img, referencia)
