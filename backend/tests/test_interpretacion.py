"""Interpretación en lenguaje natural de las métricas del seguimiento."""
from types import SimpleNamespace

import pytest

from services.interpretacion import interpretar


def seg(**kw):
    base = dict(delta_e_promedio=1.0, l_referencia=60, l_nueva=60, a_referencia=15, a_nueva=15, b_referencia=18, b_nueva=18,
                lesiones_referencia=None, lesiones_nueva=None, lesiones_nuevas=None, lesiones_persistentes=None, lesiones_resueltas=None,
                ojeras_contraste_referencia=None, ojeras_contraste_nueva=None, ssim_antes=None, ssim_despues=None)
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
