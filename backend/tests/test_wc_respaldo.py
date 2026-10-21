"""Scripts de respaldo y restauración: rotación, modo de prueba y verificación del manifiesto (sin PostgreSQL)."""
import json
import os
from datetime import datetime

import pytest

from scripts import respaldo, restaurar


def test_url_sin_controlador_para_pg_dump():
    assert respaldo.url_libpq("postgresql+psycopg2://u:c@h:5432/db") == "postgresql://u:c@h:5432/db"
    assert respaldo.url_libpq("postgresql://u@h/db") == "postgresql://u@h/db"


def test_rotacion_borra_solo_los_viejos(tmp_path):
    for n in ("respaldo_20261001_020000", "respaldo_20261020_020000", "otra_carpeta"):
        (tmp_path / n).mkdir()
    ahora = datetime(2026, 10, 21, 3, 0, 0)
    assert respaldo.rotar(str(tmp_path), 14, ahora, dry_run=True) == ["respaldo_20261001_020000"]
    assert (tmp_path / "respaldo_20261001_020000").exists()  # dry-run no borra
    respaldo.rotar(str(tmp_path), 14, ahora, dry_run=False)
    assert sorted(os.listdir(tmp_path)) == ["otra_carpeta", "respaldo_20261020_020000"]


def test_respaldo_dry_run_no_crea_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@localhost/db")
    carpeta = respaldo.respaldar(str(tmp_path / "r"), 7, dry_run=True)
    assert not os.path.exists(carpeta)


def test_respaldo_exige_postgresql(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    with pytest.raises(SystemExit):
        respaldo.respaldar(str(tmp_path), 7)


def test_restaurar_rechaza_respaldo_danado(tmp_path):
    (tmp_path / "base.dump").write_bytes(b"original")
    (tmp_path / "manifiesto.json").write_text(json.dumps({"fecha": "2026-10-21T02:00:00", "archivos": {
        "base.dump": {"bytes": 8, "sha256": respaldo.sha256(str(tmp_path / "base.dump"))}}}))
    assert restaurar.verificar(str(tmp_path))["fecha"].startswith("2026")
    (tmp_path / "base.dump").write_bytes(b"alterado")
    with pytest.raises(SystemExit):
        restaurar.verificar(str(tmp_path))


def test_restaurar_pide_confirmacion():
    with pytest.raises(SystemExit):
        restaurar.main(["respaldos/respaldo_20261021_020000"])
