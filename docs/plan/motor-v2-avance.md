# Primera entrega experimental del motor v2

Fecha: 2026-10-11. Seguimiento del [plan](motor-v2.md).

Este documento describe la primera entrega. Desde el 2026-10-12, el valor
predeterminado es v2, también para archivos sin selector; una elección
explícita de v1 se conserva. Ver el contrato vigente en
[fuentes ordenadas](../methodology/fuentes-v2.md).

## Qué está implementado

`QueryEngine` define una frontera común. La fábrica selecciona v1 o v2 una
sola vez; el servicio conserva el contrato público. La configuración 6 añade
el selector y migra proyectos anteriores a v1 sin escribir sus archivos.

El recorrido v2 es preparación → recuperación → reranking → lectura →
evidencia → redacción. Reutiliza los modelos ONNX del perfil, Qdrant y la
búsqueda híbrida. Las utilidades del corrector se separaron de la comprensión
semántica de v1; mantiene sus borrados simétricos y pares de contexto.

No aplica foco/OOV, clasificación de intención, extracción por tres oraciones,
saltos por reglas, recuperación por premisas ni herencia automática de tema.
Deduplica copias exactas dentro del mismo documento, versión y sección,
registrando las procedencias retiradas. Conserva los scores de cada método.

El lector recibe texto literal narrativo y tablas por campos con mapas a las
celdas, hasta el presupuesto de caracteres; su implementación ONNX usa
ventanas por tokens con solape. El tramo señalado y el contexto mostrado son
distintos: seleccionar un porcentaje no elimina las filas que explican la
tabla ni desplaza la fuente mejor ordenada. Los offsets y el contenido se verifican.
El presupuesto truncado queda registrado. La traza conserva entradas,
salidas, correcciones, candidatos, lectura y razones de selección.

`medium` usa recuperación, reranker y lector; `light` presenta pasajes
recuperados sin lector. V2 no calcula la confianza semántica de v1 ni aplica
su calibración. Para compatibilidad, los campos históricos `top1` y `margen`
valen cero (no calculado); los scores reales siguen en el diagnóstico.
Un tramo preferido frente a «sin respuesta» sigue siendo una hipótesis del
lector. V2 publica pasajes como `related`; sus destacados opcionales llevan
referencias fuente y no se anuncian como `exact_answer` ni respuesta confirmada.

## Activación y retorno

En una copia de proyecto, cambiar únicamente este campo de `config/engine.yaml`:

```yaml
pipeline: v2
```

Volver a `pipeline: v1` y reiniciar selecciona el motor anterior sobre el mismo
índice. Una configuración antigua sin selector elige v1. Los perfiles `light`
y `medium` siguen definiendo los modelos. Los presupuestos de v2 son propios;
no se leen desde la cascada de v1. La preparación
estructural experimental ahora permite crear otro índice en una copia; ver
[preparación documental](../methodology/preparacion-estructural.md).

Opciones externas admitidas, con sus valores por defecto:

```yaml
v2:
  spelling_corrections: true
  max_context_chars: 12000
  retrieve_n: 60
  rerank_candidates: 60
  rerank_k: 8
  read_m: 4
  max_passage_tokens: 384
  stride: 128
```

V2 no hereda temas entre preguntas. Una consulta de seguimiento que omite el
sujeto puede empeorar; la conversación forma parte de la evaluación pendiente.
El formato visible conserva texto y fuentes, pero todavía puede incluir mucho
contexto irrelevante. La API expone destacados con referencias; el widget aún
no los pinta ni representa tablas como bloques estructurados. Se exige
`read_m <= rerank_k <= rerank_candidates <= retrieve_n`.

## Comparación reproducible

Preparar un JSON privado con preguntas independientes o casos con expectativas
literales; las expectativas ayudan a revisar y no sustituyen evaluación semántica:

