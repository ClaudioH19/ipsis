# rag-extractivo

Asistente documental para tu sitio que **responde citando el texto literal
de tus documentos**. No usa un modelo generativo: si los documentos no
respaldan una respuesta, lo dice. Corre en CPU, en tu propio servidor y, una
vez descargados los modelos, sin red.

```text
¿Cada cuánto se cambia el filtro?
→ «El filtro de sedimentos se cambia cada 6 meses.»
   Manual del purificador › Mantenimiento · caracteres 139–146
```

## Características

- **Extractivo y auditable:** cada respuesta es un tramo literal con
  documento, sección y offsets; `rag auditar` comprueba que lo sigue siendo.
- **Sabe cuándo no responder:** estados `ok`, `relacionado`, `sin_respuesta` y
  `conversacional`, decididos por señales explicables (léxicas y de modelos)
  con umbrales que se pueden calibrar con riesgo controlado.
- **Tres perfiles:** `light` (búsqueda híbrida, ~85 ms), `medium` (+ reranker
  y lector QA, ~0,8 s) y `heavy` (modelos grandes y más comprobaciones).
- **Multilingüe:** paquetes de idioma `es`, `en` y `pt`; otros idiomas con
  reglas universales.
- **Widget embebible y responsive** con citas verificables, 7 tonos de
  respuesta y un avatar animado («Folio»), configurable por CLI o desde el
  panel `/admin/panel`.
- **Self-hosting:** imagen Docker por perfil y `rag desplegar preparar`, que
  genera todo para un VPS con HTTPS (Caddy).
- PDF con capa de texto, DOCX, Markdown y TXT.

## Instalación

Requiere Python 3.11 o 3.12. No necesita GPU.

```bash
pip install "rag-extractivo @ git+https://github.com/Claudiobiovision/rag-extractivo.git"
```

| Perfil | Modelos | Disco | p95 objetivo |
|---|---|---|---|
| `light` | e5-small | 0,5 GB | 150 ms |
| `medium` | e5-small + reranker + lector | 1,7 GB | 1 s |
| `heavy` | e5-base + reranker grande + lector | 2,8 GB | 5 s |

Detalle, caché de modelos y uso sin red: [docs/guia/instalacion.md](docs/guia/instalacion.md).

## Ciclo de uso

```bash
mkdir mi-asistente && cd mi-asistente
rag init --perfil medium --idioma es
rag modelos descargar
rag cargar /ruta/a/documentos
rag indexar
rag doctor                     # ¿puede funcionar? Si no, qué comando ejecutar
rag servir                     # http://127.0.0.1:8000
rag preguntar "¿Cada cuánto se cambia el filtro?" --diagnostico
```

Para tu sitio:

```bash
rag configurar cors_origenes=https://www.tu-sitio.cl
rag widget snippet --api https://asistente.tu-dominio.cl
```

Y para medir y calibrar con preguntas reales:

```bash
rag golden plantilla           # propone preguntas a partir de tus documentos
rag golden importar golden/golden.csv
rag calibrar --aplicar         # umbrales con riesgo de falso «ok» ≤ 5% (si la muestra alcanza)
```

Referencia completa de comandos: [docs/guia/uso.md](docs/guia/uso.md).

## Documentación

| Guía | Contenido |
|---|---|
| [Instalación](docs/guia/instalacion.md) | Perfiles, modelos, caché y Qdrant |
| [Uso](docs/guia/uso.md) | Ciclo de trabajo y todos los comandos |
| [Configuración](docs/guia/configuracion.md) | Cada archivo de `configuracion/` |
| [Golden set](docs/guia/golden.md) | Cómo escribir y validar preguntas de prueba |
| [Web](docs/guia/web.md) | Widget, ubicación, API JavaScript, CSP y avatar |
| [Personalidad](docs/guia/personalidad.md) | Tonos, avatar y panel `/admin` |
| [Despliegue](docs/guia/despliegue.md) | VPS con HTTPS, Docker, `rag desplegar preparar` y modos |

Cómo funciona por dentro: [fichas metodológicas](docs/metodologia/README.md) y
[decisiones de arquitectura](docs/decisiones/).

## API

`POST /consultar` con `{"pregunta": "…", "id_sesion": "…"}` devuelve el
estado, el texto extractivo, los fragmentos citados con offsets y, si el
lector marcó un tramo, `respuesta_exacta`. También: `/health`, `/ready`
(diagnóstico del proyecto; 503 si algo bloquea), `/config`, `/widget.js`,
`/avatar.js`, `/estilos.css` y `/fuente`.

## Desarrollo

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"       # .venv\Scripts\python.exe en Windows
python -m pytest -m "not slow and not browser"     # rápidas
python -m pytest                                   # todo (con el extra [browser] para Chromium)
```

Las pruebas usan documentos sintéticos: el repositorio no distribuye corpus
ni métricas de una institución concreta. El motor del avatar se construye en
[herramientas/avatar/](herramientas/avatar/LEEME.md).

## Límites

- Los PDF escaneados necesitan OCR externo; se rechazan para no indexar
  contenido vacío.
- Los umbrales de `rag init` son conservadores y genéricos: valídalos con
  preguntas de tu corpus (`rag calibrar`).
- Un sinónimo que no aparece en el documento puede llevar a abstenerse: es
  el lado seguro del error.
- No usa el historial de la conversación para preguntas de seguimiento.
- En modo local, Qdrant bloquea su carpeta mientras otro proceso la usa.

## Licencia

rag-extractivo es software libre bajo la
[GNU Affero General Public License v3.0](LICENSE) (`AGPL-3.0-only`), la misma
licencia que el motor del avatar ([@bible-strong/avatar-web](https://github.com/smontlouis/bible-strong-avatar-lab)).

- **Qué permite:** usarlo con cualquier fin, también comercial; estudiarlo,
  modificarlo y redistribuirlo.
- **Si lo instalas sin cambios** en tu VPS para tu sitio, no tienes
  obligaciones nuevas: el servicio ya enlaza a este repositorio.
- **Si lo modificas y lo ofreces como servicio por red,** debes ofrecer a
  quienes lo usan el código fuente de tu versión, bajo la misma licencia
  (§13). Para eso, el widget y el panel muestran «Código fuente», que lleva a
  `GET /fuente`. Apunta `RAG_URL_FUENTE` a tu repositorio.
- **Si lo redistribuyes** (por ejemplo, una imagen Docker), incluye la
  licencia y el código fuente correspondiente.

`rag/servicio/estaticos/avatar.js.LICENSE.txt` lista los paquetes incluidos
en el motor del avatar y sus licencias (AGPL-3.0, MIT y BSD-3-Clause).
