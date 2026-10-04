# Referencia de configuración

## Archivos de un proyecto

`ipsis init` crea la carpeta del proyecto. Todo es YAML legible y versionable,
salvo `.ipsis/`, que es generado.

```text
mi-asistente/
├── configuracion/
│   ├── asistente.yaml      # identidad, idioma, perfil, CORS, claves del widget y registro
│   ├── motor.yaml          # recuperación, componentes, Qdrant, límites y ajustes del perfil
│   ├── estilos.yaml        # tema y ubicación del widget
│   ├── personalidad.yaml   # tono de las respuestas y avatar
│   ├── dominio.yaml        # opcional: reglas y categorías propias del dominio
│   ├── idioma.yaml         # opcional: textos del paquete de idioma sobrescritos
│   ├── calibracion.yaml    # lo escribe `ipsis calibrar --aplicar`, con procedencia
│   └── avatares/           # avatares importados (.avatar.json)
├── documentos/             # archivos fuente + catalogo.yaml
├── golden/                 # golden.csv, banco/ versionado y reportes/
└── .ipsis/                   # generado: indice/ (Qdrant, estadísticas, manifiesto) y registros/
```

| Archivo | Se edita con | Detalle |
|---|---|---|
| `asistente.yaml` | `ipsis configurar clave=valor` | esta guía |
| `motor.yaml` | a mano | esta guía; los umbrales viven en el perfil y en `calibracion.yaml` |
| `estilos.yaml` | `ipsis widget tema`, panel `/admin` | [web.md](web.md) |
| `personalidad.yaml` | `ipsis personalidad`, panel `/admin` | [personalidad.md](personalidad.md) |
| `calibracion.yaml` | `ipsis calibrar --aplicar` | [metodología](../metodologia/calibracion.md) |

## Versionado

`asistente.yaml` y `motor.yaml` declaran `config_version`. La versión vigente
es la `4`.

- Un archivo sin `config_version` se lee como versión 0 y se migra paso a
  paso hasta la 4; cualquier comando `ipsis` lo hace al cargar.
- La validación rechaza claves desconocidas y una versión superior a la
  soportada.

| Versión | Qué cambió |
|---|---|
| 2 | El reranker se elige solo con `componentes.reranker` |
| 3 | `dominio.yaml` reemplaza a los perfiles de dominio; `perfil` pasa a ser el perfil de instalación (los proyectos v2 quedan en `light`); sin torch; `.cache/` pasa a `.ipsis/` |
| 4 | La política `cascada_v1` reemplaza a la anterior; los umbrales pasan al perfil y a `calibracion.yaml` |

La configuración ya validada puede cargarse desde Python:

```python
from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto

motor = cargar_proyecto()
dominio = cargar_dominio()
```

## Componentes

La sección `componentes` selecciona implementaciones por nombre:

```yaml
componentes:
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
  abstention_policy: cascada_v1
```

El reranker y el lector los define el perfil (`ipsis perfil mostrar`). Un valor `null` desactiva un componente opcional. Una implementación puede
recibir opciones usando la forma extendida:

```yaml
componentes:
  fusion:
    nombre: rrf
    k: 60
```

El registry se puede usar desde una integración:

```python
from ipsis.nucleo.contratos import RegistroComponentes
from ipsis.aplicacion.registro_base import registrar_componentes_base

registro = registrar_componentes_base(RegistroComponentes())
fusion = registro.crear("fusion", "rrf", k=60)
```

Los adaptadores base disponibles no descargan modelos durante el registro.
`onnx` abre la sesión del modelo solo al usarlo por primera vez. La conexión
a Qdrant y los rerankers se configura desde el servicio porque depende del
índice, la colección y los recursos disponibles.

### Backend de recuperación

`qdrant` es el único backend soportado. `recuperacion.modo` permite elegir
`vectorial` o `hibrida`; ambos conservan el mismo contrato y requieren volver a
indexar cuando cambia la representación persistida.

## Perfil de instalación

El perfil activo está en `configuracion/asistente.yaml::perfil` (`light`,
`medium` o `heavy`). `bm25` es solo un perfil de diagnóstico de
`ipsis benchmark`, no se instala.

```
ipsis perfil mostrar           # perfil, modelos, presupuesto p95, índice y calibración
ipsis perfil cambiar medium    # cambia solo asistente.yaml::perfil
```

