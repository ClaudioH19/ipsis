# V2 como enrutador de fuentes

V2 entrega varias fuentes ordenadas para que la persona revise y lea la
información. Usa búsqueda híbrida, corrección ortográfica optativa y hasta un
reranker del perfil. No genera una respuesta ni interpreta una votación como
certeza. El estado continúa siendo `related`; sin evidencia, `no_answer`.
V2 es el motor predeterminado desde el 2026-10-12, por decisión del usuario.
Los proyectos nuevos y los archivos sin selector usan v2, incluso al cargar
configuraciones antiguas. Una selección explícita `pipeline: v1` se conserva.
Para cambiar un proyecto existente, escribe `pipeline: v2` en
`config/engine.yaml` y reinicia el servicio. Para volver, selecciona `v1`.
Cambiar solo el motor reutiliza el índice actual; cambiar la preparación
documental requiere su propia reindexación. La preparación estructural (DOCX,
PDF, Markdown, texto y hojas de cálculo) es la predeterminada en los proyectos
nuevos y en los v2 que no habían elegido preparación, que pasan a
`config_version: 8` con el siguiente comando `ipsis` y deben ejecutar
`ipsis index` ([ADR 0009](../decisions/0009-structural-preparation-by-default.md)).
`retrieval.preparation.mode: legacy` vuelve a los fragmentos de tamaño fijo.

## Configuración

```yaml
config_version: 8
pipeline: v2
v2:
  results_limit: 3
  max_result_chars: 16000
  context_neighbors: 1
  qa_highlights: false
  query_budget_ms: 2500
  reranker_batch_size: 2
  reranker_max_tokens: 256
```

Los proyectos nuevos ya incluyen estas opciones; los existentes reciben sus
valores por defecto al cargar. `results_limit`
controla la publicación y es independiente de `retrieval.top_k` de v1 y
`read_m` del lector. Se muestran hasta tres coincidencias distintas por página de los sesenta
candidatos recuperados. La puntuación es progresiva: `rerank_candidates` limita
el trabajo por página y `query_budget_ms` su presupuesto total (2500 ms).
Se reservan 150 ms para publicar fuentes. El motor no inicia un lote si su
costo estimado no cabe; actualiza la estimación con cada lote. Los candidatos
pendientes se conservan. `rerank_k` se acepta por compatibilidad y no recorta
el conjunto ni condiciona cuántos candidatos se pueden puntuar por página.
Puede haber menos de tres fuentes si las ventanas repiten evidencia.

MiniLM usa lotes de dos y un techo de 256 tokens, sin ampliar el contexto
publicado para puntuar. Una unidad padre estructural se representa con su
mejor hijo recuperado y los encabezados que ya contiene el índice. La vista
queda en la traza con el ID y offsets del hijo; no reemplaza el texto fuente.
En legacy se usa el pasaje recuperado. El truncado del tokenizador sigue
siendo una limitación del modelo y no certifica que haya leído toda la fuente.

`light` usa búsqueda híbrida sin reranker; `medium` incorpora MiniLM y, en v2,
omite el lector QA por defecto. `qa_highlights: true` permite destacados
optativos si el perfil tiene lector; nunca cambia el ranking ni convierte
los pasajes en respuestas exactas. Los comandos de modelos del proyecto
listan, descargan y verifican solo los componentes ejecutados. Un perfil
explícito en `models download --profile` mantiene su conjunto habitual.

## Contexto y procedencia

Se puntúan vistas de las unidades recuperadas. Las fuentes se amplían para lectura con una
unidad anterior y una posterior de la misma sección, documento y versión.
El índice estructural usa las unidades y texto canónico guardados con sus
hashes. En legacy se carga la extracción del corpus al construir el motor y
se verifican versión y texto de la coincidencia antes de ampliar párrafos.
No se concatenan textos separados inventando espacios o offsets.

La ventana se centra en la coincidencia cuando el presupuesto limita su
tamaño. Si resulta recortada, la API y la tarjeta lo indican. Cada resultado
conserva los offsets completos de la ventana y los de la coincidencia.
Una coincidencia ya visible en una ventana publicada no se repite en otra
tarjeta de la misma sección y versión. El score original se conserva y no
se publica como probabilidad de respuesta correcta.

## API y widget

