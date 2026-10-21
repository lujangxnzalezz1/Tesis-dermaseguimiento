"""Política de contraseñas editable por el administrador, reglas ampliadas y vencimiento obligatorio."""
from datetime import timedelta

import pytest

from core.config import settings
from core.politica_password import errores_password
from core.tiempo import ahora
from models.auditoria import Auditoria
from models.usuario import Usuario
from tests.conftest import PASSWORD, crear_usuario, datos_registro, login

RUTA = "/admin/seguridad/politica-contrasenas"


def _politica(**extra):
    d = {"longitud_minima": 12, "requiere_mayuscula": True, "requiere_minuscula": True, "requiere_numero": True,
         "requiere_especial": False, "max_dias_vigencia": 0, "comunes_adicionales": ["Consultorio.Central"]}
    d.update(extra)
    return d


# ------------------------------------------------------------------ reglas
@pytest.mark.parametrize("password", [
    "Dragon2024!", "Qwerty#123456", "Abcdef#98Kl!", "Zzzz#2026Hola", "Pass1234567!!", "Olimpia#2026",
    "Barcelona!2026", "Contraseña#2026", "98765#Lkjhg!", "Mmmm#2026xyAb",
])
def test_rechaza_comunes_secuencias_y_repeticiones(password):
    assert errores_password(password), password


def test_rechaza_partes_del_correo():
    assert errores_password("Gonzalez#2026x", "lujan.gonzalez@example.com")
    assert not errores_password("Segura#2026ok", "lujan.gonzalez@example.com")


def test_acepta_contrasenas_robustas():
    for p in (PASSWORD, "Ventana-Roja#47", "Piel&Color2026x"):
        assert errores_password(p) == [], p


# ------------------------------------------------------------------ administración
def test_solo_admin_puede_ver_y_editar(client, doc):
    assert client.get(RUTA, headers=doc).status_code == 403
    assert client.put(RUTA, json=_politica(), headers=doc).status_code == 403
    assert client.get(RUTA).status_code == 401


def test_admin_edita_politica_y_se_refleja_en_endpoint_publico_y_validacion(client, admin, db):
    r = client.get(RUTA, headers=admin)
    assert r.status_code == 200 and r.json()["personalizada"] is False
    assert r.json()["longitud_minima"] == settings.PASSWORD_MIN_LENGTH

    r = client.put(RUTA, json=_politica(), headers=admin)
    assert r.status_code == 200, r.text
    publica = client.get("/politica-contrasenas").json()
    assert publica["longitud_minima"] == 12 and publica["requiere_especial"] is False
    assert "12 caracteres" in publica["descripcion"]

    # 11 caracteres ya no alcanza; sin carácter especial sí se acepta; la lista adicional se aplica
    assert client.post("/registro", json=datos_registro(password="Segura2026k")).status_code == 422
    assert client.post("/registro", json=datos_registro(password="Segura2026okk")).status_code == 201
    assert client.post("/registro", json=datos_registro("b@example.com", password="consultorio.central")).status_code == 422
    assert "es demasiado común" in client.post("/registro", json=datos_registro("c@example.com", password="Consultoriocentral1")).json()["detail"]

    ev = db.query(Auditoria).filter(Auditoria.accion == "politica_contrasenas").one()
    assert '"longitud_minima": 12' in ev.datos_despues and ev.datos_antes

    r = client.delete(RUTA, headers=admin)  # vuelve a los valores del entorno
    assert r.json()["personalizada"] is False and r.json()["longitud_minima"] == settings.PASSWORD_MIN_LENGTH


@pytest.mark.parametrize("campo,valor", [("longitud_minima", 4), ("longitud_minima", 100), ("max_dias_vigencia", -1),
                                         ("max_dias_vigencia", 5000), ("comunes_adicionales", ["x" * 65])])
def test_politica_validaciones(client, admin, campo, valor):
    assert client.put(RUTA, json=_politica(**{campo: valor}), headers=admin).status_code == 422


# ------------------------------------------------------------------ vencimiento de la contraseña
def _vencer(db, email="doc1@example.com", dias=100):
    u = db.query(Usuario).filter(Usuario.email == email).one()
    u.password_cambiada_en = ahora() - timedelta(days=dias)
    db.commit()


def test_password_vencida_bloquea_hasta_cambiarla(client, db, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_MAX_AGE_DAYS", 90)
    crear_usuario(client)
    _vencer(db)
    r = client.post("/login", data={"username": "doc1@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["password_vencida"] is True
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get("/pacientes", headers=h)
    assert r.status_code == 403 and "venció" in r.json()["detail"]
    perfil = client.get("/perfil", headers=h)
    assert perfil.status_code == 200 and perfil.json()["password_vencida"] is True

    nueva = "Renovada#2026xy"
    assert client.post("/cambiar-contrasena", headers=h,
                       json={"password_actual": PASSWORD, "password": nueva, "confirmar_password": nueva}).status_code == 200
    assert client.get("/pacientes", headers=h).status_code == 200
    assert client.post("/logout", headers=h).status_code == 200


def test_vencimiento_configurado_desde_admin(client, admin, db):
    crear_usuario(client)
    h = login(client)
    _vencer(db, dias=40)
    assert client.get("/pacientes", headers=h).status_code == 200  # por defecto no vencen
    client.put(RUTA, json=_politica(max_dias_vigencia=30), headers=admin)
    assert client.get("/pacientes", headers=h).status_code == 403


def test_cambio_exige_contrasena_distinta_y_sin_el_correo(client, doc):
    r = client.post("/cambiar-contrasena", headers=doc, json={"password_actual": PASSWORD, "password": PASSWORD, "confirmar_password": PASSWORD})
    assert r.status_code == 422 and "distinta" in r.json()["detail"]
    n = "Doc1#Clave2026x"  # contiene «doc1», la parte local del correo
    r = client.post("/cambiar-contrasena", headers=doc, json={"password_actual": PASSWORD, "password": n, "confirmar_password": n})
    assert r.status_code == 422 and "correo" in r.json()["detail"]
