# Consejo de reranking: experimento retirado

Estado: histórico. El experimento se retiró y ya no existe en el código (`config_version` 7).

El consejo, su configuración, factory y comparador se eliminaron. Esta nota
conserva la evidencia de la decisión; no describe una opción disponible.
La configuración 7 retira `v2.council` de los archivos anteriores y conserva
los demás presupuestos. V2 pasa a [fuentes ordenadas con contexto](fuentes-v2.md).

Se compararon MiniLM, GTE INT8, BGE INT8 y combinaciones RRF sobre los mismos
candidatos y textos del corpus de tres DOCX. Seis preguntas positivas conocidas
tenían unidades aceptadas antes de medir; dos ambiguas y tres controles sin
respuesta se excluyeron de los aciertos positivos. Una ronda por variante,
dos hilos ONNX, lote 4, techo de 512 tokens y QA desactivado.

| Variante | Fuente válida primera | Entre las tres primeras | Mediana local | RSS muestreada |
|---|---:|---:|---:|---:|
| MiniLM, primera corrida | 4/6 | 4/6 | 4,88 s | 1,43 GiB |
| GTE INT8 | 2/6 | 4/6 | 22,96 s | 2,19 GiB |
| MiniLM + GTE | 3/6 | 5/6 | 26,26 s | 2,57 GiB |
| MiniLM + GTE + híbrido | 3/6 | 4/6 | 18,79 s | 2,55 GiB |
| MiniLM, repetición | 4/6 | 4/6 | 4,36 s | 1,43 GiB |
| BGE INT8 | 4/6 | 5/6 | 24,82 s | 1,99 GiB |
| MiniLM + BGE | 3/6 | 6/6 | 30,22 s | 2,52 GiB |
| MiniLM + GTE + BGE | 3/6 | 5/6 | 42,75 s | 3,76 GiB |
| Tres modelos + híbrido | 4/6 | 4/6 | 67,05 s | 3,75 GiB |

En la ponderación coloquial de P1, el título de la tabla quedaba segundo en
MiniLM y BGE; la tabla completa, sexta y primera. RRF favorecía el título:
`2/62 = 0,032258` frente a `1/66 + 1/61 = 0,031545`. La pregunta y tabla completa
ocupaban 145 tokens en cada tokenizador, sin truncado. La respuesta estaba en
el conjunto; el acuerdo de pertinencia no certificaba una respuesta completa.

Los rankings individuales coinciden exactamente entre las combinaciones y
las ejecuciones individuales. Las 297 referencias de las 99 consultas son
literales; los textos canónicos se contrastaron con los DOCX. Los controles
sin respuesta seguían produciendo fuentes relacionadas. No se promovió ningún
consejo: su costo en CPU y selección principal no justificaron conservarlo.

Los tiempos incluyen trazas y actividad del sistema sin controlar. El orden
fijo y una sola ronda impiden atribuir diferencias de latencia al voto híbrido.
Estas pocas relaciones de un reglamento no acreditan calidad en otros corpus.
No se contrastaron los pesos INT8 con FP32 ni se entrenaron modelos propios.

Los artefactos privados conservan código congelado, parámetros, respuestas,
opiniones y hashes; permanecen fuera de Git:

- `.cache/motor-v2/consejo/comparison/run-p87zgtt1/`: cuatro variantes iniciales,
  `summary.json`, informes completos y `literal-checks.json` (132 referencias).
- `.cache/motor-v2/consejo/comparison-bge/run-kjbl9126/`: cinco variantes de BGE,
  `summary.json`, informes completos y `literal-checks.json` (165 referencias).
- `.cache/motor-v2/consejo/questions.json`: preguntas y etiquetas congeladas.

GTE se midió en revisión `ee64367e35a2db0da46bb6497e13a18f8bd585cb` y BGE en
`6f5ff65298512715a1e669753bc754d2bc8f367b`, ambos `onnx/model_int8.onnx`.
MiniLM usó `onnx/model_quint8_avx2.onnx`, snapshot
`1427fd652930e4ba29e8149678df786c240d8825`.
