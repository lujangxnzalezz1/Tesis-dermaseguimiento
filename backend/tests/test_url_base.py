"""Los enlaces (confirmación de correo, pago) usan la dirección de la solicitud solo si es local o privada."""
import pytest

from core.url_base import fijar_desde_solicitud, url_base


@pytest.mark.parametrize("host,esperado", [
    ("localhost:8000", "http://localhost:8000"),
    ("127.0.0.1:8000", "http://127.0.0.1:8000"),
    ("10.90.1.108:8000", "http://10.90.1.108:8000"),
    ("192.168.0.15:8000", "http://192.168.0.15:8000"),
    ("172.20.10.2:8000", "http://172.20.10.2:8000"),  # hotspot del iPhone
])
def test_hosts_confiables(host, esperado):
    fijar_desde_solicitud("http", host)
    assert url_base() == esperado


@pytest.mark.parametrize("host", ["sitio-malicioso.com", "evil.com:8000", "8.8.8.8:8000", "172.32.0.1:8000", None, "localhost.evil.com"])
def test_host_falsificado_usa_base_url(host):
    from core.config import settings
    fijar_desde_solicitud("http", host)
    assert url_base() == settings.BASE_URL.rstrip("/")


def test_enlace_de_pago_sigue_la_red(client, doc):
    r = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers={**doc, "Host": "192.168.1.50:8000"})
    assert r.json()["url_pago"].startswith("http://192.168.1.50:8000/pasarela-sandbox/")
    r = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_anual"}, headers={**doc, "Host": "evil.com"})
    assert "evil.com" not in r.json()["url_pago"]


def test_cors_permite_red_privada_y_rechaza_otros(client):
    ok = client.options("/planes", headers={"Origin": "http://10.90.1.108:8081", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://10.90.1.108:8081"
    no = client.options("/planes", headers={"Origin": "http://evil.com:8081", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in no.headers
