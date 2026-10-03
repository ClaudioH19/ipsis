# Referencia de configuración

## Versionado

`configuracion/motor.yaml` y `configuracion/asistente.yaml` usan
`config_version`. La versión vigente es `2`.

- Si falta `config_version`, el cargador interpreta el archivo como versión 0
  y lo migra de forma secuencial hasta la versión 2.
- La migración no modifica el archivo original.
- La validación rechaza claves desconocidas.
- Una versión superior a la soportada produce un error explícito.

La versión 2 elimina `recuperacion.reranker`: la implementación se selecciona
únicamente mediante `componentes.reranker`. Los archivos anteriores se migran
sin modificar el YAML de origen.

La configuración ya validada puede cargarse desde Python:

```python
from rag.configuracion import cargar_dominio, cargar_proyecto

motor = cargar_proyecto()
dominio = cargar_dominio()
```

## Componentes

La sección `componentes` selecciona implementaciones por nombre:

```yaml
componentes:
  parser: builtin
  chunker: builtin
  dense_encoder: sentence_transformers
  sparse_encoder: bm25
  retriever: qdrant
  fusion: rrf
  reranker: null
  intent_classifier: rules
  answer_extractor: sentence_selector
  evidence_verifier: literal_offsets
  response_renderer: templates
```

Un valor `null` desactiva un componente opcional. Una implementación puede
recibir opciones usando la forma extendida:

```yaml
componentes:
  fusion:
    nombre: rrf
    k: 60
```

El registry se puede usar desde una integración:

```python
from rag.componentes import RegistroComponentes
from rag.registro import registrar_componentes_base

registro = registrar_componentes_base(RegistroComponentes())
fusion = registro.crear("fusion", "rrf", k=60)
```

Los adaptadores base disponibles no descargan modelos durante el registro.
`sentence_transformers` carga el modelo solo al crear el encoder. La conexión
a Qdrant y los rerankers se configura desde el servicio porque depende del
índice, la colección y los recursos disponibles.

### Backend de recuperación

`qdrant` es el único backend soportado. `recuperacion.modo` permite elegir
`vectorial` o `hibrida`; ambos conservan el mismo contrato y requieren volver a
indexar cuando cambia la representación persistida.

## Presentación del widget

`configuracion/estilos.yaml` admite un `preset` y opciones independientes del
contenido documental:

```yaml
preset: editorial
presentacion:
  densidad: comoda
  citas: abiertas
  mostrar_etiqueta_estado: true
```

Los presets se administran mediante `rag widget tema`. `/config` expone estos
valores para que el widget los aplique, pero no ofrece escritura HTTP. La clave
pública del widget autoriza consultas y no debe utilizarse para administración.

## Snapshot efectivo

Para obtener una copia de la configuración con defaults y valores resueltos:

```bash
rag snapshot-config
rag snapshot-config --salida .cache/config-produccion.yaml
```

También está disponible desde Python:

```python
from rag.configuracion import configuracion_efectiva

snapshot = configuracion_efectiva()
```

El snapshot contiene `motor`, `dominio`, `config_version` y
`snapshot_version`. No contiene secretos derivados.
