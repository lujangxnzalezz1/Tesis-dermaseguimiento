"""Registro en una sola transacción, una suscripción por usuario y a lo sumo un pago pendiente por plan."""
import pytest
from sqlalchemy.exc import IntegrityError

from tests.conftest import datos_registro
from models.suscripcion import PAGO_PENDIENTE, Pago, Suscripcion
from models.usuario import Usuario
from routers import auth as auth_router


def test_si_falla_la_suscripcion_no_queda_el_usuario_a_medias(client, db, monkeypatch):
    def falla(*a, **k):
        raise RuntimeError("falla simulada al crear la suscripción")

    monkeypatch.setattr(auth_router, "asegurar_suscripcion", falla)
    try:
        r = client.post("/registro", json=datos_registro(email="medias@example.com"))
        assert r.status_code == 500
    except RuntimeError:
        pass
    db.expire_all()
    assert db.query(Usuario).filter(Usuario.email == "medias@example.com").count() == 0


def test_registro_crea_usuario_y_suscripcion_juntos(client, db):
    r = client.post("/registro", json=datos_registro(email="juntos@example.com"))
    assert r.status_code == 201
    u = db.query(Usuario).filter(Usuario.email == "juntos@example.com").one()
    assert db.query(Suscripcion).filter(Suscripcion.usuario_id == u.id).count() == 1


def test_una_sola_suscripcion_por_usuario(client, doc, db):
    s = db.query(Suscripcion).one()
    db.add(Suscripcion(usuario_id=s.usuario_id, plan_id=s.plan_id, estado=s.estado, fecha_inicio=s.fecha_inicio))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_no_puede_haber_dos_pagos_pendientes_del_mismo_plan(client, doc, db):
    info = client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc).json()
    p = db.get(Pago, info["pago_id"])
    # Simula un segundo checkout que llegó al mismo tiempo y no vio el primero
    db.add(Pago(usuario_id=p.usuario_id, suscripcion_id=p.suscripcion_id, plan_id=p.plan_id, tipo=p.tipo,
                monto=p.monto, moneda=p.moneda, estado=PAGO_PENDIENTE, proveedor=p.proveedor,
                referencia_externa=p.referencia_externa + "-b"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_correo_invalido_responde_en_espanol(client):
    r = client.post("/registro", json=datos_registro(email="dra@consultorio.test"))
    assert r.status_code == 422
    detalle = r.json()["detail"]
    assert "correo" in detalle and "email address" not in detalle
    r = client.post("/registro", json=datos_registro(email="sin-arroba"))
    assert r.status_code == 422 and "not a valid" not in r.json()["detail"]
