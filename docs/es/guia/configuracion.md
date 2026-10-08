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
│   ├── calibration.yaml    # lo escribe `ipsis calibrate --apply`, con procedencia
│   └── avatars/            # avatares importados (.avatar.json)
├── documents/              # archivos fuente + catalog.yaml
├── golden/                 # golden.csv, bank/ versionado y reports/
└── .ipsis/                 # generado: index/ (Qdrant, estadísticas, manifiesto) y logs/
```

| Archivo | Se edita con | Detalle |
|---|---|---|
| `assistant.yaml` | `ipsis configure clave=valor` | esta guía |
| `engine.yaml` | a mano | esta guía; los umbrales viven en el perfil y en `calibration.yaml` |
| `styles.yaml` | `ipsis widget theme`, `ipsis widget style`, panel `/admin` | [web.md](web.md) |
| `personality.yaml` | `ipsis personality`, panel `/admin` | [personalidad.md](personalidad.md) |
| `calibration.yaml` | `ipsis calibrate --apply` | [metodología](../../methodology/calibration.md) (en inglés) |

### `assistant.yaml`

```yaml
config_version: 5
assistant_name: "Asistente de soporte"
domain_description: "los manuales del producto"
language: es              # código ISO 639: es, en, pt, pt-br...
profile: medium           # light | medium | heavy
cors_origins: []          # orígenes que pueden insertar el widget
widget_keys: []           # claves públicas opcionales del widget
query_log:
  enabled: false          # .ipsis/logs/queries.jsonl, para `ipsis audit`
posture:
  mode: proactive         # proactive | strict: ver «Cuando la respuesta no está»
  max_alternatives: 3     # de 1 a 5
```

## Versionado

`assistant.yaml` y `engine.yaml` declaran `config_version`. La versión vigente
es la `5`.

- Cualquier comando `ipsis` migra un proyecto anterior al cargar: un archivo
  sin `config_version` se lee como versión 0 y sube paso a paso.
- La validación rechaza claves desconocidas y una versión superior a la
  soportada.

| Versión | Qué cambió |
|---|---|
| 2 | El reranker se elige solo con `components.reranker` |
| 3 | `domain.yaml` reemplaza a los perfiles de dominio; `profile` pasa a ser el perfil de instalación (los proyectos v2 quedan en `light`); sin torch; `.cache/` pasa a `.ipsis/` |
| 4 | La política `cascade_v1` reemplaza a la anterior; los umbrales pasan al perfil y a `calibration.yaml` |
| 5 | Carpetas, archivos, claves y valores en inglés (`config/`, `documents/`, `assistant.yaml`, `assistant_name`…). Los proyectos creados con nombres en español se mueven y reescriben solos, conservando sus comentarios |

La configuración ya validada puede cargarse desde Python:

```python
from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto

motor = cargar_proyecto()
asistente = cargar_dominio()
```

Estas funciones devuelven los nombres internos que usa el motor; los
archivos en disco usan los nombres en inglés de esta guía.

## Componentes

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
  intent_classifier: rules
  answer_extractor: sentence_selector
  evidence_verifier: literal_offsets
  response_renderer: templates
  abstention_policy: cascade_v1
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

El perfil activo está en `config/assistant.yaml::profile` (`light`,
`medium` o `heavy`). `bm25` es solo un perfil de diagnóstico de
`ipsis benchmark`, no se instala.

```
ipsis profile show         # perfil, modelos, presupuesto p95, índice y calibración
ipsis profile set medium   # cambia solo assistant.yaml::profile
```

`ipsis profile set` no descarga modelos, no indexa, no calibra y no borra
nada. Se conservan `profile_overrides`, el índice y `calibration.yaml`. Antes
de escribir, valida los `profile_overrides` del proyecto contra el perfil
destino. Repetir el perfil activo no hace nada.

- **light ↔ medium:** usan el mismo modelo denso (e5-small, 384), así que el
  índice sirve para ambos.
- **heavy:** usa e5-base (768) y necesita su propio índice (`ipsis index`).
  Cada modelo denso vive en su colección: el índice anterior se conserva, y
  volver al perfil anterior lo hace compatible otra vez sin reindexar.
- **Compatibilidad del índice:** se decide por el manifiesto
  (`.ipsis/index/<coleccion>.manifest.json`), con el modelo denso, la
  dimensión y la versión del payload. No se decide por el nombre del perfil.
- **Calibración:** cualquier cambio de perfil la invalida, porque su
  procedencia registra perfil, modelos y corpus. El motor la ignora y rigen
  los umbrales del perfil. El archivo se conserva para auditoría. Para
  recuperarla: `ipsis calibrate --apply`.

## Modelos

Los modelos ONNX viven en una caché global por usuario, compartida por todos
los proyectos. Por defecto es `~/.cache/ipsis/models`, y se cambia con
`IPSIS_MODELS_DIR`. Usa el formato de `huggingface_hub`. Nada se descarga
dentro del proyecto. Con `HF_HUB_OFFLINE=1` nunca se usa la red.

```
ipsis models list                     # modelos del perfil activo
ipsis models download                 # descarga los que falten del perfil activo
ipsis models download --profile heavy # prepara otro perfil sin activarlo
ipsis models verify                   # archivos completos e inferencia de prueba
ipsis models export org/modelo --int8 # desarrollo: convierte a ONNX
```

- **`list`** muestra, para cada modelo del perfil activo:
  - rol, repositorio, licencia (y atribución, si el catálogo la registra) y
    parámetros;
  - el ONNX que corresponde a la CPU actual (x86_64 o arm64);
  - si está en la caché, y cuánto ocupa.

  Todo sale del catálogo (`ipsis/modelos/catalogo.py`). light usa solo el
  denso; medium y heavy usan denso, reranker y lector.
- **`download`** baja solo lo que falta. Un modelo compartido entre perfiles,
  como e5-small (light y medium) o el lector (medium y heavy), se descarga una
  sola vez.
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
  (`pip install "ipsis[export]"`, con `optimum-onnx` y `torch`). La
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

### Respaldo de intenciones

El paquete contiene `intenciones.<nombre>.ejemplos` y ajustes por modelo en
`respaldo_intencion`. Se sobrescriben en `config/language.yaml`:

```yaml
respaldo_intencion:
  intfloat/multilingual-e5-small:
    similitud: 0.85
    margen: 0.0
    habilitadas: [fin, procedimiento]
