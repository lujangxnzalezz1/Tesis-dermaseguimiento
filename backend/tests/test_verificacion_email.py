"""Validación de que el correo existe: dominio con registros de correo (DNS/MX) y confirmación por enlace."""
import pytest
from email_validator import EmailNotValidError

from core.config import settings
from models.usuario import Usuario
from services import email_service
from tests.conftest import PASSWORD, datos_registro


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(email_service, "enviar", lambda db, dest, codigo, ctx: enviados.append((dest, codigo, ctx)) or True)
    monkeypatch.setattr(settings, "VERIFICAR_EMAIL_REGISTRO", True)
    return enviados


def _token(correos, codigo="verificar_email"):
    return [c for c in correos if c[1] == codigo][-1][2]["enlace"].split("token=")[1]


def _login(client, email="doc1@example.com", password=PASSWORD):
    return client.post("/login", data={"username": email, "password": password})


def test_cuenta_nueva_no_ingresa_hasta_confirmar(client, correos, db):
    r = client.post("/registro", json=datos_registro())
    assert r.status_code == 201 and r.json()["email_verificado"] is False
    assert correos[0][0] == "doc1@example.com" and correos[0][1] == "verificar_email"
    r = _login(client)
    assert r.status_code == 403 and "confirmaste tu correo" in r.json()["detail"]
    # abrir el enlace del correo
    pagina = client.get(f"/verificar-correo?token={_token(correos)}")
    assert pagina.status_code == 200 and "Correo confirmado" in pagina.text
    assert _login(client).status_code == 200
    u = db.query(Usuario).one()
    assert u.email_verificado is True and u.email_verificado_en is not None


def test_enlace_de_un_solo_uso_y_con_vencimiento(client, correos, db):
    from datetime import timedelta
    from core.tiempo import ahora
    from models.usuario import TokenRestablecimiento
    client.post("/registro", json=datos_registro())
    t = _token(correos)
    assert "Correo confirmado" in client.get(f"/verificar-correo?token={t}").text
    assert "no es válido" in client.get(f"/verificar-correo?token={t}").text  # segunda vez
    # vencido
    client.post("/registro", json=datos_registro("doc2@example.com"))
    db.query(TokenRestablecimiento).update({"expira_en": ahora() - timedelta(seconds=1)})
    db.commit()
    assert "no es válido" in client.get(f"/verificar-correo?token={_token(correos)}").text
    assert _login(client, "doc2@example.com").status_code == 403
    assert client.get("/verificar-correo?token=" + "x" * 43).status_code == 200  # token falso: página de error, sin 500


def test_reenviar_invalida_el_enlace_anterior(client, correos):
    client.post("/registro", json=datos_registro())
    viejo = _token(correos)
    a = client.post("/reenviar-verificacion", json={"email": "doc1@example.com"})
    b = client.post("/reenviar-verificacion", json={"email": "nadie@example.com"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()  # no revela qué correos existen
    nuevo = _token(correos)
    assert nuevo != viejo
    assert "no es válido" in client.get(f"/verificar-correo?token={viejo}").text
    assert "Correo confirmado" in client.get(f"/verificar-correo?token={nuevo}").text


def test_token_de_verificacion_no_sirve_para_cambiar_la_contrasena(client, correos):
    client.post("/registro", json=datos_registro())
    n = "Robada#Clave2026"
    r = client.post("/restablecer-contrasena", json={"token": _token(correos), "password": n, "confirmar_password": n})
    assert r.status_code == 400


def test_recuperar_contrasena_tambien_confirma_el_correo(client, correos):
    client.post("/registro", json=datos_registro())
    client.post("/recuperar-contrasena", json={"email": "doc1@example.com"})
    n = "NuevaClave#9876x"
    t = _token(correos, "restablecer_password")
    assert client.post("/restablecer-contrasena", json={"token": t, "password": n, "confirmar_password": n}).status_code == 200
    assert _login(client, password=n).status_code == 200


def test_cuentas_existentes_quedan_verificadas(client, db, monkeypatch):
    monkeypatch.setattr(settings, "VERIFICAR_EMAIL_REGISTRO", False)
    client.post("/registro", json=datos_registro())
    assert db.query(Usuario).one().email_verificado is True and _login(client).status_code == 200


# ------------------------------------------------------------------ dominio (DNS / MX), simulado para no depender de internet
def test_rechaza_dominios_que_no_reciben_correo(client, monkeypatch):
    monkeypatch.setattr(settings, "VERIFICAR_DOMINIO_EMAIL", True)

    def falso(email, check_deliverability=False):
        if email.endswith("@gmial.con"):
            raise EmailNotValidError("The domain name gmial.con does not exist.")

    monkeypatch.setattr("schemas.usuario.validate_email", falso)
    r = client.post("/registro", json=datos_registro("alguien@gmial.con"))
    assert r.status_code == 422 and "dominio del correo no existe" in r.json()["detail"]
    assert client.post("/registro", json=datos_registro("alguien@example.com")).status_code == 201


def test_si_el_dns_no_responde_no_bloquea_el_registro(client, monkeypatch):
    monkeypatch.setattr(settings, "VERIFICAR_DOMINIO_EMAIL", True)

    def caido(email, check_deliverability=False):
        raise TimeoutError("DNS sin respuesta")

    monkeypatch.setattr("schemas.usuario.validate_email", caido)
    assert client.post("/registro", json=datos_registro()).status_code == 201
