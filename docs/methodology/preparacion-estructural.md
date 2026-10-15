# Preparación documental estructurada

Estado: experimental. Versión documental `estructura-1`, parser
`docx-estructura-1`, fragmentación `unidades-estructura-1.2` y lectura `campos-1`.
No cambia la configuración de proyectos existentes ni demuestra todavía una
mejora general de respuestas. Es independiente del selector de motor.

## Propósito y recorrido

Preservar relaciones que se pierden al convertir una tabla en párrafos
aislados. El texto fuente y el texto contextual utilizado para buscar son
representaciones diferentes. La preparación no utiliza modelos ni reglas
sobre el tema del documento.

1. Recorrer el cuerpo DOCX en orden y conservar párrafos, títulos declarados,
   listas, tablas, filas y celdas físicas.
2. Construir texto canónico y referencias de caracteres, junto con localizadores
   XML. Los offsets corresponden a esta extracción, no a bytes del DOCX ni a
   posiciones de una extracción anterior.
3. Agrupar unidades fuente sin cruzar títulos o tablas. Los párrafos completos
   en negrita delimitan grupos, pero no se convierten en títulos inferidos.
4. Indexar hijos pequeños con título, sección y referencias de contexto.
   Guardar padres completos en un almacén separado y verificable.
5. En v2, recuperar hijos y ampliar al padre declarado antes del reranking.
   Varios hijos del mismo padre no suman votos. El cross-encoder ve la sección
   declarada y la fuente; QA recibe una representación por campos con mapa a
   las celdas. Las citas conservan exclusivamente texto literal. La variante
   por campos para búsqueda/reranking regresó en el control de duración;
   se conserva la representación contextual anterior en esas capas.

## Uso seguro y revisable

Desde una instalación del repositorio:

```powershell
ipsis prepare --project C:/ruta/proyecto --output C:/ruta/proyecto-estructural
```

El destino debe ser nuevo y estar fuera del proyecto original. Se validan todos
los documentos vigentes antes de crear la copia. Se copian configuración y
documentos, sin el índice activo. Revisar
`proyecto-estructural/.ipsis/preparation/preview.html`: contiene tablas con
celdas combinadas, avisos, unidades del lector y texto canónico. El JSON
`documents.json` conserva la representación tipada.

Para preparar e indexar en una sola ejecución, añadir `--index`. Para indexar
después de revisar, ejecutar `ipsis index` desde la carpeta nueva. Se requiere
la caché de modelos habitual; la preparación sin `--index` no carga modelos.
El comando configura v2, preparación estructural y Qdrant local en la copia.

La configuración externa correspondiente es:

```yaml
pipeline: v2
retrieval:
  preparation:
    mode: structural_v1
    max_unit_words: 400
    child_words: 80
```

El valor por defecto de `mode` es `legacy`. En modo estructural, el nombre
efectivo de colección añade `_estructura1` y el directorio Qdrant añade
`-estructura1`; por ejemplo `.ipsis/index/qdrant-estructura1`. No se reutiliza
la colección legacy. Una colección estructural existente no se borra para
reindexarla: usar otra copia o cambiar la versión de colección. Cambiar solo
`pipeline` permite comparar v1/v2 sobre el mismo índice. Volver al proyecto
anterior conserva conjuntamente configuración e índice anteriores.

## Contratos e invariantes

`DocumentoPreparado` extiende el contrato documental existente. Cada elemento
y celda tiene offsets verificables contra el texto canónico. Las celdas guardan
fila, columna, extensión horizontal/vertical y origen de una continuación.
Se conservan posiciones vacías y omitidas sin repetir el contenido de una
celda combinada. Los títulos proceden del outline de Word o del estilo Title;
la primera fila no se declara encabezado salvo que Word lo indique.

Las tablas guardan una referencia al párrafo previo de la misma sección. Esta
es una relación de posición, no una afirmación semántica sobre su contenido.
Los hijos y padres reutilizan `ChunkRecord` con `parent_id`, `prev_id` y
`next_id`. Las referencias adicionales a encabezados son rangos separados;
no se presentan como parte de un tramo literal contiguo.

El manifiesto registra opciones, versiones y SHA-256 del almacén
`<colección>.contexts.json`. La huella estructural incluye geometría y
metadatos, incluso si dos documentos tienen el mismo texto extraído. La huella
del corpus incluye representación de búsqueda, relaciones y fragmentación.
Al cargar y ampliar se comprueban documento, versión, huella, contenido y
offsets. Un padre ausente o un almacén inconsistente produce un error; no se
mezclan versiones de extracción.

