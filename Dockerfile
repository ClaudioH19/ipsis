# Dockerfile del microservicio Python (rag-extractivo).
#
# Etapa A/B: `/consultar` ya responde de verdad. UNA sola imagen sirve DOS
# roles distintos según el `command:` que le dé docker-compose.yml: el
# servicio (`rag.servicio.api:app`, el CMD por defecto) y la ingesta de una sola
# corrida (`rag indexar`, contenedor `ingesta` en
# docker-compose.yml) -- así ambos comparten exactamente el mismo código de
# `rag/` sin duplicar la imagen.
#
# Solo instala `requirements.txt` (runtime: servicio + ingesta), NUNCA
# `requirements-eval.txt` (optimum/onnx/scikit-learn-extra/pytest -- ver ese
# archivo) -- la imagen de despliegue no necesita evaluar nada.
#
# El corpus (`documentos/`) NO se copia a la imagen ni se necesita en el
# contenedor del servicio: solo el contenedor `ingesta` lo monta como
# volumen de solo lectura (docker-compose.yml) y persiste lo que el
# servicio sí necesita (el vocabulario BM25, `.cache/vocab_bm25/`)
# como artefacto compartido -- ver `rag/corpus.py::guardar_vocabulario_bm25`/
# `cargar_vocabulario_bm25`.
#
# CPU only, sin GPU (restricción dura del proyecto, configuracion/motor.yaml).
FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema mínimas para compilar ruedas de torch/lxml si
# hiciera falta (la mayoría de las dependencias de requirements.txt ya
# traen wheels manylinux para este intérprete, pero se dejan por si acaso).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rag/ ./rag/
COPY rag/servicio/ ./servicio/
COPY config/ ./config/

ENV PYTHONUNBUFFERED=1 \
    QDRANT_URL=http://qdrant:6333

EXPOSE 8000

# Rol por defecto: el servicio. El contenedor `ingesta` de
# docker-compose.yml sobreescribe este `command` con
# `python -m rag.cli indexar` y termina (no queda sirviendo nada).
CMD ["python", "-m", "uvicorn", "rag.servicio.api:app", "--host", "0.0.0.0", "--port", "8000"]
