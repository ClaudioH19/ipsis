# Despliegue en un servidor propio

Cómo poner el asistente en un VPS con HTTPS: el servicio, Caddy, Docker,
`ipsis deploy prepare` y los modos de ejecución. La instalación y los
perfiles están en [instalacion.md](instalacion.md).

El proyecto está pensado para self-hosting: tu servicio, tus documentos y tu
dominio.

## Integración continua

`.github/workflows/servicio.yml` se ejecuta en cada push, pull request e inicio
manual. Su job de contrato comprueba el motor y la frontera HTTP sin descargar
modelos. Su job de contenedor construye un wheel desde el checkout actual, crea
un proyecto en español con el perfil light que contiene un registro de
inventario conocido, descarga el modelo de CPU necesario, carga e indexa el
documento y luego ejecuta `ipsis deploy prepare --wheel`. El Dockerfile
generado instala ese wheel, de modo que la comprobación prueba el commit en
cuestión y no otra rama ni una versión publicada.

Docker Compose construye con el UID/GID del runner para que las carpetas
montadas de configuración e índice sean escribibles, inicia el servicio y
espera su healthcheck `/ready`. Luego `herramientas/ci/comprobar_servicio.py`
verifica un índice v2 no vacío, el modo producción, el catálogo del widget,
cuatro tipos de conversación y la recuperación de fuentes literales con offsets
correctos. Una pregunta con el prefijo «hola» debe seguir recuperando el valor
de inventario conocido. Las respuestas con HTTP 200 pero con cuerpo vacío o
incorrecto fallan. El script guarda un informe JSON incluso si falla; Actions
además sube el estado y los logs de los contenedores y, al final, detiene solo
su propio despliegue de prueba.

El workflow manual `.github/workflows/regresion-general.yml` conserva la
evaluación histórica de respuestas directas y sus artefactos. Su entrada
opcional `comparar_referencia` activa la comparación con la línea base
congelada. Esas métricas de respuesta y abstención no son métricas de ranking:
v2 devuelve fuentes para revisar a propósito. Esta evaluación es independiente
de la puerta automática de arranque del servicio; la línea base no se reescribió
para ocultar esa diferencia.

Para reproducir la comprobación del contenedor en Linux con Docker Compose y uv:

```bash
uv sync --locked --extra test
uv build --wheel --out-dir .cache/ci/wheels
uv run python herramientas/ci/preparar_contenedor.py --output .cache/ci --wheels .cache/ci/wheels
export COMPOSE_FILE="$PWD/.cache/ci/deploy/docker-compose.yml"
export COMPOSE_PROJECT_NAME=ipsis-ci
docker compose build --build-arg APP_UID="$(id -u)" --build-arg APP_GID="$(id -g)"
docker compose up -d --no-build --wait --wait-timeout 180
uv run python herramientas/ci/comprobar_servicio.py --url http://127.0.0.1:8000 --output .cache/ci/reporte.json
docker compose down --remove-orphans
```

Usa una carpeta de salida nueva al repetir la preparación. El puerto 8000 debe
estar libre. La comprobación demuestra el empaquetado, el arranque y la
interacción básica con un corpus real indexado; no certifica la calidad de la
búsqueda en todos los documentos.

## 1. Servicio en loopback

`ipsis serve` escucha en `127.0.0.1:8000` por defecto. Déjalo así y pon un
proxy con HTTPS delante. Ejemplo con systemd:

