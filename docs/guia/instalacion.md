# Instalación

Cómo instalar rag-extractivo, elegir un perfil, descargar los modelos y
ponerlo en un servidor propio (VPS) con HTTPS. El uso diario y la referencia
de comandos están en [uso.md](uso.md).

> Las partes marcadas **(P12.x)** están planificadas y todavía no existen;
> cada una se documenta en detalle cuando se implementa.

## Requisitos

- Python 3.11 o 3.12.
- CPU: no hace falta GPU. Los modelos corren con onnxruntime.
- Disco para los modelos del perfil. Es una caché global por usuario, que
  comparten todos los proyectos:

  | Perfil | Modelos | Disco aprox. | p95 objetivo |
  |---|---|---|---|
  | `light` | denso e5-small | 0,5 GB | 150 ms |
  | `medium` | e5-small + reranker mMiniLM + lector mDeBERTa | 1,7 GB | 1 s |
  | `heavy` | e5-base + reranker bge-m3 + lector mDeBERTa | 2,8 GB | 5 s |

  `bm25` es solo de diagnóstico para `rag benchmark`: no se instala.
- Red solo para descargar los modelos. Después el servicio funciona sin red.

## Instalar el paquete

Desde GitHub:

```bash
pip install "rag-extractivo @ git+https://github.com/USUARIO/rag-extractivo.git"
```

Para desarrollar desde un clon:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"        # Linux/macOS
.venv\Scripts\python.exe -m pip install -e ".[test]" # Windows
```

Extras opcionales:

| Extra | Para qué | ¿Producción? |
|---|---|---|
| `test` | pytest | no |
| `browser` | pruebas de navegador con Playwright | no |
| `exportar` | `rag modelos exportar`: convierte un modelo de Hugging Face a ONNX (`optimum-onnx` y `torch`) | no; solo desarrollo |

La producción no instala torch.

## Crear un proyecto

Cada asistente es una carpeta:

```bash
mkdir mi-asistente && cd mi-asistente
rag init --perfil medium --idioma es
rag modelos descargar          # modelos del perfil a la caché global
rag modelos verificar          # carga cada modelo y hace una inferencia mínima
rag cargar /ruta/a/documentos
rag indexar
rag doctor                     # ¿puede funcionar? Si no, qué comando ejecutar
rag servir                     # http://127.0.0.1:8000
```

- **Perfil:** `light`, `medium` o `heavy` (ver la tabla de requisitos). Se
  cambia después con `rag perfil cambiar <perfil>`. Entre `light` y `medium`
  se reutiliza el índice; `heavy` necesita reindexar.
- **Idioma:** `es`, `en` y `pt` tienen paquete propio. Una variante regional
  (`pt-br`) usa el de su idioma. Cualquier otro código ISO funciona con
  reglas universales y textos en inglés.

## Caché de modelos y uso sin red

| Variable | Efecto |
|---|---|
| `RAG_MODELOS_DIR` | Carpeta de la caché global. Por defecto, `~/.cache/rag-extractivo/modelos` |
| `HF_HUB_OFFLINE=1` | Nunca usa la red. Si falta un modelo, el error dice qué hacer |
| `RAG_HILOS_ONNX` | Hilos de onnxruntime por modelo |

En una máquina sin red, descarga en otra con
`rag modelos descargar --perfil <p>` y copia la carpeta de la caché.

## Qdrant

Por defecto el índice vive en el proyecto, en modo local
(`.rag/indice/qdrant`). En ese modo Qdrant bloquea la carpeta: detén
`rag servir` antes de ejecutar `rag indexar`, `rag doctor` o
`rag preguntar --diagnostico`.

Para usar Qdrant como servidor, en `configuracion/motor.yaml`:

```yaml
qdrant:
  modo: "servidor"
  url_servidor: "http://localhost:6333"
```

También sirven las variables `QDRANT_MODO` y `QDRANT_URL`.

## Servidor propio (VPS)

El proyecto está pensado para self-hosting: tu servicio, tus documentos y tu
dominio.

### 1. Servicio en loopback

`rag servir` escucha en `127.0.0.1:8000` por defecto. Déjalo así y pon un
proxy con HTTPS delante. Ejemplo con systemd:

```ini
# /etc/systemd/system/rag-asistente.service
[Unit]
Description=rag-extractivo
After=network.target

