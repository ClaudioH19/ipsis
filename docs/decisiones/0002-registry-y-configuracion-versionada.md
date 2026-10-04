# ADR 0002: registry declarativo y configuración versionada

## Contexto

El motor necesita cambiar parser, chunker, encoder, fusión o extractor sin
reescribir el pipeline. Además, los YAML deben poder evolucionar sin que una
instalación nueva interprete opciones desconocidas como si fueran válidas.

## Decisión

Se usan contratos Python pequeños en `ipsis.nucleo.contratos`, un
`RegistroComponentes` explícito y schemas Pydantic estrictos en
`ipsis.configuracion.esquemas`.

La selección se declara bajo `componentes` en `motor.yaml`. Las factories se
resuelven por nombre y pueden recibir opciones. Los cambios de formato pasan
por migraciones idempotentes; una versión futura se rechaza.

La configuración efectiva se puede exportar a un snapshot mediante
`ipsis snapshot-config`.

## Consecuencias

- El core no queda acoplado a una implementación concreta.
- Los errores de nombre, tipo o versión aparecen al arrancar.
- Los modelos pesados y conexiones externas se inicializan de forma lazy.
- El snapshot facilita reproducir una ejecución.
- Qdrant y rerankers con estado deben inyectarse desde el servicio.

## Estado

Implementado. Las etapas de la cascada, el retriever Qdrant, el reranker y el
lector se construyen por nombre desde el registry; las configuraciones viejas
migran solas (`config_version` 4).
