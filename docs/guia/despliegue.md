# Despliegue en un servidor propio

Cómo poner el asistente en un VPS con HTTPS: el servicio, Caddy, Docker,
`ipsis desplegar preparar` y los modos de ejecución. La instalación y los
perfiles están en [instalacion.md](instalacion.md).

El proyecto está pensado para self-hosting: tu servicio, tus documentos y tu
dominio.

## 1. Servicio en loopback

`ipsis servir` escucha en `127.0.0.1:8000` por defecto. Déjalo así y pon un
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
ExecStart=/srv/venv/bin/ipsis servir --host 127.0.0.1 --port 8000
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
ipsis configurar cors_origenes=https://www.tu-sitio.cl
ipsis configurar claves_widget=clave-publica-del-sitio   # opcional
```

## 3. Docker

La imagen la genera `ipsis desplegar preparar` (siguiente sección) junto con
tu proyecto: un `Dockerfile` por perfil, con los modelos incluidos, y un
`docker-compose.yml`. En ejecución no usa la red.

- Instala el paquete (tu wheel con `--wheel`, o el del repositorio) y
  descarga los modelos del perfil al construir (el único paso con red).
- Corre como usuario no root (uid 10001), con `HF_HUB_OFFLINE=1` y
  `IPSIS_MODE=produccion`.
- Sin `IPSIS_ADMIN_TOKEN`, `/admin` no existe; defínelo al ejecutar.
- Healthcheck a `/ready`, que da 503 si algo bloquea (con la acción en
  `proyecto.bloqueante`).
- El proyecto (`configuracion/`, `documentos/` y `.ipsis/`) se monta desde la
  carpeta generada: los cambios de configuración no exigen reconstruir.

## 4. `ipsis desplegar preparar`

Genera una carpeta lista para copiar al VPS:

```bash
ipsis desplegar preparar --dominio asistente.tu-dominio.cl
```

`dist/` incluye:
- la configuración (con `personalidad.yaml`, `estilos.yaml`, la calibración
  y los avatares importados), los documentos y el índice;
- `Dockerfile`, `docker-compose.yml` (con un Caddy opcional, perfil `https`,
  ya declarado como proxy confiable), `Caddyfile` y `.env.ejemplo`;
- `LEEME_despliegue.md` en el idioma del proyecto, con el snippet del widget
  y cómo activar `/admin`.

Los registros de consultas y los secretos no se copian.

- **Versión exacta:** sin `--wheel`, la imagen instala la versión actual del
  repositorio público. Para fijar la tuya, construye el wheel
  (`python -m pip wheel . --no-deps`) y pásalo con `--wheel`.
- **Regenerar:** `--forzar` reemplaza una carpeta preparada antes. Nunca
  borra una carpeta que no haya generado este comando.

En el servidor:

```bash
cp .env.ejemplo .env
sudo chown -R 10001:10001 configuracion .ipsis
docker compose --profile https up -d --build
```

## Modos de ejecución: desarrollo y producción

El servicio corre en uno de dos modos, con `ipsis servir --modo` o
`IPSIS_MODE`. **Por defecto es `produccion`.**

| Aspecto | `desarrollo` | `produccion` |
|---|---|---|
| Panel `/admin` por HTTP plano | permitido desde cualquier IP, con aviso | solo desde la propia máquina; desde fuera exige HTTPS |
| Token de `/admin` | obligatorio; si no defines `IPSIS_ADMIN_TOKEN`, se imprime uno temporal al arrancar | obligatorio; sin `IPSIS_ADMIN_TOKEN` el panel no existe |
| Encabezados del proxy | se aceptan de la propia máquina | solo del proxy en `IPSIS_TRUSTED_PROXY` |
| `/docs` (OpenAPI) | habilitado | deshabilitado salvo `IPSIS_DOCS=1` |
| Archivos del widget | sin caché, para ver cambios al recargar | caché larga con versión |
| Errores 500 | con detalle | solo un id; el detalle va al log |

Usa `desarrollo` en tu máquina o para probar en un VPS sin certificado.
Usa `produccion` en cualquier servicio público. El modo no cambia las
respuestas del asistente.

Variables del modo y del panel `/admin`:

| Variable | Efecto |
|---|---|
| `IPSIS_ADMIN_TOKEN` | Activa `/admin`; al menos 32 caracteres. Genera uno con `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `IPSIS_TRUSTED_PROXY` | IP del proxy (por ejemplo, Caddy) del que se aceptan `X-Forwarded-*` |
| `IPSIS_ADMIN_IPS` | Opcional: IPs permitidas para `/admin` |
| `IPSIS_MODE` | `produccion` (por defecto) o `desarrollo`; también `ipsis servir --modo` |
| `IPSIS_DOCS=1`, `IPSIS_DEMO=1` | `/docs` y `/widget/demo.html` también en producción |
| `IPSIS_SOURCE_URL` | URL de tu código fuente (AGPL §13) a la que redirige `GET /fuente`. Por defecto, este repositorio |

Tras 5 tokens incorrectos, la IP queda bloqueada 15 minutos. Cada cambio
queda en `.ipsis/registros/admin.jsonl`: fecha, IP, acción y claves, nunca el
token. `ipsis doctor` revisa el modo: avisa en desarrollo y da error con un
token corto.

En un VPS con Caddy delante:

```bash
export IPSIS_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export IPSIS_TRUSTED_PROXY=127.0.0.1      # Caddy en la misma máquina
ipsis servir --modo produccion
```

Para rotar el token, cámbialo y reinicia el servicio.

## Antes de lanzar con un cliente

Lista de verificación con el corpus real del cliente. La decide quien
publica; ningún comando la marca solo.

- [ ] **Golden real:** escrito y revisado por una persona, con al menos un
  30% de preguntas sin respuesta o con premisa falsa, y pares «mismo tema,
  dato ausente» (ver [golden.md](golden.md)).
- [ ] **Calibración:** `ipsis calibrar --alfa 0.05` da `CALIBRADO` (en `test`,
  la cota superior al 95% de falsos `ok` es ≤ 5%; con 0 errores exige al
  menos 59 respuestas aceptadas en `test`). Si da `MUESTRA_INSUFICIENTE`, se
  puede lanzar con los umbrales del perfil, sin afirmar el 5%.
- [ ] **Latencia:** `ipsis benchmark` cumple el presupuesto del perfil en la
  máquina de producción (light ≤ 150 ms, medium ≤ 1 s y heavy ≤ 5 s de p95).
- [ ] **Pruebas en verde** sobre la versión que se despliega
  (`python -m pytest`).
- [x] **Licencia:** AGPL-3.0-only.
