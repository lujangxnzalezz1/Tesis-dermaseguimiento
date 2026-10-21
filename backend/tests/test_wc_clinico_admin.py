"""Reactivación de pacientes, plantillas (borrado lógico y título único), revocación de consentimiento con
motivo, pantalla administrativa (suscripciones paginadas en SQL, comprobantes, pacientes dados de baja) y
consultas por lotes (sin N+1)."""
from datetime import timedelta

import pytest
from sqlalchemy import event

from core.database import engine
from core.tiempo import ahora
from models.auditoria import Auditoria
from models.paciente import ConsentimientoPaciente, Paciente
from models.plantilla import PlantillaIndicacion
from models.suscripcion import Comprobante, Suscripcion
from tests.conftest import archivos_seg, crear_paciente, crear_usuario, login, pagar


class _ConAjuste:
    """Envuelve `settings` (pydantic no permite agregarle campos) para simular un ajuste todavía no declarado."""

    def __init__(self, base, **ajustes):
        self._base, self._ajustes = base, ajustes

    def __getattr__(self, nombre):
        return self._ajustes[nombre] if nombre in self._ajustes else getattr(self._base, nombre)


def _baja(client, headers, pid, motivo="Se mudó de ciudad"):
    r = client.request("DELETE", f"/pacientes/{pid}", json={"motivo": motivo, "confirmar": True}, headers=headers)
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ reactivación de pacientes

def test_dermatologo_reactiva_su_paciente_y_queda_auditado(client, doc, db):
    p = crear_paciente(client, doc)
    _baja(client, doc, p["id"])
    assert client.get("/pacientes?estado=inactivos", headers=doc).json()["items"][0]["motivo_eliminacion"] == "Se mudó de ciudad"
    assert client.post(f"/pacientes/{p['id']}/reactivar", json={}, headers=doc).status_code == 400  # falta confirmar
    r = client.post(f"/pacientes/{p['id']}/reactivar", json={"confirmar": True, "motivo": "Volvió a la consulta"}, headers=doc)
    assert r.status_code == 200 and r.json()["activo"] is True and r.json()["eliminado_en"] is None
    assert r.json()["version"] == p["version"] + 2  # baja + reactivación
    assert client.post(f"/pacientes/{p['id']}/reactivar", json={"confirmar": True}, headers=doc).status_code == 409
    evento = db.query(Auditoria).filter(Auditoria.accion == "reactivar", Auditoria.modulo == "pacientes").one()
    assert evento.entidad_id == str(p["id"]) and evento.detalle == "Volvió a la consulta"


def test_no_se_reactiva_paciente_ajeno(client, doc, doc2):
    p = crear_paciente(client, doc)
    _baja(client, doc, p["id"])
    assert client.post(f"/pacientes/{p['id']}/reactivar", json={"confirmar": True}, headers=doc2).status_code == 404


def test_registro_de_cedula_dada_de_baja_sugiere_reactivar(client, doc):
    p = crear_paciente(client, doc)
    _baja(client, doc, p["id"])
    r = client.post("/pacientes", json={"cedula": p["cedula"], "nombre": "Ana", "apellido": "Gómez", "consentimiento": {"acepta": True}}, headers=doc)
    assert r.status_code == 409 and "reactivarlo" in r.json()["detail"]


def test_admin_lista_y_reactiva_pacientes_dados_de_baja(client, admin, doc, db):
    p = crear_paciente(client, doc, antecedentes_medicos="Dato clínico privado")
    crear_paciente(client, doc, cedula="7654321")
    _baja(client, doc, p["id"])
    assert client.get("/admin/pacientes-baja", headers=doc).status_code == 403
    r = client.get("/admin/pacientes-baja", headers=admin).json()
    assert r["total"] == 1 and r["items"][0]["dermatologo"] == "doc1@example.com"
    assert "Dato clínico privado" not in str(r)  # el administrador no ve datos clínicos
    assert client.get("/admin/pacientes-baja?q=000", headers=admin).json()["total"] == 0
    assert client.post(f"/admin/pacientes/{p['id']}/reactivar", json={"confirmar": False}, headers=admin).status_code == 400
    assert client.post("/admin/pacientes/9999/reactivar", json={"confirmar": True}, headers=admin).status_code == 404
    assert client.post(f"/admin/pacientes/{p['id']}/reactivar", json={"confirmar": True, "motivo": "Pedido de la doctora"}, headers=admin).status_code == 200
    assert client.get(f"/pacientes/{p['id']}", headers=doc).json()["activo"] is True
    assert db.query(Auditoria).filter(Auditoria.accion == "reactivar", Auditoria.usuario_email == "admin@example.com").count() == 1


