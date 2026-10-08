from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from core.database import Base
from core.tiempo import ahora


class Seguimiento(Base):
    __tablename__ = "seguimientos"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha = Column(DateTime, default=ahora, index=True)

    # Las rutas son claves opacas (UUID): no contienen datos de identificación (RNF-02).
    ruta_imagen_referencia = Column(String, nullable=False)
    ruta_imagen_nueva = Column(String, nullable=False)
    ruta_imagen_alineada = Column(String, nullable=False)

    landmarks_referencia = Column(Integer, nullable=False)
    landmarks_nueva = Column(Integer, nullable=False)

    ruta_mapa_calor = Column(String, nullable=False)
    delta_e_promedio = Column(Float, nullable=False)
    l_referencia = Column(Float, nullable=False)
    a_referencia = Column(Float, nullable=False)
    b_referencia = Column(Float, nullable=False)
    l_nueva = Column(Float, nullable=False)
    a_nueva = Column(Float, nullable=False)
    b_nueva = Column(Float, nullable=False)

    # RNF-06: tiempo de procesamiento medido en el servidor
    tiempo_procesamiento_ms = Column(Integer, nullable=True)

    # RF-13: similitud estructural antes y después de alinear (sobre la región del rostro)
    ssim_antes = Column(Float, nullable=True)
    ssim_despues = Column(Float, nullable=True)

    # RF-14 / RF-15: lesiones detectadas con YOLOv8 y comparación con la referencia
    lesiones_referencia = Column(Integer, nullable=True)
    lesiones_nueva = Column(Integer, nullable=True)
    lesiones_nuevas = Column(Integer, nullable=True)
    lesiones_persistentes = Column(Integer, nullable=True)
    lesiones_resueltas = Column(Integer, nullable=True)
    lesiones_detalle = Column(Text, nullable=True)  # JSON con los recuadros
    ruta_imagen_lesiones = Column(String, nullable=True)

    # RF-16: región periorbital (ojeras). Contraste = L*(mejilla) - L*(ojera); mayor = ojera más marcada
    ojeras_contraste_referencia = Column(Float, nullable=True)
    ojeras_contraste_nueva = Column(Float, nullable=True)
    ojeras_detalle = Column(Text, nullable=True)  # JSON con L*a*b* por ojo, de ambas consultas
    ruta_imagen_periorbital = Column(String, nullable=True)

    # Manchas: % de la piel analizada que es claramente más oscura que su entorno (misma superficie en ambas fotos)
    manchas_pct_referencia = Column(Float, nullable=True)
    manchas_pct_nueva = Column(Float, nullable=True)
    manchas_detalle = Column(Text, nullable=True)  # JSON con cantidad y contraste de ambas consultas
    ruta_imagen_manchas = Column(String, nullable=True)

    # Textura (líneas/arrugas, poros, brillo de la zona T): JSON con los índices de cada foto
    textura_referencia = Column(Text, nullable=True)
    textura_nueva = Column(Text, nullable=True)
    ruta_imagen_textura = Column(String, nullable=True)

    # Indicaciones que escribe el profesional para el paciente (salen en el informe PDF)
    recomendaciones = Column(Text, nullable=True)

    # Valoración clínica cargada por la profesional (IGA, mMASI, humedad, pH, firmeza): JSON
    valoracion_clinica = Column(Text, nullable=True)

    # Foto con luz UV (opcional) y conteo de porfirinas fluorescentes: JSON
    porfirinas = Column(Text, nullable=True)
    ruta_imagen_uv = Column(String, nullable=True)
    ruta_imagen_uv_analisis = Column(String, nullable=True)

    paciente = relationship("Paciente")
    usuario = relationship("Usuario")
