# ADR 0001: respuestas no generativas

- Estado: aceptado
- Fecha: 2026-09-21

## Contexto

La librería debe contestar preguntas sobre documentos propios con trazabilidad
y sin depender de servicios de generación.

## Decisión

Toda afirmación factual será un span literal del documento. Se permiten
encoders, clasificadores, rerankers y lectores extractivos porque puntúan o
seleccionan evidencia; no producen prosa nueva. Los únicos textos adicionales
son templates configurados y probados.

## Consecuencias

- Las respuestas son auditables mediante documento, sección y offsets.
- El sistema debe abstenerse o pedir aclaración con mayor frecuencia.
- Resúmenes libres y síntesis abiertas quedan fuera de alcance.
- Mejorar la interacción depende de planes, slots, estados y templates.

