# Tu golden set

> El enrutador v2 no necesita un golden dataset para funcionar. Los bancos de
> consultas siguen siendo útiles para evaluar recuperación, relevancia y
> contexto; las métricas de respuestas directas no certifican su ranking. (El
> comando `ipsis calibrate`, que elegía umbrales de respuesta para el motor v1
> retirado, ya no existe.)

El golden set es el banco de preguntas reales del cliente con el que se mide
el asistente. Vive en la carpeta `golden/` de cada proyecto y nunca
se mezcla con el banco sintético de las pruebas (`tests/datos/banco/`).

El banco versionado queda en `golden/bank/` (`manifest.json` más los casos
en JSONL). Se arma a partir de un CSV simple que completa una persona. Con 30 a 60 preguntas revisadas
por una persona conocedora del corpus sirve para ajustar y comparar perfiles
Debe cubrir las seis categorías internas (exacta, paráfrasis, sin respuesta,
premisa falsa, ambigua, conversacional) y separar casos `dev` y `test`.

## Paso a paso

```bash
ipsis golden template            # golden/golden.csv con preguntas sugeridas desde tus documentos
# completa el CSV en Excel, LibreOffice o un editor
ipsis golden import golden/golden.csv
ipsis golden validate              # ¿sigue coincidiendo con el corpus?
ipsis evaluate                     # cobertura, falsos «ok» y latencia del perfil
```

1. **Plantilla.** `ipsis golden template [--n N]` elige secciones diversas de
   tus documentos (TF-IDF y MMR, sin modelos) y escribe filas con
   `instructions`, `suggested_passage` y `key_terms` para ayudarte. Un
   ~35% son trampas: preguntas del **mismo tema** cuyo dato no está. No pisa
   un `golden.csv` existente sin `--force`. Junto al CSV queda un `README.txt`
   en el idioma del proyecto.
2. **Completar.** Columnas:

   | Columna | Contenido |
   |---|---|
   | `question` | Como la escribiría un usuario real |
   | `type` | `answerable`, `no_answer`, `false_premise`, `ambiguous` o `conversational` |
   | `literal_answer` | Solo si es respondible: el dato mínimo, copiado tal cual del documento |
   | `document` | El documento donde está (nombre o id) |
   | `subtype`, `pair` | `same_topic_trap` y el `id` de la respondible del mismo tema |
   | `id`, `notes` | Opcionales |

   Las columnas de ayuda se ignoran al importar. Los CSV anteriores a ipsis
   0.9, con columnas en español (`pregunta`, `tipo`, `respuesta_literal`…) y
   tipos en español (`respondible`, `sin_respuesta`…), se siguen importando.
3. **Importar.** `ipsis golden import` acepta el CSV (coma o punto y coma,
   con o sin BOM), un `.jsonl` o un SQuAD 2.0. Ubica cada respuesta literal en
   el documento y guarda sus offsets; clasifica las respondibles en exactas o
   paráfrasis. Si hay errores, los lista todos con su fila y no escribe nada.
   Avisa si hay menos de 30 filas o menos de un 30% sin respuesta.
4. **Exportar.** `ipsis golden export --format squad2|csv` para usarlo en
   otras herramientas.

## Reglas de curación

- `dev` puede usarse para ajustar la configuración; `test` permanece cerrado hasta la
  comparación final.
- La separación dev/test se hace al importar. Es 50/50 dentro de cada estrato:
  - categoría interna (exacta, paráfrasis, sin respuesta…);
  - más el subtipo (trampa del mismo tema).

  Así, con bancos chicos, las exactas no quedan todas de un lado. Es
  determinista: reimportar el mismo archivo da la misma separación.
- Toda pregunta respondible incluye respuesta literal y evidencia con offsets.
- Las preguntas usadas para descubrir o corregir un defecto no deben ser la
  única medición de ese comportamiento.
- No se copian documentos institucionales sensibles al repositorio; el
  manifiesto identifica y hashea el corpus evaluado localmente.

## Leer la evaluación y comparar perfiles

```bash
ipsis evaluate --output reports/evaluation.json
ipsis benchmark --bank golden/bank/manifest.json --profiles light,medium --output reports/profiles
```

Todos los perfiles usan el criterio `respuesta_completa_v2`: el literal esperado
debe estar en la respuesta publicada y en evidencia del documento y rango del
golden. Tener el dato solo dentro de una cita que no se usa en la respuesta no
cuenta como acierto. `related` tampoco cuenta como respuesta directa correcta.

- `directas_con_literal` y `cobertura_literal`: aciertos de respuesta completa
  y su proporción sobre las preguntas respondibles.
- `riesgo_aceptadas`: falsos `ok` más directas sin el dato esperado, dividido por
  las respuestas directas. Una abstención no entra en ese denominador.
- `tramos_qa_evaluados`, `tramos_qa_sin_literal` y `exactitud_tramo_qa`: calidad
  del tramo seleccionado respecto al literal del golden. Sin lector, no aplica.
  Resaltar «dos» cuando se esperan «dos días hábiles» falla aquí, aunque la
  respuesta completa pueda contener la información correcta.
  Si el golden exige una cláusula larga, un actor correctamente seleccionado
  también puede fallar esta comparación; el fallo no significa por sí solo
  que el dato QA sea falso. Cura `literal_answer` con el dato mínimo y sus unidades
  o condiciones necesarias.
- `exactitud_offsets`: fidelidad de las citas contra el texto fuente.

`evaluate` devuelve 1 si hay falsos `ok` o directas sin el dato esperado; un
resaltado insuficiente, por sí solo, se reporta aparte. Un literal en la respuesta
no verifica toda su semántica: revisa acciones, condiciones y pasajes añadidos.

Los nuevos reportes llevan versión 2 y declaran el criterio. Los anteriores
se pueden leer, pero `compare` rechaza mezclar criterios: vuelve a evaluar
ambas configuraciones. No se modifican los reportes históricos.
