# Plan: precisión del primer resultado desde la ingesta

Estado: propuesta (2026-10-15). No cambia código ni configuración.

## Problema

La fuente correcta casi siempre aparece entre los 3–5 primeros resultados,
pero no siempre en el primero. La hipótesis de trabajo es que la causa está
en cómo se fragmentan, representan y describen los documentos, no en el
flujo de recuperación. Este plan revisa esa parte y propone experimentos
medibles.

## Estado actual (verificado en el código)

| Pregunta | Respuesta | Dónde |
|---|---|---|
| ¿Qué índice se usa? | Qdrant, una colección con dos vectores: `denso` (coseno) y `bm25` disperso (`Modifier.IDF`). Se fusionan con RRF nativo (`prefetch` + `FusionQuery`). | `ipsis/indice/qdrant.py:262-266`, `:105-115` |
| ¿Hay índice ANN (HNSW)? | No se configura `hnsw_config`. En modo `local` (el predeterminado, `qdrant.mode: local`) `QdrantClient(path=…)` busca por fuerza bruta: la búsqueda es **exacta**. En modo servidor se usan los valores por defecto (m=16, ef_construct=100), pero por debajo de `full_scan_threshold` (10 000 KB, unos 6 600 vectores de 384 float32) Qdrant también busca exacto. | `ipsis/indice/qdrant.py:191-216` |
| ¿Cuantización de los vectores en Qdrant? | **Ninguna**: no hay `quantization_config`. Se guardan float32 completos. | `ipsis/indice/qdrant.py:262` |
| ¿Cuantización del modelo? | e5-small (predeterminado en todos los perfiles): `onnx/model.onnx`, fp32. Granite: `quint8_avx2` en x86, fp32 en el resto. Harrier y EmbeddingGemma: int8. Reranker mMiniLM: `quint8_avx2` en x86, `qint8` en arm64. | `ipsis/modelos/catalogo.py` |
| Dimensión | 384 (e5-small). Pooling por media y norma 1. | `ipsis/modelos/denso.py` |
| Fragmentado predeterminado | `CH-F256`: bloques enteros hasta ≥256 palabras, solape 15 %, **cruza secciones**. | `ipsis/recursos/plantillas/engine.yaml:20`, `ipsis/ingesta/chunking.py:92` |
| Cabecera contextual | **Desactivada** (`with_header: false`): el vector y el BM25 solo ven el texto del fragmento, sin documento ni sección. | `engine.yaml:21`, `ipsis/ingesta/ingesta.py:75` |
| Orden final en v2 | Con perfil `medium`, lo decide el reranker (logit), con `reranker_max_tokens: 256` para el par pregunta+pasaje. Con `light` (sin reranker) es el orden RRF híbrido. | `engine.yaml:13`, `ipsis/aplicacion/consulta.py:192-198` |
| Metadata | `categoria` (solape léxico), `keywords` (TF-IDF top-5), `entidades`, `tiene_condicion`, `tiene_excepcion`, `seccion_path`. Solo `entidades` influye en la búsqueda (filtro dirigido); el resto no entra en el vector, en BM25 ni en el reranker. | `ipsis/ingesta/metadata.py:159` |

Conclusiones directas:

- **El índice no explica errores de orden**: la búsqueda ya es exacta y sin
  cuantizar. Activar cuantización (escalar o binaria) solo podría empeorar
  la precisión; no se recomienda.
- **Subir la dimensión significa cambiar de modelo**: la dimensión está
  fijada por el modelo (no hay recorte tipo Matryoshka). El catálogo ya
  incluye candidatos de 768: e5-base, granite-311m y EmbeddingGemma.

## Causas probables, en orden de impacto esperado

### C1. El reranker no ve el final de los fragmentos

En v2 el orden final lo da el cross-encoder, truncado a 256 tokens **para
pregunta y pasaje juntos**. Un fragmento `CH-F256` tiene 256 palabras o
más (se agregan bloques enteros hasta pasar el umbral), lo que en español
equivale a unos 350–500 tokens del tokenizador XLM-R. El reranker solo lee
las primeras ~150–180 palabras.

