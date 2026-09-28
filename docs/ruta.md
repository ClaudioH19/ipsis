# Ruta de trabajo

Este documento reemplaza el orden de las fases 3 a 7 de [PLAN_V2.md](../PLAN_V2.md).
La visión, las restricciones (respuestas literales, sin LLM) y los ADR no cambian.

Principio rector: **primero algo que funcione bien, después optimizar**. No se
definen perfiles de instalación ni extras todavía; se decidirán con números.

## Estado de partida

- El registry y los contratos de [rag/componentes.py](../rag/componentes.py) existen,
  pero **ningún código de ejecución los consume**. `consultar()` en
  [rag/servicio/api.py](../rag/servicio/api.py) es un flujo de unas 200 líneas que
  llama directamente a Qdrant y a SentenceTransformers.
- La sección `componentes:` de `motor.yaml` es decorativa: el comportamiento real
  lo deciden `recuperacion.modo` y el código.
- Los esquemas V2 (`ChunkRecord`, `EvidenceSpan`...) no se usan; el pipeline
  trabaja con diccionarios de payload.
- La abstención, que es la lógica más valiosa del proyecto, no tiene contrato.
- Las importaciones de `qdrant_client` y `sentence_transformers` ya son diferidas
  en `rag/corpus.py` e `rag/indice.py`, lo que facilita el trabajo de abajo.

---

## Trabajo 1: conectar el registry al pipeline

**Objetivo.** Que cambiar un componente sea cambiar una línea de `motor.yaml`, y
que el flujo de `/consultar` no conozca Qdrant ni ningún modelo concreto.
**El comportamiento observable no cambia**: mismas respuestas, mismo contrato HTTP.

### 1.0 Red de seguridad (antes de tocar nada)

- Dejar la suite corriendo en el entorno de desarrollo (`.venv`); hoy no se
  verificó su estado.
- Añadir pruebas de caracterización sobre un corpus sintético pequeño: para un
  conjunto fijo de preguntas (con respuesta, relacionada, fuera de dominio,
  premisa falsa, saludo), congelar `estado`, `plan`, texto y offsets de la
  respuesta actual. Son la definición de "no cambió nada".

### 1.1 Rediseñar el contrato de recuperación

El protocolo actual, `recuperar(consulta, limite) -> list[RetrievalCandidate]`,
no alcanza para lo que `consultar()` hace de verdad:

1. una consulta densa solo para obtener la **señal de abstención** (`s1`, `s2`);
2. la recuperación de producción (híbrida);
3. recuperaciones dirigidas por **filtro de entidad**.

Cambios propuestos:

- `Retriever.recuperar(consulta, limite, filtro: FiltroEntidad | None = None) -> ResultadoRecuperacion`.
- `ResultadoRecuperacion` contiene los candidatos y `SenalesRecuperacion`
  (`confianza_top1`, `margen_top1_top2`, y opcionalmente `cobertura_lexica`).
  La abstención deja de leer "score denso" y lee una **señal de confianza
  normalizada** que cada retriever sabe producir. Para el retriever Qdrant es el
  coseno denso de siempre (sin cambio); para el del Trabajo 2 será otra cosa.
- `FiltroEntidad` es un tipo propio (`valor_norm`), no `models.Filter` de Qdrant.
- El retriever es dueño de su índice: expone `n_chunks()`, `warmup()`,
  `inventario_entidades()` y `estadisticas_lexico()`. Hoy esos tres datos se
  cargan aparte con rutas de `.cache/vocab_bm25` acopladas al nombre de la
  colección.

### 1.2 Nuevo protocolo `AbstentionPolicy`

Extraer de [rag/servicio/pipeline.py](../rag/servicio/pipeline.py) la decisión en
capas (fuera de dominio, premisa, zona gris, confianza alta) detrás de un
contrato: entrada `SenalesRecuperacion` + candidatos + `QueryAnalysis`, salida
`DecisionAbstencion`. La implementación actual se registra como
`layered_v1`. Las funciones existentes se mueven, no se reescriben.

### 1.3 Frontera de tipos

- Adaptadores únicos `chunk_desde_payload()` / `payload_desde_chunk()`.
- `ChunkRecord` no tiene hoy `doc_titulo`, `version` ni las banderas
  `tiene_excepcion` / `tiene_condicion` / `entidades` que el pipeline consume.
  **Decisión abierta:** añadirlos como campos tipados (recomendado, `schema_version`
  se mantiene en 1 porque `ChunkRecord` aún no se persiste) o dejarlos en `metadata`.