```json
[
  {"id": "ponderaciones", "question": "¿Cuáles son las ponderaciones?",
   "required": ["20%", "40%"]}
]
```

Desde el repositorio:

```powershell
.venv/Scripts/python.exe herramientas/evaluacion/comparar_motores.py `
  --project C:/ruta/proyecto --questions C:/ruta/preguntas.json `
  --output .cache/motor-v2/comparaciones --rounds 2
```

`--conversation` conserva una sesión por ronda. `--frozen-source` permite
ejecutar v1 desde una copia anterior del código. Cada motor corre en un proceso
separado y secuencial, con dos hilos ONNX y sin descargas. Se requiere caché de
modelos e índice local dentro de `.ipsis/index`; servidor o ruta externa se
rechazan. El comparador crea un snapshot compartido, replicas de SQLite por
backup y una copia del código actual. No consulta el índice servido.

Los reportes privados contienen respuestas, evidencias, trazas, errores,
hashes, configuración efectiva, arranque y latencias. La memoria es RSS
muestreada al terminar consultas, no un pico garantizado. Un registro de error
conserva la traza parcial y el tipo de excepción. El reporte marca los casos
como pendientes de revisión semántica y no elige un ganador automáticamente.

## Lo observado en el corpus real

La primera comparación sobre cuatro preguntas independientes del reglamento
mostró la tabla completa de ponderaciones P1 20/40/40 en v2. El lector señaló
solo «20%»; esto mejora el contexto publicado, pero no demuestra una extracción
correcta de toda la relación. En otra pregunta señaló «4 y 8 semanas», mezclando
P1/P2. La pregunta sobre precio continúa sin respuesta directa; el resultado
recuperado trata de duración. La fecha aparece con su antecedente diciembre–marzo,
pero el chunk también muestra responsabilidades que no fueron solicitadas.

Estos casos confirman dos límites separados: el lector puede elegir un tramo
incorrecto y el chunk actual puede mezclar unidades distintas. No justifican
promover v2 ni afirmar que quitar reglas resuelve todos los fallos.

La conversación original también se repitió dos veces, en procesos secuenciales
con el mismo índice y dos hilos ONNX. V1 añadió «ponderacion» a preguntas posteriores
sobre duración/fecha; v2 mantuvo cada pregunta original. V2 publicó los mismos
tramos en ambas rondas, incluidos los errores descritos arriba. Mediana de latencia:
v1 5,61 s y v2 4,54 s; p95 muestral: 6,40 s y 4,81 s. RSS máximo muestreado:
2,83 GiB y 2,70 GiB respectivamente. Son ocho consultas por motor sobre cuatro
preguntas repetidas, con trazas activas: no acreditan superioridad general ni
un presupuesto válido para corpus nuevos.

Reporte privado de conversación:
`.cache/motor-v2/comparison-conversation/run-3bl_r6x9/comparison.json`.
Los tiempos de la corrida independiente `comparison-final` coincidieron con
otra comprobación de v1; sirven para revisar contenido, no para comparar velocidad.

Los artefactos están en `.cache/motor-v2/`, excluidos de Git. La referencia
congelada incluye código anterior, hashes y el diff de cambios locales, sin
descartarlos. F4 ya tiene preparación estructurada de DOCX y un índice separado;
el avance de esta fase y sus resultados se añaden abajo.

## Preparación estructural: segunda entrega

Se implementaron el esquema documental, referencias por celda/XML, separación
fuente/búsqueda, padres/hijos y almacén verificado por manifiesto. `ipsis prepare`
crea una copia nueva, vista previa HTML y JSON; `--index` construye Qdrant local
en otro directorio/colección. Una colección estructural existente no se recrea.
La preparación solo declara DOCX del cuerpo; imágenes, notas, revisiones y
tablas anidadas tienen capacidades parciales o avisos explícitos.

