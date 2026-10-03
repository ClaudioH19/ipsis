# syntax=docker/dockerfile:1
# Construye e instala el mismo wheel que se distribuye a usuarios. El corpus,
# secretos, tests e índices quedan fuera de la imagen mediante .dockerignore.

FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY rag/ ./rag/
RUN python -m pip wheel --no-cache-dir --no-deps --wheel-dir /wheels .


FROM python:3.12-slim AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid ${APP_GID} rag \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /usr/sbin/nologin rag

WORKDIR /app
COPY --from=builder /wheels/ /wheels/
# Instalar primero PyTorch desde el índice CPU evita incorporar varios GB de
# runtimes CUDA que este proyecto no utiliza.
RUN python -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir /wheels/rag_extractivo-*.whl \
    && rm -rf /wheels

# Configuración genérica de arranque, generada con las plantillas del paquete.
# En producción se monta la carpeta del proyecto sobre /app/configuracion.
RUN cd /app && rag init \
    && mkdir -p /app/.rag/indice /app/.cache/huggingface \
    && chown -R rag:rag /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/.cache/huggingface \
    QDRANT_URL=http://qdrant:6333

USER rag
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "rag.servicio.api:app", "--host", "0.0.0.0", "--port", "8000"]
