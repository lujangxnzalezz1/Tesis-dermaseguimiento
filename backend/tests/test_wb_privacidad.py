"""Consentimiento del profesional, baja de la cuenta, retención de datos y logs sin tokens."""
import logging
import os
from datetime import timedelta

from core.config import settings
from core.tiempo import ahora
from models.auditoria import Auditoria
from models.paciente import Paciente
from models.seguimiento import Seguimiento
from models.usuario import ConsentimientoUsuario, Sesion, Usuario
from scripts import retencion_datos
from services import almacenamiento, email_service
from tests.conftest import PASSWORD, archivos_seg, crear_paciente, crear_usuario, login


# ------------------------------------------------------------------ consentimiento y nueva versión de la política
def test_registro_guarda_consentimiento_con_finalidad(client, db):
    crear_usuario(client)
    u = db.query(Usuario).one()
    c = db.query(ConsentimientoUsuario).one()
    assert u.politica_finalidad == c.finalidad == "uso del sistema"
    assert c.version_politica == settings.POLITICA_VERSION and c.usuario_id == u.id and c.fecha


def test_version_nueva_exige_aceptar_al_ingresar(client, db, monkeypatch):
    crear_usuario(client)
    r = client.post("/login", data={"username": "doc1@example.com", "password": PASSWORD})
    assert r.json()["politica_pendiente"] is False
    monkeypatch.setattr(settings, "POLITICA_VERSION", "2.0")
    r = client.post("/login", data={"username": "doc1@example.com", "password": PASSWORD})
    assert r.json()["politica_pendiente"] is True and r.json()["politica_version"] == "2.0"
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get("/pacientes", headers=h)
    assert r.status_code == 403 and "Política de Privacidad" in r.json()["detail"]
    assert client.get("/perfil", headers=h).json()["politica_pendiente"] is True
    assert client.post("/aceptar-politica", json={"version": "2.0", "acepta": False}, headers=h).status_code == 422
    assert client.post("/aceptar-politica", json={"version": "1.0", "acepta": True}, headers=h).status_code == 409
    assert client.post("/aceptar-politica", json={"version": "2.0", "acepta": True}, headers=h).status_code == 200

    assert client.get("/pacientes", headers=h).status_code == 200
    versiones = [c.version_politica for c in db.query(ConsentimientoUsuario).order_by(ConsentimientoUsuario.id)]
    assert versiones == ["1.0", "2.0"]
    assert db.query(Auditoria).filter(Auditoria.accion == "aceptar_politica").count() == 1


def test_cuenta_sin_version_registrada_recibe_el_aviso_sin_bloqueo(client, admin):
    r = client.post("/login", data={"username": "admin@example.com", "password": PASSWORD})
    assert r.json()["politica_pendiente"] is True
    assert client.get("/admin/usuarios", headers=admin).status_code == 200


# ------------------------------------------------------------------ baja de la cuenta (retiro del consentimiento)
def test_baja_de_la_cuenta_anonimiza_y_revoca(client, db):
    crear_usuario(client)
    h = login(client)
    crear_paciente(client, h)
    assert client.post("/cuenta/eliminar", json={"password": PASSWORD}, headers=h).status_code == 400  # falta confirmar
    r = client.post("/cuenta/eliminar", json={"password": "Incorrecta#1", "confirmar": True}, headers=h)
    assert r.status_code == 400
    r = client.post("/cuenta/eliminar", json={"password": PASSWORD, "confirmar": True, "motivo": "Dejo de usarlo"}, headers=h)
    assert r.status_code == 200, r.text

    db.expire_all()
    u = db.query(Usuario).one()
    assert not u.activo and u.anonimizado_en and u.consentimiento_revocado_en
    assert u.email.endswith("@anonimizado.invalid") and u.nombre == "Usuario eliminado"
    assert db.query(ConsentimientoUsuario).filter(ConsentimientoUsuario.revocado_en.is_(None)).count() == 0
    assert all(s.revocada for s in db.query(Sesion).all())
    assert db.query(Paciente).one().activo is False  # la historia clínica se conserva, desactivada
    assert client.get("/perfil", headers=h).status_code == 401
    assert client.post("/login", data={"username": "doc1@example.com", "password": PASSWORD}).status_code == 401
    # la auditoría se conserva (incluido el evento de baja)
    assert db.query(Auditoria).filter(Auditoria.accion == "eliminar_cuenta", Auditoria.resultado == "exito").count() == 1
    assert db.query(Auditoria).filter(Auditoria.usuario_id == u.id).count() >= 3
    # el correo queda libre para una cuenta nueva
    crear_usuario(client)


