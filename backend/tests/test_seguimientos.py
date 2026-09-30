import os

import pytest

from core.config import settings
from models.seguimiento import Seguimiento
from models.suscripcion import Suscripcion
from tests.conftest import archivos_seg, crear_paciente, crear_usuario, imagen_jpg, login, pagar


def procesar(client, headers, pid, files=None, data=None):
    return client.post("/procesar-seguimiento", data=data or {"paciente_id": str(pid)}, files=files or archivos_seg(), headers=headers)


def test_procesamiento_exitoso_y_datos_guardados(client, doc, pipeline_falso, db):
    p = crear_paciente(client, doc)
    r = procesar(client, doc, p["id"])
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["tiempo_procesamiento_ms"] is not None and s["delta_e_promedio"] >= 0
    assert len(client.get(f"/pacientes/{p['id']}/seguimientos", headers=doc).json()) == 1
    fila = db.query(Seguimiento).one()
    # RNF-02: las claves de las imágenes son opacas (no incluyen el id del paciente ni su cédula)
    for ruta in (fila.ruta_imagen_referencia, fila.ruta_imagen_nueva, fila.ruta_imagen_alineada, fila.ruta_mapa_calor):
        assert ruta.startswith("imagenes/") and "1234567" not in ruta and f"/{p['id']}/" not in ruta
        assert os.path.exists(os.path.join(settings.RUTA_ALMACENAMIENTO, ruta))


def test_imagenes_no_son_publicas(client, doc, doc2, pipeline_falso):
    p = crear_paciente(client, doc)
    url = procesar(client, doc, p["id"]).json()["url_imagen_alineada"]
    assert client.get(url).status_code == 401                              # sin sesión
    assert client.get(url, headers=doc2).status_code == 404                # otro dermatólogo
    ok = client.get(url, headers=doc)
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/jpeg"
    for malo in ("/archivos/../.env", "/archivos/%2e%2e/%2e%2e/.env", "/archivos/imagenes/inexistente.jpg", "/archivos/main.py"):
        assert client.get(malo, headers=doc).status_code == 404, malo


def test_paciente_ajeno_o_inexistente(client, doc, doc2, pipeline_falso):
    p = crear_paciente(client, doc)
    assert procesar(client, doc2, p["id"]).status_code == 404
    assert procesar(client, doc, 99999).status_code == 404


def test_sin_consentimiento_no_procesa(client, doc, pipeline_falso):
    p = crear_paciente(client, doc)
    client.post(f"/pacientes/{p['id']}/consentimiento/revocar", headers=doc)
    r = procesar(client, doc, p["id"])
    assert r.status_code == 409 and "consentimiento" in r.json()["detail"]


