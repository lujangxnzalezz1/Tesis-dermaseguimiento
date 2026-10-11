"""Notificaciones push con OneSignal: sin claves no se envía nada y un fallo no interrumpe la operación."""
import json

from core.config import settings
from services import push_service


def test_sin_claves_no_envia(monkeypatch):
    monkeypatch.setattr(settings, "ONESIGNAL_APP_ID", "")
    monkeypatch.setattr(settings, "ONESIGNAL_REST_API_KEY", "")
    llamado = []
    monkeypatch.setattr(push_service.urllib.request, "urlopen", lambda *a, **k: llamado.append(1))
    assert push_service.enviar(1, "Título", "Mensaje") is False
    assert not llamado


def test_envia_al_usuario_por_external_id(monkeypatch):
    monkeypatch.setattr(settings, "ONESIGNAL_APP_ID", "app-prueba")
    monkeypatch.setattr(settings, "ONESIGNAL_REST_API_KEY", "clave-prueba")
    enviado = {}

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def falso_urlopen(req, timeout):
        enviado["cuerpo"] = json.loads(req.data)
        enviado["auth"] = req.headers["Authorization"]
        return Resp()

    monkeypatch.setattr(push_service.urllib.request, "urlopen", falso_urlopen)
    assert push_service.enviar(42, "Pago recibido", "Tu plan está activo.") is True
    assert enviado["cuerpo"]["include_aliases"] == {"external_id": ["42"]}
    assert enviado["cuerpo"]["contents"]["es"] == "Tu plan está activo."
    assert enviado["auth"] == "Key clave-prueba"


def test_un_fallo_no_interrumpe(monkeypatch):
    monkeypatch.setattr(settings, "ONESIGNAL_APP_ID", "app-prueba")
    monkeypatch.setattr(settings, "ONESIGNAL_REST_API_KEY", "clave-prueba")

    def falla(*a, **k):
        raise OSError("sin conexión")

    monkeypatch.setattr(push_service.urllib.request, "urlopen", falla)
    assert push_service.enviar(1, "Título", "Mensaje") is False
