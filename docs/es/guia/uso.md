# Uso

El ciclo de trabajo de un asistente y la referencia de todos los comandos.
La instalación y los perfiles están en [instalacion.md](instalacion.md); el
VPS, Docker y los modos, en [despliegue.md](despliegue.md). El detalle de cada archivo de configuración
está en [configuracion.md](configuracion.md).

> La línea de comandos habla inglés por defecto. Con `IPSIS_LANG=es` todos los
> mensajes salen en español; los comandos y los nombres de archivo no cambian.

## Ciclo de trabajo

```text
ipsis init → ipsis models download → ipsis load → ipsis index → ipsis doctor → ipsis chat / ipsis serve
                                                    ↑                  │
                    documentos nuevos o cambiados ──┘                  ↓
                                         ipsis ask / widget en tu sitio
```

Opcional, para medir y ajustar:

```text
ipsis golden template → (una persona completa golden.csv) → ipsis golden import
  → ipsis evaluate → ipsis calibrate --apply
```

## Qué responde el asistente

Los proyectos nuevos (`ipsis init`) ya usan la preparación estructural
([ADR 0009](../../decisions/0009-structural-preparation-by-default.md)). Un proyecto existente conserva
sus fragmentos de tamaño fijo hasta que lo decidas: agrega `retrieval.preparation.mode: structural_v1`
a `config/engine.yaml` y ejecuta `ipsis index`, o revísala
antes en un proyecto separado:

```bash
ipsis prepare --project /ruta/proyecto --output /ruta/copia-nueva
# Después de revisar la vista previa, construir el índice en esa copia:
cd /ruta/copia-nueva
ipsis index
```

`ipsis prepare --index` construye además el índice durante la preparación.
La carpeta destino debe ser nueva y estar fuera del proyecto original. La copia
usa v2 y un índice estructural distinto; el original conserva su configuración.
Esta variante soporta estructura del cuerpo de DOCX, PDF, Markdown, texto plano y registros
XLSX/XLS/CSV/TSV, y publica avisos de extracción (las tablas Markdown quedan como párrafos; el PDF no
conserva tablas ni números de página). No garantiza mejor calidad de respuesta.
Ver [preparación estructural](../../methodology/preparacion-estructural.md).

Cada respuesta tiene un estado, que el widget pinta distinto:

| Estado | Qué significa |
|---|---|
| `ok` | Encontró el texto que responde; lo muestra literal, con la cita |
| `related` | No hay respuesta directa; muestra lo más cercano y lo dice |
| `no_answer` | No está en los documentos. Con `plan: clarification`, la pregunta no dice de qué se trata («¿Quién lo aprueba?» sin conversación previa) y el asistente pide el tema |
| `conversational` | Saludo, agradecimiento, despedida o «qué puedes hacer» |

Cada respuesta trae además un nivel de confianza (`confidence_level`): `high`
para una respuesta directa leída por el lector QA (medium), `medium` para una
respuesta directa sin lector (light; el widget muestra «Revisa la cita») y
`low` para un pasaje relacionado. Los niveles salen de precisiones medidas, no
de un umbral nuevo; ver [paráfrasis informales](../../methodology/informal-paraphrases.md) (en inglés).

El asistente nunca redacta contenido: el texto viene literal de tus
documentos, y las citas, con documento, sección y offsets, van debajo para
comprobarlo.

## La terminal: menú y modo interactivo

`ipsis help` imprime todos los comandos agrupados por tarea
(Empezar, Documentos, Preguntar, Personalizar, Medir y calibrar, Desplegar y
operar) con ejemplos; `ipsis` sin argumentos hace lo mismo si su salida no es
una terminal. `ipsis help <comando>` imprime las opciones de un
comando, igual que `ipsis <comando> --help`.

`ipsis` solo (o `ipsis chat`) abre el modo interactivo, al estilo de Claude
Code o Codex, con Folio y el proyecto de la carpeta. Al escribir `/` se
despliega un menú de comandos con su descripción; `Tab` muestra subcomandos y
opciones con su ayuda y completa rutas tras `/load`; la flecha arriba recupera
el historial (`~/.ipsis_history`). Lo que escribes es una pregunta; lo que
empieza con `/` es un comando:

| En `ipsis chat` | Qué hace |
|---|---|
| cualquier texto | Pregunta al motor del proyecto de esta carpeta; las preguntas de seguimiento conservan el tema |
| `/help` | Lista los comandos del modo interactivo |
| `/diagnostics on\|off` | Muestra, en cada respuesta, las etapas, las señales, la regla que decidió y el tramo exacto (lo que imprime `ipsis ask --diagnostics`) |
| `/reload` | Recarga el motor tras cambiar configuración o documentos |
| `/<comando> …` | Cualquier comando de ipsis: `/doctor`, `/load ./docs`, `/index`, `/profile show`, `/calibrate --help` |
| `/exit`, `/quit`, Ctrl+D | Sale |

