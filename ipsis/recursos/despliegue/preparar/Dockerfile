# syntax=docker/dockerfile:1
# Generado por `ipsis desplegar preparar`. Imagen del perfil {{perfil}} con sus
# modelos; en ejecución no usa la red. El proyecto (config/, documents/
# y .ipsis/) se monta desde esta carpeta (ver docker-compose.yml).

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /bin/uv

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
RUN if ls /paquete/*.whl >/dev/null 2>&1; then uv pip install --system --no-cache /paquete/*.whl; \
    else uv pip install --system --no-cache "${PAQUETE}"; fi \
    && rm -rf /paquete

ENV IPSIS_MODELS_DIR=/opt/ipsis/modelos
WORKDIR /app
# La descarga debe leer profile_overrides.models del proyecto preparado.
COPY config/ /app/config/
RUN ipsis models download --profile ${PERFIL} && chmod -R a+rX /opt/ipsis
RUN chown ipsis:ipsis /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 \
    IPSIS_MODE=production

LABEL org.opencontainers.image.licenses="AGPL-3.0-only"

USER ipsis
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)" || exit 1

CMD ["ipsis", "serve", "--host", "0.0.0.0", "--port", "8000"]