`ipsis perfil cambiar` no descarga modelos, no indexa, no calibra y no borra
nada. Se conservan `ajustes_perfil`, el índice y `calibracion.yaml`. Antes de
escribir, valida los `ajustes_perfil` del proyecto contra el perfil destino.
Repetir el perfil activo no hace nada.

- **light ↔ medium:** usan el mismo modelo denso (e5-small, 384), así que el
  índice sirve para ambos.
- **heavy:** usa e5-base (768) y necesita su propio índice (`ipsis indexar`).
  Cada modelo denso vive en su colección: el índice anterior se conserva, y
  volver al perfil anterior lo hace compatible otra vez sin reindexar.
- **Compatibilidad del índice:** se decide por el manifiesto
  (`.ipsis/indice/<coleccion>.manifiesto.json`), con el modelo denso, la
  dimensión y la versión del payload. No se decide por el nombre del perfil.
- **Calibración:** cualquier cambio de perfil la invalida, porque su
  procedencia registra perfil, modelos y corpus. El motor la ignora y rigen
  los umbrales del perfil. El archivo se conserva para auditoría. Para
  recuperarla: `ipsis calibrar --aplicar`.

## Modelos

Los modelos ONNX viven en una caché global por usuario, compartida por todos
los proyectos. Por defecto es `~/.cache/ipsis/models`, y se cambia
con `IPSIS_MODELS_DIR`. Usa el formato de `huggingface_hub`. Nada se descarga
dentro del proyecto. Con `HF_HUB_OFFLINE=1` nunca se usa la red.

```
ipsis modelos listar                     # modelos del perfil activo
ipsis modelos descargar                  # descarga los que falten del perfil activo
ipsis modelos descargar --perfil heavy   # prepara otro perfil sin activarlo
ipsis modelos verificar                  # archivos completos e inferencia de prueba
ipsis modelos exportar org/modelo --int8 # desarrollo: convierte a ONNX
```

- **`listar`** muestra, para cada modelo del perfil activo:
  - rol, repositorio, licencia (y atribución, si el catálogo la registra) y
    parámetros;
  - el ONNX que corresponde a la CPU actual (x86_64 o arm64);
  - si está en la caché, y cuánto ocupa.

  Todo sale del catálogo (`ipsis/modelos/catalogo.py`). light usa solo el
  denso; medium y heavy usan denso, reranker y lector.
- **`descargar`** baja solo lo que falta. Un modelo compartido entre perfiles,
  como e5-small (light y medium) o el lector (medium y heavy), se descarga una
  sola vez.
  - Con `--perfil` no cambia el perfil activo, y funciona fuera de un
    proyecto.
  - Sin `--perfil` necesita el proyecto (`ipsis init`).
  - `bm25` no es instalable.
- **`verificar`** solo revisa el perfil activo y nunca descarga. Por modelo:
  - los archivos requeridos (ONNX, `tokenizer.json`, `config.json`);
  - que la sesión de onnxruntime cargue;
  - una inferencia mínima: vector normalizado de la dimensión esperada,
    logit finito o lectura válida.

  El estado de cada modelo es `OK`, `FALTA` (acción: `ipsis modelos
  descargar`), `NO CARGA` (archivo presente pero inválido) o `FALLA`
  (inferencia inválida). Termina con 0 solo si todos dan `OK`.
- **`exportar`** es solo para desarrollo. Necesita el extra `[exportar]`
  (`pip install "ipsis[exportar]"`, con `optimum-onnx` y `torch`). La
  producción corre sin torch.
  - Deja `exportados/<org>--<modelo>/model.onnx` en la carpeta actual y, con
    `--int8`, también `model_int8.onnx`. Ese archivo usa la cuantización
    dinámica post-entrenamiento de onnxruntime (`quantize_dynamic`).
  - No pisa una exportación anterior ni toca la caché.
  - No registra el modelo en el catálogo ni en los perfiles: adoptarlo es
    otro paso.

## Idioma

`asistente.yaml::idioma` es un código ISO 639, por ejemplo `es`, `en` o
`pt-br`. `es`, `en` y `pt` tienen paquete propio: stemmer, stopwords,
números, fechas, conectores, mensajes e interfaz. Una variante regional
(`pt-br`, `es-cl`) usa el paquete de su idioma.

