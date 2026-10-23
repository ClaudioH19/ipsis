# Referencia de configuración

## Archivos de un proyecto

`ipsis init` crea la carpeta del proyecto. Todo es YAML legible y versionable,
salvo `.ipsis/`, que es generado. Los nombres de carpetas, archivos y claves
están en inglés en todos los idiomas.

```text
mi-asistente/
├── config/
│   ├── assistant.yaml      # identidad, idioma, perfil, CORS, claves del widget y registro
│   ├── engine.yaml         # recuperación, componentes, Qdrant, límites y ajustes del perfil
│   ├── styles.yaml         # tema y ubicación del widget
│   ├── personality.yaml    # tono de las respuestas y avatar
│   ├── domain.yaml         # opcional: reglas y categorías propias del dominio
│   ├── language.yaml       # opcional: textos del paquete de idioma sobrescritos
│   └── avatars/            # avatares importados (.avatar.json)
├── documents/              # archivos fuente + catalog.yaml
├── golden/                 # golden.csv, bank/ versionado y reports/
└── .ipsis/                 # generado: index/ (Qdrant, estadísticas, manifiesto) y logs/
```

| Archivo | Se edita con | Detalle |
|---|---|---|
| `assistant.yaml` | `ipsis configure clave=valor` | esta guía |
| `engine.yaml` | a mano | esta guía |
| `styles.yaml` | `ipsis widget theme`, `ipsis widget style`, panel `/admin` | [web.md](web.md) |
| `personality.yaml` | `ipsis personality`, panel `/admin` | [personalidad.md](personalidad.md) |

### `assistant.yaml`

```yaml
config_version: 8
assistant_name: "Asistente de soporte"
domain_description: "los manuales del producto"
language: es              # código ISO 639: es, en, pt, pt-br...
profile: medium           # light | medium
cors_origins: []          # orígenes que pueden insertar el widget
widget_keys: []           # claves públicas opcionales del widget
query_log:
  enabled: false          # .ipsis/logs/queries.jsonl, para `ipsis audit`
```

## Versionado

`assistant.yaml` y `engine.yaml` declaran `config_version`. La versión vigente
es la `8`.

- Cualquier comando `ipsis` migra un proyecto anterior al cargar: un archivo
  sin `config_version` se lee como versión 0 y sube paso a paso.
- La validación rechaza claves desconocidas y una versión superior a la
  soportada.

| Versión | Qué cambió |
|---|---|
| 2 | El reranker se elige solo con `components.reranker` |
| 3 | `domain.yaml` reemplaza a los perfiles de dominio; `profile` pasa a ser el perfil de instalación (los proyectos v2 quedan en `light`); sin torch; `.cache/` pasa a `.ipsis/` |
| 4 | La política `cascade_v1` del motor v1 (retirado) reemplaza a la anterior; los umbrales pasan al perfil y a `calibration.yaml` |
| 5 | Carpetas, archivos, claves y valores en inglés (`config/`, `documents/`, `assistant.yaml`, `assistant_name`…). Los proyectos creados con nombres en español se mueven y reescriben solos, conservando sus comentarios |
| 6 | `engine.yaml` sin `pipeline` pasa a `pipeline: v2` (una selección explícita `pipeline: v1` se conservó hasta retirar el motor v1: ahora se carga como v2) |
| 7 | Se elimina el experimento `v2.council` de `engine.yaml`; los demás presupuestos de v2 se conservan |
| 8 | Los proyectos v2 que no habían elegido preparación pasan a la estructural (`retrieval.preparation.mode: structural_v1`); ejecuta `ipsis index` para construir el índice nuevo ([ADR 0009](../../decisions/0009-structural-preparation-by-default.md)) |