`/ask` identifica el modo con `response_mode: ranked_sources`. `fragments`
es la lista de resultados; conserva los campos anteriores y añade `rank`,
`doc_id`, `source_name`, `match_start`, `match_end`, `truncated` y `score_kind`.
Este último distingue `reranker_logit` de `retrieval_score`; no se deben
ordenar fuentes mezclando esos valores. `rank` indica el orden publicado. El nombre de
archivo ayuda a reconocer la fuente y no expone la ruta local. `text` contiene la ventana
literal completa; `offset_start` y `offset_end` la anclan al documento.
La coincidencia está dentro de esa ventana. `answer` ofrece una representación
de texto numerada para clientes anteriores; no certifica una respuesta única.

El widget v2 presenta resultados como un buscador: barra de consulta arriba,
título de sección, archivo/versión, ruta de secciones y extracto visibles.
Las palabras de la consulta se destacan en el extracto sin sustituir el
texto fuente. El título y **Leer contexto completo** abren la ventana literal.
No se crean enlaces a archivos que la API no sirve ni se promete mostrar
el documento entero cuando se dispone de una ventana de contexto.

### Lectura de párrafos y tablas

El texto documental respeta `presentation.text_align` del tema; el valor por
defecto es justificado, también en `search` y `search_compact`. Los títulos y
las celdas se alinean al inicio. Los párrafos tienen separación vertical y
conservan los saltos de línea. Los encabezados declarados en el documento
se muestran como subtítulos; no se generan títulos por interpretación del texto.

Los fragmentos v2 pueden incluir `source_blocks`: párrafos, encabezados y
tablas con filas, columnas, celdas y offsets globales. Se verifican contra
el texto de la ventana. DOCX legacy y Markdown conservan la cuadrícula al
volver a leer el corpus, sin cambiar su texto canónico ni requerir reindexación
solo por esta presentación. La preparación estructural conserva además las
combinaciones horizontales y verticales. La primera fila no se convierte en
encabezado si el documento no la declara.

Las tablas cortas se ven en el extracto; las largas se leen en el contexto
desplegable, con desplazamiento horizontal accesible en pantallas estrechas.
**Ver texto original** permite comparar la representación con el texto literal
y sus separadores. `text`, offsets y ranking mantienen su contrato.

Si falta estructura, es inconsistente o una tabla preparada queda cortada
por el límite de contexto, se conserva el texto literal. No se inventan
columnas separando cualquier barra `|` encontrada en una frase. Las columnas
ya perdidas en una extracción PDF o de texto plano requieren mejorar esa
extracción; esta presentación no puede reconstruirlas con certeza.

La lista acumula **Mostrar más resultados** de tres en tres. Una consulta nueva
reemplaza la lista; no se presenta como una conversación de burbujas. El
contador describe resultados efectivamente mostrados y no estima totales
del corpus. La consulta se conserva en la barra para modificarla. El modo
se informa en `/config::response_mode` y se reconoce también en `/ask`.

Dos presets nuevos permiten ajustar la presentación:

```powershell
ipsis widget theme apply search
ipsis widget theme apply search_compact
ipsis widget theme preview --output preview.html
```

`search` usa un panel amplio, enlaces destacados y espacios para escanear
los extractos. `search_compact` reduce los espacios para paneles pequeños.
Los temas classic/minimal/editorial/contrast también usan la lista de búsqueda
cuando el motor es v2. El formato de citas de v1 conserva su configuración.
Se puede incrustar el buscador con `<ipsis-chat mode="embedded" api="...">`.
El panel conserva soporte móvil, contraste, teclado y el acceso al código fuente.

### Continuación de una búsqueda

La primera respuesta incluye `continuation` (cursor opaco o `null`) y `has_more`.
Para pedir la siguiente página se envía al mismo `/ask` la misma `question`,
el mismo `session_id` y el cursor en `continuation`. Los rangos son globales:
1–3, 4–6, etc. Un reintento con el mismo cursor devuelve la misma página.
El botón **Mostrar más resultados** añade la siguiente página sin repetir la pregunta.
Escribir otra pregunta inicia una búsqueda independiente y desactiva los
botones anteriores; un error temporal permite reintentar el cursor.

Se guarda el conjunto recuperado, las ventanas ya ampliadas/deduplicadas y
las puntuaciones conocidas. Cada continuación puntúa solo candidatos
pendientes, dentro de su propio presupuesto, y reordena las fuentes aún no
publicadas. Los candidatos puntuados van primero, ordenados por logit; los
pendientes mantienen el orden híbrido. No se comparan numéricamente scores
híbridos y logits, ni se afirma que las tres primeras sean las mejores de
un conjunto que el modelo todavía no ha terminado de puntuar.