# ------------------------------------------------------------------ edición con bloqueo optimista

def test_edicion_con_version_vieja_da_409(client, doc):
    p = crear_paciente(client, doc)
    r = client.patch(f"/pacientes/{p['id']}", json={"version": p["version"], "telefono": "0981 123456"}, headers=doc)
    assert r.status_code == 200 and r.json()["version"] == p["version"] + 1
    r = client.patch(f"/pacientes/{p['id']}", json={"version": p["version"], "telefono": "0981 000000"}, headers=doc)
    assert r.status_code == 409 and "modificada" in r.json()["detail"]


# ------------------------------------------------------------------ consentimiento

def test_revocar_consentimiento_con_motivo(client, doc, db):
    p = crear_paciente(client, doc)
    r = client.post(f"/pacientes/{p['id']}/consentimiento/revocar", json={"motivo": "El paciente lo pidió por escrito"}, headers=doc)
    assert r.status_code == 200
    c = db.query(ConsentimientoPaciente).filter_by(paciente_id=p["id"]).one()
    assert c.revocado_en is not None and c.motivo_revocacion == "El paciente lo pidió por escrito"
    assert db.query(Auditoria).filter_by(accion="consentimiento_revocado").one().detalle == "El paciente lo pidió por escrito"
    assert client.post(f"/pacientes/{p['id']}/consentimiento", headers=doc).status_code == 200
    assert client.post(f"/pacientes/{p['id']}/consentimiento/revocar", json={"motivo": "<script>"}, headers=doc).status_code == 422


# ------------------------------------------------------------------ plantillas de indicaciones

def test_plantilla_borrado_logico_y_titulo_unico(client, doc, doc2, db):
    datos = {"titulo": "Acné leve", "texto": "Limpieza suave."}
    pid = client.post("/plantillas-indicaciones", json=datos, headers=doc).json()["id"]
    r = client.post("/plantillas-indicaciones", json={"titulo": "  acné LEVE ", "texto": "Otra"}, headers=doc)
    assert r.status_code == 409 and "Ya tenés una plantilla" in r.json()["detail"]
    assert client.post("/plantillas-indicaciones", json=datos, headers=doc2).status_code == 201  # otro profesional sí puede
    assert client.delete(f"/plantillas-indicaciones/{pid}", headers=doc).status_code == 204
    fila = db.get(PlantillaIndicacion, pid)
    assert fila is not None and fila.eliminada_en is not None  # no se borró de la base
    assert client.delete(f"/plantillas-indicaciones/{pid}", headers=doc).status_code == 404
    assert client.post("/plantillas-indicaciones", json=datos, headers=doc).status_code == 201  # el título vuelve a estar libre


def test_indice_unico_de_plantillas_en_la_base(db):
    from sqlalchemy.exc import IntegrityError
    db.add_all([PlantillaIndicacion(usuario_id=1, titulo="Rosácea", texto="a"), PlantillaIndicacion(usuario_id=1, titulo="ROSÁCEA".lower(), texto="b")])
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_maximo_de_plantillas_configurable(client, doc, monkeypatch):
    import routers.procesamiento as rp
    monkeypatch.setattr(rp, "settings", _ConAjuste(rp.settings, MAX_PLANTILLAS=2))
    for i in range(2):
        assert client.post("/plantillas-indicaciones", json={"titulo": f"P{i}", "texto": "x"}, headers=doc).status_code == 201
    r = client.post("/plantillas-indicaciones", json={"titulo": "P9", "texto": "x"}, headers=doc)
    assert r.status_code == 400 and "máximo de 2" in r.json()["detail"]


# ------------------------------------------------------------------ administración

