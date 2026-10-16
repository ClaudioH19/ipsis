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

## Alcance y rasgos distintivos de unidades hermanas

Dos unidades casi iguales (la tabla de ponderaciones de la Práctica I y la de la II) se confunden porque
lo que las separa es poco. La preparación estructural guarda dos señales para distinguirlas:

- **Alcance** (`scope` en la API): la etiqueta corta que encabeza la unidad, por ejemplo «Práctica Profesional II».
  Se toma del párrafo previo a una tabla o del párrafo en énfasis que abre el grupo (como máximo 80 caracteres y 10
  palabras; se reinicia al cambiar de sección o de título). **En documentos sin encabezados** (formularios, plantillas,
  texto con estilos manuales) sirve cualquier línea corta que parezca un título (hasta 8 palabras y 60 caracteres, sin
  punto final ni marca de lista, como «III. Escala de niveles») y además abre una unidad nueva, de modo que una unidad
  no cruza secciones visuales. Medido sobre los documentos reales, estos cortes no cambian ninguna métrica. **Siempre se
  calcula y se muestra** en el resultado del widget como una etiqueta junto al título del documento, para que quien
  lee sepa de qué parte del documento viene. No cambia el orden. La opción `scope: true` además la agrega al texto
  que se indexa y puntúa; **no se recomienda** (ver abajo).
- **Rasgos distintivos** (`distinctive_terms: N`, `sibling_threshold`): se agrupan las unidades por coseno TF-IDF
  (componentes conexas, determinista, sin modelo ni segunda pasada de codificación) y de cada una se guardan los
  hasta N términos que más pesan en ella y menos aparecen en el resto de su grupo (cifras, códigos como P2 y
  numerales como II incluidos). Se agregan como una línea («Se distingue por: …») al texto indexado y a la unidad
  que ve el reranker, y quedan en el payload (`grupo_similar`, `rasgos_distintivos`). **Activado por defecto con
  `distinctive_terms: 5` y `sibling_threshold: 0,6`** en proyectos nuevos y en los migrados a `config_version` 8; un
  proyecto con su propio bloque `preparation` conserva lo que tiene. Cambiarlo obliga a reindexar en una colección nueva.
  Los términos también se muestran en cada resultado («Se distingue por: …», `distinctive_terms` en la API).

**Contexto en el resultado.** Cada resultado muestra una etiqueta de contexto junto al título del documento: el alcance de la
unidad si lo tiene y, si no, el **título de la sección que la contiene** (el encabezado que está sobre el de la propia unidad;
la ruta no repite lo que ya dice la etiqueta). Un documento sin estructura ni títulos reconocibles no muestra etiqueta: no se
inventa contexto. Así la escala de estructura se degrada sin romperse: documentos con encabezados y tablas (alcance +
sección padre + términos), formularios con líneas-título (alcance por línea corta) y texto plano (solo título del documento).

```yaml
retrieval:
  preparation:
    mode: structural_v1
    distinctive_terms: 5
    sibling_threshold: 0.6
```

**Agrupar por vectores vecinos** (`sibling_similarity: vectors`, `vector_threshold`): en vez de TF-IDF, dos unidades son
hermanas si el coseno de sus vectores del modelo denso supera el umbral (con e5 los cosenos se comprimen: la tabla de P1 y la
de P2 dan 0,977 y la mediana del mejor vecino es 0,958, así que los umbrales útiles son 0,93 a 0,97). Codifica las unidades una
vez más al indexar. Con 5 términos sobre las 56 preguntas adversarias: umbral 0,93 → 0,857; 0,95 → 0,839; **0,97 → 0,893**,
igual que TF-IDF con 0,6. No aporta más que TF-IDF y cuesta una pasada de codificación, por eso el valor por defecto sigue siendo
`tfidf`.

Medido en `medium` (es, bge con 10 candidatos) sobre las 56 preguntas adversarias con documentos reales:

| Variante | hit@1 | informal | pares P1/P2 |
|---|---|---|---|
| sin señales (actual) | 0,857 | 0,786 | 0,794 |
| `scope: true` | 0,786 | 0,679 | 0,706 |
| `distinctive_terms: 3`, umbral 0,5 | 0,821 | 0,714 | 0,794 |
| `distinctive_terms: 5`, umbral 0,4 | 0,875 | 0,786 | 0,853 |
| `distinctive_terms: 5`, umbral 0,6 | **0,893** | 0,821 | 0,853 |
| `distinctive_terms: 8`, umbral 0,4 | 0,875 | 0,786 | 0,853 |

Con 5 términos y umbral 0,6 las otras dos mediciones (33 preguntas formales con documentos reales y 116 del banco
sintético) quedan idénticas (0,849 y 0,991). La ganancia es de 2 casos sobre 56, dentro del ruido de un banco tan
chico y no monótona con los parámetros: es una tendencia, no una conclusión. Agregar el alcance al texto empeora
(6 casos pasan a segundo lugar): repite el nombre de la práctica en muchas unidades y refuerza la coincidencia sin
distinguir a cuál se refiere la pregunta.

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
| LaTeX (`.tex`) | Se convierte a Markdown legible (`ipsis/ingesta/latex.py`) y se prepara como Markdown; parser `latex-estructura-1`. Títulos (`\chapter`…`\paragraph`, el nivel más alto presente es el 1), listas, `tabular` (filas-párrafo con su `\caption` como párrafo previo), entornos tipo teorema (una línea-título corta) y formato en línea reducido a su texto. **Las fórmulas se conservan como texto fuente** (`$…$` en línea; las de bloque, como párrafo propio) para poder buscarlas. Se descartan comentarios y preámbulo; macros desconocidas se quitan sin fallar. Con aviso |
| Texto plano (`.txt`) | Párrafos bajo los títulos que reconoce el parser de texto; parser `texto-estructura-1` |
| PDF | Secciones desde el outline del PDF o, sin él, desde las líneas en letra claramente mayor que el cuerpo; párrafos y listas como en el parser de PDF; parser `pdf-estructura-1`. Se conservan los avisos de OCR y de falta de estructura; un PDF escaneado sin OCR sigue rechazándose. Sin números de página ni tablas |
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