Los modelos se cargan una vez, con la primera pregunta. Antes de correr un
comando se cierra el motor (el índice local admite un solo cliente) y se
vuelve a cargar con la pregunta siguiente. Igual que `ipsis ask
--diagnostics`, requiere detener `ipsis serve` cuando el índice es local.

Los comandos muestran las etapas reales y el tiempo transcurrido: lectura de
archivos, preparación de fragmentos, cálculo de vectores o búsqueda y
verificación de citas. La respuesta de Folio separa el texto y las fuentes.
`Ctrl+C` cancela y permite seguir en el chat; `/exit` o Ctrl+D salen.
Las comillas incompletas se explican sin cerrar la sesión. Los avisos de progreso
van a stderr y la salida de los comandos a stdout; fuera de una terminal no
hay animaciones ni códigos de color. `ipsis --help`, `ipsis help` y `/help`
incluyen la instalación con uv, sin crear ni activar entornos manualmente.

## Referencia de comandos

### Proyecto

| Comando | Qué hace |
|---|---|
| `ipsis init [--profile light\|medium] [--language en] [--assistant-name N] [--domain-description D] [--force]` | Crea `config/` y `documents/`. El idioma por defecto es `en` (o `es` con `IPSIS_LANG=es`). Sin `--force` no pisa un proyecto existente |
| `ipsis configure clave=valor …` | Edita `assistant.yaml`: `assistant_name`, `domain_description`, `language`, `profile`, `cors_origins`, `widget_keys` (listas separadas por coma) y `query_log.enabled` (true o false) |
| `ipsis profile show` | Perfil activo, modelos, presupuesto p95 y si el índice y la calibración le sirven |
| `ipsis profile set <perfil>` | Cambia el perfil. Avisa si hay que reindexar; la calibración anterior deja de aplicarse |
| `ipsis snapshot-config [--output RUTA]` | Escribe la configuración efectiva, con los valores por defecto resueltos |

### Modelos

| Comando | Qué hace |
|---|---|
| `ipsis models list` | Modelos del perfil activo: licencia, archivo ONNX de tu CPU y si están en la caché |
| `ipsis models download [--profile P]` | Descarga lo que falte a la caché global. Con `--profile` prepara otro perfil sin activarlo |
| `ipsis models verify` | Comprueba que los archivos estén completos y hace una inferencia mínima por modelo. No descarga |
| `ipsis models export <id_hf> [--int8]` | Solo desarrollo, con el extra `[export]`: convierte a ONNX en `exported/` |

### Corpus

Los inventarios XLSX, XLS, CSV y TSV se cargan con `ipsis load` o desde el panel.
Cada resultado conserva una fila completa con sus columnas y coordenadas;
ver [formatos y límites](inventarios.md).

`ipsis serve --demo` sirve la página con el tema del proyecto en
`/widget/demo.html`; `ipsis serve --open` también la abre cuando está lista.
Añade `--mode development` para habilitar el panel con un token temporal.

Enter resuelve comandos incompletos únicos y errores próximos, incluidos
subcomandos: `/widg the app search` pasa a `/widget theme apply search`.
También funciona desde la shell: `ipsis ser --demo`. La consola muestra la
interpretación, conserva argumentos y opciones, y no ejecuta nombres ambiguos.

`ipsis help serve` y `ipsis serve --help` muestran todas las opciones y sus
ejemplos. La ayuda anidada admite `ipsis help widget theme apply`. Dentro de
la terminal usa `/help serve` o `/help widget theme apply`; escribe `/serve `
y pulsa Tab para ver opciones y descripciones. La ayuda conserva el motor
cargado y no migra la configuración del proyecto.

| Comando | Qué hace |
|---|---|
| `ipsis load <archivo\|carpeta>` | Copia los documentos (PDF con texto, DOCX, MD, TXT, XLSX, XLS, CSV, TSV) a `documents/` y los cataloga. Si un archivo tiene el mismo nombre que otro ya cargado y distinto contenido, se agrega aparte: para retirar el anterior, marca `active: false` en `documents/catalog.yaml` |
| `ipsis index [--corpus CARPETA]` | Reconstruye el índice completo. Ejecútalo después de cada cambio de documentos o de un cambio de perfil que lo pida |

### Consulta