def test_suscripciones_paginadas_en_sql(client, admin, db):
    for i in range(5):
        crear_usuario(client, f"doc{i}@example.com")
    uid_vencida = db.query(Suscripcion).order_by(Suscripcion.id).first().usuario_id
    db.query(Suscripcion).filter(Suscripcion.usuario_id == uid_vencida).update({"fecha_vencimiento": ahora() - timedelta(days=1)})
    db.commit()
    r = client.get("/admin/suscripciones?tamano=2&pagina=1", headers=admin).json()
    assert r["total"] == 5 and len(r["items"]) == 2 and r["resumen"]["vencida"] == 1  # se sincronizó el vencimiento
    assert sum(r["resumen"].values()) == 5
    ultima = client.get("/admin/suscripciones?tamano=2&pagina=3", headers=admin).json()
    assert len(ultima["items"]) == 1
    v = client.get("/admin/suscripciones?categoria=vencida", headers=admin).json()
    assert v["total"] == 1 and v["items"][0]["categoria"] == "vencida"
    assert client.get("/admin/suscripciones?q=doc3", headers=admin).json()["total"] == 1


def test_suscripcion_vencida_con_pago_pendiente(client, admin, doc, db):
    client.post("/suscripcion/checkout", json={"plan_codigo": "premium_mensual"}, headers=doc)
    db.query(Suscripcion).update({"estado": "vencida"})
    db.commit()
    r = client.get("/admin/suscripciones?categoria=pendiente_pago", headers=admin).json()
    assert r["total"] == 1 and r["resumen"]["pendiente_pago"] == 1


def test_comprobantes_para_anular(client, admin, doc, db):
    pagar(client, doc)
    r = client.get("/admin/comprobantes", headers=admin).json()
    assert r["total"] == 1
    cid = r["items"][0]["id"]
    assert client.post(f"/admin/comprobantes/{cid}/anular", json={"motivo": "Error en el nombre", "confirmar": True}, headers=admin).status_code == 200
    assert client.get("/admin/comprobantes?estado=anulado", headers=admin).json()["items"][0]["motivo_anulacion"] == "Error en el nombre"
    assert db.get(Comprobante, cid).estado == "anulado"


def test_csv_de_auditoria_respeta_el_maximo(client, admin, doc, monkeypatch):
    import routers.admin as ra
    for c in ("1111111", "2222222", "3333333"):
        crear_paciente(client, doc, cedula=c)
    monkeypatch.setattr(ra, "settings", _ConAjuste(ra.settings, MAX_FILAS_CSV=2))
    texto = client.get("/admin/auditoria.csv?modulo=pacientes", headers=admin).content.decode("utf-8-sig")
    assert "Total de registros;2" in texto


# ------------------------------------------------------------------ consultas por lotes

def _contar_consultas():
    contador = {"n": 0}

    def _antes(conn, cursor, sentencia, *a):
        contador["n"] += 1
    event.listen(engine, "before_cursor_execute", _antes)
    return contador, lambda: event.remove(engine, "before_cursor_execute", _antes)


def test_listado_de_pacientes_sin_n_mas_1(client, doc):
    for i in range(3):
        crear_paciente(client, doc, cedula=f"10000{i}")
    contador, quitar = _contar_consultas()
    client.get("/pacientes?tamano=3", headers=doc)
    pocos = contador["n"]
    for i in range(3, 10):
        crear_paciente(client, doc, cedula=f"10000{i}")
    contador["n"] = 0
    r = client.get("/pacientes?tamano=10", headers=doc).json()
    quitar()
    assert len(r["items"]) == 10 and all(p["tiene_consentimiento"] for p in r["items"])
    assert contador["n"] == pocos  # la cantidad de consultas no crece con la cantidad de pacientes


def test_archivos_se_encuentran_por_cualquier_ruta(client, doc, doc2, pipeline_falso):
    p = crear_paciente(client, doc)
    s = client.post("/procesar-seguimiento", data={"paciente_id": str(p["id"])}, files=archivos_seg(), headers=doc).json()
    for url in (s["url_imagen_referencia"], s["url_mapa_calor"], s["url_mapa_rojez"], s["url_mapa_luminosidad"]):
        assert client.get(url, headers=doc).status_code == 200
        assert client.get(url, headers=doc2).status_code == 404


def test_indices_nuevos_existen():
    from sqlalchemy import inspect
    insp = inspect(engine)
    indexados = lambda t: {c for ix in insp.get_indexes(t) for c in ix["column_names"] if c}  # noqa: E731
    assert {"usuario_id", "ruta_imagen_referencia", "ruta_mapa_luminosidad"} <= indexados("seguimientos")
    assert "revocado_en" in indexados("consentimientos")
    assert "usuario_email" in indexados("auditoria")
    assert Paciente.__table__.c.activo.index
