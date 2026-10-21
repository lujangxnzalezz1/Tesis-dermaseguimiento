"""Respaldo de la base de datos (pg_dump) y de las imágenes clínicas, con rotación por antigüedad.

    python -m scripts.respaldo                          # respaldo en ./respaldos, conserva 14 días
    python -m scripts.respaldo --destino /srv/respaldos --dias 30
    python -m scripts.respaldo --dry-run                # muestra lo que haría, sin ejecutar nada

Cada respaldo queda en una carpeta `respaldo_AAAAMMDD_HHMMSS/` con:
- `base.dump`: copia de PostgreSQL en formato personalizado (se restaura con pg_restore),
- `imagenes.tar.gz`: el directorio de almacenamiento de imágenes (RUTA_ALMACENAMIENTO),
- `manifiesto.json`: fecha, tamaños y SHA-256 de cada archivo (para verificar la copia).

Pensado para cron (por ejemplo, todos los días a las 2:00):

    0 2 * * *  cd /ruta/backend && ./venv/bin/python -m scripts.respaldo --destino /srv/respaldos >> /var/log/derma_respaldo.log 2>&1

Requiere `pg_dump` en el PATH (paquete postgresql-client, misma versión mayor que el servidor).
Los respaldos contienen datos de salud: guardalos cifrados y fuera del servidor (RNF-02).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timedelta

PATRON = re.compile(r"^respaldo_(\d{8}_\d{6})$")


def configuracion() -> tuple[str, str]:
    """DATABASE_URL y RUTA_ALMACENAMIENTO: del entorno o, si no están, de la configuración del backend (.env)."""
    url, ruta = os.environ.get("DATABASE_URL"), os.environ.get("RUTA_ALMACENAMIENTO")
    if not url or not ruta:
        from core.config import settings
        url, ruta = url or settings.DATABASE_URL, ruta or settings.RUTA_ALMACENAMIENTO
    return url, ruta


def url_libpq(url: str) -> str:
    """pg_dump no entiende el sufijo del controlador de SQLAlchemy (postgresql+psycopg2://)."""
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


def sha256(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def rotar(destino: str, dias: int, ahora: datetime, dry_run: bool) -> list[str]:
    """Borra los respaldos con más de `dias` días (según la fecha de su nombre). Devuelve los borrados."""
    limite = ahora - timedelta(days=dias)
    borrados = []
    if not os.path.isdir(destino):
        return borrados
    for nombre in sorted(os.listdir(destino)):
        m = PATRON.match(nombre)
        if m and datetime.strptime(m.group(1), "%Y%m%d_%H%M%S") < limite:
            borrados.append(nombre)
            if not dry_run:
                shutil.rmtree(os.path.join(destino, nombre), ignore_errors=True)
    return borrados


def respaldar(destino: str, dias: int, incluir_imagenes: bool = True, dry_run: bool = False, ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now()
    url, almacenamiento = configuracion()
    if not url.startswith("postgresql"):
        raise SystemExit("El respaldo con pg_dump requiere una base PostgreSQL (DATABASE_URL=postgresql://...).")
    carpeta = os.path.join(destino, f"respaldo_{ahora:%Y%m%d_%H%M%S}")
    volcado = os.path.join(carpeta, "base.dump")
    comando = ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", f"--file={volcado}", url_libpq(url)]

    print(f"Destino: {carpeta}")
    print("Base de datos: pg_dump --format=custom (la contraseña no se muestra)")
    if incluir_imagenes:
        print(f"Imágenes: {almacenamiento} -> imagenes.tar.gz")
    if dry_run:
        print("[dry-run] No se ejecutó nada.")
    else:
        if os.path.exists(carpeta):
            raise SystemExit(f"Ya existe {carpeta}: esperá un segundo y volvé a intentar.")
        os.makedirs(carpeta)
        try:
            subprocess.run(comando, check=True)
            if incluir_imagenes and os.path.isdir(almacenamiento):
                with tarfile.open(os.path.join(carpeta, "imagenes.tar.gz"), "w:gz") as tar:
                    tar.add(almacenamiento, arcname="almacenamiento")
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            shutil.rmtree(carpeta, ignore_errors=True)  # nunca dejar un respaldo a medias que parezca válido
            raise SystemExit(f"El respaldo falló y se descartó: {e}")
        archivos = {n: {"bytes": os.path.getsize(os.path.join(carpeta, n)), "sha256": sha256(os.path.join(carpeta, n))}
                    for n in sorted(os.listdir(carpeta)) if n != "manifiesto.json"}
        with open(os.path.join(carpeta, "manifiesto.json"), "w") as f:
            json.dump({"fecha": ahora.isoformat(timespec="seconds"), "incluye_imagenes": incluir_imagenes, "archivos": archivos}, f, indent=2)
        total = sum(a["bytes"] for a in archivos.values())
        print(f"Respaldo completo: {len(archivos)} archivos, {total / 1_048_576:.1f} MB")

    borrados = rotar(destino, dias, ahora, dry_run)
    if borrados:
        print(("[dry-run] Se borrarían" if dry_run else "Respaldos borrados") + f" (más de {dias} días): {', '.join(borrados)}")
    return carpeta


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Respaldo de la base y de las imágenes de DermaSeguimiento.")
    p.add_argument("--destino", default=os.environ.get("RESPALDO_DIR", "respaldos"), help="Carpeta donde se guardan los respaldos")
    p.add_argument("--dias", type=int, default=int(os.environ.get("RESPALDO_DIAS", "14")), help="Días que se conservan (rotación)")
    p.add_argument("--sin-imagenes", action="store_true", help="Respalda solo la base de datos")
    p.add_argument("--dry-run", action="store_true", help="Muestra lo que haría sin ejecutar nada")
    a = p.parse_args(argv)
    if a.dias < 1:
        p.error("--dias debe ser 1 o más.")
    respaldar(a.destino, a.dias, incluir_imagenes=not a.sin_imagenes, dry_run=a.dry_run)


if __name__ == "__main__":
    main(sys.argv[1:])
