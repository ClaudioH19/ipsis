# Continuación V4: memoria e intención, 2026-10-06

F4 conserva hasta cuatro temas, un núcleo de tres términos, el último
seguimiento y vocabulario de los últimos tres pasajes fuente verificados.
La sesión vence por inactividad y el widget crea un identificador por carga
de página. La auditoría añade protección frente a respuestas concurrentes
tardías, vencimiento exacto, compactación de formas y registro de vocabulario
después de las guardias. No guarda respuestas ni texto completo de pasajes.

F3 añade 210 ejemplos independientes, codificados una vez por motor. Solo
una intención desconocida con tema en el corpus puede usar el vector denso
existente. Patrones y umbrales de respuesta conservan su prioridad; la
inferencia aporta pistas sin eliminar palabras de la pregunta. BM25 y los
modelos sin medición propia omiten el respaldo.

## Resultados y límites

Las [tablas generadas](tablas.md) muestran las tres evaluaciones completas,
latencia y activaciones reales. [comparacion.json](comparacion.json) comprueba
por identificador las correctas perdidas, directas erróneas nuevas y cambios
de estado; no reemplaza esa comprobación por totales. La herencia correcta
light pasa de 26/25/21 a 36/35/34 (es/en/pt, de 38 turnos). Los retornos
de tema -007 y -015 heredan en los tres idiomas y ambos perfiles.

**Hay cuatro pérdidas de respuestas literales correctas en conversaciones frente a F1**:
light pt-conv-003:2 y pt-conv-016:2; medium es-conv-013:3 y en-conv-013:3.
En tres de esos casos la pregunta pasa a evidencia relacionada al cambiar
el foco por el núcleo/seguimiento. En español medium el estado sigue directo,
pero el lector escoge `gratuito` en vez de la oración completa; la cita sí
contiene la respuesta. No se acomoda el orden de palabras a un caso del
banco para ocultar este defecto. [caracterizacion.md](caracterizacion.md)
explica cada cambio de estado y esta pérdida sin cambio de estado.

Además, cinco turnos positivos son nuevas directas sin el literal esperado
del lector. En es/pt-conv-007:3 de medium, el lector elige a quien firma
cuando se pregunta quién redacta; la cita contiene ambos actores. Los
otros tres spans son incompletos. Estos errores se conservan por caso y
no se consideran aceptables solo por pasar las comprobaciones negativas.

G4 cuenta herencias indebidas y directas en los **cuatro turnos negativos**
de cada idioma. Pasarlo no significa conservar todos los aciertos positivos.
La métrica de tramo literal también muestra limitaciones anteriores de
medium. Los bancos pequeños detectan regresiones; no certifican riesgo de
producción ni una mejora general de exactitud.

## Selección de intención

| Idioma | τ (coseno, estricto) | δ (margen, estricto) | Categorías habilitadas | Dev: aciertos / errores | Test: aciertos / errores |
|---|---|---|---|---|---|
| es | 0,850 | 0,000 | fin, procedimiento | 3 / 0 | 1 / 0 |
| en | 0,870 | 0,000 | fin | 2 / 0 | 0 / 0 |
| pt | 0,895 | 0,000 | procedimiento | 1 / 0 | 1 / 0 |

Modelo: `intfloat/multilingual-e5-small`. Cada intención puntúa con su mejor
ejemplo y el margen compara las dos mejores **categorías**, incluidas las
no habilitadas. El grid dev maximiza cobertura sin errores y desempata por
el menor margen y luego el menor coseno. Solo categorías con respaldo
correcto comprobado en dev quedan habilitadas. Los datos y umbrales forman
parte de la huella que invalida calibraciones léxicas antiguas.

Las primeras iteraciones fallidas se conservan en `intenciones-intento-*.json`.
Test no entra en la búsqueda de umbrales, pero fue observado al revisar las
iteraciones: no se presenta como un conjunto estadístico intacto. Son ocho
consultas con intención adicional por perfil (4 es, 2 en, 2 pt), sin errores
de etiqueta activos; las decisiones de respuesta se comparan por separado.

Los bancos secundarios sí muestran inferencias equivocadas: el importe del
viático extranjero se infiere como `fin` y la empresa que retira una devolución
como `procedimiento`. No cambian sus decisiones de respuesta, pero se
conservan los diagnósticos completos y no se declara exactitud de intención
fuera del banco natural. El contexto heredado puede dominar la similitud.
Estos hallazgos no se usan para volver a ajustar umbrales con los bancos
de verificación; ampliar ejemplos y etiquetas exige una evaluación nueva.