Si la respuesta está en la segunda mitad de un fragmento, el reranker lo
puntúa por su comienzo y lo deja por debajo de otro cuyo inicio se parece
más a la pregunta. Es el patrón descrito: la fuente correcta está entre los
3–5 primeros (la recuperación la encontró), pero no sale primera.

El codificador denso (tope 512) trunca menos, pero los fragmentos largos
también quedan cerca o por encima del límite.

*Pendiente de medir*: el porcentaje de fragmentos truncados con el
tokenizador real sobre el corpus del usuario (desde este entorno no se pudo
descargar el tokenizador).

### C2. Fragmentos parecidos sin contexto que los distinga

Con la cabecera desactivada, dos fragmentos de documentos o secciones
distintas que tratan lo mismo (por ejemplo, «plazos» en dos reglamentos) son
casi indistinguibles para el vector, para BM25 y para el reranker. Lo que los
separa (documento, sección, a quién aplica) no está en el texto que se
representa.

### C3. Fragmentos heterogéneos

`CH-F256` mezcla temas: cruza secciones, y el solape del 15 % crea casi
duplicados que compiten entre sí. Con pooling por media, un fragmento con
varios temas produce un vector «promedio» que se parece moderadamente a
muchas preguntas y mucho a ninguna. La documentación dice que «un fragmento
nunca cruza secciones» (`docs/methodology/retrieval.md`), pero eso solo se
cumple en `CH-PAR`, `CH-SEC` y en la preparación estructural.

### C4. La metadata existe pero no discrimina

La metadata se calcula, pero no llega a ninguna señal de orden. Además, la
categoría (`score = solape/6`) es gruesa: los fragmentos «hermanos» suelen
recibir la misma.

### C5. Los bancos de prueba no ejercitan el problema

En los corpus de `tests/datos`, `CH-F256` produce 26 fragmentos para unos 24
documentos (mediana de 127 palabras): casi cada documento es un solo
fragmento. Esos bancos miden el orden de documentos, no de pasajes dentro de
un documento largo. Cualquier mejora debe medirse sobre el corpus real o
sobre un banco con documentos largos.

## Propuestas

Ordenadas por costo y beneficio esperado. Cada una es un experimento con
la misma medición (fase 0) antes y después.

### Fase 0 — Medición (requisito para todo lo demás)

1. Banco de pasajes sobre el corpus real: preguntas con documento y rango
   esperado (el formato golden ya lo admite). Al menos 100 preguntas, con
   pares de fragmentos «hermanos» deliberados.
2. Métricas por etapa: hit@1, hit@3, hit@5 y MRR después de la recuperación
   híbrida y después del reranker (`ipsis/evaluacion/metricas.py` ya calcula
   MRR). La comparación entre etapas dice si el error es de recuperación o
   de orden.
3. Diagnóstico de longitud: distribución de tokens por fragmento con el
   tokenizador de cada modelo (denso y reranker) y porcentaje truncado.
   Requiere los modelos descargados.

### Fase 1 — Cambios de configuración (sin código)

| Experimento | Cambio | Hipótesis |
|---|---|---|
| E1 | `with_header: true` | C2: documento y sección entran en el vector, en BM25 y en el reranker. |
| E2 | `chunking_strategy: CH-PAR` (80–400) o `CH-SEC` | C3: fragmentos de una sola sección y sin solape. |
| E3 | `reranker_max_tokens: 512` | C1: el reranker ve el fragmento entero. Cuesta latencia (cuadrática en tokens); medir el p95. |
| E4 | E1 + E2 + E3 combinados | Efecto conjunto. |

Cambiar el fragmentado o la cabecera invalida la calibración (el
`hash_corpus` cambia) y obliga a reindexar.

### Fase 2 — Fragmentado consciente del modelo

1. **Presupuesto en tokens del modelo, no en palabras.** `_n_tokens`
   aproxima con `split()`. Con el tokenizador del codificador (ya cargado en
   `ModeloOnnx`) se puede cortar para que cabecera + fragmento quepan en la
   ventana del reranker menos la pregunta (~200 tokens con el tope de 256).
2. **No exceder el umbral con bloques enteros.** Hoy un párrafo largo se
   agrega completo aunque pase el máximo; partirlo por oraciones.