En los tres documentos reales se prepararon 112 unidades padre y 366 hijos,
frente a 38 chunks del índice anterior. Se conservaron las celdas vacías,
las combinaciones y las tablas P1/P2 separadas. Vista previa privada:
`.cache/motor-v2/structured-context-project/.ipsis/preparation/preview.html`.
El proyecto servido y su índice permanecen intactos.

La primera corrida estructural mostró una pérdida posterior a la recuperación:
la tabla P1 llegaba como candidato, pero el cross-encoder seleccionaba un
anexo comparativo y el lector extraía una condición de reprobación. Se añadió
la sección declarada al texto del reranker, sin modificar el texto literal
del lector ni introducir patrones sobre prácticas. La fragmentación se versionó
como `unidades-estructura-1.1` y se construyó otra copia de índice.

La segunda corrida tampoco resolvió el problema: ante la ponderación de la
primera práctica, v2 mostró la tabla P2 y el glosario como resultados relacionados;
ante la fecha eligió el prerrequisito «quinto semestre». Conservar estructura
mejora la auditabilidad, pero esta muestra presenta regresiones de relación y
no autoriza activar la nueva ingesta en producción.

Reporte de la segunda corrida C/D:
`.cache/motor-v2/structure-context-comparison/run-0tde90u9/comparison.json`.
La corrida anterior se conserva en
`.cache/motor-v2/structure-comparison/run-o6z1fb0o/comparison.json`.
No se interpreta su velocidad: hubo otras comprobaciones compartiendo CPU.

Se completó también el par A/B con el índice anterior:
`.cache/motor-v2/current-matrix-comparison/run-4zt2lb19/comparison.json`.
A mantiene las decisiones anteriores; B conserva la tabla P1 completa, pero
señala solo «20%» y mezcla duración P1/P2. En C, v1 consulta los hijos del
índice nuevo usando sus contratos existentes, sin ampliación al padre; no es
la misma unidad de lectura que D. C tampoco resuelve las ponderaciones P1.
Los tres DOCX tienen los mismos SHA-256 en ambos snapshots. Se verificaron
36 referencias publicadas, incluidos tramos QA, contra el texto canónico de
su extracción: todas son literales. Esto valida procedencia, no corrección
semántica. La comprobación privada está en
`.cache/motor-v2/matrix-literal-checks.json`.

Quedan pendientes el contraste medido con Docling, bloques tabulares en la
salida y evaluación reservada. La lectura por campos incorpora ahora
encabezados externos de tablas grandes con mapas de varios rangos.
La siguiente investigación de calidad debe separar selección del hijo,
expansión al padre, truncado del cross-encoder y elección del tramo QA. No se
han introducido reglas específicas para hacer aprobar estas cuatro preguntas.

La [investigación posterior](../methodology/motor-v2-diagnostico.md) ya separa
esas pérdidas: presupuestos heredados, ranking P1/P2 y rechazo QA de tablas.
Incluye controles de formato, lectura oráculo y reranker alternativo. Sus tres
primeras propuestas están implementadas de forma experimental; los resultados
posteriores se documentan por separado y no acreditan superioridad general.
La [entrega de lectura por campos](../methodology/motor-v2-mejoras-lectura.md)
registra sus resultados, la regresión descartada y los fallos que permanecen.
El [consejo fue retirado](../methodology/consejo-v2.md): las combinaciones con
GTE y BGE encarecieron mucho la consulta en CPU sin mejorar la selección principal.
Su código y opciones se eliminaron; el informe conserva los resultados históricos.
V2 se orienta ahora a [fuentes ordenadas](../methodology/fuentes-v2.md): hasta tres
resultados por página, contexto literal ampliado después del ranking y tarjetas verificables.
La publicación se separa de la lectura QA, que queda apagada por defecto.
La configuración 7 migra la opción retirada y preserva los demás presupuestos.