El retiro del motor v1 no añadió una versión: un proyecto que todavía dice
`pipeline: v1`, nombra los componentes de v1 (`intent_classifier`,
`answer_extractor`, `response_renderer`, `abstention_policy`), conserva las
secciones `rendering`, `abstention` o `acceptance_criteria`, sobrescribe en
`profile_overrides` la cascada, los umbrales o las alternativas, sobrescribe
`respaldo_intencion` en el paquete de idioma, o tiene `posture` en
`assistant.yaml`, se carga sin errores: corre v2 y esas claves se ignoran (la
primera imprime un aviso). Bórralas de los archivos cuando puedas. El índice
no se reconstruye.

La configuración ya validada puede cargarse desde Python:

```python
from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto

motor = cargar_proyecto()
asistente = cargar_dominio()
```

Estas funciones devuelven los nombres internos que usa el motor; los
archivos en disco usan los nombres en inglés de esta guía.

## Componentes

### Selección del motor

Proyectos nuevos y configuraciones sin selector usan v2:

```yaml
config_version: 8
pipeline: v2
```

V2 publica fuentes literales ordenadas con continuación. Sus opciones están
en [fuentes ordenadas](../../methodology/fuentes-v2.md). El motor v1 (cascada de
respuesta, calibración y alternativas en abstenciones) se retiró: una
configuración que todavía dice `pipeline: v1` se carga como v2 y muestra un
aviso.

La sección `components` selecciona implementaciones por nombre:

```yaml
components:
  parser: builtin
  chunker: builtin
  dense_encoder: onnx
  sparse_encoder: bm25
  retriever: qdrant
  fusion: rrf
  reranker: null
  evidence_verifier: literal_offsets
```

El reranker y el lector los define el perfil (`ipsis profile show`). Un valor
`null` desactiva un componente opcional. Una implementación puede recibir
opciones usando la forma extendida:

```yaml
components:
  fusion:
    name: rrf
    k: 60
```

El registry se puede usar desde una integración:

```python
from ipsis.nucleo.contratos import RegistroComponentes
from ipsis.aplicacion.registro_base import registrar_componentes_base

registro = registrar_componentes_base(RegistroComponentes())
fusion = registro.crear("fusion", "rrf", k=60)
```

Los adaptadores base no descargan modelos durante el registro. `onnx` abre la
sesión del modelo solo al usarlo por primera vez. La conexión a Qdrant y los
rerankers los configura el servicio, porque dependen del índice, la colección
y los recursos disponibles.

### Backend de recuperación

`qdrant` es el único backend soportado. `retrieval.mode` permite elegir
`dense` o `hybrid`; ambos conservan el mismo contrato y requieren volver a
indexar cuando cambia la representación persistida.

## Perfil de instalación

El perfil activo está en `config/assistant.yaml::profile` (`light` o
`medium`). `bm25` es solo un perfil de diagnóstico de
`ipsis benchmark`, no se instala.

```
ipsis profile show         # perfil, modelos, presupuesto p95 e índice
ipsis profile set medium   # cambia solo assistant.yaml::profile
```

`ipsis profile set` no descarga modelos, no indexa y no borra nada. Se
conservan `profile_overrides` y el índice. Antes de escribir, valida los `profile_overrides` del proyecto contra el perfil
destino. Repetir el perfil activo no hace nada.

- **light ↔ medium:** usan el mismo modelo denso (e5-small, 384), así que el
  índice sirve para ambos.
- **Proyectos con `heavy`:** ese perfil se retiró. Un `assistant.yaml` que lo
  tenga se carga como `medium`; si su índice se construyó con otro modelo
  denso, `ipsis profile show` lo marca incompatible y pide `ipsis index`.
  Cada modelo denso vive en su colección: el índice anterior se conserva.
- **Compatibilidad del índice:** se decide por el manifiesto
  (`.ipsis/index/<coleccion>.manifest.json`), con el modelo denso, la
  dimensión y la versión del payload. No se decide por el nombre del perfil.

## Cambiar configuración antes o después de desplegar

