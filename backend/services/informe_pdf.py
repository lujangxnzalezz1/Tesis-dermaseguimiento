"""Informe de evolución en PDF para entregar al paciente (una consulta comparada con su referencia).

Usa lenguaje simple: primero las fotos y el resumen en palabras, después los índices. Repite la
aclaración de que no es un diagnóstico.
"""
import io
import json
import os
from typing import Optional
from xml.sax.saxutils import escape

import cv2
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.tiempo import ahora
from services import almacenamiento as alm
from services.interpretacion import interpretar

VERDE = colors.HexColor("#2E6B4F")
ANCHO_UTIL = A4[0] - 36 * mm


def _num(x: float, dec: int = 2) -> str:
    return f"{x:.{dec}f}".replace(".", ",")


def _imagen(clave: Optional[str], ancho: float) -> Optional[Image]:
    """Lee la imagen guardada y la achica para que el PDF no pese demasiado."""
    if not clave:
        return None
    ruta = alm.ruta_absoluta(clave)
    img = cv2.imread(ruta) if os.path.exists(ruta) else None
    if img is None:
        return None
    escala = min(1.0, 900 / img.shape[1])
    img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        return None
    alto = ancho * img.shape[0] / img.shape[1]
    return Image(io.BytesIO(jpg.tobytes()), width=ancho, height=alto)


def _indices(s) -> list[list[str]]:
    filas = [["Indicador", "Referencia", "Esta consulta", "Qué mide"]]
    i = interpretar(s)
    filas.append(["Cambio de color", "—", f"Delta E {_num(s.delta_e_promedio)} ({i['magnitud_color']})",
                  "Diferencia de color de la piel entre las dos fotos"])
    if s.manchas_pct_nueva is not None:
        filas.append(["Superficie con manchas", f"{_num(s.manchas_pct_referencia)} %", f"{_num(s.manchas_pct_nueva)} %",
                      "Parte de la piel más oscura que la de alrededor"])
    if s.ojeras_contraste_nueva is not None:
        filas.append(["Ojeras (contraste)", _num(s.ojeras_contraste_referencia, 1), _num(s.ojeras_contraste_nueva, 1),
                      "Cuánto más oscura es la zona bajo los ojos"])
    tr = json.loads(s.textura_referencia) if s.textura_referencia else {}
    tn = json.loads(s.textura_nueva) if s.textura_nueva else {}
    if tn.get("lineas_mm_cm2") is not None and tr.get("lineas_mm_cm2") is not None:
        filas.append(["Líneas de expresión", f"{_num(tr['lineas_mm_cm2'], 1)} mm/cm²", f"{_num(tn['lineas_mm_cm2'], 1)} mm/cm²",
                      "Frente, entrecejo y contorno de los ojos"])
    if tn.get("poros_cm2") is not None and tr.get("poros_cm2") is not None:
        filas.append(["Poros visibles", f"{_num(tr['poros_cm2'], 1)} /cm²", f"{_num(tn['poros_cm2'], 1)} /cm²", "Mejillas"])
    if tn.get("brillo_pct") is not None and tr.get("brillo_pct") is not None:
        filas.append(["Brillo zona T", f"{_num(tr['brillo_pct'], 1)} %", f"{_num(tn['brillo_pct'], 1)} %", "Reflejo de la luz (grasa); depende de la iluminación"])
    if s.lesiones_nueva is not None:
        filas.append(["Regiones con aspecto de lesión", str(s.lesiones_referencia), str(s.lesiones_nueva),
                      f"Nuevas: {s.lesiones_nuevas} · Ya no aparecen: {s.lesiones_resueltas}"])
    return filas


