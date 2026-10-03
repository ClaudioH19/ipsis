# Arquitectura

`rag-extractivo` es una librería de recuperación documental extractiva. El
motor Python ingiere documentos, crea un índice híbrido y expone una API. El
widget web consume esa API; no ejecuta embeddings ni Qdrant en el navegador.

```text
documentos -> parsing -> chunks -> metadata -> Qdrant dense+sparse
                                           |
pregunta -> análisis -> Qdrant -> selección literal -> API -> widget
```

## Restricción central

El sistema no genera afirmaciones. Una respuesta contiene texto literal del
corpus con offsets verificables y conectores definidos en configuración. Si la
evidencia no alcanza, devuelve un estado de abstención o aclaración.

## Capas

- `rag/`: ingesta, configuración, recuperación y contratos.
- `rag/servicio/`: API, pipeline de decisión, seguridad y widget.
- `rag/recursos/plantillas/`: recursos globales incluidos en el wheel.
- `configuracion/`: copia editable y específica de cada instalación.
- `documentos/`: corpus del usuario, nunca incluido en la distribución.

## Artefactos de distribución

- wheel Python: motor, CLI, API, recursos y widget actual;
- imagen Docker: instala el mismo wheel y conecta con Qdrant;
- widget: actualmente se sirve como `/widget.js`; la V2 añadirá paquete npm,
  bundle ESM/UMD y Web Component manteniendo esta vía simple.

## Evolución V2

Los protocolos de `rag.componentes` y esquemas de `rag.esquemas` forman el
límite entre etapas. Las implementaciones V1 se adaptarán gradualmente sin
romper el contrato HTTP vigente.

## Contratos, configuración y registry

Los modelos de [rag/esquemas.py](../rag/esquemas.py) representan los datos que
cruzan las etapas de la tubería. Todos incluyen `schema_version`; los offsets
de `EvidenceSpan` deben corresponder exactamente al largo del texto literal.

Los contratos de [rag/componentes.py](../rag/componentes.py) describen las
capacidades intercambiables: parser, chunker, encoders, retriever, fusión,
reranker, análisis de intención, extracción, verificación y renderizado.
`RegistroComponentes` normaliza nombres, rechaza reemplazos accidentales y
puede resolver una selección declarativa con opciones.

Los adaptadores actualmente disponibles se registran mediante
`rag.registro.registrar_componentes_base()`. Esta función no carga modelos ni
abre conexiones; las dependencias pesadas se inicializan únicamente cuando se
crea el componente correspondiente.

El retriever base soportado es `qdrant`, en modo vectorial o híbrido. Entrega
tipos versionados, admite filtros exactos por entidad y conserva señales densas
y léxicas en el diagnóstico.

La configuración de [configuracion/motor.yaml](../configuracion/motor.yaml)
declara los nombres estables bajo `componentes`. Los archivos antiguos sin
`config_version` se migran de forma idempotente a la versión 2; las versiones
futuras se rechazan para evitar interpretar silenciosamente una configuración
incompatible.

Para inspeccionar todos los defaults aplicados:

```bash
rag snapshot-config
```

El comando escribe `.cache/configuracion-efectiva.yaml`, sin modificar los
YAML fuente. Qdrant y los rerankers que requieren estado de ejecución se
inyectan desde el servicio y no se inicializan al importar la librería.