Las fuentes ya publicadas y sus rangos permanecen fijos. Repetir un cursor
reutiliza su página sin inferencias; dos peticiones simultáneas del mismo
cursor comparten el trabajo. Otras búsquedas tienen su propio candado y
pueden avanzar independientemente. No se repite recuperación ni QA; los
destacados QA optativos de la primera búsqueda se reutilizan si corresponden.
Las coincidencias incluidas en un contexto no reaparecen en otra página.
La tokenización de denso y reranker protege su estado mutable compartido.

`/ask::deadline_ms` es optativo y reduce el presupuesto del servidor;
un cliente no puede ampliarlo. El tiempo cuenta desde el inicio de cada
consulta/continuación, incluida la espera por un cursor en curso. Se registra
el presupuesto aplicado, cada lote, sus candidatos y los pendientes. Este
es un límite de trabajo, no un plazo duro: una inferencia ONNX iniciada,
la recuperación o la escritura del registro no se interrumpen. El lector
optativo no arranca si el presupuesto ya se agotó; habilitarlo añade costo
que no está incluido en las mediciones de latencia con QA apagado.

Los cursores pertenecen a una consulta, sesión e instancia del motor. Caducan
a los diez minutos o al reiniciar/recargar el motor. La caché está protegida
para concurrencia y limitada a 64 búsquedas y 32 millones de caracteres
retenidos estimados (este presupuesto no equivale al consumo exacto de RAM).
El desalojo por capacidad también puede invalidar una búsqueda antes del plazo.
Un cursor inválido devuelve HTTP 409 e invita a enviar la pregunta de nuevo;
v1 devuelve HTTP 400 si un cliente pide una continuación que no soporta.

No se amplía silenciosamente la búsqueda más allá del conjunto recuperado:
cuando se agota, el widget invita a reformular. La primera búsqueda aplica el presupuesto
del reranker; paginar no corrige su calidad ni la del parser. El
saludo, subtítulo, campo de consulta y mensajes de v2 describen una búsqueda
de fuentes en español, inglés y portugués. El modo de búsqueda sustituye
el saludo del tono; v1 mantiene sus textos y presentación.

Este contrato permite navegar manuales, normas, narraciones o fichas de
productos. La implementación actual admite DOCX, PDF con texto, Markdown y
TXT en legacy, y DOCX en preparación estructural. Este cambio no incorpora
un parser de Excel ni interpreta stock o precios como datos estructurados.

## Validación

Las pruebas cubren publicación independiente de QA, ausencia del consejo,
migración sin mutar opciones, modelos ejecutados, contexto de tablas,
límites de sección/versión, coincidencias tardías, deduplicación, offsets y
presentación de tarjetas en navegador con contenido adversarial.
Se conserva el [informe del consejo retirado](consejo-v2.md) como antecedente.

## Comprobación anterior del caso real (cinco resultados)

Se ejecutaron cuatro preguntas conocidas sobre los mismos tres DOCX, en
réplicas locales, dos hilos ONNX, una ronda, con trazas y QA apagado. La métrica
comprueba si una unidad fuente aceptada queda íntegra en alguna de las cinco
ventanas publicadas. No mide una respuesta única ni calidad general.

| Perfil | Reranker | Fuente aceptada visible | Mediana local |
|---|---|---:|---:|
| light | ninguno | 2/4 | 0,193 s |
| medium | MiniLM, lote 16 | 4/4 | 12,011 s |
| medium | MiniLM, lote 4 | 4/4 | 8,181 s |

Cada corrida publica cinco resultados por pregunta, con 20 referencias
verificadas contra el texto canónico. La primera medición muestra que el
reranker consume prácticamente todo el tiempo; ampliar contexto cuesta
unos milisegundos. Lotes de cuatro reducen el relleno de textos breves junto
a largos; ese ajuste queda como presupuesto general de v2, sin cambiar v1.
El techo de tokens queda declarado por separado de la ventana publicada.
La diferencia observada es local: una ronda y actividad del sistema sin
controlar no permiten prometer una aceleración en cualquier CPU/corpus.

Light recupera la ponderación P1 y P2 pero no presenta las unidades aceptadas
de las dos preguntas de fecha. Medium sí las presenta. El enrutador deja que
la persona lea y verifique, pero no resuelve por sí mismo la pérdida de recall.
El consejo se elimina; seguir ampliando modelos no es la vía adoptada.

Artefactos privados, con código congelado, configuración y trazas:

- `.cache/motor-v2/router/run-al3m8z6k/`: medium, lote 16.
- `.cache/motor-v2/router/run-0zf52gaw/`: medium, lote 4.
- `.cache/motor-v2/router/run-v_q3aa6s/`: light.

