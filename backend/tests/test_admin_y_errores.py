import os
import re

import pytest
from sqlalchemy import text

from core.crypto import descifrar
from models.auditoria import Auditoria
from models.configuracion import ConfiguracionCorreo
from services.auditoria_service import registrar
from tests.conftest import PASSWORD, crear_paciente, crear_usuario, login, pagar


def test_auditoria_registra_acciones_y_fallos(client, admin, doc, db):
    crear_paciente(client, doc)
    client.post("/login", data={"username": "doc1@example.com", "password": "mala"})
    items = client.get("/admin/auditoria?tamano=200", headers=admin).json()["items"]
    acciones = {(i["modulo"], i["accion"], i["resultado"]) for i in items}
    assert ("auth", "registro", "exito") in acciones and ("auth", "login", "exito") in acciones
    assert ("auth", "login", "fallo") in acciones and ("pacientes", "crear", "exito") in acciones
    crear = next(i for i in items if i["accion"] == "crear")
    assert crear["usuario"] == "doc1@example.com" and crear["ip"] and crear["fecha"] and crear["entidad"] == "paciente"
    assert "password" not in (crear["datos_despues"] or "")
    fallo = next(i for i in items if i["accion"] == "login" and i["resultado"] == "fallo")
    assert fallo["usuario"] == "doc1@example.com"


def test_auditoria_guarda_antes_y_despues(client, admin, doc):
    p = crear_paciente(client, doc)
    client.patch(f"/pacientes/{p['id']}", json={"version": 1, "telefono": "0981 111222"}, headers=doc)
    mod = next(i for i in client.get("/admin/auditoria?accion=modificar", headers=admin).json()["items"])
    assert '"telefono": null' in mod["datos_antes"] and "0981 111222" in mod["datos_despues"]


def test_auditoria_es_inmutable(db):
    registrar(db, None, None, "prueba", "evento")
    fila = db.query(Auditoria).one()
    fila.detalle = "manipulado"
    with pytest.raises(PermissionError):
        db.commit()
    db.rollback()
    db.delete(db.query(Auditoria).one())
    with pytest.raises(PermissionError):
        db.commit()
    db.rollback()
    assert db.query(Auditoria).count() == 1


def test_no_hay_endpoint_para_modificar_auditoria(client, admin):
    for m in ("put", "patch", "delete"):
        assert getattr(client, m)("/admin/auditoria", headers=admin).status_code == 405


def test_filtros_de_auditoria_y_csv(client, admin, doc):
    crear_paciente(client, doc)
    assert all(i["modulo"] == "pacientes" for i in client.get("/admin/auditoria?modulo=pacientes", headers=admin).json()["items"])
    assert client.get("/admin/auditoria?resultado=raro", headers=admin).status_code == 422
    csv = client.get("/admin/auditoria.csv?modulo=pacientes", headers=admin)
    assert csv.status_code == 200 and "Bitácora de auditoría" in csv.content.decode("utf-8-sig") and "modulo=pacientes" in csv.content.decode("utf-8-sig")


def test_listado_de_usuarios_y_cambio_de_rol(client, admin, doc):
    r = client.get("/admin/usuarios?q=doc1", headers=admin).json()
    assert r["total"] == 1 and "password_hash" not in str(r)
    uid = r["items"][0]["id"]
    assert client.put(f"/admin/usuarios/{uid}/rol", json={"rol": "admin"}, headers=admin).status_code == 400
    assert client.put(f"/admin/usuarios/{uid}/rol", json={"rol": "superman", "confirmar": True}, headers=admin).status_code == 422
    assert client.put(f"/admin/usuarios/{uid}/rol", json={"rol": "admin", "confirmar": True}, headers=admin).status_code == 200
    assert client.get("/admin/usuarios", headers=doc).status_code == 401  # su sesión se cerró; el rol nuevo exige volver a entrar
    assert client.get("/admin/usuarios", headers=login(client)).status_code == 200


def test_admin_no_puede_inactivarse_a_si_mismo(client, admin):
    yo = client.get("/perfil", headers=admin).json()["id"]
    assert client.post(f"/admin/usuarios/{yo}/inactivar", json={"motivo": "x", "confirmar": True}, headers=admin).status_code == 400