def test_ultimo_admin_no_puede_darse_de_baja(client, admin):
    r = client.post("/cuenta/eliminar", json={"password": PASSWORD, "confirmar": True}, headers=admin)
    assert r.status_code == 409


# ------------------------------------------------------------------ retención de datos
def test_retencion_simula_por_defecto_y_aplica_con_bandera(client, db, pipeline_falso, monkeypatch):
    crear_usuario(client)
    h = login(client)
    viejo = crear_paciente(client, h, "1111111")
    reciente = crear_paciente(client, h, "2222222")
    for pid in (viejo["id"], reciente["id"]):
        r = client.post("/procesar-seguimiento", data={"paciente_id": str(pid)}, files=archivos_seg(), headers=h)
        assert r.status_code == 201, r.text
    hace_seis = ahora() - timedelta(days=365 * 6)
    db.query(Seguimiento).filter(Seguimiento.paciente_id == viejo["id"]).update({"fecha": hace_seis})
    db.query(Paciente).filter(Paciente.id == viejo["id"]).update({"fecha_creacion": hace_seis})
    db.commit()
    claves = [db.query(Seguimiento).filter(Seguimiento.paciente_id == viejo["id"]).one().ruta_imagen_alineada]
    assert os.path.exists(almacenamiento.ruta_absoluta(claves[0]))

    resumen = retencion_datos.main([])  # simulación: no cambia nada
    assert resumen["modo"] == "simulacion" and resumen["pacientes_anonimizados"] == 1 and resumen["imagenes_borradas"] >= 3
    db.expire_all()
    assert db.get(Paciente, viejo["id"]).nombre == "Ana"

    resumen = retencion_datos.main(["--aplicar"])
    assert resumen["pacientes_anonimizados"] == 1
    db.expire_all()
    p = db.get(Paciente, viejo["id"])
    assert p.cedula.startswith("anon-") and p.nombre == "Paciente" and p.telefono is None and not p.activo
    assert not os.path.exists(almacenamiento.ruta_absoluta(claves[0]))
    assert db.get(Paciente, reciente["id"]).nombre == "Ana"  # dentro del plazo: intacto
    assert retencion_datos.main(["--aplicar"])["pacientes_anonimizados"] == 0  # idempotente
    assert db.query(Auditoria).filter(Auditoria.accion == "retencion_datos").count() == 2


def test_retencion_anonimiza_cuentas_inactivas_viejas(client, db):
    crear_usuario(client)
    u = db.query(Usuario).one()
    u.activo = False
    u.fecha_inactivacion = ahora() - timedelta(days=365 * 6)
    db.commit()
    assert retencion_datos.ejecutar(db, aplicar=True)["usuarios_anonimizados"] == 1
    db.expire_all()
    assert db.query(Usuario).one().email.endswith("@anonimizado.invalid")


# ------------------------------------------------------------------ logs sin tokens
def test_log_de_correo_deshabilitado_enmascara_tokens(client, caplog):
    token = "AbCdEf" + "x" * 37
    with caplog.at_level(logging.WARNING, logger="correo"):
        from core.database import SessionLocal
        with SessionLocal() as s:
            email_service.enviar(s, "a@b.com", "restablecer_password",
                                 {"nombre": "Ana", "enlace": f"dermaseguimiento://restablecer?token={token}", "minutos": 10})
    texto = caplog.text
    assert token not in texto and "token=AbCdEf…[oculto]" in texto


def test_enmascarar_tokens_sueltos():
    assert email_service.enmascarar_tokens("código: Zx81Qa" + "k" * 30) == "código: Zx81Qa…[oculto]"
    assert email_service.enmascarar_tokens("Hola Ana, vale 10 minutos") == "Hola Ana, vale 10 minutos"


def test_flujo_de_recuperacion_no_deja_el_token_en_el_log(client, caplog):
    crear_usuario(client)
    with caplog.at_level(logging.WARNING, logger="correo"):
        client.post("/recuperar-contrasena", json={"email": "doc1@example.com"})
    linea = [r.getMessage() for r in caplog.records if r.name == "correo"][0]
    pista = linea.split("token=")[1].split()[0]
    assert pista.endswith("…[oculto]") and len(pista.split("…")[0]) == 6


def test_politica_sin_contacto_configurado(client, monkeypatch):
    monkeypatch.setattr(settings, "CONTACTO_PRIVACIDAD", "")
    texto = str(client.get("/politica-privacidad").json())
    assert "Mi cuenta" in texto and "gmail" not in texto
