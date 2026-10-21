"""Cantidades negativas o fuera de rango: la API responde 422 con un mensaje claro, nunca 500."""
import pytest

from tests.conftest import archivos_seg, crear_paciente


@pytest.mark.parametrize("ruta", ["/pacientes", "/admin/usuarios", "/admin/suscripciones", "/admin/auditoria",
                                  "/admin/comprobantes", "/admin/pacientes-baja"])
@pytest.mark.parametrize("qs", ["tamano=-1", "tamano=0", "tamano=100000", "pagina=0", "pagina=-5", "pagina=abc", "tamano=1.5"])
def test_paginacion_invalida(client, admin, ruta, qs):
    r = client.get(f"{ruta}?{qs}", headers=admin)
    assert r.status_code == 422, (ruta, qs, r.text)
    assert r.json()["detail"].startswith("Revisá los datos ingresados")


@pytest.mark.parametrize("qs", ["tamano=-1", "pagina=0"])
def test_paginacion_invalida_en_historial(client, doc, qs):
    p = crear_paciente(client, doc)
    assert client.get(f"/pacientes/{p['id']}/seguimientos?{qs}", headers=doc).status_code == 422


def test_fechas_invalidas_en_filtros(client, doc):
    assert client.get("/pacientes?creado_desde=2026-13-40", headers=doc).status_code == 422
    assert client.get("/pacientes?estado=borrados", headers=doc).status_code == 422


@pytest.mark.parametrize("valoracion", [
    {"iga": -1}, {"iga": 5}, {"humedad": -0.1}, {"humedad": 151}, {"ph": -7}, {"ph": 2.9}, {"ph": 9.5},
    {"firmeza": -1}, {"firmeza": 101}, {"iga": "mucho"},
    {"masi": {r: {"area": -1, "oscuridad": 0} for r in ("frente", "malar_derecha", "malar_izquierda", "menton")}},
    {"masi": {r: {"area": 1, "oscuridad": 5} for r in ("frente", "malar_derecha", "malar_izquierda", "menton")}},
])
def test_valores_clinicos_negativos_o_fuera_de_rango(client, doc, pipeline_falso, valoracion):
    p = crear_paciente(client, doc)
    s = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])}, files=archivos_seg(), headers=doc).json()
    r = client.put(f"/seguimientos/{s['id']}/valoracion", json=valoracion, headers=doc)
    assert r.status_code == 422, r.text


def test_identificadores_negativos(client, doc):
    assert client.get("/pacientes/-1", headers=doc).status_code == 404
    assert client.patch("/pacientes/1", json={"version": "uno"}, headers=doc).status_code == 422