Ejecuta los comandos desde la carpeta que contiene `config/` y `documents/`.
Con Qdrant local, detén `ipsis serve` antes de abrir el índice desde otro proceso.
En el servidor, usa la carpeta del proyecto desplegado.

| Qué cambiar | Comando o archivo | Qué hacer después |
|---|---|---|
| Perfil | `ipsis profile set medium` | `ipsis models download`, `ipsis profile show`; evaluar |
| Identidad y CORS | `ipsis configure assistant_name="Soporte" cors_origins=https://www.tu-sitio.com` | Reiniciar el servicio |
| Registro de consultas | `ipsis configure query_log.enabled=true` | Reiniciar; después `ipsis audit` comprueba las citas registradas |
| Lectura y recuperación | `config/engine.yaml`, secciones `v2` y `profile_overrides` | Reiniciar y evaluar |
| Fragmentación, modelo denso o representación del índice | `config/engine.yaml`, sección `retrieval` | Reindexar, validar el golden y evaluar |
| Documentos vigentes | `documents/catalog.yaml`, `active` | Reindexar y validar el golden |
| Sinónimos | `config/domain.yaml`, `synonyms` | Reiniciar y evaluar |
| Tono y avatar | `ipsis personality` o `config/personality.yaml` | Se recargan en el servicio; ver [personalidad](personalidad.md) |
| Tema y posición del widget | `ipsis widget style` o `config/styles.yaml` | Ver [web](web.md) |

`ipsis configure` edita las claves de `assistant.yaml` que aparecen en esta
guía; los ajustes del motor se cambian por archivo. No edites los perfiles
incluidos en el paquete. Añade o combina este bloque en `config/engine.yaml`:

```yaml
profile_overrides:
  models:
    reranker: Horizon-Labs/multilingual-reranker-small
```

`profile_overrides` reemplaza campos del perfil incluido: `models` (`dense`,
`reranker`, `reader`), `retrieval_mode` y los rerankers por idioma
(`language_rerankers`, `language_rerank_candidates`). Los presupuestos de
lectura y ranking de v2 (candidatos, lote del reranker, contexto) están en el
bloque `v2` del mismo archivo. Más candidatos o ventanas mayores aumentan el
trabajo, sin garantizar más exactitud.

La precedencia es **perfil → `profile_overrides`**. Un proyecto que fija
`models.reranker` conserva el suyo y no recibe ni el reranker del idioma ni su
cantidad de candidatos.

Flujo de revisión antes de preparar el despliegue:

```bash
ipsis profile show
ipsis snapshot-config --output reports/config-review.yaml
ipsis golden validate
ipsis evaluate --output reports/evaluation.json
ipsis doctor
ipsis deploy prepare --domain asistente.tu-dominio.com
```

El snapshot conserva configuración validada y valores por defecto; el reporte
de evaluación conserva las señales y la configuración del flujo usado. Evalúa
la respuesta completa y el tramo QA por separado ([golden](golden.md)).
`doctor` y `/ready` comprueban que el servicio pueda funcionar, no la
exactitud de sus respuestas.

En Docker, edita `config/` de la carpeta desplegada y reinicia con
`docker compose restart asistente`. Para cambios de perfil con otros modelos,
prepara de nuevo la imagen y el índice. El `DEPLOY.md` generado incluye
estas instrucciones; consulta [despliegue](despliegue.md).

## Modelos

### Modelos alternativos

Hasta octubre de 2026 existía un perfil `heavy` con modelos mayores. Se
retiró porque ninguna variante superó a medium: con Granite-311M R2,
Granite-97M R2, Harrier-270M o EmbeddingGemma 2 como recuperador, y con
Horizon base/small como reranker, el banco de consultas dio exactamente los
mismos 25 aciertos que medium, y los Horizon añadieron un error aceptado. El
antiguo e5-base/BGE con cascada 30/8/4 tenía menos aciertos y más errores.
Ver [ADR 0003](../../decisions/0003-onnx-and-profiles.md).

