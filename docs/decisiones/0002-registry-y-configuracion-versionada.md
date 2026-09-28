# ADR 0002: registry declarativo y configuración versionada

## Contexto

La V2 necesita cambiar parser, chunker, encoder, fusión o extractor sin
reescribir el pipeline. Además, los YAML deben poder evolucionar sin que una
instalación nueva interprete opciones desconocidas como si fueran válidas.

## Decisión

Se usan contratos Python pequeños en `rag.componentes`, un
`RegistroComponentes` explícito y schemas Pydantic estrictos en
`rag.esquemas_configuracion`.

La selección se declara bajo `componentes` en `motor.yaml`. Las factories se
resuelven por nombre y pueden recibir opciones. Los cambios de formato pasan
por migraciones idempotentes; una versión futura se rechaza.

La configuración efectiva se puede exportar a un snapshot mediante
`rag snapshot-config`.

## Consecuencias

- El core no queda acoplado a una implementación concreta.
- Los errores de nombre, tipo o versión aparecen al arrancar.
- Los modelos pesados y conexiones externas se inicializan de forma lazy.
- El snapshot facilita reproducir una ejecución.
- Qdrant y rerankers con estado deben inyectarse desde el servicio.

## Estado

Implementado para los adaptadores base. La integración completa del retriever
Qdrant y del reranker con el pipeline multietapa queda para las fases 3 y 4.
