# Facial Traceability

![Estado](https://img.shields.io/badge/Estado-En%20desarrollo-yellow)
![Python](https://img.shields.io/badge/Python-3.12.7-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18.3-blue)

## Descripción

API backend desarrollada como proyecto final de la carrera de Ingeniería 
Informática de la Universidad de la Integración de las Américas (UNIDA).

El sistema permite la trazabilidad del cuidado dermatológico facial en 
consultorios independientes de Asunción, Paraguay, mediante normalización 
geométrica automática de fotografías clínicas y análisis colorimétrico 
cuantitativo con OpenCV y MediaPipe.

## Autora

**Luján Esmeralda González López**
Matrícula N.º 2020101109
Ingeniería Informática — UNIDA
📧 lujangxnzalezz1@gmail.com

## Tutores

- Ing. Lucía Caballero
- Dr. Ariel Pedrozo
- Mg. Laura Salinas

## Tecnologías

| Componente | Tecnología | Versión |
|------------|------------|---------|
| Backend | Python + FastAPI | 3.12.7 / 0.115 |
| Base de datos | PostgreSQL | 18.3 |
| Procesamiento de imágenes | OpenCV + MediaPipe | 4.x / 0.10.x |
| Almacenamiento de imágenes | MinIO | Latest |
| Aplicación móvil | React Native | Latest LTS |
| Contenedores | Docker | Latest |
| Control de versiones | Git + GitHub | 2.54.0 |

## Estructura del proyecto

```
proyectoDeTesis/
├── backend/                  API FastAPI
│   ├── main.py               arranque, manejo global de errores, cabeceras de seguridad
│   ├── core/                 configuración (.env), seguridad/sesiones, política de contraseñas, límites, errores
│   ├── models/               tablas (usuarios, pacientes, seguimientos, auditoría, suscripciones, pagos…)
│   ├── schemas/              validación de entrada/salida (Pydantic)
│   ├── routers/              endpoints (auth, pacientes, procesamiento, suscripciones, admin, privacidad…)
│   ├── services/             lógica de negocio (imágenes, colorimetría, suscripciones, pasarela, correo, auditoría)
│   ├── migrations/           migraciones Alembic (esquema versionado)
│   ├── scripts/              seed (datos iniciales), recordatorios de vencimiento, medición de RNF-06
│   └── tests/                pruebas automáticas (pytest)
├── dermaseguimiento/         App móvil (React Native + Expo Router)
└── docker-compose.yml        Base de datos + API en contenedores
```

## Instalación y configuración

### Requisitos previos

| Herramienta | Versión usada |
|---|---|
| Python | 3.12 |
| PostgreSQL | 16 o superior |
| Node.js / npm | 20+ (para la app móvil) |
| Git | 2.x |

### Backend

```bash
git clone https://github.com/lujangxnzalezz1/facial-traceability-api.git
cd facial-traceability-api/backend
python3.12 -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

**1. Crear la base de datos**

```bash
createdb dermaseguimiento
```

**2. Variables de entorno** (nada sensible se guarda en el código)

```bash
cp .env.example .env
```

Completar en `.env`: `DATABASE_URL`, `SECRET_KEY` (generar con `python -c "import secrets; print(secrets.token_urlsafe(48))"`),
`PASARELA_WEBHOOK_SECRET` (idem), `ADMIN_EMAIL` y `ADMIN_PASSWORD` (debe cumplir la política de contraseñas).
Todos los parámetros (expiración de sesión, inactividad, política de contraseñas, intentos de login, tamaño máximo de fotos,
días de prueba, avisos de vencimiento…) están documentados en `.env.example` y en `core/config.py`.

**3. Crear las tablas y los datos iniciales**

```bash
alembic upgrade head        # crea/actualiza el esquema (migraciones versionadas)
python -m scripts.seed      # planes, plantillas de correo y usuario administrador (se puede repetir sin problema)
```

Si ya tenías una base creada antes de existir las migraciones: `alembic stamp 0001` y luego `alembic upgrade head`.

**4. Iniciar el servidor**

```bash
uvicorn main:app --reload
```

- Documentación interactiva: http://127.0.0.1:8000/docs
- Chequeo de disponibilidad: http://127.0.0.1:8000/salud

**5. Pruebas automáticas**

```bash
pytest
```

### App móvil

```bash
cd dermaseguimiento
npm install
cp .env.example .env      # EXPO_PUBLIC_API_URL: dirección del backend (ver comentarios del archivo)
npx expo start
```

### Contenedores (opcional)

```bash
cp backend/.env.example backend/.env       # completar SECRET_KEY, PASARELA_WEBHOOK_SECRET, ADMIN_*
POSTGRES_PASSWORD=una-clave-fuerte docker compose up --build
```

### Usuarios iniciales

El administrador se crea con `ADMIN_EMAIL` / `ADMIN_PASSWORD` al ejecutar el seed. Los dermatólogos se registran desde la app;
cada uno recibe automáticamente un período de prueba (`TRIAL_DAYS`).

### Pagos (entorno de pruebas)

`PASARELA=sandbox` usa una pasarela de pruebas propia: el sistema crea la operación, redirige a su página de pago y **solo cambia
el estado del pago al recibir un webhook firmado (HMAC-SHA256)**, con validación de monto, antigüedad e idempotencia.
Para probar desde un celular real, `BASE_URL` debe ser una dirección alcanzable desde el celular (por ejemplo `http://192.168.1.20:8000`).
Para una pasarela real en sandbox (Pagopar, Bancard, etc.) se agrega una clase con la misma interfaz en `services/pasarela.py`.

### Tareas programadas

Avisos de vencimiento por correo (una vez al día, con cron):

```bash
0 9 * * *  cd /ruta/backend && ./venv/bin/python -m scripts.enviar_recordatorios
```

Medición de RNF-06 (tiempo de procesamiento) con fotos reales: `python -m scripts.medir_rnf foto1.jpg foto2.jpg 10`

## Estado del desarrollo

| Fase | Descripción | Estado |
|------|-------------|--------|
| Fase 1 | Configuración del entorno | ✅ Completado |
| Fase 2 | Estructura base del backend | ✅ Completado |
| Fase 3 | Módulo de gestión clínica | ✅ Completado |
| Fase 4 | Módulo de procesamiento de imágenes | 🔄 En progreso |
| Fase 5 | Aplicación móvil React Native | 🔄 En progreso |
| Fase 6 | Prueba piloto con dermatólogos | ⏳ Pendiente |

## Documentación de la API

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

## Universidad

**Universidad de la Integración de las Américas (UNIDA)**
Facultad de Ingeniería — Ingeniería Informática
Asunción, Paraguay — 2026
