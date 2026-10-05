# syntax=docker/dockerfile:1
# Generado por `ipsis desplegar preparar`. Imagen del perfil {{perfil}} con sus
# modelos; en ejecución no usa la red. El proyecto (config/, documents/
# y .ipsis/) se monta desde esta carpeta (ver docker-compose.yml).

FROM python:3.12-slim

ARG PERFIL={{perfil}}
# Paquete a instalar si paquete/ no trae un wheel (ipsis desplegar preparar --wheel).
ARG PAQUETE="{{paquete}}"
ARG APP_UID=10001
ARG APP_GID=10001

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid ${APP_GID} ipsis \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /usr/sbin/nologin ipsis

COPY paquete/ /paquete/
RUN if ls /paquete/*.whl >/dev/null 2>&1; then python -m pip install --no-cache-dir /paquete/*.whl; \
    else python -m pip install --no-cache-dir "${PAQUETE}"; fi \
    && rm -rf /paquete

ENV IPSIS_MODELS_DIR=/opt/ipsis/modelos
RUN ipsis modelos descargar --perfil ${PERFIL} && chmod -R a+rX /opt/ipsis

WORKDIR /app
RUN chown ipsis:ipsis /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 \
    IPSIS_MODE=produccion

LABEL org.opencontainers.image.licenses="AGPL-3.0-only"

USER ipsis
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)" || exit 1

CMD ["ipsis", "servir", "--host", "0.0.0.0", "--port", "8000"]
