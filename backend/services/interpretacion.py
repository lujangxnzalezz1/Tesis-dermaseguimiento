"""Traduce las métricas del seguimiento a frases comprensibles para el dermatólogo.

Solo describe cambios observables entre dos fotografías; NO interpreta clínicamente ni diagnostica.
Los umbrales de magnitud provienen de la percepción del color (CIE76: ~2,3 = diferencia mínima
perceptible, Sharma 2003) y son configurables; no están validados clínicamente.
"""
import json

from core.config import settings


def _num(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _magnitud(delta_e: float) -> str:
    s = settings
    if delta_e < s.INTERP_DELTA_E_PERCEPTIBLE:
        return "imperceptible"
    if delta_e < s.INTERP_DELTA_E_MODERADO:
        return "leve"
    if delta_e < s.INTERP_DELTA_E_MARCADO:
        return "moderado"
    return "marcado"


def _textura(seg, campo):
    v = getattr(seg, campo, None)
    if v is None:
        return None
    return json.loads(v) if isinstance(v, str) else v


def interpretar(seg) -> dict:
    """`seg` es un Seguimiento (modelo ORM)."""
    s = settings
    frases, advertencias = [], []
    mag = _magnitud(seg.delta_e_promedio)
    dl, da, db = seg.l_nueva - seg.l_referencia, seg.a_nueva - seg.a_referencia, seg.b_nueva - seg.b_referencia
    u = s.INTERP_UMBRAL_COMPONENTE

    if mag == "imperceptible":
        frases.append("El color de la piel se mantiene prácticamente igual que en la consulta de referencia.")
    else:
        direcciones = []
        if da > u:
            direcciones.append("más enrojecida")
        elif da < -u:
            direcciones.append("menos enrojecida")
        if dl > u:
            direcciones.append("más clara")
        elif dl < -u:
            direcciones.append("más oscura")
        if db > u:
            direcciones.append("más amarillenta")
        elif db < -u:
            direcciones.append("menos amarillenta")
        como = (" y ".join([", ".join(direcciones[:-1]), direcciones[-1]]) if len(direcciones) > 1 else direcciones[0]) if direcciones else "con un tono distinto"
        frases.append(f"En promedio, la piel del rostro se ve {como} que en la consulta de referencia (cambio {mag}).")

    # Un cambio grande de luminosidad en todo el rostro suele deberse a la iluminación, no a la piel
    if abs(dl) > s.CAPTURA_DIF_LUZ_MAX:
        advertencias.append(f"La luminosidad general del rostro cambió bastante ({'más clara' if dl > 0 else 'más oscura'}): "
                            "parte de la diferencia puede deberse a una iluminación distinta entre las fotos y no a la piel. "
                            "Conviene repetir la foto con la misma luz y en el mismo lugar.")

    if seg.lesiones_nueva is not None:
        if seg.lesiones_nuevas == 0 and seg.lesiones_resueltas == 0:
            frases.append(f"Se marcaron {seg.lesiones_nueva} regiones con aspecto de lesión, en las mismas zonas que en la referencia.")
        else:
            partes = []
            if seg.lesiones_nuevas:
                partes.append(f"{seg.lesiones_nuevas} aparecen en zonas donde antes no había")
            if seg.lesiones_persistentes:
                partes.append(f"{seg.lesiones_persistentes} persisten")
            if seg.lesiones_resueltas:
                partes.append(f"{seg.lesiones_resueltas} de la referencia ya no se detectan")
            frases.append(f"Regiones con aspecto de lesión: {seg.lesiones_referencia} en la referencia y {seg.lesiones_nueva} ahora; "
                          + ", ".join(partes) + ".")

    if seg.ojeras_contraste_nueva is not None and seg.ojeras_contraste_referencia is not None:
        d = seg.ojeras_contraste_nueva - seg.ojeras_contraste_referencia
        if abs(d) < s.INTERP_UMBRAL_OJERAS:
            frases.append("Las ojeras se ven similares a la consulta de referencia.")
        else:
            frases.append(f"Las ojeras se ven {'más marcadas' if d > 0 else 'más atenuadas'} que en la consulta de referencia.")

    if seg.manchas_pct_nueva is not None and seg.manchas_pct_referencia is not None:
        d = seg.manchas_pct_nueva - seg.manchas_pct_referencia
        cifras = f"{_num(seg.manchas_pct_referencia)} % de la piel analizada en la referencia y {_num(seg.manchas_pct_nueva)} % ahora"
        if abs(d) < s.INTERP_UMBRAL_MANCHAS_PCT:
            frases.append(f"Las zonas más oscuras que la piel de alrededor (manchas) ocupan una superficie similar ({cifras}).")
        else:
            frases.append(f"Las zonas más oscuras que la piel de alrededor (manchas) ocupan {'más' if d > 0 else 'menos'} "
                          f"superficie que en la referencia ({cifras}).")

    tr, tn = _textura(seg, "textura_referencia"), _textura(seg, "textura_nueva")
    if tr and tn:
        if tr.get("lineas_mm_cm2") is not None and tn.get("lineas_mm_cm2") is not None:
            d = tn["lineas_mm_cm2"] - tr["lineas_mm_cm2"]
            if abs(d) < s.INTERP_UMBRAL_LINEAS:
                frases.append("Las líneas de expresión (frente, entrecejo y contorno de los ojos) se ven similares a la referencia.")
            else:
                frases.append(f"Se marcan {'más' if d > 0 else 'menos'} líneas de expresión que en la referencia "
                              f"({_num(tr['lineas_mm_cm2'])} → {_num(tn['lineas_mm_cm2'])} mm de línea por cm²).")
        if tr.get("poros_cm2") is not None and tn.get("poros_cm2") is not None:
            d = tn["poros_cm2"] - tr["poros_cm2"]
            if abs(d) >= s.INTERP_UMBRAL_POROS:
                frases.append(f"Se ven {'más' if d > 0 else 'menos'} poros en las mejillas ({_num(tr['poros_cm2'])} → {_num(tn['poros_cm2'])} por cm²).")
            else:
                frases.append("La cantidad de poros visibles en las mejillas es similar a la referencia.")
        if tr.get("brillo_pct") is not None and tn.get("brillo_pct") is not None:
            d = tn["brillo_pct"] - tr["brillo_pct"]
            if abs(d) >= s.INTERP_UMBRAL_BRILLO:
                frases.append(f"La zona T se ve {'más' if d > 0 else 'menos'} brillante ({_num(tr['brillo_pct'])} % → {_num(tn['brillo_pct'])} %). "
                              "El brillo depende mucho de la luz: compará solo fotos tomadas en el mismo lugar.")

    if seg.ssim_antes is not None and seg.ssim_despues is not None and seg.ssim_despues > seg.ssim_antes:
        frases.append("La alineación automática hizo las fotos comparables (la similitud estructural subió de "
                      f"{_num(seg.ssim_antes)} a {_num(seg.ssim_despues)}).")

    return {
        "magnitud_color": mag,
        "resumen": frases,
        "advertencias": advertencias,
        "aclaracion": "Descripción automática de diferencias entre dos fotografías. No constituye diagnóstico; "
                      "la interpretación clínica corresponde al profesional.",
    }
