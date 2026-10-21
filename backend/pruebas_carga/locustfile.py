"""Prueba de carga de la API con Locust (no se ejecuta en CI: necesita un servidor levantado).

Escenario: cada usuario virtual inicia sesión una vez y después alterna entre listar sus pacientes,
buscar uno y consultar los planes, con pausas de 1 a 3 segundos (ritmo de uso de un consultorio).

Meta (RNF de rendimiento): 50 usuarios concurrentes con percentil 95 < 1 s y 0 % de errores en los
endpoints de consulta. El procesamiento de imágenes se mide aparte con scripts/medir_rnf.py.

Preparación (una sola vez, contra una base de PRUEBA, nunca la de producción):

    pip install locust==2.32.4
    python -m pruebas_carga.preparar_usuarios --cantidad 50     # crea carga01..carga50@example.com con pacientes

Ejecución sin interfaz (5 minutos, 50 usuarios, 5 nuevos por segundo), con reporte HTML:

    cd backend
    RATE_LIMIT_ENABLED=false uvicorn main:app --workers 4          # en otra terminal
    locust -f pruebas_carga/locustfile.py --host http://127.0.0.1:8000 \\
           --headless -u 50 -r 5 -t 5m --html pruebas_carga/reporte.html --csv pruebas_carga/resultado

Con interfaz web: `locust -f pruebas_carga/locustfile.py --host http://127.0.0.1:8000` y abrir http://localhost:8089.
El límite de intentos de login (RATE_LIMIT_*) debe estar desactivado en el servidor de prueba: si no, todas las
sesiones salen de la misma IP y se bloquean. Al terminar, el script marca la corrida como fallida si no se
cumple la meta (código de salida 1), para poder usarlo en una verificación automática.
"""
import os
import random

from locust import HttpUser, between, events, task

PASSWORD = os.environ.get("CARGA_PASSWORD", "Carga#2026segura")
CANTIDAD = int(os.environ.get("CARGA_USUARIOS", "50"))
META_P95_MS = float(os.environ.get("CARGA_META_P95_MS", "1000"))


class Dermatologo(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        email = f"carga{random.randint(1, CANTIDAD):02d}@example.com"
        with self.client.post("/login", data={"username": email, "password": PASSWORD}, name="/login", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"No se pudo iniciar sesión con {email} ({r.status_code}). ¿Corriste preparar_usuarios?")
                return
            self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task(5)
    def listar_pacientes(self):
        self.client.get("/pacientes?pagina=1&tamano=20", name="/pacientes")

    @task(2)
    def buscar_paciente(self):
        self.client.get(f"/pacientes?q={random.randint(1, 9)}", name="/pacientes?q=")

    @task(2)
    def ver_planes(self):
        self.client.get("/planes", name="/planes")

    @task(1)
    def ver_suscripcion(self):
        self.client.get("/suscripcion", name="/suscripcion")


@events.quitting.add_listener
def _verificar_meta(environment, **_):
    total = environment.stats.total
    p95 = total.get_response_time_percentile(0.95) or 0
    print(f"Solicitudes: {total.num_requests} · errores: {total.fail_ratio:.1%} · p95: {p95:.0f} ms (meta < {META_P95_MS:.0f} ms)")
    if total.fail_ratio > 0 or p95 >= META_P95_MS:
        environment.process_exit_code = 1