- En este trabajo los tipos se aplican **en la frontera**: retriever, extractor y
  verificador hablan `ChunkRecord`/`EvidenceSpan`. Las funciones internas de
  redacción pueden seguir usando diccionarios; se migran cuando se toquen.

### 1.4 Un `Motor` que orquesta

Crear `rag/servicio/motor.py`:

- `Motor.desde_configuracion(cfg)` resuelve cada componente por nombre con el
  registry y **falla al arrancar** (y en `rag doctor`) si un nombre no existe o
  sus opciones son inválidas.
- `Motor.consultar(pregunta, id_sesion) -> AssistantResult`, con el flujo actual
  partido en pasos pequeños y con un `diagnostico` por etapa (latencias,
  candidatos, decisión y motivo). Esa observabilidad sale gratis al hacer el corte.
- `api.py` queda con seguridad, admisión, mapeo `AssistantResult` ->
  `RespuestaConsulta` (contrato V1 intacto) y endpoints estáticos.

### 1.5 Estado global y arranque

- Reemplazar `estado` global y `@app.on_event("startup")` por
  `crear_app(motor) -> FastAPI`. Es lo que permite probar sin Qdrant y, más
  adelante, servir varios corpus en un proceso.
- `_cargar_plantillas` usa `lru_cache` con la ruta relativa `configuracion/textos.yaml`,
  que depende del directorio de trabajo, y `configurar_perfil` es global. Inyectar
  ambos en el `Motor`.
- Eliminar la duplicación entre `recuperacion.modo`/`recuperacion.reranker` y
  `componentes.*`: una sola fuente de verdad, con migración idempotente de
  `config_version`.

### 1.6 Pruebas

- Pruebas de contrato parametrizadas por tipo de componente: cualquier
  implementación registrada debe cumplir orden determinista y offsets exactos.
- Prueba de intercambio: registrar un `Retriever` falso en memoria y ejecutar
  `Motor.consultar` de punta a punta **sin Qdrant ni torch**.
- Las pruebas de caracterización de 1.0 siguen verdes.

### Hecho cuando

- `grep` no encuentra `qdrant`, `sentence_transformers` ni `ColeccionQdrant` en
  `api.py`, `pipeline.py` ni `motor.py`.
- Cambiar `componentes.fusion` o `componentes.retriever` altera el comportamiento
  real (hoy no lo hace).
- Suite completa y caracterización en verde.

### Fuera de alcance

Nuevas técnicas, recalibración de umbrales, cambios de widget y el prefijo
`passage:` de E5 (requiere reindexar y se trata aparte, con medición).

**Tamaño estimado:** M–L. Lo más delicado es 1.1 (el contrato) y 1.2.

---

## Trabajo 2: retriever léxico sobre SQLite FTS5

**Objetivo.** Una segunda implementación completa de `Retriever` + almacén de
índice que **no necesita Qdrant ni modelo de embeddings**. Es la prueba de que
la abstracción del Trabajo 1 es real, da una línea base BM25 contra la cual
medir lo que aporta la búsqueda densa, y resuelve el bloqueo de carpeta del
Qdrant local (SQLite admite varios lectores).

No es un "perfil": es otro valor de `componentes.retriever` (`sqlite_fts`).
Las dependencias pesadas siguen en el `pyproject` por ahora; lo que se exige es
que el código **no las importe** en este camino. Moverlas a extras se decide
después, con datos.

Verificado en este entorno: SQLite 3.45.3 con FTS5, y el tokenizer
`unicode61 remove_diacritics 2` ya encuentra "año" con la consulta "ano".

### 2.1 Almacén de índice

Un archivo `.cache/indice/<nombre>.sqlite` con:

- `chunks`: `chunk_id`, `doc_id`, texto, offsets, sección y el payload completo
  en JSON (lo que hoy devuelve Qdrant con cada punto);
- `chunks_fts`: tabla virtual FTS5 con `unicode61 remove_diacritics 2`;
- `entidades(valor_norm, chunk_id)`: sustituye el filtro `entidades[].valor_norm`
  de Qdrant y el inventario de entidades;
- `manifiesto`: `schema_version`, chunker, `pipeline_version`, hash del corpus,
  fecha, y estadísticas léxicas (fracción de documentos por término, que hoy
  vive en `.cache/vocab_bm25`).