## Procedencia y reproducción

- `antes-*`: final de F2, **ya con memoria de temas**. Se reutilizan sus
  resultados tras comprobar igualdad de código Python/YAML; no representa F1.
- `f1-*`: motor original `39c7878`, con **solo** `metricas.py` sustituido para
  evaluar el mismo tramo literal. Sus conteos medium no se comparan con los
  históricos que acreditaban un literal presente únicamente en la cita amplia.
- `f4-*`: ensayos aislados, sin F3. El primer recorte excesivo de contexto
  pierde herencias; el segundo ensayo se detuvo y no tiene banco completo.
  `f4-final-*` registra contexto del primer pasaje citado tras las guardias,
  y conserva la herencia de la base al empezar esta continuación.
- `final-*`: primera ronda de tres bancos completos, seis combinaciones por banco, con
  auditoría de intenciones reales en `*.intenciones.json`.
- `corregido-*`: ronda final con `genericas_memoria` separado del foco y
  selección. Recupera es-parafrasis-019; `comparacion-antes-separacion.json`
  y `validacion-antes-separacion.json` conservan el G3 fallido anterior.
- `pareadas-corregidas/` y `pareadas-f1-corregidas/`: tres pares finales
  de latencia light AB/BA, 90 preguntas por idioma y versión. Las rondas
  previas `pareadas/` y `pareadas-f1/` también se conservan.
- `pruebas-corregidas.xml`: suite final, **1.054 aprobadas y 2 omitidas**
  (21 min 53 s). `pruebas-separacion.xml`: 62 pruebas específicas aprobadas;
  el primer intento falló en la preparación de la carpeta temporal de
  Windows y se conserva como `pruebas-separacion-temporal-fallida.xml`.
- `pruebas.xml`: primera suite completa, **1.052 aprobadas y 2 omitidas** (23 min).
  Después se corrigió exclusivamente el ranking de diagnóstico para usar
  las mismas pistas semánticas/contexto que la selección; sus **19 pruebas**
  pasan en `pruebas-diagnostico.xml`, incluyendo un caso añadido después de
  recoger la suite completa. No se suman ambos conteos como pruebas únicas.
- `final-revision-code.zip`: código de la primera ronda con esa corrección; su única
  diferencia frente al código de los bancos es `ipsis/aplicacion/consulta.py`.
  `metadata.json` verifica esa procedencia y conserva hashes de archivos,
  modelos locales, plataforma, métrica y estado de recursos.
- `corregido-code.zip`: código de V4 inicial, incluida la separación de las
  palabras genéricas de memoria; corresponde al commit `b23ad8a`. Las
  [correcciones posteriores](../v4-correcciones/README.md) guardan otro ZIP
  y mantienen esta ronda como referencia histórica.

Todas las mediciones son offline con los mismos modelos locales y dos
hilos ONNX, bajo carga variable del equipo. El valor por defecto del servicio
no cambia. G5 se decide por rondas alternadas, no por medias tomadas en
momentos separados; tampoco son una promesa de latencia para otro equipo.

Los ZIP guardan código `.py`, `.yaml` y `.js`, **no los modelos ni el gran
inventario léxico**. Para reproducir, crear árboles nuevos a partir del
`ipsis/` actual sin esos tipos de archivo ni `__pycache__`, extraer el ZIP
correspondiente y conservar los recursos inalterados de F2. Los archivos de
procedencia identifican los árboles medidos. `f1-evaluacion-code.zip` es la
base con evaluación corregida; `f1-original-code.zip` conserva el original.

Ejemplo (ajustar las dos rutas a los árboles reconstruidos):

```powershell
$env:PYTHONUTF8 = '1'
$env:IPSIS_ONNX_THREADS = '2'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:IPSIS_CODIGO = "$PWD/.cache/v4-continuacion/corregido"
$env:TEMP = "$PWD/.cache/v4-continuacion/tmp"
$env:TMP = $env:TEMP
.venv/Scripts/python.exe tests/datos/banco_consultas/medir.py consultas.json light,medium es,en,pt
.venv/Scripts/python.exe tests/datos/banco_universal/medir_latencia.py .cache/v4-continuacion/f1 .cache/v4-continuacion/corregido .cache/v4-repeticion 3
```

El ejecutor `ejecutar.py` prepara también la importación del árbol congelado
para conversaciones y captura el diagnóstico real. `comparar.py` genera el
informe por caso; `documentar.py` comprueba el código final y genera las tablas.
Los scripts de inserción de ejemplos conservan la historia del desarrollo;
**no deben ejecutarse otra vez sobre los YAML finales**.