Los modelos siguen en el catálogo para probarlos sobre medium con el corpus
de un despliegue. Combina este bloque con `config/engine.yaml` (claves en
inglés):

```yaml
retrieval:
  model: null
profile_overrides:
  models:
    dense: ibm-granite/granite-embedding-311m-multilingual-r2
```

| Rol | Repositorio soportado |
|---|---|
| Denso | `ibm-granite/granite-embedding-311m-multilingual-r2` |
| Denso | `ibm-granite/granite-embedding-97m-multilingual-r2` |
| Denso | `onnx-community/harrier-oss-v1-270m-ONNX` |
| Denso | `onnx-community/embeddinggemma-2-ONNX` (solo texto) |
| Denso | `intfloat/multilingual-e5-base` |
| Reranker | `Horizon-Labs/multilingual-reranker-base` |
| Reranker | `Horizon-Labs/multilingual-reranker-small` |
| Reranker | `onnx-community/bge-reranker-v2-m3-ONNX` |

Usan revisiones fijas del catálogo. El runtime respeta sus prefijos,
pooling, relleno, salidas y datos externos; EmbeddingGemma 2 recibe entradas
vacías para las modalidades que no se usan. Sus escalas de similitud son
distintas: Granite, por ejemplo, da cosenos entre 0,73 y 0,94 también a
preguntas ajenas al corpus. Evalúa con el golden del despliegue antes de usar
otro recuperador.

Con el servicio detenido: `ipsis models download`, `ipsis models verify`,
`ipsis index`, `ipsis profile show`, `ipsis golden validate`, `ipsis evaluate`.
Cualquier cambio de recuperador exige reindexar, aunque la dimensión sea la
misma.
Los ajustes se conservan al cambiar de perfil: quítalos para usar sus valores
predeterminados. La [regresión general](../../../herramientas/evaluacion/README.md)
permite comparar variantes sin modificar un proyecto existente. La imagen
Docker preparada lee estos ajustes al descargar; hay que reconstruirla si
cambian modelos (`docker compose build --no-cache asistente`).

Los modelos ONNX viven en una caché global por usuario, compartida por todos
los proyectos. Por defecto es `~/.cache/ipsis/models`, y se cambia con
`IPSIS_MODELS_DIR`. Usa el formato de `huggingface_hub`. Nada se descarga
dentro del proyecto. Con `HF_HUB_OFFLINE=1` nunca se usa la red.

```
ipsis models list                     # modelos del perfil activo
ipsis models download                 # descarga los que falten del perfil activo
ipsis models download --profile medium # prepara otro perfil sin activarlo
ipsis models verify                   # archivos completos e inferencia de prueba
ipsis models export org/modelo --int8 # desarrollo: convierte a ONNX
```

- **`list`** muestra, para cada modelo del perfil activo:
  - rol, repositorio, licencia (y atribución, si el catálogo la registra) y
    parámetros;
  - el ONNX que corresponde a la CPU actual (x86_64 o arm64);
  - si está en la caché, y cuánto ocupa.

  Todo sale del catálogo (`ipsis/modelos/catalogo.py`). light usa solo el
  denso; medium usa denso, reranker y lector.
- **`download`** baja solo lo que falta. Un modelo compartido entre perfiles,
  como e5-small (light y medium), se descarga una sola vez.
  - Con `--profile` no cambia el perfil activo, y funciona fuera de un
    proyecto.
  - Sin `--profile` necesita el proyecto (`ipsis init`).
  - `bm25` no es instalable.
- **`verify`** solo revisa el perfil activo y nunca descarga. Por modelo:
  - los archivos requeridos (ONNX, `tokenizer.json`, `config.json`);
  - que la sesión de onnxruntime cargue;
  - una inferencia mínima: vector normalizado de la dimensión esperada,
    logit finito o lectura válida.

  Cada modelo termina en `OK`, `FALTA` (acción: `ipsis models download`),
  `NO CARGA` (archivo presente pero inválido) o `FALLA` (inferencia
  inválida). Sale con 0 solo si todos dan `OK`.