def test_pantalla_administrativa_de_suscripciones(client, admin, doc, doc2, db):
    from datetime import timedelta
    from core.tiempo import ahora
    from models.suscripcion import Suscripcion
    pagar(client, doc)
    db.query(Suscripcion).filter(Suscripcion.usuario_id == 2).update({"fecha_vencimiento": ahora() + timedelta(days=3)})
    db.commit()
    r = client.get("/admin/suscripciones", headers=admin).json()
    assert r["total"] == 2 and r["resumen"]["proxima_a_vencer"] >= 1
    assert client.get("/admin/suscripciones?categoria=proxima_a_vencer", headers=admin).json()["total"] >= 1
    assert client.get("/admin/suscripciones?categoria=inventada", headers=admin).status_code == 422
    assert client.post("/admin/recordatorios/ejecutar", headers=admin).json()["avisos_generados"] >= 1


# ------------------------------------------------------------------ correo (punto 16)
def _cfg(**extra):
    d = {"habilitado": True, "host": "smtp.ejemplo.com", "puerto": 587, "seguridad": "starttls", "usuario": "apikey",
         "password": "SuperSecreta-SMTP-123", "remitente_email": "no-reply@ejemplo.com", "remitente_nombre": "Derma", "timeout_segundos": 10}
    d.update(extra)
    return d


def test_config_correo_nunca_expone_ni_guarda_en_claro_la_password(client, admin, db):
    r = client.put("/admin/config-correo", json=_cfg(), headers=admin)
    assert r.status_code == 200 and "SuperSecreta" not in r.text and r.json()["password_configurada"] is True
    assert "SuperSecreta" not in client.get("/admin/config-correo", headers=admin).text
    guardada = db.query(ConfiguracionCorreo).one().password_cifrada
    assert "SuperSecreta" not in guardada and descifrar(guardada) == "SuperSecreta-SMTP-123"
    client.put("/admin/config-correo", json=_cfg(password=None, puerto=465, seguridad="ssl"), headers=admin)  # sin password = conserva
    db.expire_all()
    assert descifrar(db.query(ConfiguracionCorreo).one().password_cifrada) == "SuperSecreta-SMTP-123"


@pytest.mark.parametrize("campo,valor", [("puerto", 0), ("puerto", 70000), ("seguridad", "raro"), ("remitente_email", "nada")])
def test_config_correo_validaciones(client, admin, campo, valor):
    assert client.put("/admin/config-correo", json=_cfg(**{campo: valor}), headers=admin).status_code == 422


def test_config_correo_solo_admin_y_probar_conexion_falla_con_mensaje_amable(client, admin, doc):
    assert client.put("/admin/config-correo", json=_cfg(), headers=doc).status_code == 403
    client.put("/admin/config-correo", json=_cfg(host="127.0.0.1", puerto=1, timeout_segundos=1), headers=admin)
    r = client.post("/admin/config-correo/probar", headers=admin)
    assert r.status_code == 502 and "Revisá" in r.json()["detail"] and "Traceback" not in r.text


def test_plantillas_de_correo_editables(client, admin):
    lista = client.get("/admin/plantillas-correo", headers=admin).json()
    assert {p["codigo"] for p in lista} >= {"restablecer_password", "aviso_vencimiento"}
    assert client.put("/admin/plantillas-correo/inexistente", json={"asunto": "hola", "cuerpo": "cuerpo de prueba"}, headers=admin).status_code == 404
    assert client.put("/admin/plantillas-correo/aviso_vencimiento", json={"asunto": "Aviso nuevo", "cuerpo": "Hola $nombre: $mensaje"}, headers=admin).status_code == 200


# ------------------------------------------------------------------ errores sin información técnica (puntos 17-18, RNF-18)
def test_ruta_inexistente_y_metodo_no_permitido(client):
    r = client.get("/no-existe")
    assert r.status_code == 404 and r.json() == {"detail": "No encontramos lo que buscás."}
    assert client.delete("/planes").status_code == 405