```ini
# /etc/systemd/system/ipsis-asistente.service
[Unit]
Description=ipsis
After=network.target

[Service]
User=ipsis
WorkingDirectory=/srv/mi-asistente
Environment=HF_HUB_OFFLINE=1
ExecStart=/srv/venv/bin/ipsis serve --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## 2. HTTPS con Caddy

Caddy obtiene y renueva el certificado solo:

```caddyfile
asistente.tu-dominio.cl {
    reverse_proxy 127.0.0.1:8000
}
```

Luego, en el proyecto:

```bash
ipsis configure cors_origins=https://www.tu-sitio.cl
ipsis configure widget_keys=clave-publica-del-sitio   # opcional
```

## 3. Docker

La imagen la genera `ipsis deploy prepare` (siguiente sección) junto con
tu proyecto: un `Dockerfile` por perfil, con los modelos incluidos, y un
`docker-compose.yml`. En ejecución no usa la red.

- Instala el paquete (tu wheel con `--wheel`, o el del repositorio) y
  descarga los modelos del perfil al construir (el único paso con red).
- Corre como usuario no root (uid 10001), con `HF_HUB_OFFLINE=1` y
  `IPSIS_MODE=production`.
- Sin `IPSIS_ADMIN_TOKEN`, `/admin` no existe; defínelo al ejecutar.
- Healthcheck a `/ready`, que da 503 si algo bloquea (con la acción en
  `project.blocking`).
- El proyecto (`config/`, `documents/` y `.ipsis/`) se monta desde la
  carpeta generada: los cambios de configuración no exigen reconstruir.

## 4. `ipsis deploy prepare`

Genera una carpeta lista para copiar al VPS:

```bash
ipsis deploy prepare --domain asistente.tu-dominio.cl
```

`dist/` incluye:
- la configuración (con `personality.yaml`, `styles.yaml`
  y los avatares importados), los documentos y el índice;
- `Dockerfile`, `docker-compose.yml` (con un Caddy opcional, perfil `https`,
  ya declarado como proxy confiable), `Caddyfile` y `.env.example`;
- `DEPLOY.md` en el idioma del proyecto, con el snippet del widget
  y cómo activar `/admin`.

Los registros de consultas y los secretos no se copian.

- **Versión exacta:** sin `--wheel`, la imagen instala la versión actual del
  repositorio público. Para fijar la tuya, construye el wheel
  (`uv build --wheel`) y pásalo con `--wheel`.
- **Regenerar:** `--force` reemplaza una carpeta preparada antes. Nunca
  borra una carpeta que no haya generado este comando.

En el servidor:

```bash
cp .env.example .env
sudo chown -R 10001:10001 config .ipsis
docker compose --profile https up -d --build
```

## Modos de ejecución: desarrollo y producción

El servicio corre en uno de dos modos, con `ipsis serve --mode` o
`IPSIS_MODE`. **Por defecto es `production`.**

| Aspecto | `development` | `production` |
|---|---|---|
| Panel `/admin` por HTTP plano | permitido desde cualquier IP, con aviso | solo desde la propia máquina; desde fuera exige HTTPS |
| Token de `/admin` | obligatorio; si no defines `IPSIS_ADMIN_TOKEN`, se imprime uno temporal al arrancar | obligatorio; sin `IPSIS_ADMIN_TOKEN` el panel no existe |
| Encabezados del proxy | se aceptan de la propia máquina | solo del proxy en `IPSIS_TRUSTED_PROXY` |
| `/docs` (OpenAPI) | habilitado | deshabilitado salvo `IPSIS_DOCS=1` |
| Archivos del widget | sin caché, para ver cambios al recargar | caché larga con versión |
| Errores 500 | con detalle | solo un id; el detalle va al log |

Usa `development` en tu máquina o para probar en un VPS sin certificado.
Usa `production` en cualquier servicio público. El modo no cambia las
respuestas del asistente.

Variables del modo y del panel `/admin`:

| Variable | Efecto |
|---|---|
| `IPSIS_ADMIN_TOKEN` | Activa `/admin`; al menos 32 caracteres. Genera uno con `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `IPSIS_TRUSTED_PROXY` | IP del proxy (por ejemplo, Caddy) del que se aceptan `X-Forwarded-*` |
| `IPSIS_ADMIN_IPS` | Opcional: IPs permitidas para `/admin` |
| `IPSIS_MODE` | `production` (por defecto) o `development`; también `ipsis serve --mode` |
| `IPSIS_DOCS=1`, `IPSIS_DEMO=1` | `/docs` y `/widget/demo.html` también en producción |
| `IPSIS_SOURCE_URL` | URL de tu código fuente (AGPL §13) a la que redirige `GET /source`. Por defecto, este repositorio |
| `IPSIS_LANG` | `es` para servir el `/admin/panel` en español |

Tras 5 tokens incorrectos, la IP queda bloqueada 15 minutos. Cada cambio
queda en `.ipsis/logs/admin.jsonl` (el panel también sube documentos de hasta 20 MiB
y reindexa: trata el token como una credencial de despliegue; mientras se recarga el motor `/ask`
responde 503, así que reindexa fuera de horas de uso): fecha, IP, acción y claves, nunca el
token. `ipsis doctor` revisa el modo: avisa en desarrollo y da error con un
token corto.

En un VPS con Caddy delante:

```bash
export IPSIS_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export IPSIS_TRUSTED_PROXY=127.0.0.1      # Caddy en la misma máquina
ipsis serve --mode production
```

Para rotar el token, cámbialo y reinicia el servicio.

## Antes de lanzar con un cliente

Para cambios posteriores de perfil, lectura, CORS o personalidad,
consulta [configuración para despliegue](configuracion.md#cambiar-configuración-antes-o-después-de-desplegar).
El `DEPLOY.md` generado incluye comandos de administración del contenedor,
ejemplos de `profile_overrides` y el flujo de evaluación antes de aplicar cambios.

Lista de verificación con el corpus real del cliente. La decide quien
publica; ningún comando la marca solo.

- [ ] **Golden real:** escrito y revisado por una persona, con al menos un
  30% de preguntas sin respuesta o con premisa falsa, y pares «mismo tema,
  dato ausente» (ver [golden.md](golden.md)).
- [ ] **Evaluación:** correr `ipsis evaluate` sobre el golden y revisar por
  separado las métricas de respuesta completa y la calidad del tramo QA.
- [ ] **Latencia:** `ipsis benchmark` cumple el presupuesto del perfil en la
  máquina de producción (light ≤ 150 ms y medium ≤ 1 s de p95).
- [ ] **Pruebas en verde** sobre la versión que se despliega
  (`uv run --locked --extra test --extra browser pytest`).
- [x] **Licencia:** AGPL-3.0-only.