Otro código funciona con un respaldo:
- solo las reglas universales (fechas numéricas, montos, artículos);
- términos sin stem;
- la interfaz y los tonos de `en`, que se pueden traducir con
  `configuracion/idioma.yaml` (interfaz) y
  `configuracion/personalidad.yaml` (tono).

`ipsis init` y `ipsis configurar idioma=` lo avisan, y `ipsis doctor` lo marca
como aviso.

## Tono de las respuestas

Lo que el asistente dice alrededor del texto del documento viene de un
**tono**, en `ipsis/recursos/tonos/<idioma>/<tono>.yaml`: `cordial` (por
defecto), `formal`, `serio`, `animoso`, `cercano`, `empatico` y `directo`.
Ver [personalidad.md](personalidad.md).

Cada tono tiene 18 situaciones con 5 variantes cada una:
- motor: saludo, agradecimiento, despedida, capacidad, apertura,
  complemento, condición, excepción, relacionado, término ausente, sin
  respuesta y premisa no encontrada;
- widget: bienvenida, esperando, invitación a revisar las citas y errores
  de red, de límite y de servicio.

El tono **solo enmarca**: el texto del documento va literal y las citas,
debajo. Cambiar de tono no cambia el estado de la respuesta, ni pide
reindexar ni recalibrar.

**Variedad sin perder reproducibilidad.**
- En una conversación, la variante se elige por sesión, turno y situación.
  No repite la misma frase en turnos seguidos de una sesión.
- La misma sesión y el mismo turno dan siempre el mismo texto.
- Cada variante usada queda como `plantilla_id` (`cordial.sin_respuesta.3`)
  en `ipsis preguntar --diagnostico` y en el registro de consultas.

Para cambiar textos propios del proyecto, sin tocar el paquete, usa
`configuracion/personalidad.yaml`:

```yaml
tono:
  plantillas:
    sin_respuesta:
    - Eso no está en el manual del equipo.
```

Cada sobrescritura pasa por las mismas reglas que los paquetes. Si no las
cumple, el motor no arranca y el error dice qué regla falló:
- una línea, de hasta 200 caracteres;
- sin dígitos, URLs, HTML, Markdown, emojis ni palabras enteras en
  mayúsculas;
- solo las variables de su situación (`{termino}`, `{entidad}`,
  `{nombre_asistente}`, `{descripcion_dominio}`);
- los conectores terminan en «:»;
- sin expresiones de la lista prohibida del idioma.

Los textos de `configuracion/idioma.yaml` anteriores a los tonos
(`mensajes.sin_respuesta`, `mensajes.conectores.apertura`, `interfaz.saludo`…)
siguen funcionando: se toman como sobrescrituras del tono.
`personalidad.yaml` tiene prioridad sobre ellos.

## Documentos vigentes

`documentos/catalogo.yaml` lista lo cargado. Una entrada con `vigente: false`
no se indexa ni entra en el golden (hay que ejecutar `ipsis indexar` después de
cambiarla).

Si `ipsis cargar` recibe un archivo con el mismo nombre que uno ya cargado y
otro contenido:
- lo agrega como documento nuevo (`<nombre>-<hash>.<ext>`) y lo avisa;
- los dos se indexan hasta que el anterior se marque `vigente: false`.

## Diagnóstico (`ipsis doctor`)

`ipsis doctor` responde si el proyecto puede funcionar ahora y, si no, qué
comando ejecutar. Solo diagnostica:
- no usa la red ni carga modelos ONNX;
- no descarga, no indexa ni calibra;
- no escribe nada.

Revisa, en este orden: configuración, perfil, idioma, stemmer, modelos,
índice, calibración, golden, CORS, personalidad y modo. El servicio publica
el mismo diagnóstico en `/ready`. Cada chequeo muestra una marca:

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
  `ipsis modelos verificar`.
- **Índice:** se compara su manifiesto con el perfil (modelo, dimensión,
  payload) y con el stemmer del idioma. Para saber si el corpus cambió, primero
  compara una huella de los bytes de los documentos vigentes, guardada en el
  manifiesto: si coincide, no parsea nada. Si difiere, o el manifiesto es
  anterior y no la tiene, recalcula el hash exacto parseando y fragmentando,
  sin modelos. Si no hay índice ni documentos, es
  un aviso; si hay documentos sin indexar, el corpus cambió o el índice es
  incompatible, es un error y la acción es `ipsis indexar`.