Validación de esta entrega: 700 pruebas dirigidas aprobadas, una omitida y
una prueba de empaquetado ejecutada aparte y aprobada (701 aprobadas en total).
Incluye configuración, contratos, ingesta, índice, consulta, aplicación, CLI,
servicio, comparador, arquitectura y documentación. El ajuste final de metadatos
de auditoría se verificó también: v2 distingue componentes configurados de los
ejecutados y publica la preparación efectiva del índice cuando existe. Las
pruebas técnicas no incluyen la evaluación documental reservada de promoción.

## Validación

Las pruebas comprueban migración, contrato HTTP, arranque de ambos perfiles,
ausencia de imports semánticos de v1, tablas completas, procedencia, offsets,
deduplicación, presupuesto de variantes, errores/admisión y aislamiento del
comparador. La revisión de calidad usa las respuestas reales además de pytest.
Dos expectativas de aclaración de v1 fallan también con el código congelado
anterior; no se han cambiado para adaptar sus resultados a v2.

Las comprobaciones de compatibilidad sobre las cuatro preguntas independientes
conservan exactamente estado, texto publicado, tramo, evidencias y regla de v1
frente a la referencia congelada. La suite dirigida pasó 416 pruebas más 61 de
servicio; la construcción del wheel y sus licencias también pasó. Las dos
pruebas añadidas después cubren truncado y diagnóstico sin reinterpretación y
también pasaron (480 comprobaciones dirigidas aprobadas en total). El wheel
contiene los módulos nuevos y las opciones externas de v2 se cargan correctamente.
La regresión documental general completa y la evaluación reservada siguen
pendientes como requisitos de promoción, no se deduce su resultado de esta suite.

### Navegación de fuentes

El widget muestra tres desplegables cerrados con archivo y sección, y permite
seguir buscando dentro del ranking completo. El cursor conserva ventanas y
orden, evita duplicados entre páginas y no ejecuta nuevamente los modelos.
La caché tiene límites de tiempo/capacidad; los errores de continuación no
impiden reformular. La API publica `continuation` y `has_more` solo en v2.
El saludo y los textos de búsqueda se adaptan en es/en/pt.

La comprobación local de cuatro preguntas encuentra una fuente aceptada entre
las primeras tres en 4/4 casos de medium, y 2/4 de light. Navegando, ambos
alcanzan 4/4; light necesita hasta ocho páginas. La mediana de continuación
con trazas es de unos 60 ms. Ver costos, límites y artefactos en
[fuentes v2](../methodology/fuentes-v2.md).

### Presupuesto de consulta y puntuación progresiva

Se conserva el conjunto recuperado y se aplica un presupuesto de trabajo
por consulta/página, 2500 ms por defecto. MiniLM puntúa vistas compactas del
mejor hijo recuperado, en lotes de dos y con un techo de 256 tokens. La
fuente publicada conserva contexto literal y offsets. Los pendientes siguen
disponibles; la continuación puntúa solo pendientes y reordena las fuentes
no publicadas. Los reintentos comparten una página ya calculada.

El deadline HTTP optativo reduce el presupuesto del servidor. No se inicia
un lote cuyo costo estimado no cabe; una inferencia iniciada no se interrumpe.
La ruta de v1 conserva su contrato y componentes. Se protege el estado del
tokenizador compartido entre consultas simultáneas.

Comprobación local de once consultas: 1,393–2,550 segundos iniciales, cinco de
seis positivas con fuente aceptada entre las primeras tres y la restante en
la segunda página. Se verificaron 212 referencias y ausencia de inferencias
repetidas. Los controles de ausencia/ambigüedad son resultados para revisar;
no se cuentan como respuestas correctas. Estas rondas no sustituyen la
regresión documental reservada para promover v2 como motor por defecto.

Validación de la entrega progresiva: 478 pruebas distintas aprobadas,
incluidas las 36 del widget, modelos, contratos, arquitectura y empaquetado.
Los ajustes finales de auditoría se verificaron con comprobaciones dirigidas.
