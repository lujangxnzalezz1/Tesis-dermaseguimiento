from datetime import timedelta

import pytest

from core.config import settings
from core.tiempo import ahora
from models.usuario import Sesion, TokenRestablecimiento, Usuario
from services import email_service
from tests.conftest import PASSWORD, crear_usuario, datos_registro, login


# ------------------------------------------------------------------ registro y validación (puntos 5 y 6)
@pytest.mark.parametrize("password,fragmento", [
    ("corta1A!", "al menos"), ("todominuscula1!", "mayúscula"), ("TODOMAYUSCULA1!", "minúscula"),
    ("SinNumeros!!!!", "número"), ("SinEspecial123A", "especial"), ("Password123!", "común"),
])
def test_politica_de_contrasenas(client, password, fragmento):
    r = client.post("/registro", json=datos_registro(password=password))
    assert r.status_code == 422
    assert fragmento in r.json()["detail"]


def test_password_igual_al_correo_rechazada(client):
    r = client.post("/registro", json=datos_registro(email="marcelo.perez@x.com", password="Marcelo.Perez1!"))
    assert r.status_code == 422


def test_confirmacion_de_password_distinta(client):
    d = datos_registro()
    d["confirmar_password"] = "OtraDistinta#1234"
    assert client.post("/registro", json=d).status_code == 422


@pytest.mark.parametrize("campo,valor", [("email", "no-es-un-correo"), ("email", ""), ("nombre", ""), ("nombre", "<script>alert(1)</script>"),
                                       ("nombre", "x" * 101), ("acepta_politica", False)])
def test_registro_rechaza_datos_invalidos(client, campo, valor):
    r = client.post("/registro", json=datos_registro(**{campo: valor}))
    assert r.status_code == 422


def test_registro_campos_vacios_o_ausentes(client):
    assert client.post("/registro", json={}).status_code == 422
    assert client.post("/registro", content="{roto", headers={"Content-Type": "application/json"}).status_code == 422


def test_registro_duplicado_409_y_correo_normalizado(client):
    crear_usuario(client, "Doc@Example.com")
    r = client.post("/registro", json=datos_registro("doc@example.com"))
    assert r.status_code == 409 and "ya está registrado" in r.json()["detail"]


def test_registro_guarda_version_de_politica(client, db):
    crear_usuario(client)
    u = db.query(Usuario).first()
    assert u.politica_aceptada_version == settings.POLITICA_VERSION and u.politica_aceptada_en
    assert u.password_hash != PASSWORD and u.password_hash.startswith("$2")  # bcrypt


def test_no_se_puede_elegir_rol_admin_al_registrarse(client, db):
    r = client.post("/registro", json=datos_registro(rol="admin"))
    assert r.status_code == 201 and r.json()["rol"] == "dermatologo"