def test_error_inesperado_no_filtra_detalles(doc, monkeypatch):
    from fastapi.testclient import TestClient
    from main import app

    def rompe(*a, **k):
        raise RuntimeError("SELECT * FROM usuarios WHERE password='x' /home/lujan/secreto.py")

    monkeypatch.setattr("routers.pacientes._respuesta", rompe)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post("/pacientes", json={"cedula": "7654321", "nombre": "A", "apellido": "B", "consentimiento": {"acepta": True}}, headers=doc)
    assert r.status_code == 500
    for prohibido in ("SELECT", "/home/", "RuntimeError", "Traceback", "secreto"):
        assert prohibido not in r.text
    assert "Ocurrió un error inesperado" in r.json()["detail"]


def test_error_de_validacion_en_espanol_sin_estructura_interna(client):
    r = client.post("/registro", json={"email": "x"})
    assert r.status_code == 422
    d = r.json()["detail"]
    assert "Revisá los datos" in d and "loc" not in r.text and "pydantic" not in r.text.lower()


def test_integridad_devuelve_409_amable(client, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    def rompe(*a, **k):
        raise IntegrityError("INSERT INTO usuarios ...", {}, Exception("duplicate key value violates unique constraint uq"))
    monkeypatch.setattr("routers.auth.hash_password", rompe)
    r = client.post("/registro", json={"email": "z@example.com", "password": PASSWORD, "confirmar_password": PASSWORD, "nombre": "Z", "acepta_politica": True})
    assert r.status_code == 409 and "duplicate" not in r.text and "INSERT" not in r.text


# ------------------------------------------------------------------ configuración y calidad (puntos 24, 33, 34)
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _archivos_py():
    for base, dirs, files in os.walk(BACKEND):
        dirs[:] = [d for d in dirs if d not in ("venv", "__pycache__", "tests", "migrations", "almacenamiento")]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(base, f)


def test_no_hay_credenciales_ni_urls_de_base_en_el_codigo():
    for ruta in _archivos_py():
        codigo = open(ruta, encoding="utf-8").read()
        assert not re.search(r"postgres(ql)?://[^\s\"']*@", codigo), f"URL de base con usuario en {ruta}"
        assert "cambiar-esto-por-una-clave" not in codigo, ruta
        assert not re.search(r"(SECRET_KEY|PASSWORD|SECRETO)\w*\s*=\s*[\"'][^\"']{8,}[\"']", codigo, re.I), ruta


def test_env_no_esta_versionado():
    raiz = os.path.dirname(BACKEND)
    assert ".env" in open(os.path.join(raiz, ".gitignore")).read()
    assert os.path.exists(os.path.join(BACKEND, ".env.example"))


def test_parametros_configurables():
    from core.config import Settings
    campos = Settings.model_fields
    for c in ("ACCESS_TOKEN_EXPIRE_MINUTES", "INACTIVITY_TIMEOUT_MINUTES", "LOGIN_MAX_ATTEMPTS", "PASSWORD_MIN_LENGTH", "RESET_TOKEN_MINUTES",
              "MAX_UPLOAD_MB", "AVISOS_DIAS_ANTES", "TRIAL_DAYS", "DELTA_E_MAXIMO_VISUAL"):
        assert c in campos


def test_salud_no_expone_datos(client):
    assert client.get("/salud").json() == {"estado": "ok"}
    assert client.get("/test-db").status_code == 404  # el endpoint que revelaba la versión de PostgreSQL ya no existe


def test_cabeceras_de_seguridad(client):
    r = client.get("/planes")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"


# ------------------------------------------------------------------ SUS (RF-08 / RNF-11)
def test_calculo_y_registro_sus(client, doc, admin):
    from routers.sus import calcular_sus
    assert calcular_sus([5, 1] * 5) == 100 and calcular_sus([1, 5] * 5) == 0 and calcular_sus([3] * 10) == 50
    assert client.post("/sus", json={"respuestas": [5, 1] * 5, "comentario": "Muy clara"}, headers=doc).json()["puntaje"] == 100
    assert client.post("/sus", json={"respuestas": [4, 2] * 5}, headers=doc).status_code == 201
    assert client.post("/sus", json={"respuestas": [6] + [3] * 9}, headers=doc).status_code == 422
    assert client.post("/sus", json={"respuestas": [3] * 9}, headers=doc).status_code == 422
    r = client.get("/admin/sus", headers=admin).json()
    assert r["respuestas"] == 2 and r["puntaje_promedio"] == 87.5 and r["cumple_objetivo_68"] is True