| Comando | Qué hace |
|---|---|
| `ipsis serve [carpeta] [--host H] [--port P] [--reindex] [--mode production\|development] [--demo] [--open]` | Levanta la API y el widget. Con una carpeta de documentos, crea y prepara un proyecto privado en `.ipsis-project/`. `--mode`: ver [despliegue.md](despliegue.md#modos-de-ejecución-desarrollo-y-producción); en desarrollo, sin `IPSIS_ADMIN_TOKEN`, imprime un token temporal |
| `ipsis chat [--diagnostics]` | Modo interactivo: preguntas y `/comandos` (ver arriba) |
| `ipsis ask "<pregunta>" [--url URL] [--timeout S]` | Pregunta al servicio en marcha |
| `ipsis ask "<pregunta>" --diagnostics` | Ejecuta el motor localmente, sin servicio, y muestra etapas con su latencia, señales, términos foco, la regla que decidió, el tramo exacto, el tono y las plantillas usadas. En modo Qdrant local, detén `ipsis serve` antes |

### Operación

| Comando | Qué hace |
|---|---|
| `ipsis doctor` | Diagnóstico de solo lectura: configuración, perfil, idioma, stemmer, modelos, índice, calibración, golden, CORS, personalidad y modo. Cada error trae su acción. Sale con 0 si no hay errores |
| `ipsis audit [--from FECHA] [--to FECHA]` / `ipsis audit --trace ID` | Revisa el registro de consultas: estados, reglas, tonos y si cada evidencia sigue siendo literal del corpus. Con `--from`/`--to` (`AAAA-MM-DD` o ISO 8601, UTC por defecto, inclusivas) solo cuenta ese rango. `--trace` muestra una consulta original y sus pasos por `consulta_id`, sin ejecutarla ni consultar el corpus. El registro se activa con `ipsis configure query_log.enabled=true` |

### Personalidad

Detalle en [personalidad.md](personalidad.md). Solo presentación: no pide
reindexar ni recalibrar.

| Comando | Qué hace |
|---|---|
| `ipsis personality show` | Tono activo, variedad y avatar (ubicación, tamaño, mirada, colores, eventos con respaldo) |
| `ipsis personality validate` | Revisa `personality.yaml`, las plantillas propias y el avatar. Sale con 1 si hay errores |
| `ipsis personality tone list` | Tonos del idioma del proyecto, con un ejemplo de cada uno |
| `ipsis personality tone apply <tono>` | Activa `cordial`, `formal`, `serious`, `upbeat`, `friendly`, `empathetic` o `direct` |
| `ipsis personality tone try [--tone T] [--situation S]` | Imprime las variantes con las variables del proyecto |
| `ipsis personality avatar list` | Avatares incluidos e importados |
| `ipsis personality avatar import <archivo.avatar.json> [--name N]` | Valida un avatar exportado del Studio y lo copia a `config/avatars/` |
| `ipsis personality avatar apply <nombre>` | Usa ese avatar en el widget |
| `ipsis personality avatar events` | Qué animación o expresión dispara cada evento, y cuáles usan un respaldo |
| `ipsis personality avatar assign <evento> <clave>` | Asigna a un evento una clave que el avatar tenga |
| `ipsis personality avatar colors [--body #rrggbb] [--eyes #rrggbb]` | Colores del avatar, sin modificar su archivo |

Sin terminal: el panel gráfico `/admin/panel` hace lo mismo con
formularios y una vista previa del widget. Necesita `IPSIS_ADMIN_TOKEN`; ver
[personalidad.md](personalidad.md#panel-gráfico-adminpanel).

### Golden set y evaluación

Detalle en [golden.md](golden.md).

| Comando | Qué hace |
|---|---|
| `ipsis golden template [--n 40] [--force]` | Genera `golden/golden.csv` y `golden/README.txt` a partir de tus documentos |
| `ipsis golden import <archivo>` | Valida el CSV, JSONL o SQuAD 2.0, ubica las respuestas, separa dev y test, y escribe `golden/bank/` |
| `ipsis golden validate` | Comprueba el banco contra el corpus actual |
| `ipsis golden export --format squad2\|csv [--output RUTA]` | Exporta el banco |
| `ipsis evaluate [--bank MANIFIESTO] [--output RUTA]` | Métricas del perfil activo, con la cota de falsos `ok` |
| `ipsis calibrate [--alpha 0.05] [--apply]` | Elige umbrales con control de riesgo usando solo dev. No entrena nada |
| `ipsis compare <a.json> <b.json> [--output RUTA]` | Compara dos reportes de `ipsis evaluate` |
| `ipsis benchmark --bank M [--bank M2…] [--profiles …] [--experiments] [--latency-only] [--repetitions N] [--output DIR]` | Compara perfiles: seguridad, cobertura, latencia y costo |

### Widget

Detalle en [web.md](web.md).

| Comando | Qué hace |
|---|---|
| `ipsis widget theme list` | Presets visuales disponibles |
| `ipsis widget theme apply <preset> [--path RUTA]` | Aplica un preset a `config/styles.yaml` |
| `ipsis widget theme preview [--path RUTA] [--output RUTA]` | Genera un HTML para ver el tema |
| `ipsis widget style show [--section S]` | Cada valor de estilo: `presentation`, `placement`, `colors`, `dark_colors`, `typography`, `shape`, `shadows` y `animations` |
| `ipsis widget style set seccion.clave=valor …` | Cambia uno o más valores (p. ej. `colors.accent=#0ea5e9 shape.panel_radius=10px`). Rechaza claves inexistentes y caracteres CSS peligrosos; si algo falla, no escribe nada |
| `ipsis widget export <carpeta> [--api URL] [--position P]` | Exporta `widget.js`, `snippet.html`, el motor del avatar (`avatar.js` y sus licencias) y la definición del avatar activo, para servirlos aparte. `P`: `bottom-right`, `bottom-left`, `top-right`, `top-left` o `embedded` |
| `ipsis widget snippet [--api URL] [--component] [--key K]` | Imprime el código para pegar en tu sitio, según `styles.yaml::placement` |

### Despliegue

| Comando | Qué hace |
|---|---|
| `ipsis deploy prepare [--target D] [--domain DOM] [--wheel W] [--force]` | Genera en `dist/` todo lo necesario para un VPS: proyecto, índice, `Dockerfile`, `docker-compose.yml` con Caddy opcional y `DEPLOY.md`. Ver [despliegue.md](despliegue.md) |

## Variables de entorno

V2 es el motor predeterminado de proyectos nuevos y configuraciones sin
selector. Enruta consultas a fuentes ordenadas para revisar. Una selección
explícita `pipeline: v1` en `config/engine.yaml` conserva el motor anterior;
cámbiala a `pipeline: v2` y reinicia el servicio para activar v2. Publica hasta
tres desplegables por página con contexto literal cercano, botón para seguir
buscando y QA apagado por defecto. El reranking es progresivo, con presupuesto
de trabajo de 2500 ms; los candidatos pendientes se conservan para continuar.
Los presets `search` y `search_compact` muestran títulos y extractos visibles,
barra de búsqueda superior y contexto desplegable; se aplican con
`ipsis widget theme apply search`.
Ver [fuentes ordenadas](../../methodology/fuentes-v2.md) para presupuestos,
campos de la API y migración del consejo retirado.

| Variable | Efecto |
|---|---|
| `IPSIS_LANG` | `es` para los mensajes en español (CLI y panel `/admin`); inglés en otro caso |
| `IPSIS_MODELS_DIR` | Carpeta de la caché global de modelos |
| `HF_HUB_OFFLINE=1` | Nunca usa la red |
| `IPSIS_ONNX_THREADS` | Hilos de onnxruntime |
| `QDRANT_MODE`, `QDRANT_URL` | Qdrant `local` o `server` |
| `IPSIS_MODE`, `IPSIS_ADMIN_TOKEN`, `IPSIS_TRUSTED_PROXY`, `IPSIS_ADMIN_IPS`, `IPSIS_DOCS`, `IPSIS_DEMO`, `IPSIS_SOURCE_URL` | Modo de ejecución y `/admin`; ver [despliegue.md](despliegue.md) |

## Problemas frecuentes

| Síntoma | Qué hacer |
|---|---|
| «already accessed» al indexar o diagnosticar | Qdrant local está bloqueado por `ipsis serve`: detén el servicio o usa Qdrant en modo servidor |
| `ipsis doctor` dice que faltan modelos | `ipsis models download` |
| Índice incompatible tras cambiar de perfil | `ipsis index` |
| Los documentos cambiaron | `ipsis index` (`ipsis doctor` lo detecta) |
| El navegador bloquea el widget | Agrega el origen exacto del sitio con `ipsis configure cors_origins=https://…` |
| El widget muestra un ícono en vez del avatar | La CSP de tu sitio no permite `'unsafe-eval'` (lo necesita el motor del avatar), o el avatar no es válido: `ipsis personality validate`. El chat funciona igual |
| `/ready` responde 503 | Lee `project.blocking`: trae el chequeo que falla y el comando que lo arregla (lo mismo que `ipsis doctor`) |
