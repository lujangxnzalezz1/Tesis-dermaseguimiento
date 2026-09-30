FROM python:3.12-slim
# Librerías de sistema que necesitan OpenCV y MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Migra la base, carga los datos iniciales (idempotente) y arranca la API
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed && uvicorn main:app --host 0.0.0.0 --port 8000"]
