"""Interpretación en lenguaje natural de las métricas del seguimiento."""
from types import SimpleNamespace

import pytest

from services.interpretacion import interpretar


def seg(**kw):
    base = dict(delta_e_promedio=1.0, l_referencia=60, l_nueva=60, a_referencia=15, a_nueva=15, b_referencia=18, b_nueva=18,
                lesiones_referencia=None, lesiones_nueva=None, lesiones_nuevas=None, lesiones_persistentes=None, lesiones_resueltas=None,
                ojeras_contraste_referencia=None, ojeras_contraste_nueva=None, ssim_antes=None, ssim_despues=None,
                manchas_pct_referencia=None, manchas_pct_nueva=None, textura_referencia=None, textura_nueva=None)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("de,mag", [(1.0, "imperceptible"), (3.0, "leve"), (7.0, "moderado"), (15.0, "marcado")])
def test_magnitud(de, mag):
    assert interpretar(seg(delta_e_promedio=de, a_nueva=18))["magnitud_color"] == mag


def test_sin_cambio():
    r = interpretar(seg())
    assert "prácticamente igual" in r["resumen"][0] and r["advertencias"] == []


def test_direccion_del_cambio():
    r = interpretar(seg(delta_e_promedio=6, a_nueva=19, l_nueva=57))
    assert "más enrojecida y más oscura" in r["resumen"][0] and "moderado" in r["resumen"][0]
    assert "menos enrojecida" in interpretar(seg(delta_e_promedio=4, a_nueva=12))["resumen"][0]


def test_advierte_cambio_de_iluminacion():
    r = interpretar(seg(delta_e_promedio=9.4, l_nueva=66, a_nueva=18.5))
    assert r["advertencias"] and "iluminación" in r["advertencias"][0] and "más clara" in r["advertencias"][0]


def test_lesiones_y_ojeras():
    r = interpretar(seg(lesiones_referencia=3, lesiones_nueva=4, lesiones_nuevas=2, lesiones_persistentes=2, lesiones_resueltas=1,
                        ojeras_contraste_referencia=14.0, ojeras_contraste_nueva=17.0, ssim_antes=0.4, ssim_despues=0.7))
    texto = " ".join(r["resumen"])
    assert "2 aparecen en zonas donde antes no había" in texto and "2 persisten" in texto and "1 de la referencia ya no" in texto
    assert "ojeras se ven más marcadas" in texto and "0,40 a 0,70" in texto


def test_nunca_diagnostica():
    r = interpretar(seg(delta_e_promedio=20, a_nueva=25))
    assert "No constituye diagnóstico" in r["aclaracion"]
    for palabra in ("acné", "rosácea", "dermatitis", "diagnóstico de", "tratamiento"):
        assert palabra not in " ".join(r["resumen"]).lower()


def test_manchas():
    assert "superficie similar" in " ".join(interpretar(seg(manchas_pct_referencia=1.2, manchas_pct_nueva=1.4))["resumen"])
    r = " ".join(interpretar(seg(manchas_pct_referencia=3.0, manchas_pct_nueva=1.0))["resumen"])
    assert "ocupan menos superficie" in r and "3,00 %" in r and "1,00 %" in r
    assert "ocupan más superficie" in " ".join(interpretar(seg(manchas_pct_referencia=1.0, manchas_pct_nueva=2.5))["resumen"])


def test_textura():
    t = lambda li, po, br: {"lineas_mm_cm2": li, "poros_cm2": po, "brillo_pct": br}  # noqa: E731
    r = " ".join(interpretar(seg(textura_referencia=t(2.0, 20.0, 1.0), textura_nueva=t(8.0, 30.0, 4.0)))["resumen"])
    assert "más líneas de expresión" in r and "más poros" in r and "más brillante" in r and "mismo lugar" in r
    r = " ".join(interpretar(seg(textura_referencia=t(5.0, None, 1.0), textura_nueva=t(5.5, None, 1.2)))["resumen"])
    assert "líneas de expresión" in r and "similares" in r and "poros" not in r and "brillante" not in r  # sin poros: no se menciona


def test_causas_del_cambio_de_color():
    from services.color_regiones import causas
    zona = lambda n, dL, da, db, g: {"nombre": n, "dL": dL, "da": da, "db": db, "dL_local": dL - g[0], "da_local": da - g[1], "db_local": db - g[2]}  # noqa: E731
    g = (-6.0, 0.0, 0.0)  # todo el rostro más oscuro y parejo → luz
    c = causas({"global": {"dL": g[0], "da": g[1], "db": g[2]}, "zonas": {k: zona(k.title(), -6.2, 0, 0, g) for k in ("frente", "nariz", "menton")}})
    assert any("luz" in x for x in c) and "no un diagnóstico" in c[-1]
    g = (0.0, 0.5, 0.0)  # solo una mejilla más roja → cambio local
    c = causas({"global": {"dL": 0, "da": 0.5, "db": 0}, "zonas": {
        "mejilla_derecha": zona("Mejilla derecha", 0, 4.0, 0, g), "frente": zona("Frente", 0, 0.3, 0, g)}})
    assert any(x.startswith("Mejilla derecha: más enrojecida") for x in c) and not any("Frente" in x for x in c)
    assert causas({"global": {"dL": 0.2, "da": 0.1, "db": 0}, "zonas": {"frente": zona("Frente", 0.2, 0.1, 0, (0.2, 0.1, 0))}}) == []