En cada directorio, `report.json` incluye la salida pública que pinta el widget
y las referencias; `summary.json`, costos y parámetros. Las mediciones usan
contexto estructural; la prueba separada de Markdown valida la ampliación
legacy sin reindexar. La suite amplia pasó 747 pruebas, con una omitida; las
33 del widget también pasaron. El caso legacy añadido y el empaquetado pasan
por separado (782 comprobaciones únicas aprobadas). El ajuste final de lotes
y metadatos se verificó con otras 128 comprobaciones dirigidas, sin fallos.

## Navegación anterior con ranking completo: comprobación local

Se repitieron las mismas cuatro preguntas con ranking completo, tres resultados
por página, dos hilos ONNX y trazas activadas. Se navegó hasta agotar cada
búsqueda y se validó el texto de cada ventana contra el documento canónico.

| Perfil | Fuente aceptada en página 1 | En alguna página | Mediana inicial | Mediana continuación |
|---|---:|---:|---:|---:|
| medium | 4/4 | 4/4 | 8,437 s | 0,062 s |
| light | 2/4 | 4/4 | 0,229 s | 0,059 s |

En light, la pregunta de fecha original requiere llegar a la página 8; la
fecha explícita aparece en la página 2. Esto no equivale a acertar la primera
opción: muestra evidencia accesible con navegación y deja pendiente mejorar
el ranking. Las continuaciones ejecutaron solo evidencia y redacción, sin
nuevas inferencias. No se repitieron IDs entre páginas.

Artefactos privados con código congelado y respuestas de todas las páginas:

- `.cache/motor-v2/router/run-mbzchj_t/`: medium, 84 referencias verificadas.
- `.cache/motor-v2/router/run-923zs_x0/`: light, 83 referencias verificadas.

Estos cuatro casos conocidos y una ronda local no permiten estimar la calidad
general, ni garantizan que todos los documentos relevantes estén en el conjunto
recuperado. La evaluación futura debe distinguir fuente correcta entre las
primeras tres, cantidad de páginas necesarias y costo de la búsqueda inicial.

La verificación técnica de navegación aprobó 442 pruebas distintas, incluidas
36 de navegador y la construcción del paquete distribuible. Cubre expiración,
sesión/consulta, desalojo, reintentos, doble clic, reformulación, offsets y
compatibilidad de v1. La vista interactiva privada está en
`.cache/motor-v2/paginacion/preview-fuentes.html`.

## Diagnóstico previo al presupuesto progresivo de 1–3 segundos

El preset v2 priorizó recuperar y puntuar un conjunto amplio; no aplica un
presupuesto de tiempo. En la corrida medium anterior, el reranker consume
entre 5,099 y 11,102 segundos por pregunta, aproximadamente el 95–98 %
del tiempo total. De los 60 candidatos recuperados, la deduplicación deja
18–36 pares pregunta/pasaje para MiniLM, con lotes de cuatro y hasta 512 tokens.
La expansión de fuentes publicadas ocurre después y no explica esa latencia.
QA está apagado. El presupuesto p95 del perfil se usa en evaluaciones;
`/ask::deadline_ms` se declara, pero actualmente no se aplica al motor.

Se hicieron pruebas exploratorias sobre las mismas cuatro preguntas,
dos hilos ONNX, una ronda con trazas y una instancia por experimento.
`rerank_candidates` es el techo; el número efectivo puede ser menor.

| Techo de candidatos | Tokens del reranker | Mediana inicial | Máximo local | Fuente aceptada entre las tres |
|---:|---:|---:|---:|---:|
| 60 | 512 | 8,437 s | 11,311 s | 4/4 |
| 60 | 256 | 4,200 s | 6,012 s | 4/4 |
| 12 | 512 | 5,108 s | 7,289 s | 3/4 |
| 20 | 256 | 3,778 s | 4,372 s | 3/4 |
| 60 | 128 | 2,942 s | 3,609 s | 3/4 |

Reducir a doce o veinte elimina del conjunto publicado la fuente de fecha
original, que llegaba en la posición 27 antes del reranking. En el motor
actual, los candidatos fuera del techo de reranking también quedan fuera de
la continuación: reducir ese techo sin conservar el resto perjudica el recall.
Con 128 tokens se conservan los candidatos, pero la fecha explícita pasa a
la segunda página. La mediana se acerca al objetivo sin cumplirlo en todos
los casos. No se cambiaron los valores por defecto a partir de estas pruebas.

