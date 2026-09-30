import pytest

from models.paciente import Paciente
from tests.conftest import crear_paciente, datos_paciente


def test_crear_y_buscar_paciente(client, doc):
    p = crear_paciente(client, doc)
    assert p["tiene_consentimiento"] is True and p["activo"] is True
    r = client.get("/pacientes/buscar/1234567", headers=doc).json()
    assert r["existe"] is True and r["paciente"]["id"] == p["id"]
    assert client.get("/pacientes/buscar/9999999", headers=doc).json() == {"existe": False, "paciente": None}


def test_sin_consentimiento_no_se_registra(client, doc):
    r = client.post("/pacientes", json=datos_paciente(consentimiento={"acepta": False}), headers=doc)
    assert r.status_code == 400 and "consentimiento" in r.json()["detail"]
    assert client.post("/pacientes", json={k: v for k, v in datos_paciente().items() if k != "consentimiento"}, headers=doc).status_code == 422


@pytest.mark.parametrize("campo,valor", [
    ("cedula", "abc"), ("cedula", "12"), ("cedula", ""), ("cedula", "1" * 11),
    ("nombre", ""), ("nombre", "   "), ("nombre", "<b>x</b>"), ("apellido", "y" * 81),
    ("telefono", "hola"), ("telefono", "1" * 30), ("sexo", "X"),
    ("fecha_nacimiento", "2999-01-01"), ("fecha_nacimiento", "1800-01-01"), ("fecha_nacimiento", "no-es-fecha"),
    ("observaciones", "<script>alert(1)</script>"), ("observaciones", "z" * 2001),
])
def test_validaciones_de_paciente(client, doc, campo, valor):
    r = client.post("/pacientes", json=datos_paciente(**{campo: valor}), headers=doc)
    assert r.status_code == 422, (campo, valor, r.text)
    assert "detail" in r.json() and "Traceback" not in r.text


def test_cedula_se_normaliza(client, doc):
    assert crear_paciente(client, doc, cedula="1.234.567")["cedula"] == "1234567"


def test_cedula_duplicada_409(client, doc):
    crear_paciente(client, doc)
    r = client.post("/pacientes", json=datos_paciente(), headers=doc)
    assert r.status_code == 409


def test_cada_dermatologo_ve_solo_lo_suyo(client, doc, doc2):
    p = crear_paciente(client, doc)
    assert client.get("/pacientes/buscar/1234567", headers=doc2).json()["existe"] is False
    assert client.get(f"/pacientes/{p['id']}", headers=doc2).status_code == 404
    assert client.get(f"/pacientes/{p['id']}/seguimientos", headers=doc2).status_code == 404
    assert client.patch(f"/pacientes/{p['id']}", json={"version": 1, "nombre": "Hack"}, headers=doc2).status_code == 404
    assert client.request("DELETE", f"/pacientes/{p['id']}", json={"motivo": "intento ajeno", "confirmar": True}, headers=doc2).status_code == 404
    assert client.get("/pacientes", headers=doc2).json()["total"] == 0
    # el otro puede registrar la misma cédula: son carteras independientes
    assert client.post("/pacientes", json=datos_paciente(), headers=doc2).status_code == 201


def test_manipular_identificadores(client, doc):
    for ruta in ("/pacientes/999999", "/pacientes/0", "/pacientes/-1"):
        assert client.get(ruta, headers=doc).status_code == 404
    assert client.get("/pacientes/abc", headers=doc).status_code == 422


def test_sin_token_no_hay_acceso(client):
    assert client.get("/pacientes").status_code == 401
    assert client.post("/pacientes", json=datos_paciente()).status_code == 401
    assert client.get("/pacientes/buscar/1234567").status_code == 401


def test_listado_con_filtros_y_paginacion(client, doc):
    for i, (n, a) in enumerate([("Ana", "Zorrilla"), ("Beatriz", "Acosta"), ("Carlos", "Benítez")]):
        crear_paciente(client, doc, cedula=str(1000000 + i), nombre=n, apellido=a)
    r = client.get("/pacientes?tamano=2", headers=doc).json()
    assert r["total"] == 3 and len(r["items"]) == 2 and r["items"][0]["apellido"] == "Acosta"
    assert len(client.get("/pacientes?tamano=2&pagina=2", headers=doc).json()["items"]) == 1
    assert client.get("/pacientes?q=benít", headers=doc).json()["total"] == 1
    assert client.get("/pacientes?q=1000001", headers=doc).json()["total"] == 1
    assert client.get("/pacientes?tamano=0", headers=doc).status_code == 422
    assert client.get("/pacientes?estado=raro", headers=doc).status_code == 422


def test_control_de_concurrencia_en_edicion(client, doc):
    p = crear_paciente(client, doc)
    a = client.patch(f"/pacientes/{p['id']}", json={"version": 1, "telefono": "0981 123456"}, headers=doc)
    assert a.status_code == 200 and a.json()["version"] == 2
    # una segunda persona que abrió la ficha antes intenta guardar con la versión vieja
    b = client.patch(f"/pacientes/{p['id']}", json={"version": 1, "telefono": "0991 000000"}, headers=doc)
    assert b.status_code == 409 and "modificada" in b.json()["detail"]
    assert client.get(f"/pacientes/{p['id']}", headers=doc).json()["telefono"] == "0981 123456"


def test_baja_logica_con_confirmacion_y_motivo(client, doc, db):
    p = crear_paciente(client, doc)
    assert client.request("DELETE", f"/pacientes/{p['id']}", json={"motivo": "duplicado"}, headers=doc).status_code == 400  # sin confirmar
    assert client.request("DELETE", f"/pacientes/{p['id']}", json={"motivo": "x", "confirmar": True}, headers=doc).status_code == 422
    assert client.request("DELETE", f"/pacientes/{p['id']}", json={"motivo": "Carga duplicada", "confirmar": True}, headers=doc).status_code == 200
    assert client.get("/pacientes", headers=doc).json()["total"] == 0
    assert client.get("/pacientes?estado=inactivos", headers=doc).json()["total"] == 1
    fila = db.query(Paciente).one()  # la fila sigue existiendo
    assert fila.activo is False and fila.motivo_eliminacion == "Carga duplicada" and fila.eliminado_en
    assert client.post("/pacientes", json=datos_paciente(), headers=doc).status_code == 409  # cédula sigue reservada


def test_revocar_y_renovar_consentimiento(client, doc):
    p = crear_paciente(client, doc)
    assert client.post(f"/pacientes/{p['id']}/consentimiento", headers=doc).status_code == 409
    assert client.post(f"/pacientes/{p['id']}/consentimiento/revocar", headers=doc).status_code == 200
    assert client.get(f"/pacientes/{p['id']}", headers=doc).json()["tiene_consentimiento"] is False
    assert client.post(f"/pacientes/{p['id']}/consentimiento/revocar", headers=doc).status_code == 409
    assert client.post(f"/pacientes/{p['id']}/consentimiento", headers=doc).status_code == 200
    assert client.get(f"/pacientes/{p['id']}", headers=doc).json()["tiene_consentimiento"] is True


def test_politica_de_privacidad_publica(client):
    r = client.get("/politica-privacidad")
    assert r.status_code == 200
    titulos = " ".join(s["titulo"].lower() for s in r.json()["secciones"])
    for esperado in ("qué datos", "para qué", "responsable", "conservamos", "compartimos", "seguridad", "derechos"):
        assert esperado in titulos