@pytest.mark.parametrize("nombre,contenido,tipo,codigo", [
    ("virus.exe", b"MZ" + b"\x00" * 100, "application/octet-stream", 400),
    ("falsa.jpg", b"esto no es una imagen, solo texto", "image/jpeg", 400),          # extensión miente
    ("doc.pdf", b"%PDF-1.4 ...", "application/pdf", 400),
    ("vacia.jpg", b"", "image/jpeg", 400),
    ("rota.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 50, "image/jpeg", 400),               # firma JPEG pero dañada
    ("script.svg", b"<svg onload=alert(1)>", "image/svg+xml", 400),
])
def test_archivos_no_permitidos(client, doc, pipeline_falso, nombre, contenido, tipo, codigo):
    p = crear_paciente(client, doc)
    files = archivos_seg()
    files["imagen_nueva"] = (nombre, contenido, tipo)
    r = procesar(client, doc, p["id"], files=files)
    assert r.status_code == codigo, r.text
    assert client.get(f"/pacientes/{p['id']}/seguimientos", headers=doc).json() == []  # nada quedó guardado


def test_archivo_demasiado_grande(client, doc, pipeline_falso, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    p = crear_paciente(client, doc)
    files = archivos_seg()
    files["imagen_nueva"] = ("grande.jpg", b"\xff\xd8\xff" + b"\x00" * (2 * 1024 * 1024), "image/jpeg")
    r = procesar(client, doc, p["id"], files=files)
    assert r.status_code == 413 and "MB" in r.json()["detail"]


def test_misma_foto_dos_veces(client, doc, pipeline_falso):
    p = crear_paciente(client, doc)
    igual = imagen_jpg(5)
    files = {"imagen_referencia": ("a.jpg", igual, "image/jpeg"), "imagen_nueva": ("b.jpg", igual, "image/jpeg")}
    r = procesar(client, doc, p["id"], files=files)
    assert r.status_code == 400 and "misma foto" in r.json()["detail"]


def test_faltan_campos(client, doc, pipeline_falso):
    assert client.post("/procesar-seguimiento", data={"paciente_id": "1"}, headers=doc).status_code == 422
    assert client.post("/procesar-seguimiento", files=archivos_seg(), headers=doc).status_code == 422
    assert client.post("/procesar-seguimiento", data={"paciente_id": "abc"}, files=archivos_seg(), headers=doc).status_code == 422


def test_error_al_guardar_no_deja_nada_a_medias(client, doc, pipeline_falso, monkeypatch, db):
    p = crear_paciente(client, doc)
    llamadas = {"n": 0}
    real = __import__("services.almacenamiento", fromlist=["x"]).guardar_imagen

    def falla_en_la_tercera(img, clave):
        llamadas["n"] += 1
        if llamadas["n"] == 3:
            raise OSError("disco lleno /var/secreto/ruta")
        real(img, clave)

    monkeypatch.setattr("services.almacenamiento.guardar_imagen", falla_en_la_tercera)
    r = procesar(client, doc, p["id"])
    assert r.status_code == 500
    assert "disco" not in r.text and "/var/" not in r.text  # sin detalles técnicos al usuario
    assert db.query(Seguimiento).count() == 0
    huerfanas = [f for _, _, fs in os.walk(os.path.join(settings.RUTA_ALMACENAMIENTO, "imagenes")) for f in fs]
    assert huerfanas == []


def test_rostro_no_detectado_da_mensaje_claro(client, doc, monkeypatch):
    monkeypatch.setattr("routers.procesamiento.procesar_par_de_imagenes", lambda a, b: {"exito": False, "error": "No se detectó un rostro."})
    p = crear_paciente(client, doc)
    r = procesar(client, doc, p["id"])
    assert r.status_code == 422 and "rostro" in r.json()["detail"]


def test_procesamiento_exige_suscripcion_premium(client, doc, pipeline_falso, db):
    """RF-20: con la suscripción vencida se bloquea lo avanzado, pero se puede seguir consultando."""
    p = crear_paciente(client, doc)
    assert procesar(client, doc, p["id"]).status_code == 201       # período de prueba
    from core.tiempo import ahora
    from datetime import timedelta
    db.query(Suscripcion).update({"fecha_vencimiento": ahora() - timedelta(days=1)})
    db.commit()
    r = procesar(client, doc, p["id"], files=archivos_seg(3, 4))
    assert r.status_code == 402 and "suscripción" in r.json()["detail"]
    assert client.get("/pacientes", headers=doc).status_code == 200                      # consulta básica sigue
    assert client.get(f"/pacientes/{p['id']}/seguimientos", headers=doc).status_code == 200
    assert client.get(f"/pacientes/{p['id']}/reporte", headers=doc).status_code == 402
    info, resp = pagar(client, doc)                                                       # renueva y vuelve a funcionar
    assert resp.status_code == 200
    assert procesar(client, doc, p["id"], files=archivos_seg(3, 4)).status_code == 201


def test_reporte_de_evolucion_json_y_csv(client, doc, pipeline_falso):
    p = crear_paciente(client, doc)
    procesar(client, doc, p["id"], files=archivos_seg(1, 2))
    procesar(client, doc, p["id"], files=archivos_seg(3, 4))
    r = client.get(f"/pacientes/{p['id']}/reporte", headers=doc).json()
    assert r["total_consultas"] == 2 and len(r["serie"]) == 2
    csv = client.get(f"/pacientes/{p['id']}/reporte.csv", headers=doc)
    assert csv.status_code == 200 and csv.content.startswith(b"\xef\xbb\xbf")               # BOM: acentos correctos en Excel
    texto = csv.content.decode("utf-8-sig")
    assert "Evolución colorimétrica" in texto and "Delta E promedio" in texto and "Generado" in texto
    assert "Total de registros;2" in texto and 'attachment; filename="evolucion_ci1234567_' in csv.headers["content-disposition"]
    punto = client.get(f"/pacientes/{p['id']}/reporte.csv?decimal=punto", headers=doc).content.decode("utf-8-sig")
    assert "separador_decimal=punto" in punto
    assert client.get(f"/pacientes/{p['id']}/reporte.csv", headers={}).status_code == 401