```

Son los valores medidos para español. Inglés usa 0.87 y `[fin]`; portugués,
0.895 y `[procedimiento]`, ambos con margen estrictamente positivo. Los
patrones mantienen prioridad. BM25 y modelos sin ajustes medidos no usan
el respaldo; E5 base no tiene ajustes predeterminados. Cambiar los ejemplos
o valores exige reconstruir el motor y regenerar la calibración. Antes de
activar categorías nuevas, mídalas en dev. Estos valores no son los umbrales
de la política que decide si puede responder.

### Grupos de sinónimos

Español, inglés y portugués usan las tablas filtradas de WordNet incluidas
en el paquete para ampliar la recuperación BM25, reutilizando el vector
denso original. Solo se expande una palabra
ausente del corpus, con un único sentido después del stemming; las palabras
de la relación y las correcciones manuales tienen prioridad. Los grupos
automáticos no cambian la validación del foco ni los umbrales de aceptación.
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
configuración léxica. Un motor nuevo empieza con memoria de conversación y
cachés de consultas vacías. La procedencia de calibración incluye
`lexical_hash`: una huella ausente o diferente invalida la calibración
anterior. `ipsis doctor` lo informa; recalibre con el golden del proyecto.

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
debajo. Cambiar de tono no cambia el estado de la respuesta, ni pide
reindexar ni recalibrar.

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
- no descarga, no indexa ni calibra;
- no escribe nada.

Revisa, en este orden: configuración, perfil, idioma, stemmer, modelos,
índice, calibración, golden, CORS, personalidad y modo. El servicio publica
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
- **Calibración y golden son opcionales.**
  - Si faltan, es un aviso y rigen los umbrales del perfil.
  - Una calibración obsoleta o no habilitada es un aviso; la acción es
    `ipsis calibrate --apply`.
  - Un golden cuyo corpus cambió también es un aviso, y no debe usarse para
    evaluar ni calibrar hasta actualizarlo (`ipsis golden validate`).
  - Un banco de regresión sirve para evaluar, no para calibrar.
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
- la regla que decidió, el motivo y el perfil;
- cada etapa con su latencia en ms, y el total;
- las señales que vio la política (`s_ret`, `s_oov`, `s_foco`, `s_cov`,
  `s_rr`, `s_qa`, `dominio`);
- los términos foco encontrados y ausentes en la oración evaluada, y los
  términos de la pregunta que no están en el corpus;
- el tramo exacto que marcó el lector, con sus offsets;
- las evidencias;
- el tono y los ids de plantilla usados.

En modo Qdrant local hay que detener `ipsis serve` antes, porque Qdrant
bloquea la carpeta del índice.

## Memoria de la conversación

Las preguntas de seguimiento («¿y en el extranjero?») heredan el tema de la
conversación (ver la [arquitectura](../../architecture.md#understanding-the-question),
en inglés). El motor guarda cada conversación en memoria, por `session_id`, y
la olvida tras un tiempo sin preguntas:

```yaml
# engine.yaml
conversation:
  expiry_minutes: 30     # se olvida tras 30 minutos sin preguntas
  max_sessions: 1024     # a lo sumo estas conversaciones a la vez
