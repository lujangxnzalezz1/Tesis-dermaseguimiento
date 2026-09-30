"""Puente HTTPS → HTTP para la app web en desarrollo (solo red local).

Recibe conexiones seguras en 8443 y las reenvía tal cual al servidor de Expo (8081). Así el iPhone
abre la app por https y Safari habilita la cámara en vivo. Sin dependencias: solo la librería estándar.
"""
import asyncio
import os
import ssl
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
ORIGEN, DESTINO = int(sys.argv[1]) if len(sys.argv) > 1 else 8443, int(sys.argv[2]) if len(sys.argv) > 2 else 8081


async def _copiar(lector, escritor):
    try:
        while datos := await lector.read(65536):
            escritor.write(datos)
            await escritor.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        escritor.close()


async def _atender(lector_cliente, escritor_cliente):
    try:
        lector_srv, escritor_srv = await asyncio.open_connection("127.0.0.1", DESTINO)
    except OSError:
        escritor_cliente.close()
        return
    await asyncio.gather(_copiar(lector_cliente, escritor_srv), _copiar(lector_srv, escritor_cliente))


async def main():
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(os.path.join(DIR, "certs", "servidor.crt"), os.path.join(DIR, "certs", "servidor.key"))
    servidor = await asyncio.start_server(_atender, "0.0.0.0", ORIGEN, ssl=ctx)
    print(f"HTTPS {ORIGEN} → http://127.0.0.1:{DESTINO}", flush=True)
    async with servidor:
        await servidor.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
