"""Restauración de un respaldo hecho con scripts/respaldo.py, midiendo el tiempo que tarda (RTO).

    python -m scripts.restaurar respaldos/respaldo_20261021_020000 --dry-run   # verifica y muestra los pasos
    python -m scripts.restaurar respaldos/respaldo_20261021_020000 --si        # restaura de verdad

Pasos: 1) verifica el manifiesto (SHA-256 de cada archivo); 2) pg_restore --clean sobre DATABASE_URL;
3) reemplaza el directorio de imágenes (RUTA_ALMACENAMIENTO). Al final imprime el tiempo de cada paso y el
total, que sirve como medición del tiempo de recuperación ante un desastre.

ATENCIÓN: sobrescribe la base y las imágenes actuales. Detené la API antes de restaurar y, si es posible,
probalo primero sobre una base vacía (DATABASE_URL=postgresql://.../derma_prueba_restauracion).
Requiere `pg_restore` en el PATH.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time

from scripts.respaldo import configuracion, sha256, url_libpq


def verificar(carpeta: str) -> dict:
    ruta = os.path.join(carpeta, "manifiesto.json")
    if not os.path.isfile(ruta):
        raise SystemExit(f"No es un respaldo válido: falta {ruta}.")
    with open(ruta) as f:
        manifiesto = json.load(f)
    for nombre, info in manifiesto["archivos"].items():
        archivo = os.path.join(carpeta, nombre)
        if not os.path.isfile(archivo) or sha256(archivo) != info["sha256"]:
            raise SystemExit(f"El archivo {nombre} falta o está dañado (no coincide su SHA-256). No se restauró nada.")
    return manifiesto


def _extraer_seguro(tar: tarfile.TarFile, destino: str) -> None:
    """Extrae evitando rutas que salgan del destino (../ o absolutas)."""
    base = os.path.realpath(destino)
    for m in tar.getmembers():
        if not os.path.realpath(os.path.join(base, m.name)).startswith(base + os.sep):
            raise SystemExit(f"El archivo de imágenes contiene una ruta no permitida: {m.name}")
    tar.extractall(base, filter="data")


def restaurar(carpeta: str, incluir_imagenes: bool = True, dry_run: bool = False) -> dict[str, float]:
    tiempos: dict[str, float] = {}
    inicio = t = time.perf_counter()
    manifiesto = verificar(carpeta)
    tiempos["verificación"] = time.perf_counter() - t
    print(f"Respaldo del {manifiesto['fecha']} verificado ({len(manifiesto['archivos'])} archivos).")

    url, almacenamiento = configuracion()
    volcado = os.path.join(carpeta, "base.dump")
    comando = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges", "--single-transaction",
               f"--dbname={url_libpq(url)}", volcado]
    imagenes = os.path.join(carpeta, "imagenes.tar.gz")
    restaurar_imagenes = incluir_imagenes and os.path.isfile(imagenes)

    print("Base de datos: pg_restore --clean --single-transaction (la contraseña no se muestra)")
    if restaurar_imagenes:
        print(f"Imágenes: imagenes.tar.gz -> {almacenamiento}")
    if dry_run:
        print("[dry-run] No se modificó nada.")
    else:
        t = time.perf_counter()
        try:
            subprocess.run(comando, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise SystemExit(f"pg_restore falló (la base quedó como estaba gracias a --single-transaction): {e}")
        tiempos["base de datos"] = time.perf_counter() - t
        if restaurar_imagenes:
            t = time.perf_counter()
            padre = os.path.dirname(os.path.abspath(almacenamiento))
            temporal = os.path.join(padre, ".restauracion_tmp")
            shutil.rmtree(temporal, ignore_errors=True)
            os.makedirs(temporal)
            with tarfile.open(imagenes, "r:gz") as tar:
                _extraer_seguro(tar, temporal)
            # Se reemplaza recién cuando la extracción terminó bien
            shutil.rmtree(almacenamiento, ignore_errors=True)
            os.replace(os.path.join(temporal, "almacenamiento"), almacenamiento)
            shutil.rmtree(temporal, ignore_errors=True)
            tiempos["imágenes"] = time.perf_counter() - t

    tiempos["total"] = time.perf_counter() - inicio
    print("Tiempos:")
    for paso, seg in tiempos.items():
        print(f"  {paso:<15} {seg:8.2f} s")
    return tiempos


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Restaura un respaldo de DermaSeguimiento y mide el tiempo de recuperación.")
    p.add_argument("carpeta", help="Carpeta respaldo_AAAAMMDD_HHMMSS generada por scripts.respaldo")
    p.add_argument("--sin-imagenes", action="store_true", help="Restaura solo la base de datos")
    p.add_argument("--dry-run", action="store_true", help="Verifica el respaldo y muestra los pasos sin modificar nada")
    p.add_argument("--si", action="store_true", help="Confirma que se sobrescriben la base y las imágenes actuales")
    a = p.parse_args(argv)
    if not a.dry_run and not a.si:
        p.error("La restauración sobrescribe los datos actuales: agregá --si para confirmar o usá --dry-run.")
    restaurar(a.carpeta, incluir_imagenes=not a.sin_imagenes, dry_run=a.dry_run)


if __name__ == "__main__":
    main(sys.argv[1:])
