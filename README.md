# Facial Traceability API

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
proyectoDeTesis/
├── backend/
│   ├── main.py          # Punto de entrada del servidor
│   ├── routers/         # Endpoints organizados por módulo
│   ├── models/          # Modelos de base de datos
│   ├── schemas/         # Validación de datos
│   ├── services/        # Lógica de negocio
│   └── core/            # Configuración general
├── .gitignore
└── README.md

## Instalación y configuración

### Requisitos previos

- Python 3.12.7
- PostgreSQL 18.3
- Git 2.54.0

### Pasos

**1. Clonar el repositorio**
```bash
git clone https://github.com/lujangxnzalezz1/facial-traceability-api.git
cd facial-traceability-api
```

**2. Crear y activar el entorno virtual**
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
```

**3. Instalar dependencias**
```bash
pip install -r requirements.txt
```

**4. Configurar variables de entorno**
```bash
cp .env.example .env
# Editar .env con tus datos de PostgreSQL
```

**5. Iniciar el servidor**
```bash
uvicorn main:app --reload
```

**6. Verificar que funciona**

Abrí el navegador en:
- API: http://127.0.0.1:8000
- Documentación: http://127.0.0.1:8000/docs

## Estado del desarrollo

| Fase | Descripción | Estado |
|------|-------------|--------|
| Fase 1 | Configuración del entorno | ✅ Completado |
| Fase 2 | Estructura base del backend | 🔄 En progreso |
| Fase 3 | Módulo de gestión clínica | ⏳ Pendiente |
| Fase 4 | Módulo de procesamiento de imágenes | ⏳ Pendiente |
| Fase 5 | Aplicación móvil React Native | ⏳ Pendiente |
| Fase 6 | Prueba piloto con dermatólogos | ⏳ Pendiente |

## Documentación de la API

Una vez iniciado el servidor, la documentación interactiva está disponible en:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

## Universidad

**Universidad de la Integración de las Américas (UNIDA)**
Facultad de Ingeniería — Ingeniería Informática
Asunción, Paraguay — 2026