- **`export`** es solo para desarrollo. Necesita el extra `[export]`
  (`uv sync --locked --extra export`, con `optimum-onnx` y `torch`). La
  producción corre sin torch.
  - Deja `exported/<org>--<modelo>/model.onnx` en la carpeta actual y, con
    `--int8`, también `model_int8.onnx`, con la cuantización dinámica
    post-entrenamiento de onnxruntime (`quantize_dynamic`).
  - No pisa una exportación anterior ni toca la caché.
  - No registra el modelo en el catálogo ni en los perfiles: adoptarlo es
    otro paso.

## Idioma

`assistant.yaml::language` es un código ISO 639, por ejemplo `es`, `en` o
`pt-br`. `es`, `en` y `pt` tienen paquete propio: stemmer, stopwords,
números, fechas, conectores, mensajes e interfaz. Una variante regional
(`pt-br`, `es-cl`) usa el paquete de su idioma.

Las preguntas casi nunca se escriben como los documentos. Cada paquete trata
las abreviaturas informales y los restos de contracciones como palabras
funcionales («q», «pa», «pra», «vc», «u», «ur», la «t» de «don't»), y el
análisis corrige erratas con el vocabulario del corpus («pasword» →
«password», «covran» → «cobra», «abreel» → «abre el», «estacio namiento» →
«estacionamiento»; nunca una palabra real que el corpus no trae, como
«feriados», ni un nombre propio).
`ipsis ask --diagnostics` muestra cada corrección. Ver
[paráfrasis informales](../../methodology/informal-paraphrases.md) (en inglés).

Otro código funciona con un respaldo:

- solo las reglas universales (fechas numéricas, montos, artículos);
- términos sin stem;
- la interfaz y los tonos de `en`, que se pueden traducir con
  `config/language.yaml` (interfaz) y `config/personality.yaml` (tono).

`ipsis init` y `ipsis configure language=` lo avisan, y `ipsis doctor` lo
marca como aviso.

El idioma de los documentos es independiente del idioma de la línea de
comandos (`IPSIS_LANG`): un proyecto en portugués se puede administrar con
mensajes en inglés o en español.

## Sinónimos locales

### Grupos de sinónimos

Español, inglés y portugués usan las tablas filtradas de WordNet incluidas
en el paquete para ampliar la recuperación BM25, reutilizando el vector
denso original. Solo se expande una palabra
ausente del corpus, con un único sentido después del stemming; las palabras
de la relación y las correcciones manuales tienen prioridad. Los grupos
automáticos no cambian el resto de la consulta.
Los diccionarios completos y los índices morfológicos quedan como recursos
de desarrollo, sin descargas al instalar.

Declare equivalencias propias en `config/domain.yaml`:

```yaml
synonyms:
  - [OC, orden de compra]
```

Los grupos del proyecto reemplazan los del idioma que se superponen. Las
frases coinciden completas y todos los términos de contenido de un reemplazo
deben existir en el corpus. Reinicie el servicio después de cambiar la
configuración léxica. Un motor nuevo empieza con cachés de consultas vacías.

## Tono de las respuestas

Lo que el asistente dice alrededor del texto del documento viene de un
**tono**, en `ipsis/recursos/tonos/<idioma>/<tono>.yaml`: `cordial` (por
defecto), `formal`, `serious`, `upbeat`, `friendly`, `empathetic` y
`direct`. Ver [personalidad.md](personalidad.md).

Cada tono tiene 19 situaciones, con 7 a 12 variantes cada una:

- motor: `greeting`, `thanks`, `farewell`, `capability`, `opening`,
  `addition`, `condition`, `exception`, `related_intro`, `missing_focus`,
  `alternatives_intro`, `no_answer` y `premise_not_found`;
- widget: `welcome`, `waiting`, `citations_hint`, `network_error`,
  `rate_limit_error` y `service_error`.

El tono **solo enmarca**: el texto del documento va literal y las citas,
debajo. Cambiar de tono no cambia el estado de la respuesta ni pide
reindexar.

**Variedad sin perder reproducibilidad.**

- En una conversación, la variante se elige por sesión, turno y situación.
  No repite la misma frase en turnos seguidos de una sesión.
- La misma sesión y el mismo turno dan siempre el mismo texto.
- Cada variante usada queda como id de plantilla (`cordial.no_answer.3`) en
  `ipsis ask --diagnostics` y en el registro de consultas.

Para cambiar textos propios del proyecto, sin tocar el paquete, usa
`config/personality.yaml`:

```yaml
tone:
  templates:
    no_answer:
    - Eso no está en el manual del equipo.
```

Cada sobrescritura pasa por las mismas reglas que los paquetes. Si no las
cumple, el motor no arranca y el error dice qué regla falló:

- una línea, de hasta 200 caracteres;
- sin dígitos, URLs, HTML, Markdown, emojis ni palabras enteras en
  mayúsculas;
- solo las variables de su situación (`{term}`, `{entity}`,
  `{assistant_name}`, `{domain_description}`);
- los conectores terminan en «:»;
- sin expresiones de la lista prohibida del idioma.

Los textos de `config/language.yaml` anteriores a los tonos
(`mensajes.sin_respuesta`, `mensajes.conectores.apertura`, `interfaz.saludo`…)
siguen funcionando: se toman como sobrescrituras del tono.
`personality.yaml` tiene prioridad sobre ellos.

## Documentos vigentes

`documents/catalog.yaml` lista lo cargado. Una entrada con `active: false`
no se indexa ni entra en el golden (hay que ejecutar `ipsis index` después de
cambiarla).

Si `ipsis load` recibe un archivo con el mismo nombre que uno ya cargado y
otro contenido:

- lo agrega como documento nuevo (`<nombre>-<hash>.<ext>`) y lo avisa;
- los dos se indexan hasta que el anterior se marque `active: false`.

## Diagnóstico (`ipsis doctor`)

`ipsis doctor` responde si el proyecto puede funcionar ahora y, si no, qué
comando ejecutar. Solo diagnostica:

- no usa la red ni carga modelos ONNX;
- no descarga ni indexa;
- no escribe nada.

Revisa, en este orden: configuración, perfil, idioma, stemmer, modelos,
índice, golden, CORS, personalidad y modo. El servicio publica
el mismo diagnóstico en `/ready`. Cada chequeo muestra una marca (con
`IPSIS_LANG=es`):

| Marca | Significado |
|---|---|
| `[OK]` | Listo. |
| `[AVISO]` | Funciona, pero algo opcional falta o merece atención. No cambia el código de salida. |
| `[ERROR]` | Impide o invalida el funcionamiento. Siempre trae una `Acción:`. |
| `[--]` | No se evaluó porque depende de un chequeo que falló. |

El resumen final cuenta errores y avisos y lista las acciones sin repetir.
El comando sale con 0 si no hay errores y con 1 si hay alguno. Fuera de un
proyecto, pide `ipsis init`.

- **Modelos:** solo mira si están completos en la caché (ONNX,
  `tokenizer.json`, `config.json`). Para probar la inferencia, usa
  `ipsis models verify`.
- **Índice:** se compara su manifiesto con el perfil (modelo, dimensión,
  payload) y con el stemmer del idioma. Para saber si el corpus cambió,
  primero compara una huella de los bytes de los documentos vigentes,
  guardada en el manifiesto: si coincide, no parsea nada. Si difiere, o el
  manifiesto es anterior y no la tiene, recalcula el hash exacto parseando y
  fragmentando, sin modelos. Si no hay índice ni documentos, es un aviso; si
  hay documentos sin indexar, el corpus cambió o el índice es incompatible,
  es un error y la acción es `ipsis index`.
- **El golden es opcional.**
  - Si falta, es un aviso.
  - Un golden cuyo corpus cambió también es un aviso, y no debe usarse para
    evaluar hasta actualizarlo (`ipsis golden validate`).
  - Un banco de regresión sirve para evaluar.
- **Idioma:**
  - Un idioma sin paquete propio es un aviso: rige el respaldo (ver
    «Idioma»).
  - Un `stemmer` que snowballstemmer no conoce es un error.
  - `stemmer: null` es válido: los términos quedan sin stem.

## Diagnóstico de una consulta (`ipsis ask --diagnostics`)

```
ipsis ask --diagnostics "¿Cada cuánto se cambia el filtro?"
```

Ejecuta la pregunta con el motor del proyecto en el mismo proceso, sin pasar
por el servicio HTTP: el servicio no publica el diagnóstico. Antes de medir,
calienta los modelos, para que las latencias sean las de operación. Muestra:

- el estado y la respuesta;
- la regla y el motivo;
- cada etapa con su latencia en ms, y el total;
- las erratas corregidas contra el corpus;
- las evidencias (documento y offsets);
- los candidatos, con su lugar en cada ranking (denso, BM25, fusión,
  reranker) y, si corre el lector, su probabilidad;
- las advertencias de la ejecución (por ejemplo, un contexto truncado).

En modo Qdrant local hay que detener `ipsis serve` antes, porque Qdrant
bloquea la carpeta del índice.

## Memoria de la conversación

**v2 todavía no usa memoria de conversación**: cada pregunta se busca por sí
sola (el plan para llevarla a v2 está en [docs/plan](../../plan/README.md)).
Los ajustes de abajo se aceptan y validan, y regirán cuando esté activa. La
memoria guarda cada conversación, por `session_id`, y la olvida tras un
tiempo sin preguntas:

```yaml
# engine.yaml
conversation:
  expiry_minutes: 30     # se olvida tras 30 minutos sin preguntas
  max_sessions: 1024     # a lo sumo estas conversaciones a la vez
```

Los paquetes distinguen `genericas` (verbos de apoyo, unidades y
cuantificadores de la pregunta como `tiempo/tempo/time`, `often`, `quantos`)
de `genericas_memoria` (solo se ignoran en la memoria de temas). Ambas listas
se pueden sobrescribir en `config/language.yaml`.

La memoria vivirá en el proceso del servicio (cada worker tendrá la suya),
guardará términos de las preguntas y de los pasajes que las respondieron,
nunca las respuestas, y se perderá al reiniciar.

## Registro de consultas y auditoría (`ipsis audit`)

El servicio puede guardar una línea JSON por consulta en
`.ipsis/logs/queries.jsonl`. Está apagado por defecto, por privacidad:

```
ipsis configure query_log.enabled=true   # y reiniciar 'ipsis serve'
ipsis audit
ipsis audit --from 2026-10-01 --to 2026-10-31
ipsis audit --trace <consulta_id>
```

- **Qué guarda (versión 2):** un `consulta_id` aleatorio, fecha UTC, duración,
  pregunta, respuesta completa, contrato de salida y diagnóstico: estado,
  regla, motivo, evidencias (documento, offsets y texto) y advertencias.
  No guarda el identificador
  de sesión ni la IP; las preguntas y los textos documentales sí se conservan.
- **Traza de ejecución:** `traza` contiene eventos ordenados con tiempos y
  estado. Cada etapa guarda su entrada y salida: pregunta corregida o
  interpretada, intención, señales, candidatos, descartes, evidencia y
  decisión. Registra las etapas omitidas y su motivo, las salidas tempranas
  y la admisión o saturación. Cada recuperación real (principal o por
  variante ortográfica) conserva pregunta, límite, filtro, modo y candidatos
  con su texto, offsets y puntuaciones. El reranker y el lector guardan las
  preguntas y pasajes exactos que recibieron y sus salidas, incluyendo el
  reranking de oraciones previo a la lectura semántica.
- **Contexto de la ejecución:** la traza del motor del proyecto conserva
  versión de Ipsis, componentes, perfil efectivo, modelos, hashes
  del corpus y léxico, y una huella de la configuración. No vuelca tokens
  ni claves del servicio. Los hashes identifican el entorno; no archivan
  todos los documentos ni garantizan reproducir exactamente la ejecución.
- **Quién escribe:** solo `POST /ask` del servicio. `ipsis ask
  --diagnostics`, `ipsis evaluate` y `ipsis benchmark` no escriben. Si
  escribir falla, la respuesta no se ve afectada; queda un aviso en el log
  del servicio. Los fallos de ejecución también dejan una entrada con
  `estado: error`, tipo de excepción y la traza parcial; se omite el mensaje
  interno de la excepción. Las trazas están aisladas entre peticiones.
- **Inspeccionar un caso:** toma el `consulta_id` de una línea JSONL y usa
  `ipsis audit --trace <consulta_id>`. Devuelve el registro original como
  JSON, sin modelos, búsquedas ni corpus; no se combina con filtros de fecha.
  Las líneas antiguas (versión 1) siguen admitidas por `ipsis audit`.
- **Qué revisa `ipsis audit`:** cuenta las consultas por estado, por regla y
  por tono, y comprueba que el texto de cada evidencia y de cada tramo siga
  en esos offsets del corpus vigente.
  - Problemas posibles: `altered`, `altered_span`, `missing_document` (el
    documento se retiró) u `out_of_range`.
  - `--from` y `--to` (fecha o ISO 8601, UTC por defecto, inclusivas)
    limitan el rango; las líneas sin fecha se excluyen y se informan.
  - Sale con 0 si todo coincide y con 1 si hay problemas, líneas ilegibles o
    no hay registro.
  - No usa modelos ni el índice.

La traza documenta pasos observables y motivos explícitos del sistema, no
razonamiento interno de un modelo. Permite auditar qué ocurrió; la
literalidad que comprueba `ipsis audit` no demuestra que la respuesta sea
correcta o completa. Conviene revisar los casos reales y convertir los
fallos encontrados en casos de regresión del banco. El JSONL es local y
editable, sin rotación automática ni protección contra alteraciones; al
activarlo, administra su acceso y conservación junto con el corpus.

## Presentación del widget

`config/styles.yaml` admite un `preset` y opciones independientes del
contenido documental:

```yaml
preset: editorial
presentation:
  density: comfortable
  citations: list          # accordion | list (las citas siempre se muestran)
  show_status_label: true
  text_align: justify      # justify | start (pasajes del documento)
```

Los presets se administran con `ipsis widget theme`, y cada valor con
`ipsis widget style show|set` (por ejemplo
`ipsis widget style set colors.accent=#0ea5e9`), o desde el panel
`/admin/panel` (pestaña Widget, «Estilo completo»). `/config` expone estos
valores para que el widget los aplique y no admite escritura; los cambios
por HTTP pasan por `/admin`, con token (ver
[personalidad.md](personalidad.md)). La clave pública del widget autoriza
consultas y no sirve para administrar.

## Snapshot efectivo

Para obtener una copia de la configuración con defaults y valores resueltos:

```bash
ipsis snapshot-config
ipsis snapshot-config --output .ipsis/production-config.yaml
```

También está disponible desde Python:

```python
from ipsis.configuracion.carga import configuracion_efectiva

snapshot = configuracion_efectiva()
```

El snapshot contiene `engine`, `assistant`, `personality`, `config_version` y
`snapshot_version`. No contiene secretos derivados.
