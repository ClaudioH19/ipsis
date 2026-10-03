# Capa léxica (BM25 y TF-IDF) y multilenguaje

## 1. Por qué una capa léxica propia

Los modelos (codificador, reranker y lector) entienden paráfrasis, pero son
cajas negras y cuestan latencia. BM25 y TF-IDF son baratos, deterministas,
explicables y, con un stemmer por idioma, funcionan en muchos idiomas sin
listas a mano. Se usan para tres cosas:

1. **Recuperar** (como hoy: híbrido denso + BM25).
2. **Detectar el «se parece pero no responde»** con señales que se pueden
   auditar y explicar al usuario.
3. **Ahorrar latencia** con salidas tempranas: si las señales léxicas ya
   prueban que no hay respuesta, no se ejecutan el reranker ni el lector.

## 2. Un solo camino de términos

Toda la capa usa **una única función** para convertir texto en términos, en
la indexación y en la consulta. Así lo que se indexa y lo que se consulta
siempre coinciden, y un auditor puede reproducir cualquier puntaje.

```text
terminos(texto, paquete) =
  tokenizar Unicode (\w+)  →  casefold  →  quitar tildes (solo escritura latina)
  →  stem Snowball del idioma (si el paquete define `stemmer`)
```

- **Stemmer:** [`snowballstemmer`](https://pypi.org/project/snowballstemmer/)
  (BSD-3-Clause, Python puro, 29 stemmers para 28 idiomas ✔). Si el idioma no
  tiene stemmer, se usan los términos sin stem.
- **Sin listas de stopwords obligatorias.** El IDF ya resta peso a las
  palabras frecuentes. Las stopwords del paquete son opcionales y solo
  afinan. Así se elimina la lista curada de «palabras generales», que hoy
  arrastra restos de un dominio académico.

## 3. Estadísticas del corpus (`EstadisticasLexicas`)

Se calculan al indexar y se guardan junto al índice, en
`.rag/indice/estadisticas.json`: JSON legible, versionado y con el hash del
corpus.

| Campo | Uso |
|---|---|
| `n_chunks`, `largo_medio` | Normalización de BM25 por largo |
| `df[término]` | IDF de cada término (`ln(1 + (N − df + 0,5)/(df + 0,5))`) |
| `superficie[término]` | Forma original más frecuente del término, para mostrarla al usuario («garantía», no «garant») |

Reemplaza a los archivos actuales `vocab_bm25`, `inventario` y
`estadisticas_lexico_dominio`: una sola fuente para todas las señales.

## 4. BM25 en Qdrant sin vocabulario propio

Como recomienda Qdrant, la parte del documento de BM25 se calcula en el
cliente y el IDF se aplica en el servidor (`modifier: idf`) ✔:

- **Id de término:** hash estable de 32 bits del término (`zlib.crc32`). No
  hace falta guardar un vocabulario aparte.
- **Valor en el chunk:** `tf·(k1+1) / (tf + k1·(1 − b + b·largo/largo_medio))`,
  con `k1 = 1,2` y `b = 0,75`.
- **Valor en la consulta:** 1 por término único.

## 5. Señales léxicas

Todas son funciones puras en `rag/lenguaje/lexico.py`, con resultado en
`[0, 1]`. Las calcula la etapa de filtros (sobre la pregunta y los candidatos)
y la de selección (sobre el tramo elegido).

| Señal | Definición | Qué detecta |
|---|---|---|
| `s_oov` | Peso IDF de los términos de la pregunta **ausentes del corpus** / peso IDF total (un término desconocido recibe el IDF máximo) | Pregunta fuera de dominio. Reemplaza las «palabras generales» |
| `foco` | Los 1–2 términos de la pregunta con mayor IDF que **existen en el corpus** | El «de qué se habla»: en «¿Cuánto dura la garantía?», el foco es «garantía» |
| `s_foco` | Fracción de términos foco presentes en la **oración** que contiene la respuesta | **El caso garantía/filtro:** el tramo «6 meses» está en una oración sin «garantía» → `s_foco = 0` |
| `s_cov` | Peso IDF de los términos de la pregunta presentes en el tramo / peso IDF total | Cobertura general de la pregunta |
| `s_lex` | BM25(pregunta, oración) / BM25 ideal de la pregunta | Pertinencia léxica normalizada, para ordenar oraciones (tf-isf) |
| `acuerdo` | 1 si el top-1 denso está en el top-3 de BM25 y viceversa; 0,5 si solo uno; 0 si ninguno | Diseñada para la confianza de light; **no se calcula** (P10.2). Se evalúa en P10.4 |

### Cómo las usa la cascada

| Etapa | Uso léxico |
|---|---|
| Filtros | `s_oov` alto y señal de recuperación baja → `sin_respuesta` (fuera de dominio) **antes de ejecutar modelos** |
| Filtros | **Salida temprana:** si ningún candidato del top N contiene algún término foco → no se ejecutan reranker ni lector; la política decide entre `relacionado` y `sin_respuesta` |
| Selección (light) | Oración con mayor `s_lex` dentro de cada candidato (reemplaza el Jaccard actual) |
| Lectura (medium/heavy) | **Proximidad:** si el tramo del lector está en una oración con `s_foco = 0`, se marca y la política lo baja de `ok` |
| Política | `ok` exige `s_foco ≥ τ_foco` en todos los perfiles |
| Redacción | Mensaje explicable: *«No encontré información específica sobre «garantía». Esto es lo más cercano:»* (la forma de superficie viene de `superficie[término]`) |
| Diagnóstico | Lista de términos foco, encontrados y ausentes, con su IDF |

**Límite conocido:** si el usuario usa un sinónimo que no aparece en el
documento («cartucho» y el texto dice «filtro»), `s_foco` cae y el sistema se
abstiene de más. Es el lado seguro del error. El umbral `τ_foco` se calibra
con el golden set (la categoría `parafrasis` lo mide), y en medium/heavy el
reranker y el lector compensan una parte.

### Otros usos de TF-IDF

| Dónde | Uso |
|---|---|
| Metadata de chunks | Palabras clave = top TF-IDF del chunk (reemplaza el conteo por frecuencia) |
| `rag golden plantilla` | Elige secciones **diversas** con MMR sobre vectores TF-IDF y llena la columna `terminos_clave` para ayudar al cliente a escribir preguntas |
| `rag golden importar` | Clasifica cada caso respondible en `exacta` (`s_cov ≥ 0,6` entre pregunta y evidencia) o `parafrasis` |
| `rag benchmark` | Perfil de diagnóstico `bm25` (solo léxico) como línea base: muestra cuánto aportan el denso y los modelos |
| Chunking (experimento) | `texttiling_v1`: corta donde cae la cohesión léxica (coseno TF-IDF entre bloques vecinos), sin cruzar secciones ni superar el máximo de tokens. Se adopta solo si mejora las métricas del banco |

## 6. Multilenguaje: inventario de reglas atadas al español

| # | Ubicación actual | Qué es | Decisión | Tarea |
|---|---|---|---|---|
| 1 | `rag/servicio/pipeline.py` `_RE_SOLICITUD_*`, `_NUMEROS_CANTIDAD`, `verificar_respaldo_dato_solicitado` | Guardia regex por tipo de pregunta | **Borrar.** La reemplazan `s_foco` y la proximidad (todos los perfiles) y el lector (medium/heavy) | P8.3 |
| 2 | `rag/reglas_extraccion.py` `NUMEROS_TEXTO`, `MESES`, `ORDINALES`, `_DIAS_SEMANA`, `_UNIDADES_PLAZO`, «hábiles/corridos» | Plazos y fechas con palabras | **Paquete de idioma** | P3.4 |
| 3 | `rag/reglas_extraccion.py` artículo/anexo/capítulo | Referencias a partes del documento | **Paquete:** `referencias_documento` | P3.4 |
| 4 | `_RE_DECIMAL`, `_RE_PORCENTAJE` | Cifras | **Universal**; se agregan fechas numéricas y montos con símbolo de moneda | P3.3 |
| 5 | `configuracion/dominios/idiomas/es.yaml` (con «curso», «universidad») | Palabras generales | **Borrar.** Las reemplaza el IDF (`s_oov`); stopwords opcionales en el paquete | P3.1 |
| 6 | `rag/texto_util.py:61` `[a-z0-9]+` | Tokenización latina | **Reemplazar** por `terminos()` | P3.2 |
| 7 | `rag/corpus.py:47` `[a-záéíóúñü0-9]+` y BM25 con vocabulario propio | Tokenización y BM25 en español | **Reemplazar** por `terminos()` + BM25 con hash e IDF en Qdrant (§4) | P4.3 |
| 8 | `rag/metadata.py:75` | Palabras clave | **Reemplazar** por TF-IDF sobre `terminos()` | P4.6 |
| 9 | `rag/chunking.py:196`, `rag/seleccion_fragmento.py:37` | Separar oraciones (`. ? !`) | **Universal**: una sola `dividir_oraciones()` con `。 ！ ？ ؟ ।` | P3.2 |
| 10 | `configuracion/textos.yaml` conversacional | Saludos y gracias | **Paquete** | P3.5 |
| 11 | `configuracion/textos.yaml` abstención y conectores | Mensajes | **Paquete** | P3.5 |
| 12 | `textos.yaml` `planes`, `elegir_plan`, `extraer_slots` | Plantillas que nunca se usan | **Borrar** | P1.4 |
| 13 | `configuracion/categorias.yaml` marcadores | «salvo», «siempre que» | **Paquete** | P3.4 |
| 14 | `rag/servicio/estaticos/widget.js` (líneas 351–605) | Textos de la interfaz | **Paquete** vía `/config` | P3.6 |
| 15 | `rag/cli.py` `escribir_idioma_es_si_falta` | Inicialización en español | **Reemplazar:** `--idioma` valida contra los paquetes | P3.1 |
| 16 | `rag/abstencion.py` `tiene_grounding_lexico` | Vocabulario del dominio | **Reemplazar** por `s_oov` | P4.4 |
| 17 | `rag/metricas.py` | Evaluador antiguo | **Borrar** | P0.2 |

### Paquete de idioma (`rag/recursos/idiomas/<código>.yaml`)

```yaml
codigo: es
nombre: Español
stemmer: spanish                 # nombre de snowballstemmer; null si no hay
stopwords: []                    # opcional
numeros: {un: 1, una: 1, dos: 2, ...}
ordinales: {primer: 1, primera: 1, ...}
meses: [enero, febrero, ...]
dias_semana: [lunes, martes, ...]
unidades_tiempo: {dia: [día, días, dia, dias], semana: [semana, semanas], mes: [mes, meses], ...}
calificadores_plazo: [hábiles, corridos]
referencias_documento: {articulo: [artículo, artículos], anexo: [anexo], capitulo: [capítulo]}
marcadores: {excepcion: [salvo, excepto], condicion: [siempre que]}
conversacional:
  patrones: {saludo: ['^\s*hola\b'], agradecimiento: ['\bgracias\b'], despedida: [...], capacidad: [...]}
  respuestas: {saludo: [...], agradecimiento: [...], despedida: [...], capacidad: [...]}
mensajes:
  sin_respuesta: "No encontré esa información en los documentos disponibles."
  premisa_no_encontrada: "No encontré información sobre «{entidad}» en los documentos disponibles."
  relacionado_intro: "No encontré una respuesta directa. Esto es lo que dicen los documentos sobre el tema:"
  relacionado_foco_ausente: "No encontré información específica sobre «{termino}». Esto es lo más cercano:"
  conectores: {apertura: [...], complemento: [...]}
interfaz: {titulo: Asistente, placeholder: "Escribe tu pregunta...", cerrar: "Cerrar chat", enviar: "Enviar pregunta", esperando: "Buscando en el documento", error_red: "...", error_limite: "...", error_origen: "...", no_directa: "No es una respuesta directa"}
golden_instrucciones: |
  ...
```

Paquetes iniciales: `es`, `en` y `pt`. Un idioma sin paquete funciona con las
reglas universales, `terminos()` sin stem y los mensajes de `en`, y
`rag doctor` lo advierte.

**Fuera de alcance:** detectar el idioma de cada pregunta y corpus con varios
idiomas a la vez.