3. **Nunca cruzar secciones en el fragmentado fijo**, como ya hacen las
   otras estrategias.
4. **«Small-to-big» para todos los formatos.** La preparación estructural ya
   indexa hijos de ~80 palabras con título, sección y contexto, y amplía al
   padre antes del reranking (`ipsis/ingesta/unidades.py`), pero solo admite
   DOCX y tabulares (`ipsis/ingesta/preparacion.py:22`). Extenderla a PDF,
   Markdown y texto es la vía más directa para que el vector represente una
   idea y no un promedio.

### Fase 3 — Metadata que distingue fragmentos parecidos

1. **Grupos de hermanos y rasgos distintivos.** Durante la ingesta, agrupar
   los fragmentos con coseno alto entre sí (umbral a calibrar) y calcular
   para cada uno los términos que tiene y sus hermanos no (TF-IDF del
   fragmento menos el del grupo). Guardarlos en el payload (`grupo_similar`,
   `rasgos_distintivos`) y agregarlos a la cabecera embebida. Así el vector
   y el reranker reciben justo lo que separa a los fragmentos.
2. **Cabecera enriquecida y determinista.** Además de documento y sección:
   tipos de dato presentes (plazo, monto, fecha, actor, a partir de
   `entidades`), si contiene condición o excepción, y a quién aplica cuando
   el texto lo declara. Todo con reglas, sin modelos generativos (ADR 0001).
3. **Revisar la categoría.** Si en la fase 0 la categoría no separa
   hermanos, reemplazar el solape léxico por la sección declarada o por los
   rasgos del punto 1, en lugar de afinar `palabras_gatillo`.

`descripcion_libre` sigue reservada y desactivada. Una descripción generada
por un modelo requeriría una decisión aparte.

### Fase 4 — Representación vectorial

1. **Modelo de mayor dimensión.** Comparar e5-small (384), e5-base (768),
   granite-311m (768) y EmbeddingGemma (768) con el mismo fragmentado. Cada
   modelo crea su propia colección (`{coleccion}_{modelo}_v{n}`), así que la
   comparación no mezcla vectores. Es esperable que mejore más el hit@5 que
   el hit@1, porque el orden final lo decide el reranker; por eso va después
   de las fases 1–3.
2. **Vectores por oración (multivector).** Qdrant admite multivectores con
   `MultiVectorConfig(comparator=MAX_SIM)`: un fragmento puntúa por su
   oración más parecida, no por el promedio. Ataca C3 sin achicar el pasaje
   que se cita. Multiplica el tamaño del índice; medir.
3. **Cuantización del modelo.** Si se elige Granite en x86, comparar
   `quint8_avx2` contra fp32 (`"*"` en el catálogo): la cuantización int8
   del modelo puede borrar diferencias finas.

### Lo que no se recomienda

- Cuantizar los vectores en Qdrant (escalar, PQ o binaria): hoy no hay, y
  solo reduciría la precisión.
- Ajustar HNSW: con la búsqueda exacta actual no tiene efecto. Si el corpus
  pasa de unos 6 000 fragmentos en modo servidor, evaluar con
  `SearchParams(exact=True)` para descartar error del ANN.

## Criterios de aceptación

- hit@1 tras el reranker sube de forma significativa sobre el banco de la
  fase 0, sin bajar hit@5 ni la cobertura literal (`respuesta_completa_v2`).
- p95 dentro de `query_budget_ms` (2 500 ms en v2).
- Sin regresión en `tests/` ni en la regresión general multilingüe.

## Archivos afectados (si se implementa)

- `ipsis/ingesta/chunking.py`: presupuesto en tokens, cortes por sección y
  oración.
- `ipsis/ingesta/preparacion.py`, `ipsis/ingesta/unidades.py`: preparación
  estructural para PDF, Markdown y texto.
- `ipsis/ingesta/metadata.py`, `ipsis/ingesta/ingesta.py`: grupos de
  hermanos, rasgos distintivos y cabecera enriquecida.
- `ipsis/indice/qdrant.py`: multivector opcional.
- `ipsis/recursos/plantillas/engine.yaml`: nuevos valores por defecto, solo
  si los experimentos los justifican.
