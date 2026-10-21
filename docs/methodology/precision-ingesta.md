# Precisión del primer resultado desde la ingesta

Resumen de las mediciones del plan de precisión (octubre de 2026), que respaldan el
[ADR 0003](../decisions/0003-onnx-and-profiles.md) (reranker por idioma) y el
[ADR 0009](../decisions/0009-structural-preparation-by-default.md) (preparación estructural
por defecto). Las herramientas están en `herramientas/evaluacion/` (`ranking_pasajes.py`,
`tokens_fragmentos.py`, `puntuar_fuera.py`). Los detalles de la preparación estructural están en
[preparacion-estructural.md](preparacion-estructural.md).

## Problema

La fuente correcta aparecía entre las primeras cinco, pero no siempre primera. Línea base
(`CH-F256`: 256 palabras o más, sin cabecera, reranker con ventana de 256 tokens, e5-small, CPU de
4 núcleos), banco sintético `tests/datos/banco_pasajes/es`, partición `dev` (72 preguntas):

| Perfil | Etapa | hit@1 | hit@3 | hit@5 |
|---|---|---|---|---|
| light | híbrido = final | 0,792 | 0,986 | 1,000 |
| medium | híbrido | 0,792 | 0,986 | 1,000 |
| medium | final (reranker) | 0,736 | 0,875 | 0,958 |

La fuente correcta siempre estaba en las cinco primeras del orden híbrido, y en `medium` el reranker
la empeoraba. Causa dominante: con la ventana de 256 tokens el reranker no veía el final del
fragmento (44 % de las evidencias quedaban cortadas con `CH-F256`).

## Experimentos (banco sintético, `dev`, hit@1)

| Experimento | light | medium |
|---|---|---|
| base `CH-F256` | 0,792 | 0,736 |
| cabecera básica / extendida | 0,833 / 0,847 | 0,750 / 0,750 |
| `CH-PAR` (por párrafo) | 0,931 | 0,694 |
| `CH-SEC` (por sección) | 0,972 | 0,833 |
| reranker con ventana de 512 | — | 0,861 |
| `CH-F256S` (respeta secciones) | 0,792 | 0,889 |
| `CH-SEC` + 512 | — | 0,986 |
| **preparación estructural** | **1,000** | **0,986** (p95 1,1 s) |

En la partición `test` (44 preguntas, medida una vez por configuración) la estructural da 1,000 en
`light` y 0,977 en `medium`, frente a 0,864 y 0,727 de la base. Con PDF, DOCX y texto
(`banco_general`, saturado) no hay regresiones en `medium`.

Conclusiones: la cabecera aporta poco; `CH-PAR` empeora `medium`; la preparación estructural es la
mejor opción y a la vez la más rápida. Se adoptó por defecto (ADR 0009).

## Documentos reales

Tres documentos institucionales (reglamento con tablas P1/P2 y dos versiones de una rúbrica), que no
están en el repositorio. 56 preguntas adversarias (28 objetivos × formal e informal), `medium`:

| Configuración | hit@1 | hit@3 | p95 ms |
|---|---|---|---|
| legacy `CH-F256` | 0,54 | 0,79 | 2 388 |
| legacy + reranker 512 | 0,50 | 0,84 | 2 444 |
| legacy `CH-SEC` + 512 | 0,52 | 0,75 | 2 572 |
| legacy `CH-F256S` | 0,48 | 0,66 | 2 415 |
| **estructural** | **0,79** | **0,91** | **1 431** |

La ventaja de la estructural es mayor con preguntas difíciles y coloquiales. Lo informal sigue costando
(0,68 frente a 0,89 formal) y es un problema de vocabulario, no de fragmentado.

## Vectores y reranker

Con la estructural, la fuente correcta está en el top 20 del recuperador el 95 a 98 % de las veces,
pero primera solo el 54 a 62 %. Cambiar el modelo denso no mejora la discriminación fina (e5-base,
granite-311m, harrier-270m y embeddinggemma dan 0,54 a 0,62 en el recuperador y el final queda igual
o peor): **no se cambia el modelo denso**. La discriminación está en el reranker:

| Reranker (56 adversarias, motor) | hit@1 | informal | p95 ms |
|---|---|---|---|
| mMiniLM (referencia) | 0,79 | 0,68 | 1 431 |
| gte-multilingual-base | 0,71 | 0,50 | 2 216 |
| bge-reranker-v2-m3, 10 candidatos | **0,86** | **0,79** | 1 874 |

Decisión (2026-10-15): `medium` usa `bge-reranker-v2-m3` con 10 candidatos para español y portugués;
mMiniLM para el resto. Costo medido: 85 ms por pasaje (frente a 21 ms), 560 MB en disco y RAM. Con los
documentos reales: hit@1 0,786 → 0,857. En inglés no hay documentos reales para decidir.

**Candidatos descartados** (licencia, tamaño o resultado): `jina-reranker-v2/v3` (CC-BY-NC),
`Qwen3-Reranker-4B/8B` y `bge-reranker-v2-gemma` (2 a 9 B), Horizon small y base, Vela 1.0 (no superan a
bge dentro del motor), lb-reranker-0.5B y mxbai-rerank-base-v2 (buenos fuera de línea, 0,81 y 0,84,
pero sin pesos ONNX utilizables y hasta 26 s por pregunta). Las medias fuera de línea y las del motor no
son comparables; la comparación válida es la del motor.

## Ventana del reranker y alcance

- **Ventana (F2.2):** con la estructural la evidencia queda fuera de los 256 tokens en el 22 % de las
  preguntas reales, pero subir `reranker_max_tokens` a 384 o 512 no mejora (0,857 → 0,839). No se
  implementó un presupuesto en tokens.
- **Alcance y rasgos distintivos (F3.2):** de los 8 errores de primer lugar que quedaban, 6 eran pares
  P1/P2 cuya respuesta es una fila de tabla que no dice a qué práctica pertenece. Agregar el alcance al
  texto indexado empeora (0,786); los rasgos distintivos (`distinctive_terms: 5`, umbral TF-IDF 0,6) dan
  0,893. Son 2 casos sobre 56: tendencia, no conclusión. La variante por vectores vecinos no aporta más.

## Pendiente

- **F3.3** (condicional): errores de rango 2 a 5 en la misma categoría que el acierto; no se analizó.
  Con hit@3 de 0,946 y hit@5 de 0,982 sobre documentos reales queda poco margen.
- **F4.3**: requiere aprobación del usuario.

## Cautelas

El banco sintético lo generó el mismo asistente que construye el sistema y su corpus es muy regular;
`light` está casi saturado y varias diferencias son de 1 a 3 casos sobre 72. Con 89 preguntas un caso
son 1,1 puntos. Nada sustituye una medición con preguntas de personas reales.
