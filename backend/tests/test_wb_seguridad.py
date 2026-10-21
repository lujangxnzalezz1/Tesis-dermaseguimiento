"""CAPTCHA, límite de frecuencia persistente e IP real detrás de proxies."""
import io
import json
import urllib.parse

import pytest
from starlette.requests import Request

from core import captcha, ratelimit
from core.config import settings
from core.security import ip_cliente
from models.auditoria import Auditoria
from models.configuracion import IntentoLimitado
from tests.conftest import PASSWORD, crear_usuario, datos_registro


# ------------------------------------------------------------------ CAPTCHA
class _RespuestaFalsa(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def proveedor(monkeypatch):
    """Activa el CAPTCHA y simula la llamada HTTP al proveedor: acepta solo el token «valido»."""
    monkeypatch.setattr(settings, "CAPTCHA_SECRET", "secreto-captcha-de-prueba")
    monkeypatch.setattr(settings, "CAPTCHA_SITE_KEY", "clave-publica")
    monkeypatch.setattr(settings, "CAPTCHA_PROVIDER", "turnstile")
    llamadas = []

    def urlopen(req, timeout=None):
        datos = dict(urllib.parse.parse_qsl(req.data.decode()))
        llamadas.append((req.full_url, datos))
        return _RespuestaFalsa(json.dumps({"success": datos["response"] == "valido", "error-codes": []}).encode())

    monkeypatch.setattr(captcha.urllib.request, "urlopen", urlopen)
    return llamadas


def _login(client, token=None, email="doc1@example.com", password=PASSWORD):
    datos = {"username": email, "password": password}
    if token:
        datos["captcha_token"] = token
    return client.post("/login", data=datos)


def test_captcha_desactivado_sin_secreto(client):
    assert settings.CAPTCHA_SECRET == ""
    crear_usuario(client)  # sin token
    assert _login(client).status_code == 200
    assert client.get("/config-publica").json()["captcha"]["activo"] is False


def test_captcha_rechaza_sin_token_o_invalido_y_audita(client, proveedor, db):
    r = client.post("/registro", json=datos_registro())
    assert r.status_code == 400 and "CAPTCHA" in r.json()["detail"]
    r = client.post("/registro", json=datos_registro(captcha_token="falso"))
    assert r.status_code == 400 and "falló" in r.json()["detail"]
    assert _login(client).status_code == 400
    assert _login(client, "falso").status_code == 400
    for ruta, cuerpo in [("/recuperar-contrasena", {"email": "a@b.com"}), ("/reenviar-verificacion", {"email": "a@b.com"}),
                         ("/restablecer-contrasena", {"token": "x" * 43, "password": "NuevaClave#9876x", "confirmar_password": "NuevaClave#9876x"})]:
        assert client.post(ruta, json=cuerpo).status_code == 400, ruta
    fallos = db.query(Auditoria).filter(Auditoria.modulo == "seguridad", Auditoria.accion == "captcha").all()
    assert len(fallos) == 7 and all(f.resultado == "fallo" for f in fallos)


def test_captcha_acepta_token_valido(client, proveedor):
    r = client.post("/registro", json=datos_registro(captcha_token="valido"))
    assert r.status_code == 201, r.text
    assert _login(client, "valido").status_code == 200
    assert client.post("/recuperar-contrasena", json={"email": "doc1@example.com", "captcha_token": "valido"}).status_code == 200
    url, datos = proveedor[0]
    assert url == captcha.URLS_VERIFICACION["turnstile"] and datos["secret"] == "secreto-captcha-de-prueba"
    publica = client.get("/config-publica").json()["captcha"]
    assert publica == {"activo": True, "proveedor": "turnstile", "site_key": "clave-publica", "eximir_app_nativa": False}
    assert "secreto" not in json.dumps(publica)


def test_captcha_otros_proveedores_y_puntaje_recaptcha_v3(client, monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_SECRET", "s")
    monkeypatch.setattr(settings, "CAPTCHA_PROVIDER", "recaptcha")
    urls = []

    def urlopen(req, timeout=None):
        urls.append(req.full_url)
        return _RespuestaFalsa(json.dumps({"success": True, "score": 0.1}).encode())

    monkeypatch.setattr(captcha.urllib.request, "urlopen", urlopen)
    assert _login(client, "t").status_code == 400  # puntaje bajo = probable robot
    assert urls[-1] == captcha.URLS_VERIFICACION["recaptcha"]
    monkeypatch.setattr(settings, "CAPTCHA_PROVIDER", "hcaptcha")
    _login(client, "t")
    assert urls[-1] == captcha.URLS_VERIFICACION["hcaptcha"]


def test_captcha_proveedor_caido_responde_503(client, monkeypatch):
    monkeypatch.setattr(settings, "CAPTCHA_SECRET", "s")

    def caido(req, timeout=None):
        raise OSError("sin red")

    monkeypatch.setattr(captcha.urllib.request, "urlopen", caido)
    assert _login(client, "t").status_code == 503


def test_app_nativa_eximida_solo_si_la_configuracion_lo_permite(client, proveedor, monkeypatch):
    cab = {"X-Cliente": "app-nativa"}
    assert client.post("/registro", json=datos_registro(), headers=cab).status_code == 400
    monkeypatch.setattr(settings, "CAPTCHA_EXIMIR_APP_NATIVA", True)
    assert client.post("/registro", json=datos_registro(), headers=cab).status_code == 201
    assert client.post("/registro", json=datos_registro("otro@example.com")).status_code == 400  # web sigue exigiéndolo


# ------------------------------------------------------------------ límite de frecuencia
@pytest.fixture
def limite(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_MAX", 3)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "base")


def test_login_cuenta_solo_intentos_fallidos(client, limite, db):
    crear_usuario(client)
    for _ in range(5):  # los ingresos correctos no consumen el cupo
        assert _login(client).status_code == 200
    codigos = [_login(client, password="Incorrecta#1").status_code for _ in range(4)]
    assert codigos == [401, 401, 401, 429]
    assert _login(client).status_code == 429  # ni la correcta, hasta que pase la ventana
    assert db.query(IntentoLimitado).filter(IntentoLimitado.clave.like("login:%")).count() == 3
    rechazos = db.query(Auditoria).filter(Auditoria.accion == "limite_frecuencia").all()
    assert len(rechazos) == 2 and "login" in rechazos[0].detalle


def test_limite_en_la_base_sobrevive_al_reinicio_del_proceso(client, limite):
    for _ in range(3):
        _login(client, email="a@b.com", password="x")
    ratelimit.reiniciar()  # equivale a otro proceso / reinicio: el contador en memoria se pierde
    assert _login(client, email="a@b.com", password="x").status_code == 429


def test_limite_en_memoria_como_alternativa(client, limite, monkeypatch, db):
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "memoria")
    codigos = [_login(client, email="a@b.com", password="x").status_code for _ in range(4)]
    assert codigos == [401, 401, 401, 429]
    assert db.query(IntentoLimitado).count() == 0


def test_limite_en_registro(client, limite):
    codigos = [client.post("/registro", json=datos_registro(f"doc{i}@example.com")).status_code for i in range(4)]
    assert codigos == [201, 201, 201, 429]


def test_limite_en_recuperar_contrasena(client, limite):
    codigos = [client.post("/recuperar-contrasena", json={"email": "a@b.com"}).status_code for _ in range(6)]
    assert codigos == [200] * 5 + [429]  # este endpoint tiene su propio máximo (5 por minuto)


def test_retry_after_en_429(client, limite):
    for _ in range(3):
        _login(client, email="a@b.com", password="x")
    r = _login(client, email="a@b.com", password="x")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


# ------------------------------------------------------------------ IP real y proxies de confianza
def _request(cliente="10.0.0.5", cabeceras=None):
    cabeceras = [(k.lower().encode(), v.encode()) for k, v in (cabeceras or {}).items()]
    return Request({"type": "http", "headers": cabeceras, "client": (cliente, 1234), "method": "GET", "path": "/"})


def test_ip_ignora_cabeceras_si_no_hay_proxies_de_confianza(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "")
    assert ip_cliente(_request("10.0.0.5", {"X-Forwarded-For": "1.2.3.4"})) == "10.0.0.5"


def test_ip_desde_proxy_de_confianza(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "10.0.0.0/24, 127.0.0.1")
    # el cliente puede inventar la primera IP; se toma la última que no es un proxy propio
    assert ip_cliente(_request("10.0.0.5", {"X-Forwarded-For": "6.6.6.6, 1.2.3.4, 10.0.0.9"})) == "1.2.3.4"
    assert ip_cliente(_request("127.0.0.1", {"X-Real-IP": "5.5.5.5"})) == "5.5.5.5"
    assert ip_cliente(_request("8.8.8.8", {"X-Forwarded-For": "1.2.3.4"})) == "8.8.8.8"  # no es proxy propio


def test_limite_por_ip_real_detras_del_proxy(client, limite, monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "testclient")  # entrada inválida: se ignora sin romper
    for _ in range(3):
        client.post("/login", data={"username": "a@b.com", "password": "x"}, headers={"X-Forwarded-For": "1.1.1.1"})
    # sin proxy de confianza, cambiar la cabecera no permite saltarse el límite
    r = client.post("/login", data={"username": "a@b.com", "password": "x"}, headers={"X-Forwarded-For": "2.2.2.2"})
    assert r.status_code == 429


def test_login_rechaza_usuario_demasiado_largo(client):
    r = client.post("/login", data={"username": "a" * 300 + "@b.com", "password": "x"})
    assert r.status_code == 422