Para cumplir el objetivo hace falta tratar la latencia como presupuesto de
trabajo: conservar la recuperación amplia, ofrecer al reranker representaciones
compactas de las unidades y evaluar puntuación progresiva por lotes. Un límite
de tiempo debe evitar iniciar más inferencias, no limitarse a devolver un
error al terminar una inferencia lenta. El texto completo publicado y sus
citas deben mantenerse separados del texto usado para puntuar. Cualquier
variante progresiva debe especificar cómo ordena los candidatos aún no
puntuados y preservar las fuentes restantes para seguir buscando.

Artefactos privados:

- `.cache/motor-v2/router/run-atrykbc0/`: techos 60/256, 12/512 y 20/256.
- `.cache/motor-v2/router/run-w6s3kjg5/`: techo 60/128.

Son comparaciones exploratorias, no mediciones de p95 ni garantías de SLA.
Las representaciones recortadas no equivalen a una preparación estructural
compacta; las cuatro preguntas no permiten aprobar un cambio general.

## Entrega progresiva y objetivo de latencia

La versión progresiva ya aplica `query_budget_ms`, usa vistas del hijo
recuperado y conserva pendientes para la continuación. Se repitieron los
cuatro casos iniciales y luego los once del banco exploratorio, dos hilos
ONNX, QA apagado y trazas activadas. La calidad se cuenta solo sobre las
seis preguntas con unidades aceptadas; las otras cinco son controles de
ambigüedad/ausencia y no tienen respuesta positiva etiquetada.

| Corrida local | Mediana inicial | Máximo inicial | Fuente aceptada entre las tres | Navegando |
|---|---:|---:|---:|---:|
| Cuatro casos iniciales | 1,824 s | 2,407 s | 4/4 | 4/4 |
| Once consultas, seis positivas | 2,259 s | 2,550 s | 5/6 | 6/6 |

En la ronda amplia, la pregunta de fecha original aparece en la página 2.
Se validaron 212 referencias publicadas contra el texto canónico, sin
repetir IDs de fuentes ni puntuar dos veces el mismo candidato en una
búsqueda. Las continuaciones tienen una mediana de 40 ms, porque la mayoría
ya no necesita inferencias, pero un máximo de 2,275 s al puntuar pendientes.
El botón de continuar también tiene presupuesto; no se promete que siempre
cueste los 60 ms de la modalidad anterior que puntuaba todo al inicio.

El costo inicial está entre 1 y 3 segundos en estas corridas locales con
modelos calientes. La cantidad que se alcanza a puntuar depende del tiempo
disponible y de la actividad del sistema: no es un ranking global completo
ni una garantía de latencia para cualquier CPU o corpus. Los controles siguen
ofreciendo fuentes `related`, sin certificar respuestas exactas ni inventar
valores ausentes. Su pertinencia debe revisarse; no se cuentan como aciertos.

Artefactos privados con código congelado:

- `.cache/motor-v2/router/run-3ld4x21l/`: cuatro casos, contexto completo.
- `.cache/motor-v2/router/run-j902e5p7/`: once consultas, diagnósticos de cada
  continuación y comprobación de inferencias no repetidas.

Las pruebas automáticas añadidas ejercitan plazos agotados, preservación de
cola, logits negativos, lotes inválidos, vistas por versión, reintentos,
concurrencia del mismo cursor, tokenización compartida y deadline HTTP.

Verificación técnica de esta entrega: 478 pruebas distintas aprobadas,
incluidas 36 de navegador, los modelos, la arquitectura y el paquete
distribuible. Los ajustes finales de auditoría se comprobaron además con
pruebas dirigidas de motor, paginación y API.

## Templates de búsqueda y vistas de revisión

Las vistas interactivas privadas usan el widget real y una consulta fija del
corpus documentado, con respuestas guardadas. Permiten abrir contexto y
mostrar más resultados; no ejecutan modelos ni llamadas al servicio:

- `.cache/motor-v2/buscador/buscador-real.html`: preset search.
- `.cache/motor-v2/buscador/buscador-compacto-real.html`: preset search_compact.

El comando de vista previa de esos presets muestra tres resultados de
**ejemplo**, identificados como tales, con contexto accesible. Las pruebas
de navegador verifican los seis temas, barra de búsqueda (abajo), extractos visibles,
destacados literales, teclado, seguridad de texto, continuación y reemplazo
al reformular. La recuperación y el presupuesto del motor no cambian en esta
entrega de presentación.

La entrega de templates aprobó 192 pruebas distintas, incluidas 42 de
navegador y el empaquetado. Se verifican texto seguro, extractos Unicode,
consulta persistente, acceso por teclado, nuevos presets y compatibilidad
de API y configuración.