```

Los paquetes distinguen `genericas` (se ignoran en foco/selección de respuesta)
de `genericas_memoria` (solo se ignoran en la memoria de temas). Esta última
excluye `tiempo/tempo` del núcleo sin cambiar su peso original al seleccionar
una respuesta. Ambas listas se pueden sobrescribir en `config/language.yaml`.

La memoria vive en el proceso del servicio (cada worker tiene la suya),
guarda términos de las preguntas y de los pasajes que las respondieron, nunca
las respuestas, y se pierde al reiniciar. El widget empieza una conversación
nueva en cada carga de página.

## Cuando la respuesta no está (postura)

Cuando los documentos no tienen lo pedido, el asistente lo dice. Con la
postura **proactiva** (la de fábrica) además ofrece hasta `max_alternatives`
pasajes parecidos que sí están en los documentos, bajo una frase fija del
tono que dice que no son lo pedido:

```
No encontré "TP-500" en los documentos disponibles.

Te muestro lo más parecido que sí aparece en los documentos:

El taladro percutor TP-600 tiene un motor de 800 W … (Fuente: Catálogo …).
El taladro percutor TP-400 tiene un motor de 600 W … (Fuente: Catálogo …).
```

```
ipsis configure posture.mode=strict          # solo «no está»
ipsis configure posture.max_alternatives=2
```

- **Cuándo:** solo tras una premisa falsa (una entidad de la pregunta no está
  en los documentos) o una pregunta sin respuesta. Las preguntas fuera de
  dominio, las respuestas relacionadas y los turnos conversacionales nunca
  traen alternativas. Con los perfiles incluidos, en la práctica solo tras
  una premisa falsa cuya entidad tiene familia en los documentos (abajo).
- **Qué se muestra:** cada alternativa es un párrafo literal de los
  documentos con su cita, verificado como la evidencia de una respuesta. No
  se genera nada. El estado sigue siendo `no_answer`: las alternativas viajan
  en su propio campo `alternatives` de `/ask` y nunca cuentan como respuesta.
- **Cómo se eligen:** con los metadatos que el índice ya guarda de cada
  fragmento, sin otro modelo. Cada párrafo candidato recibe una afinidad,
  la media ponderada de seis señales; los pesos y el umbral son parte del
  perfil de instalación
  ([ADR 0008](../../decisions/0008-proactive-posture-and-metadata-similarity.md)):

  | Señal | Valor para el párrafo | Peso incluido |
  |---|---|---|
  | `family` | 1 si tiene una entidad de la familia de la ausente: mismo tipo y forma («TP-400» para «TP-500»). Solo tienen familia los tipos que declara domain.yaml: las medidas del núcleo («90 días», «20 %») aparecen en documentos sin relación | 1 |
  | `terms` | parte de las palabras de la pregunta que tiene (sobre todas, también las ausentes; las de la propia entidad no cuentan) | 0 |
  | `section`, `keywords` | la misma parte sobre su título de documento y sección, o sus palabras clave | 0 |
  | `category` | 1 si es de la categoría de la pregunta en la taxonomía del proyecto | 0 |
  | `similarity` | coseno denso con la pregunta, desde el piso del modelo | 0 |

  Los pesos se eligieron con el banco de alternativas para una precisión de
  al menos 0,9 y el margen de umbrales más ancho: solo sobrevivió la
  familia. Las palabras, secciones o categorías por sí solas también
  ofrecían pasajes sin relación («¿A qué distancia está la Luna?» → «trabajo
  a distancia»). Si la entidad ausente tiene familia, solo se ofrecen
  párrafos de esa familia. Las alternativas no alimentan la memoria de la
  conversación.
- **Tus códigos:** un código de producto es una entidad solo si
  `domain.yaml` lo declara (`regex_extractors`, por ejemplo
  `'\b(?P<pre>[A-Z]{2})-(?P<num>\d{1,3})\b'` con `transform: {pre:
  minusculas}`). Sin eso, un código ausente no tiene familia ni
  alternativas. La señal de categoría necesita al menos dos categorías
  propias en `taxonomy`.
- **Ajuste:** `profile_overrides.alternatives.threshold` y
  `profile_overrides.alternatives.weights` en `engine.yaml`. `ipsis ask
  --diagnostics` muestra cada alternativa ofrecida o descartada, con su
  afinidad y sus señales.

## Registro de consultas y auditoría (`ipsis audit`)

El servicio puede guardar una línea JSON por consulta en
`.ipsis/logs/queries.jsonl`. Está apagado por defecto, por privacidad:

```
ipsis configure query_log.enabled=true   # y reiniciar 'ipsis serve'
ipsis audit
ipsis audit --from 2026-10-01 --to 2026-10-31
```

- **Qué guarda:** la pregunta, el estado, la regla, el motivo, el perfil, las
  señales de la política, el tono y los ids de plantilla usados, las
  evidencias (documento, offsets y texto) y el tramo exacto. No guarda la
  sesión ni la IP.
- **Quién escribe:** solo `POST /ask` del servicio. `ipsis ask
  --diagnostics`, `ipsis evaluate` y `ipsis benchmark` no escriben. Si
  escribir falla, la respuesta no se ve afectada; queda un aviso en el log
  del servicio.
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
