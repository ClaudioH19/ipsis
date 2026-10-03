# Golden set del cliente

El golden set es el banco de preguntas reales del cliente con el que se mide
y calibra el asistente. Vive en la carpeta `golden/` de cada proyecto y nunca
se mezcla con el banco sintético de las pruebas (`tests/datos/banco/`).

El banco versionado queda en `golden/banco/` (`manifiesto.json` más los casos
en JSONL) con el esquema de `rag.evaluacion.banco`. Los comandos
`rag golden plantilla` e `rag golden importar` (plan V3, fase P9) generan y
cargan ese banco a partir de un CSV simple. Debe contener entre 30 y 50
preguntas revisadas por una persona conocedora del corpus, cubrir las seis
categorías (`exacta`, `parafrasis`, `sin_respuesta`, `premisa_falsa`,
`ambigua`, `conversacional`) y separar casos `dev` y `test` antes de calibrar.

Reglas de curación:

- `dev` puede usarse para ajustar umbrales; `test` permanece cerrado hasta la
  comparación final.
- Toda pregunta respondible incluye respuesta literal y evidencia con offsets.
- Las preguntas usadas para descubrir o corregir un defecto no deben ser la
  única medición de ese comportamiento.
- No se copian documentos institucionales sensibles al repositorio; el
  manifiesto identifica y hashea el corpus evaluado localmente.