[Service]
User=rag
WorkingDirectory=/srv/mi-asistente
Environment=HF_HUB_OFFLINE=1
ExecStart=/srv/venv/bin/rag servir --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### 2. HTTPS con Caddy

Caddy obtiene y renueva el certificado solo:

```caddyfile
asistente.tu-dominio.cl {
    reverse_proxy 127.0.0.1:8000
}
```

Luego, en el proyecto:

```bash
rag configurar cors_origenes=https://www.tu-sitio.cl
rag configurar claves_widget=clave-publica-del-sitio   # opcional
```

### 3. Docker

```bash
docker build -t rag-extractivo .
```

La imagen instala el wheel sin torch, corre con un usuario no root y expone
el puerto 8000 con un healthcheck a `/ready`, que da 503 si algo bloquea
(con la acción en `proyecto.bloqueante`). La configuración del proyecto
se monta en `/app/configuracion`. Pendiente **(P12.12)**: una imagen por
perfil, con los modelos incluidos y sin red. **(P12.13)**:
`rag desplegar preparar`, que genera `docker-compose.yml` con un servicio
Caddy opcional.

## Modos de ejecución: desarrollo y producción

El servicio corre en uno de dos modos, con `rag servir --modo` o
`RAG_MODO`. **Por defecto es `produccion`.**

| Aspecto | `desarrollo` | `produccion` |
|---|---|---|
| Panel `/admin` por HTTP plano | permitido desde cualquier IP, con aviso | solo desde la propia máquina; desde fuera exige HTTPS |
| Token de `/admin` | obligatorio; si no defines `RAG_ADMIN_TOKEN`, se imprime uno temporal al arrancar | obligatorio; sin `RAG_ADMIN_TOKEN` el panel no existe |
| Encabezados del proxy | se aceptan de la propia máquina | solo del proxy en `RAG_PROXY_CONFIABLE` |
| `/docs` (OpenAPI) | habilitado | deshabilitado salvo `RAG_DOCS=1` |
| Archivos del widget | sin caché, para ver cambios al recargar | caché larga con versión |
| Errores 500 | con detalle | solo un id; el detalle va al log |

Usa `desarrollo` en tu máquina o para probar en un VPS sin certificado.
Usa `produccion` en cualquier servicio público. El modo no cambia las
respuestas del asistente.

Variables del modo y del panel `/admin`:

| Variable | Efecto |
|---|---|
| `RAG_ADMIN_TOKEN` | Activa `/admin`; al menos 32 caracteres. Genera uno con `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `RAG_PROXY_CONFIABLE` | IP del proxy (por ejemplo, Caddy) del que se aceptan `X-Forwarded-*` |
| `RAG_ADMIN_IPS` | Opcional: IPs permitidas para `/admin` |
| `RAG_MODO` | `produccion` (por defecto) o `desarrollo`; también `rag servir --modo` |
| `RAG_DOCS=1`, `RAG_DEMO=1` | `/docs` y `/widget/demo.html` también en producción |
| `RAG_URL_FUENTE` | URL de tu código fuente (AGPL §13) a la que redirige `GET /fuente`. Por defecto, este repositorio |

Tras 5 tokens incorrectos, la IP queda bloqueada 15 minutos. Cada cambio
queda en `.rag/registros/admin.jsonl`: fecha, IP, acción y claves, nunca el
token. `rag doctor` revisa el modo: avisa en desarrollo y da error con un
token corto.

En un VPS con Caddy delante:

```bash
export RAG_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export RAG_PROXY_CONFIABLE=127.0.0.1      # Caddy en la misma máquina
rag servir --modo produccion
```

Para rotar el token, cámbialo y reinicia el servicio.

## Licencia

El proyecto es AGPL-3.0 (`AGPL-3.0-only`), la misma licencia que la librería
del avatar. Detalle en la sección Licencia del [README](../../README.md):
- instalarlo sin cambios en tu VPS no te impone obligaciones nuevas;
- si lo modificas y lo ofreces como servicio, debes publicar tus cambios y
  apuntar `RAG_URL_FUENTE` a tu repositorio. El widget y el panel enlazan a
  `GET /fuente`, que redirige ahí.