def generar_informe(s, paciente, profesional) -> bytes:
    """`s` es un Seguimiento; `paciente` y `profesional`, sus modelos ORM."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Informe de evolución de la piel", author=profesional.nombre)
    est = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=est["Title"], textColor=VERDE, fontSize=18, spaceAfter=2 * mm, alignment=0)
    sub = ParagraphStyle("s", parent=est["Heading2"], textColor=VERDE, fontSize=12.5, spaceBefore=5 * mm, spaceAfter=2 * mm)
    normal = ParagraphStyle("n", parent=est["BodyText"], fontSize=10, leading=14)
    pie = ParagraphStyle("p", parent=normal, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"))
    centro = ParagraphStyle("c", parent=normal, alignment=1, fontSize=9, textColor=colors.HexColor("#444444"))

    i = interpretar(s)
    e = []
    e.append(Paragraph("Informe de evolución de la piel", titulo))
    e.append(Paragraph(f"<b>Paciente:</b> {escape(paciente.nombre)} {escape(paciente.apellido)} (CI {escape(paciente.cedula)})<br/>"
                       f"<b>Profesional:</b> {escape(profesional.nombre)}<br/>"
                       f"<b>Fecha de la consulta:</b> {s.fecha:%d/%m/%Y}", normal))

    e.append(Paragraph("Fotos comparadas", sub))
    ancho_foto = (ANCHO_UTIL - 6 * mm) / 2
    ref, hoy = _imagen(s.ruta_imagen_referencia, ancho_foto), _imagen(s.ruta_imagen_alineada, ancho_foto)
    if ref and hoy:
        t = Table([[ref, hoy], [Paragraph("Consulta de referencia", centro), Paragraph("Esta consulta (alineada)", centro)]],
                  colWidths=[ancho_foto + 3 * mm] * 2)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        e.append(t)
        e.append(Paragraph("La foto de esta consulta se ajustó automáticamente (posición, tamaño y giro) para que coincida "
                           "con la de referencia y se puedan comparar.", pie))

    e.append(Paragraph("Qué cambió", sub))
    for frase in i["resumen"]:
        e.append(Paragraph(f"• {escape(frase)}", normal))
    for adv in i["advertencias"]:
        e.append(Spacer(1, 2 * mm))
        e.append(Paragraph(f"<b>Atención:</b> {escape(adv)}", normal))

    tabla = Table([[Paragraph(escape(c), normal) for c in fila] for fila in _indices(s)],
                  colWidths=[40 * mm, 26 * mm, 36 * mm, ANCHO_UTIL - 102 * mm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF0ED")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C0D3CA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    e.append(KeepTogether([Paragraph("Índices medidos", sub), tabla]))

    extras = []
    ancho_extra = (ANCHO_UTIL - 12 * mm) / 3
    manchas = _imagen(s.ruta_imagen_manchas, ancho_extra)
    lesiones = _imagen(s.ruta_imagen_lesiones, ancho_extra)
    textura = _imagen(s.ruta_imagen_textura, ancho_extra)
    if manchas:
        extras.append((manchas, "Manchas: celeste = referencia, naranja = esta consulta"))
    if lesiones:
        extras.append((lesiones, "Regiones con aspecto de lesión"))
    if textura:
        extras.append((textura, "Textura: líneas en naranja, poros en celeste, brillo en blanco"))
    if extras:
        filas_t = []
        for k in range(0, len(extras), 3):
            grupo = extras[k:k + 3]
            relleno = [""] * (3 - len(grupo))
            filas_t.append([x[0] for x in grupo] + relleno)
            filas_t.append([Paragraph(x[1], centro) for x in grupo] + relleno)
        t = Table(filas_t, colWidths=[ancho_extra + 4 * mm] * 3)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        e.append(KeepTogether([Paragraph("Detalle de las zonas analizadas", sub), t]))

    if s.recomendaciones:
        caja = Table([[Paragraph(escape(s.recomendaciones).replace("\n", "<br/>"), normal)]], colWidths=[ANCHO_UTIL])
        caja.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F2E7")),
                                  ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#C9B280")),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                  ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        e.append(KeepTogether([Paragraph(f"Indicaciones de {escape(profesional.nombre)}", sub), caja]))

    e.append(Spacer(1, 6 * mm))
    e.append(Paragraph(f"<b>Importante:</b> {i['aclaracion']} Los índices sirven para comparar consultas de la misma persona "
                       "tomadas en condiciones parecidas; la luz, el maquillaje o el ángulo de la foto pueden influir.", pie))
    e.append(Paragraph(f"Generado con DermaSeguimiento el {ahora():%d/%m/%Y %H:%M} (hora del servidor, UTC).", pie))
    doc.build(e)
    return buf.getvalue()