# ------------------------------------------------------------------ login, bloqueo, usuarios inactivos (punto 2)
def test_login_incorrecto_mensaje_generico(client):
    crear_usuario(client)
    a = client.post("/login", data={"username": "doc1@example.com", "password": "Incorrecta#1"})
    b = client.post("/login", data={"username": "noexiste@example.com", "password": "Incorrecta#1"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]  # no revela si el correo existe


def test_bloqueo_tras_intentos_fallidos(client):
    crear_usuario(client)
    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        assert client.post("/login", data={"username": "doc1@example.com", "password": "mala"}).status_code == 401
    r = client.post("/login", data={"username": "doc1@example.com", "password": PASSWORD})  # ni la correcta entra
    assert r.status_code == 429 and "esperá" in r.json()["detail"]


def test_usuario_inactivo_no_puede_ingresar(client, admin, db):
    u = crear_usuario(client)
    h = login(client)
    assert client.get("/perfil", headers=h).status_code == 200
    r = client.post(f"/admin/usuarios/{u['id']}/inactivar", json={"motivo": "Baja solicitada", "confirmar": True}, headers=admin)
    assert r.status_code == 200
    # la sesión abierta deja de funcionar y no puede volver a entrar
    assert client.get("/perfil", headers=h).status_code == 401
    r = client.post("/login", data={"username": "doc1@example.com", "password": PASSWORD})
    assert r.status_code == 403 and "inactiva" in r.json()["detail"]
    fila = db.query(Usuario).filter(Usuario.id == u["id"]).one()
    assert fila.fecha_inactivacion and fila.motivo_inactivacion == "Baja solicitada"
    # reactivación
    assert client.post(f"/admin/usuarios/{u['id']}/reactivar", json={"confirmar": True}, headers=admin).status_code == 200
    db.expire_all()
    assert db.query(Usuario).filter(Usuario.id == u["id"]).one().fecha_reactivacion
    login(client)


def test_inactivar_exige_confirmacion_y_motivo(client, admin):
    u = crear_usuario(client)
    assert client.post(f"/admin/usuarios/{u['id']}/inactivar", json={"motivo": "x"}, headers=admin).status_code == 400
    assert client.post(f"/admin/usuarios/{u['id']}/inactivar", json={"confirmar": True}, headers=admin).status_code == 400


# ------------------------------------------------------------------ sesiones (punto 3)
def test_rutas_protegidas_sin_token_o_con_token_falso(client):
    for ruta in ("/perfil", "/pacientes", "/suscripcion", "/notificaciones", "/pagos"):
        r = client.get(ruta)
        assert r.status_code == 401 and r.json()["detail"] == "Necesitás iniciar sesión para continuar." 
    assert client.get("/perfil", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_token_manipulado_es_rechazado(client, doc):
    token = doc["Authorization"].split()[1]
    partes = token.split(".")
    falso = ".".join([partes[0], partes[1], partes[2][:-3] + "AAA"])
    assert client.get("/perfil", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_sesion_expira(client, doc, db):
    db.query(Sesion).update({"expira_en": ahora() - timedelta(seconds=1)})
    db.commit()
    r = client.get("/perfil", headers=doc)
    assert r.status_code == 401 and "expiró" in r.json()["detail"]


def test_sesion_se_cierra_por_inactividad(client, doc, db):
    db.query(Sesion).update({"ultimo_uso": ahora() - timedelta(minutes=settings.INACTIVITY_TIMEOUT_MINUTES + 1)})
    db.commit()
    r = client.get("/perfil", headers=doc)
    assert r.status_code == 401 and "inactividad" in r.json()["detail"]


def test_logout_invalida_el_token(client, doc):
    assert client.get("/perfil", headers=doc).status_code == 200
    assert client.post("/logout", headers=doc).status_code == 200
    assert client.get("/perfil", headers=doc).status_code == 401  # el mismo token ya no sirve


def test_rutas_de_admin_prohibidas_para_dermatologos(client, doc):
    for m, ruta in [("get", "/admin/usuarios"), ("get", "/admin/auditoria"), ("get", "/admin/suscripciones"),
                    ("get", "/admin/config-correo"), ("get", "/admin/sus"), ("get", "/admin/auditoria.csv")]:
        assert getattr(client, m)(ruta, headers=doc).status_code == 403, ruta
    assert client.post("/admin/recordatorios/ejecutar", headers=doc).status_code == 403


def test_rate_limit_en_login(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_MAX", 3)
    codigos = [client.post("/login", data={"username": "a@b.com", "password": "x"}).status_code for _ in range(5)]
    assert codigos[:3] == [401, 401, 401] and codigos[3:] == [429, 429]


# ------------------------------------------------------------------ recuperación de contraseña (punto 4)
@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(email_service, "enviar", lambda db, dest, codigo, ctx: enviados.append((dest, codigo, ctx)) or True)
    return enviados


def _token(correos):
    return correos[-1][2]["enlace"].split("token=")[1]


def test_recuperacion_completa_y_token_de_un_solo_uso(client, correos):
    crear_usuario(client)
    h_vieja = login(client)
    r = client.post("/recuperar-contrasena", json={"email": "doc1@example.com"})
    assert r.status_code == 200 and len(correos) == 1
    token = _token(correos)
    nueva = "NuevaClave#9876x"
    assert client.post("/restablecer-contrasena", json={"token": token, "password": nueva, "confirmar_password": nueva}).status_code == 200
    login(client, password=nueva)
    assert client.post("/login", data={"username": "doc1@example.com", "password": PASSWORD}).status_code == 401
    assert client.get("/perfil", headers=h_vieja).status_code == 401  # sesiones anteriores cerradas
    otra = "OtraClave#5555xx"  # el mismo enlace no se puede reutilizar
    assert client.post("/restablecer-contrasena", json={"token": token, "password": otra, "confirmar_password": otra}).status_code == 400


def test_token_de_recuperacion_vencido(client, correos, db):
    crear_usuario(client)
    client.post("/recuperar-contrasena", json={"email": "doc1@example.com"})
    db.query(TokenRestablecimiento).update({"expira_en": ahora() - timedelta(seconds=1)})
    db.commit()
    n = "NuevaClave#9876x"
    r = client.post("/restablecer-contrasena", json={"token": _token(correos), "password": n, "confirmar_password": n})
    assert r.status_code == 400 and "venció" in r.json()["detail"]


def test_token_de_recuperacion_invalido_y_politica_aplicada(client, correos):
    crear_usuario(client)
    n = "NuevaClave#9876x"
    assert client.post("/restablecer-contrasena", json={"token": "x" * 43, "password": n, "confirmar_password": n}).status_code == 400
    client.post("/recuperar-contrasena", json={"email": "doc1@example.com"})
    assert client.post("/restablecer-contrasena", json={"token": _token(correos), "password": "debil", "confirmar_password": "debil"}).status_code == 422


def test_recuperacion_no_revela_si_el_correo_existe(client, correos):
    crear_usuario(client)
    a = client.post("/recuperar-contrasena", json={"email": "doc1@example.com"})
    b = client.post("/recuperar-contrasena", json={"email": "fantasma@example.com"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert len(correos) == 1  # solo el existente recibió correo


def test_token_se_guarda_hasheado(client, correos, db):
    crear_usuario(client)
    client.post("/recuperar-contrasena", json={"email": "doc1@example.com"})
    assert _token(correos) not in [t.token_hash for t in db.query(TokenRestablecimiento).all()]


def test_cambiar_contrasena(client, doc):
    n = "CambioClave#2026x"
    assert client.post("/cambiar-contrasena", json={"password_actual": "incorrecta", "password": n, "confirmar_password": n}, headers=doc).status_code == 400
    assert client.post("/cambiar-contrasena", json={"password_actual": PASSWORD, "password": n, "confirmar_password": n}, headers=doc).status_code == 200
    login(client, password=n)