- **Calibración y golden son opcionales.**
  - Si faltan, es un aviso y rigen los umbrales del perfil.
  - Una calibración obsoleta o no habilitada es un aviso; la acción es
    `ipsis calibrar --aplicar`.
  - Un golden cuyo corpus cambió también es un aviso, y no debe usarse para
    evaluar ni calibrar hasta actualizarlo (`ipsis golden validar`).
  - Un banco de regresión sirve para evaluar, no para calibrar.
- **Idioma:**
  - Un idioma sin paquete propio es un aviso: rige el respaldo (ver
    «Idioma»).
  - Un `stemmer` que snowballstemmer no conoce también es un error.
  - `stemmer: null` es válido: los términos quedan sin stem.

## Diagnóstico de una consulta (`ipsis preguntar --diagnostico`)

```
ipsis preguntar --diagnostico "¿Cada cuánto se cambia el filtro?"
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
- el tono y los `plantilla_id` usados.

En modo Qdrant local hay que detener `ipsis servir` antes, porque Qdrant
bloquea la carpeta del índice.

## Registro de consultas y auditoría (`ipsis auditar`)

El servicio puede guardar una línea JSON por consulta en
`.ipsis/registros/consultas.jsonl`. Está apagado por defecto, por privacidad:

```
ipsis configurar registro.activo=true   # y reiniciar 'ipsis servir'
ipsis auditar
ipsis auditar --desde 2026-10-01 --hasta 2026-10-31
```

- **Qué guarda:** la pregunta, el estado, la regla, el motivo, el perfil, las
  señales de la política, el tono y los `plantilla_id` usados, las
  evidencias (documento, offsets y texto) y el tramo exacto. No guarda la
  sesión ni la IP.
- **Quién escribe:** solo `/consultar` del servicio. `ipsis preguntar
  --diagnostico`, `ipsis evaluar` y `ipsis benchmark` no escriben. Si escribir
  falla, la respuesta no se ve afectada; queda un aviso en el log del
  servicio.
- **Qué revisa `ipsis auditar`:** cuenta las consultas por estado, por regla y
  por tono,
  y comprueba que el texto de cada evidencia y de cada tramo siga en esos
  offsets del corpus vigente.
  - Problemas posibles: `alterada`, `tramo_alterado`, `documento_ausente`
    (el documento se retiró) o `fuera_de_rango`.
  - `--desde` y `--hasta` (fecha o ISO 8601, UTC por defecto, inclusivas)
    limitan el rango; las líneas sin fecha se excluyen y se informan.
  - Sale con 0 si todo coincide y con 1 si hay problemas, líneas ilegibles o
    no hay registro.
  - No usa modelos ni el índice.

## Presentación del widget

`configuracion/estilos.yaml` admite un `preset` y opciones independientes del
contenido documental:

```yaml
preset: editorial
presentacion:
  densidad: comoda
  citas: lista          # acordeon | lista (las citas siempre se muestran)
  mostrar_etiqueta_estado: true
```

Los presets se administran con `ipsis widget tema`, y cada valor con
`ipsis widget estilo mostrar|cambiar` (por ejemplo
`ipsis widget estilo cambiar colores.acento=#0ea5e9`), o desde el panel
`/admin/panel` (pestaña Widget, «Estilo completo»). `/config` expone estos valores para que el widget los aplique
y no admite escritura; los cambios por HTTP pasan por `/admin`, con token (ver
[personalidad.md](personalidad.md)). La clave pública del widget autoriza
consultas y no sirve para administrar.

## Snapshot efectivo

Para obtener una copia de la configuración con defaults y valores resueltos:

```bash
ipsis snapshot-config
ipsis snapshot-config --salida .ipsis/config-produccion.yaml
```

También está disponible desde Python:

```python
from ipsis.configuracion.carga import configuracion_efectiva

snapshot = configuracion_efectiva()
```

El snapshot contiene `motor`, `dominio`, `config_version` y
`snapshot_version`. No contiene secretos derivados.
