# Instalación

Cómo instalar ipsis, elegir un perfil, descargar los modelos y
crear el primer proyecto. El uso diario y la referencia de comandos están en
[uso.md](uso.md); el servidor con HTTPS, en [despliegue.md](despliegue.md).

## Requisitos

- `uv` y Git. `uv` instala Python 3.12 automáticamente si falta; no necesitas instalarlo antes.
- CPU: no hace falta GPU. Los modelos corren con onnxruntime.
- Disco para los modelos del perfil. Es una caché global por usuario, que
  comparten todos los proyectos:

  | Perfil | Modelos | Disco aprox. | p95 objetivo (`ipsis benchmark`) |
  |---|---|---|---|
  | `light` | denso e5-small | 0,5 GB | 150 ms |
  | `medium` | e5-small + reranker (bge-reranker-v2-m3 en español y portugués, mMiniLM en otros idiomas) | 1,0 GB (español, portugués) · 0,6 GB (otros idiomas) | 1 s |

  `bm25` es solo de diagnóstico para `ipsis benchmark`: no se instala.
  Los tamaños son los de los archivos ONNX en disco (medidos el 2026-10-16 tras `ipsis models download`: e5-small
  470 MB, bge-reranker-v2-m3 int8 571 MB, mMiniLM 119 MB). El lector QA extractivo (mDeBERTa) solo se carga si se activa
  el opcional `v2.qa_highlights`; si no, ni el motor ni `ipsis models download` lo traen, y `ipsis models list`
  muestra lo que usa la configuración activa.
  Latencia medida de una consulta completa de `medium` (v2; banco sintético de pasajes, 116 preguntas, 4 CPU de un
  Intel Xeon a 2,1 GHz, 2026-10-16): español con bge-reranker-v2-m3, p50 604 ms y p95 749 ms; inglés con mMiniLM,
  p50 349 ms y p95 620 ms. Ese banco tiene pasajes cortos: con documentos reales en español el p95 fue de 1,7 s
  (ver el [ADR 0003](../../decisions/0003-onnx-and-profiles.md)).
  El «p95 objetivo» es el `p95_budget_ms` del perfil: la referencia con que `ipsis benchmark` marca si un perfil
  cumple su latencia, que también muestran `ipsis profile` y el panel. El motor predeterminado (v2) no lo aplica a
  las consultas: una consulta v2 se acota con `v2.query_budget_ms` (2500 ms), igual para los dos perfiles.
  `medium` es la opción recomendada y el valor por defecto de `ipsis init`.
- Red solo para descargar los modelos. Después el servicio funciona sin red.

## Instalar el paquete

La instalación de Python y sus dependencias se hace con **uv**. No necesitas
crear un entorno virtual, activarlo ni clonar el repositorio para usar ipsis.

### 1. Instalar uv (una sola vez)

En Windows, desde PowerShell:

```powershell
winget install --id astral-sh.uv -e
```

En Linux o macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Abre una terminal nueva. Comprueba `uv --version` y `git --version`; Git es
necesario para instalar desde el repositorio. Si falta en Windows, instala
`winget install --id Git.Git -e`; en Linux o macOS usa el gestor de tu sistema.

### 2. Instalar ipsis (el mismo comando en todos los sistemas)

```bash
uv tool install --python 3.12 "ipsis @ git+https://github.com/ClaudioH19/ipsis.git"
uv tool update-shell
```

Abre una terminal nueva y ejecuta `ipsis --version`. Ya puedes usar `ipsis`
desde cualquier carpeta. `uv` mantiene un entorno aislado interno para evitar
conflictos; tú no tienes que crearlo ni activarlo. La instalación del paquete
es distinta de un proyecto: cada asistente sigue viviendo en su propia carpeta.

### Actualizar

```bash
uv tool upgrade ipsis
```

Detén el servicio antes de actualizar y vuelve a iniciarlo desde la misma
carpeta del proyecto. Se conservan documentos, índice y configuración;
los cambios de presentación no requieren reindexación. El `styles.yaml`
existente se conserva: aplica un preset o cambia valores individuales para
adoptar opciones nuevas. Recarga el navegador y reemplaza las copias exportadas
de `widget.js` si tu sitio las utiliza.

Una instalación desde una rama Git se actualiza a un commit nuevo de esa rama.
Para fijar la release 1.1, usa `ipsis @
git+https://github.com/ClaudioH19/ipsis.git@v1.1.0` al instalar. Si fijaste un
tag o commit, debes cambiar esa referencia para actualizar a otra release.

**En Docker:** `ipsis deploy prepare` genera la imagen de tu proyecto;
también instala el paquete con uv (ver [despliegue.md](despliegue.md#3-docker)).

### Solo si vas a desarrollar el repositorio

Para usar ipsis no necesitas estos pasos. Para modificar su código:

```bash
git clone https://github.com/ClaudioH19/ipsis.git
cd ipsis
uv sync --locked --extra test
uv run --locked --extra test ipsis --help
uv run --locked --extra test pytest -m "not slow and not browser"
```

`uv sync` crea y mantiene `.venv` automáticamente con las versiones de
`uv.lock`; `uv run` ejecuta dentro de ella sin activarla. Para pruebas de
navegador usa `uv sync --locked --extra test --extra browser` y
`uv run --locked --extra test --extra browser playwright install chromium`.
Conserva esos extras en los comandos `uv run` que los necesiten.

| Extra | Instalar en el clon | Para qué |
|---|---|---|
| `test` | `uv sync --locked --extra test` | pytest |
| `browser` | `uv sync --locked --extra test --extra browser` | Playwright |
| `export` | `uv sync --locked --extra export` | Exportar modelos a ONNX; solo desarrollo |
| `ocr` | `uv sync --locked --extra ocr` | Leer PDF escaneados; además necesita Tesseract |

La producción no instala torch. Si mueves el clon, vuelve a ejecutar `uv sync`.

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

- **Perfil:** `light` o `medium` (ver la tabla de requisitos). Se
  cambia después con `ipsis profile set <perfil>`. Entre `light` y `medium`
  se reutiliza el índice.
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
uv tool install --force --python 3.12 "ipsis[ocr] @ git+https://github.com/ClaudioH19/ipsis.git"
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
