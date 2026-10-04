# Instalación

Cómo instalar rag-extractivo, elegir un perfil, descargar los modelos y
ponerlo en un servidor propio (VPS) con HTTPS. El uso diario y la referencia
de comandos están en [uso.md](uso.md).

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
pip install "rag-extractivo @ git+https://github.com/Claudiobiovision/rag-extractivo.git"
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
dominio. El paso a paso (Caddy con HTTPS, Docker, `rag desplegar preparar`,
modos de desarrollo y producción y el panel `/admin`) está en
[despliegue.md](despliegue.md).

## Licencia

El proyecto es AGPL-3.0 (`AGPL-3.0-only`), la misma licencia que la librería
del avatar. Detalle en la sección Licencia del [README](../../README.md):
- instalarlo sin cambios en tu VPS no te impone obligaciones nuevas;
- si lo modificas y lo ofreces como servicio, debes publicar tus cambios y
  apuntar `RAG_URL_FUENTE` a tu repositorio. El widget y el panel enlazan a
  `GET /fuente`, que redirige ahí.
