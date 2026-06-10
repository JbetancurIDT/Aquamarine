# Imagen básica del backend Aquamarine (E00).
# Docker Compose y orquestación se agregan en E02; esto es solo la imagen base.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instala dependencias primero para aprovechar la cache de capas de Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código de la app.
COPY . .

EXPOSE 8000

# Arranque de producción (sin --reload). En desarrollo se usa uvicorn --reload.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