`ContextoLectura` contiene texto derivado y copias verificables. Por ejemplo,
`Instrumento: Supervisor; Peso: 20%.` copia etiquetas y valores desde sus
celdas; los separadores añadidos no reciben offsets fuente. Un tramo QA que
cruza etiqueta y valor se representa mediante referencias separadas, nunca
como una cita contigua inventada. El almacén verifica también la identidad de
las celdas y que las copias pertenezcan a la unidad o a su contexto declarado.

Cuando Word no declara encabezados, `campos-1` usa la primera fila como
etiquetas por posición y registra el supuesto
`primera_fila_como_etiquetas_no_declaradas` en vista previa y diagnóstico.
No se modifica el encabezado del contrato documental. Esta aproximación puede
ser inadecuada para tablas sin cabecera: revisar la vista previa; el texto
canónico publicado se conserva incluso cuando el supuesto sea incorrecto.

## Presupuestos y límites

El presupuesto nominal de un padre es 400 palabras; un hijo narrativo tiene
80. Las tablas pequeñas se leen completas y las grandes se agrupan por filas
enteras. Una fila indivisible o un párrafo largo puede superar el presupuesto
del padre. La ampliación conserva el hijo si este quedaría fuera del límite
de caracteres del lector y registra el motivo. El límite de contexto v2
sigue siendo 12 000 caracteres por candidato por defecto.

Los grupos posteriores de una tabla grande incorporan al contexto de lectura
el párrafo previo y sus etiquetas externas, con referencias separadas. La
publicación conserva el rango literal de la unidad y no lo reemplaza por esa
representación derivada. La API añade `answer_blocks[].highlights` con
referencias de posibles fragmentos; QA no elige el pasaje ni asigna `ok` o
confianza alta. El widget todavía no pinta esos destacados ni bloques tabulares.

El parser trabaja en memoria con el DOCX y el texto extraído. La representación
incluye documento completo, padres e hijos, por lo que el almacenamiento tiene
duplicación acotada por la fragmentación. No hay OCR, red ni generación. Los
costos de embeddings, búsqueda, cross-encoder y lector se miden por separado.

## Soporte declarado

| Contenido | Preparación estructural |
|---|---|
| DOCX: párrafos, títulos declarados, listas textuales | Conservados en orden; sin reproducir numeración automática de Word |
| DOCX: tablas, filas, celdas vacías/omitidas y combinaciones | Geometría y referencias conservadas; vista previa tabular |
| DOCX: tablas anidadas | Texto conservado; relaciones internas no soportadas, con aviso |
| Imágenes, formas y ecuaciones | Sin extracción visual/matemática, con aviso |
| Encabezados, pies y notas fuera del cuerpo | No extraídos, con aviso cuando existen partes correspondientes |
| Control de cambios | No resuelto; aviso y revisión de vista previa |
| Markdown (`.md`, `.markdown`) | Títulos `#`, párrafos y listas con sección y offsets literales; parser `markdown-estructura-1`, que reutiliza el de `parsear.py`. Las tablas Markdown quedan como párrafos (una fila por párrafo, sin celdas ni encabezados), con aviso |
| Texto plano (`.txt`) | Párrafos bajo los títulos que reconoce el parser de texto; parser `texto-estructura-1` |
| PDF | Continúa por el recorrido legacy; rechazado por esta preparación |
| XLSX, XLS, CSV y TSV | Registros completos con etiquetas y coordenadas; parser `tabular-1`, sin recalcular fórmulas. Ver [inventarios](../guide/inventories.md) |

La tabla expresa capacidades de estructura, no comprensión de manuales,
recetas, cuentos, leyes o diccionarios. Esos temas requieren evaluación real.
Los textos privados y reportes del experimento se guardan fuera de Git. La
vista previa escapa el contenido documental y no ejecuta sus etiquetas.

## Validación y procedencia

Las pruebas verifican orden, literalidad, separación de tablas P1/P2, celdas
vacías y combinadas, posiciones omitidas, tablas anidadas, geometría en hashes,
fragmentación sin pérdida, ampliación con presupuesto, rechazo de versiones
mezcladas, integridad del almacén, copia independiente y rechazo de recreación
de colecciones existentes. La comparación pareada evalúa además respuestas
reales; pasar estas pruebas no certifica que el lector elija la relación correcta.

Se amplió la dependencia existente python-docx trabajando con celdas físicas
OOXML. Su documentación describe la diferencia entre cuadrícula, celdas
combinadas y filas con posiciones omitidas:
[tablas en python-docx](https://python-docx.readthedocs.io/en/latest/user/tables.html).
[Docling declara DOCX entre sus formatos](https://docling-project.github.io/docling/usage/supported_formats/),
pero todavía no se ha ejecutado una comparación local equivalente de fidelidad,
dependencias y CPU. No se afirma superioridad de este parser frente a Docling.

El índice anterior y ambos motores permanecen disponibles. La preparación y
el motor v2 siguen experimentales; la promoción requiere la evaluación de F6.
