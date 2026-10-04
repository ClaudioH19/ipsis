# syntax=docker/dockerfile:1
# Imagen por perfil: el mismo wheel que se distribuye (con avatar.js, avatares y
# tonos) más los modelos del perfil, descargados al construir. En ejecución no
# usa la red. El corpus, secretos, tests e índices quedan fuera (.dockerignore).
#
#   docker build --build-arg PERFIL=light -t rag-extractivo:light .
#
# La carpeta del proyecto se monta sobre /app (configuracion/, documentos/ y
# .rag/); `rag desplegar preparar` la genera junto a un docker-compose.yml.

FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY rag/ ./rag/
RUN python -m pip wheel --no-cache-dir --no-deps --wheel-dir /wheels .


FROM python:3.12-slim AS runtime

ARG PERFIL=medium
ARG APP_UID=10001
ARG APP_GID=10001

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid ${APP_GID} rag \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /usr/sbin/nologin rag

WORKDIR /app
COPY --from=builder /wheels/ /wheels/
# Sin torch: los modelos corren con onnxruntime en CPU.
RUN python -m pip install --no-cache-dir /wheels/rag_extractivo-*.whl \
    && rm -rf /wheels

# Modelos del perfil en una caché fuera de /app, para que montar el proyecto
# no los tape. Es el único paso con red.
ENV RAG_MODELOS_DIR=/opt/rag/modelos
RUN rag modelos descargar --perfil ${PERFIL} \
    && chmod -R a+rX /opt/rag

# Proyecto genérico de arranque; en producción se monta el propio sobre /app.
RUN rag init --perfil ${PERFIL} \
    && mkdir -p /app/.rag/indice /app/.rag/registros \
    && chown -R rag:rag /app

# Producción explícita y sin red. Sin RAG_ADMIN_TOKEN, /admin no existe:
# defínelo al ejecutar (docker run -e / compose) para activarlo.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 \
    RAG_MODO=produccion

LABEL org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.source="https://github.com/Claudiobiovision/rag-extractivo" \
      rag-extractivo.perfil="${PERFIL}"

USER rag
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)" || exit 1

# rag servir aplica RAG_PROXY_CONFIABLE a uvicorn (cabeceras X-Forwarded-* del proxy).
CMD ["rag", "servir", "--host", "0.0.0.0", "--port", "8000"]
