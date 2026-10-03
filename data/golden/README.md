# Golden set manual

Este directorio está reservado para el banco manual del dominio real y no se
mezcla con el conjunto sintético de pruebas ubicado en
`tests/evaluacion/sintetico/`.

El archivo final será `golden.jsonl`, acompañado por un `manifiesto.json` con
el esquema definido en `rag.banco_evaluacion`. Debe contener entre 30 y 50
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
