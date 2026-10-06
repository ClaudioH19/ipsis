# Instalación

Cómo instalar ipsis, elegir un perfil, descargar los modelos y
crear el primer proyecto. El uso diario y la referencia de comandos están en
[uso.md](uso.md); el servidor con HTTPS, en [despliegue.md](despliegue.md).

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

  `bm25` es solo de diagnóstico para `ipsis benchmark`: no se instala.
- Red solo para descargar los modelos. Después el servicio funciona sin red.

## Instalar el paquete

Conviene un entorno virtual por servidor o por máquina. El paquete instala
el comando `ipsis`.

**Linux y macOS**

```bash
python3 -m venv ~/.venvs/ipsis
source ~/.venvs/ipsis/bin/activate
pip install "ipsis @ git+https://github.com/ClaudioH19/ipsis.git"
ipsis --version
```

**Windows (PowerShell)**

```powershell
py -3.12 -m venv $HOME\.venvs\ipsis
& $HOME\.venvs\ipsis\Scripts\Activate.ps1
pip install "ipsis @ git+https://github.com/ClaudioH19/ipsis.git"
ipsis --version
```

**En un servidor con Docker:** `ipsis deploy prepare` genera la imagen y el
compose de tu proyecto (ver [despliegue.md](despliegue.md#3-docker)).

### Para desarrollar

```bash
git clone https://github.com/ClaudioH19/ipsis.git
cd ipsis
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"        # Linux/macOS
.venv\Scripts\python.exe -m pip install -e ".[test]" # Windows
```

Extras opcionales:

| Extra | Para qué | ¿Producción? |
|---|---|---|
| `test` | pytest | no |
| `browser` | pruebas de navegador con Playwright (`python -m playwright install chromium`) | no |
| `export` | `ipsis models export`: convierte un modelo de Hugging Face a ONNX (`optimum-onnx` y `torch`) | no; solo desarrollo |

La producción no instala torch. Una instalación editable guarda rutas
absolutas: si mueves el clon, reinstala.

## Crear un proyecto

Cada asistente es una carpeta con su configuración, sus documentos y su
índice:

```bash
mkdir mi-asistente && cd mi-asistente
ipsis init --profile medium --language es \
  --assistant-name "Asistente de soporte" --domain-description "los manuales del producto"
ipsis models download          # modelos del perfil a la caché global (una sola vez por máquina)
ipsis models verify          # carga cada modelo y hace una inferencia mínima
ipsis load /ruta/a/documentos  # PDF con texto, DOCX, Markdown o TXT
ipsis index
ipsis doctor                     # ¿puede funcionar? Si no, qué comando ejecutar
ipsis serve                     # http://127.0.0.1:8000 (abre /widget/demo.html con --mode development)
```

En otra terminal:

```bash
ipsis ask "¿Cada cuánto se cambia el filtro?"
```

- **Perfil:** `light`, `medium` o `heavy` (ver la tabla de requisitos). Se
  cambia después con `ipsis profile set <perfil>`. Entre `light` y `medium`
  se reutiliza el índice; `heavy` necesita reindexar.
- **Idioma:** `es`, `en` y `pt` tienen paquete propio. Una variante regional
  (`pt-br`) usa el de su idioma. Cualquier otro código ISO funciona con
  reglas universales y textos en inglés. Sin `--language`, `ipsis init`
  usa `en` (o `es` con `IPSIS_LANG=es`).
- **Atajo:** `ipsis serve ./mis-documentos` crea un proyecto privado en
  `.ipsis-project/`, carga los archivos, indexa si hace falta y sirve.

## PDF escaneados (OCR, opcional)

Un PDF hecho de imágenes (un escaneo, fotos de páginas) no tiene texto que
extraer. Con OCR, `ipsis load` lee esas páginas con
[Tesseract](https://github.com/tesseract-ocr/tesseract); sin él, el PDF se
rechaza y el resto de la carpeta se carga igual.

```bash
pip install "ipsis[ocr]"
```

Después instala el programa Tesseract con el idioma de tus documentos:

| Sistema | Comando |
|---|---|
| Debian/Ubuntu | `sudo apt install tesseract-ocr tesseract-ocr-spa tesseract-ocr-por` |
| macOS | `brew install tesseract tesseract-lang` |
| Windows | `winget install UB-Mannheim.TesseractOCR` (elige los idiomas en el instalador) |

- Solo pasan por OCR las páginas sin texto; las digitales se leen como siempre.
- El idioma del proyecto elige el del OCR (`es` → `spa`, `pt` → `por`,
  `en` → `eng`), más inglés para siglas.
- `ipsis load` e `ipsis index` muestran cada página a medida que la leen, con
  su **confianza** (el promedio de Tesseract sobre sus palabras, de 0 a
  100 %), y listan los archivos leídos con OCR. Bajo 85 % la página se marca
  con confianza baja: ahí el OCR empieza a confundir letras («Horanos» por
  «Horarios»), así que revisa sus citas o vuelve a escanearla.
- Lo que lee `ipsis load` se guarda en `.ipsis/ocr`: `ipsis index` reutiliza
  el mismo texto en vez de leer de nuevo, mientras no cambien el archivo, los
  idiomas ni la versión de Tesseract.
- `IPSIS_OCR=off` lo desactiva aunque esté instalado.

## Caché de modelos y uso sin red

| Variable | Efecto |
|---|---|
| `IPSIS_MODELS_DIR` | Carpeta de la caché global. Por defecto, `~/.cache/ipsis/models` |
| `HF_HUB_OFFLINE=1` | Nunca usa la red. Si falta un modelo, el error dice qué hacer |
| `IPSIS_ONNX_THREADS` | Hilos de onnxruntime por modelo |

En una máquina sin red, descarga en otra con
`ipsis models download --profile <p>` y copia la carpeta de la caché.

## Qdrant

Por defecto el índice vive en el proyecto, en modo local
(`.ipsis/index/qdrant`). En ese modo Qdrant bloquea la carpeta: detén
`ipsis serve` antes de ejecutar `ipsis index`, `ipsis doctor` o
`ipsis ask --diagnostics`.

Para usar Qdrant como servidor, en `config/engine.yaml`:

```yaml
qdrant:
  mode: "server"
  server_url: "http://localhost:6333"
```

También sirven las variables `QDRANT_MODE` y `QDRANT_URL`.

## Servidor propio (VPS)

El proyecto está pensado para self-hosting: tu servicio, tus documentos y tu
dominio. El paso a paso (Caddy con HTTPS, Docker, `ipsis deploy prepare`,
modos de desarrollo y producción y el panel `/admin`) está en
[despliegue.md](despliegue.md).

## Licencia

El proyecto es AGPL-3.0 (`AGPL-3.0-only`), la misma licencia que la librería
del avatar. Detalle en la sección Licencia del [README](../../../README.es.md):

- instalarlo sin cambios en tu VPS no te impone obligaciones nuevas;
- si lo modificas y lo ofreces como servicio, debes publicar tus cambios y
  apuntar `IPSIS_SOURCE_URL` a tu repositorio. El widget y el panel enlazan a
  `GET /source`, que redirige ahí.
