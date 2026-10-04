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
from rag.configuracion.carga import cargar_dominio, cargar_proyecto

motor = cargar_proyecto()
dominio = cargar_dominio()
```

## Componentes

La sección `componentes` selecciona implementaciones por nombre:

```yaml
componentes:
  parser: builtin
  chunker: builtin
  dense_encoder: onnx
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
from rag.nucleo.contratos import RegistroComponentes
from rag.aplicacion.registro_base import registrar_componentes_base

registro = registrar_componentes_base(RegistroComponentes())
fusion = registro.crear("fusion", "rrf", k=60)
```

Los adaptadores base disponibles no descargan modelos durante el registro.
`onnx` abre la sesión del modelo solo al usarlo por primera vez. La conexión
a Qdrant y los rerankers se configura desde el servicio porque depende del
índice, la colección y los recursos disponibles.

### Backend de recuperación

`qdrant` es el único backend soportado. `recuperacion.modo` permite elegir
`vectorial` o `hibrida`; ambos conservan el mismo contrato y requieren volver a
indexar cuando cambia la representación persistida.

### Perfil de instalación

El perfil activo está en `configuracion/asistente.yaml::perfil` (`light`,
`medium` o `heavy`). `bm25` es solo un perfil de diagnóstico de
`rag benchmark`, no se instala.

```
rag perfil mostrar           # perfil, modelos, presupuesto p95, índice y calibración
rag perfil cambiar medium    # cambia solo asistente.yaml::perfil
```

`rag perfil cambiar` no descarga modelos, no indexa, no calibra y no borra
nada. Se conservan `ajustes_perfil`, el índice y `calibracion.yaml`. Antes de
escribir, valida los `ajustes_perfil` del proyecto contra el perfil destino.
Repetir el perfil activo no hace nada.

- **light ↔ medium:** usan el mismo modelo denso (e5-small, 384), así que el
  índice sirve para ambos.
- **heavy:** usa e5-base (768) y necesita su propio índice (`rag indexar`).
  Cada modelo denso vive en su colección: el índice anterior se conserva, y
  volver al perfil anterior lo hace compatible otra vez sin reindexar.
- **Compatibilidad del índice:** se decide por el manifiesto
  (`.rag/indice/<coleccion>.manifiesto.json`), con el modelo denso, la
  dimensión y la versión del payload. No se decide por el nombre del perfil.
- **Calibración:** cualquier cambio de perfil la invalida, porque su
  procedencia registra perfil, modelos y corpus. El motor la ignora y rigen
  los umbrales del perfil. El archivo se conserva para auditoría. Para
  recuperarla: `rag calibrar --aplicar`.

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
from rag.configuracion.carga import configuracion_efectiva

snapshot = configuracion_efectiva()
```

El snapshot contiene `motor`, `dominio`, `config_version` y
`snapshot_version`. No contiene secretos derivados.