La escritura se hace en un archivo temporal y se **renombra al terminar**: el
índice es inmutable y un fallo a mitad de indexación nunca deja el servicio
con un índice roto (adelanta la idea de alias del plan sin su complejidad).
El servicio abre en solo lectura (WAL).

### 2.2 Retriever `sqlite_fts`

- Consulta: tokenizar, quitar stopwords con `rag/texto_util.py`, **entrecomillar
  cada término** antes de armar la expresión FTS. Sin esto una pregunta con
  `AND`, `NEAR`, comillas o `*` rompe la consulta o cambia su significado.
  Prueba de inyección obligatoria.
- Orden con `bm25()` de FTS5; desempate determinista por `chunk_id`.
- Filtro por entidad: `JOIN entidades`.
- Los `RetrievalSignals` rellenan `sparse_score`/`sparse_rank`; los densos quedan `None`.

### 2.3 El problema difícil: confianza sin coseno

Toda la abstención actual se apoya en el coseno denso del mejor fragmento
(umbrales 0.80 / 0.85, específicos de e5-small). Un puntaje BM25 no es
comparable entre consultas, así que **no se puede reutilizar el mismo umbral**.

Propuesta para `confianza_top1` en este backend: **cobertura léxica ponderada
por IDF**, es decir, qué fracción del peso IDF de los términos de contenido de
la pregunta aparece en el mejor fragmento. Está acotada en [0, 1], es
determinista y se puede explicar a un usuario ("encontré 4 de tus 5 términos
clave"). El margen top1–top2 se calcula igual que hoy.

Consecuencias que hay que asumir de frente:

- Los umbrales viven por backend (`abstencion.por_backend.sqlite_fts`) y se
  marcan `sin_calibrar` hasta tener evaluación (Ruta, Fase C).
- La búsqueda léxica no entiende paráfrasis. Habrá preguntas que el backend
  denso responde y este no, y se abstendrá o dará `relacionado`. Es el
  comportamiento seguro y esperado; lo importante es medirlo, no ocultarlo.
- Español sin lematizador: "cambia/cambiar/cambio" no coinciden. Primero
  medir; si duele, evaluar un stemmer ligero opcional. No se añade por intuición.

### 2.4 Ingesta y CLI

- Separar en `rag/corpus.py` lo genérico (catálogo, parseo, chunking, payloads,
  inventario de entidades) de lo específico de Qdrant (`indexar_qdrant`,
  vocabulario sparse). Hoy conviven en 703 líneas.
- `rag indexar` construye el almacén que corresponda al `retriever` configurado.
- `/ready` y `rag doctor` dejan de asumir "colección" y modelo; informan del
  backend activo y sus chequeos (por ejemplo, disponibilidad de FTS5).
- El calentamiento solo codifica una pregunta si el backend tiene encoder.
- La selección de oraciones ya usa `metodo_seleccion: lexico` por defecto y
  `modelo_st` es opcional en `seleccion_fragmento.py`; comprobar que no haya
  otro punto que exija el modelo.

### 2.5 Pruebas

- Toda la suite de pipeline/API parametrizada por backend: los mismos casos
  deben cumplir los mismos **invariantes** (offsets exactos, texto literal,
  guardia, estados). Las respuestas concretas pueden diferir entre backends.
- Prueba de aislamiento: importar `sentence_transformers` y `qdrant_client`
  falla a propósito (`sys.modules` envenenado) y el ciclo
  cargar -> indexar -> consultar sigue funcionando.
- Acentos, mayúsculas, consulta vacía, solo stopwords, caracteres FTS, términos
  repetidos, corpus de un solo documento.
- Lectores concurrentes sobre el mismo archivo.

### Hecho cuando

- `rag init && rag cargar && rag indexar && rag servir` funciona con
  `retriever: sqlite_fts` en un entorno donde `torch` y `qdrant_client` no
  están instalados.
- Los invariantes pasan en ambos backends.
- El documento de metodología `docs/metodologias/recuperacion-lexica.md` está
  escrito con la plantilla del plan (incluye limitaciones y señal de confianza).

### Fuera de alcance

Lematización, BM25 propio en memoria, modo en el navegador, y decidir si este
backend pasa a ser el predeterminado.

**Tamaño estimado:** M. Depende del Trabajo 1 (1.1 y 1.2 al menos).

---

## Ruta

Cada fase termina con criterios comprobables. Una fase no empieza a medias de otra
salvo donde se indica.

### Fase 0: higiene (antes de todo)

- Commitear el trabajo pendiente en ramas/commits con sentido (hoy 12 archivos
  modificados y varios nuevos, con un único commit previo).
- Entorno de desarrollo con `pytest`; baseline de la suite anotado.
- Retirar del código y los docs las referencias internas ("molde", "Etapa C/D",
  "sección 6.1") o convertirlas en enlaces a docs reales. Un colaborador externo
  no puede seguirlas.
- Quitar del dominio genérico los tipos de entidad académicos heredados
  (`nota`, y revisar `plazo`/`articulo`) o moverlos a un perfil de ejemplo.
- `LICENSE`, `CHANGELOG.md`, `.github/workflows` con pytest en Linux y Windows.

### Fase A: Trabajo 1 (registry conectado)

### Fase B: Trabajo 2 (retriever léxico SQLite)

### Fase C: medir, sin calibrar todavía a ciegas

Aquí se decide con datos lo que hoy son opiniones.

- `rag eval`: genera preguntas a partir del propio corpus (una oración por
  fragmento, con offset de la respuesta) y reporta Recall@k, MRR y la tasa de
  abstención por estado. Las preguntas sintéticas subestiman la dificultad real;
  sirven para comparar backends y detectar regresiones, no como garantía de calidad.
- Un golden set pequeño y real (30–50 preguntas) sobre **un** corpus concreto:
  incluir sin respuesta, premisa falsa y paráfrasis.
- Tabla comparativa: `sqlite_fts` contra `qdrant` denso e híbrido.
- Primera calibración de umbrales por backend con `calibrar_umbral`, que ya existe.
- **Con esto se decide** si el léxico basta como valor por defecto, si el
  híbrido justifica su peso y si hace falta separar extras.

### Fase D: integración web mínima

- `rag servir` funcionando en un comando desde una carpeta de documentos, sin
  `init` previo obligatorio (crea el proyecto en caliente).
- `rag widget exportar <carpeta>`: `widget.js` y un snippet listo para pegar.
- Web Component `<rag-extractivo-chat>` sobre el widget actual (Shadow DOM ya
  está), con atributos HTML y eventos.
- Ejemplos verificados: HTML estático, React y WordPress (snippet, sin plugin).
- Prueba del wheel en entorno limpio y de la imagen Docker en CI.
- Widget: arrastre, móvil y accesibilidad (ya planeados en Fase 5 del plan).
- **Se pospone** el paquete npm, ESM/UMD y tipos TypeScript hasta que el
  Web Component se estabilice.

### Fase E: calidad de respuesta

Solo con la medición de la Fase C como guía; cada técnica entra si mejora las
métricas o se descarta.

- Corrección `passage:` de E5 con reindexación.
- Análisis de pregunta, intención y slots; desambiguación
  ("¿te refieres a X200 o X300?") en vez de elegir una opción.
- Contexto conversacional acotado para preguntas de seguimiento.
- Chunker jerárquico con tokenizer real y conservación de tablas.
- Reranker opcional.

### Fase F: producto y diferenciación

- Registro de **preguntas sin respuesta** y panel para el mantenedor (qué le falta
  a la documentación). Hoy no se registra nada de esto.
- Ingesta desde sitemap/sitio y Markdown de documentación.
- Cita con resalte exacto y enlace al pasaje en el documento fuente.
- `rag audit`: recorre un log de respuestas y comprueba que cada una es
  subcadena literal del corpus. Publicar esa garantía.
- Servidor MCP como herramienta de recuperación literal.
- Modo estático en navegador (índice JSON + buscador en el cliente), para sitios
  sin backend. Solo si la Fase C muestra que el léxico rinde.
- Perfiles/extras de instalación, decididos con los números de la Fase C.

## Qué se recorta de PLAN_V2

No se abandonan; se posponen hasta que haya evidencia de que hacen falta:
Docling/Unstructured, ColBERT, servidor TEI, circuit breakers, `late_chunking`,
`multi_granularity`, `interact.js`, Floating UI, exportación de conversación,
SBOM, la taxonomía completa de 13 estados (se usan los que necesita cada fase)
y el plan de nombres de extras.

## Decisiones abiertas

1. ¿`ChunkRecord` gana `doc_titulo`, `version` y banderas como campos tipados
   (recomendado) o van en `metadata`?
2. ¿La señal de confianza léxica es cobertura IDF (propuesta) u otra? Se puede
   cambiar tras la Fase C, pero conviene fijar la interfaz ahora.
3. ¿El almacén SQLite guarda también los vectores en la Fase E, o sigue siendo
   solo léxico y Qdrant sigue siendo el backend denso?
