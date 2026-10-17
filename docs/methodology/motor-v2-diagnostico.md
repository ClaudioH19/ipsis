# Diagnóstico de calidad del motor v2

Fecha: 2026-10-11. Estado: histórico. Investigación sobre tres DOCX reales,
anterior a que v2 fuera el motor predeterminado (2026-10-12) y a que lo fuera la
preparación estructural (2026-10-15). El proyecto original seguía configurado con
v1 e ingesta legacy; v2 y la preparación estructural se ejecutaron en copias. No se
cambió el motor para hacer pasar los casos.

## Conclusión

Se retiraron los vetos semánticos de v1, pero quedaron dos decisiones de
arquitectura insuficientes: presupuestos diseñados para v1 y elección del
pasaje por la mayor preferencia QA frente a «sin respuesta». Además, guardar
celdas estructuradas no implica entregarlas estructuradas al lector:
actualmente recibe tablas aplanadas con barras.

Hay pérdidas en recuperación, reranking y lectura. Ampliar candidatos ayuda
a un caso de fecha, pero también puede introducir respuestas incorrectas con
scores QA mayores. Cambiar únicamente el reranker tampoco resuelve el problema.

## Método y controles

Se ejecutaron 72 consultas con variantes de presupuesto/corrección/reranking,
sobre ocho preguntas distintas: cuatro del caso real y controles que explicitan
relación o nombre documental. Una pregunta original se repitió en el contraste
de formato. Se añadió un reranker alternativo en nueve ejecuciones, lecturas
oráculo, diez contrastes de formato/longitud y catorce extensiones a ocho padres
leídos. Los oráculos son unidades conocidas para diagnóstico; no se incorporan
como reglas al asistente.

Se usaron copias Qdrant locales, modelos ONNX disponibles en caché, sin
descargas y con dos hilos. El script memoiza inferencias iguales para ahorrar
CPU: sus tiempos globales **no son latencias de producción**. Guarda entradas,
salidas y tiempos de inferencias nuevas. Los scores cross-encoder se cachean
por lote completo: puntuar individualmente no reproduce exactamente el resultado
del modelo cuantizado con padding.

Las cuatro respuestas base coinciden exactamente con la comparación anterior
en estado, texto y tramo QA. En las siete preguntas del primer grupo,
desactivar la corrección ortográfica conserva esos resultados. Las trazas no
ejecutan foco, intención, dominio, herencia de tema ni cascada v1. Todas las
recuperaciones se realizan sin filtro de entidad. La corrección y los pares
léxicos siguen siendo algoritmos del sistema; no explican los fallos observados.

## Qué se perdió y dónde

| Caso | Evidencia observada | Consecuencia |
|---|---|---|
| Ponderaciones P1, pregunta original | El hijo correcto ocupa el primer puesto híbrido. 20 hijos se amplían a 13 padres; se puntúan 5 y leen 2. El reranker coloca P2 primera, glosario segundo y P1 tercera | La tabla correcta no llega al lector base |
| Ponderaciones P1, lectura oráculo | La tabla P1 completa obtiene preferencia de respuesta 0,007695 frente a nulo | El lector también falla independientemente de la búsqueda |
| Ponderaciones P1, leer 4 | Gana una condición de reprobación del anexo, con preferencia 0,812248 | Más lectura aumenta un falso positivo; no basta con bajar exigencia |
| Fecha, pregunta original | El párrafo diciembre–marzo aparece en el puesto 47 en la búsqueda híbrida de 60 hijos | Hay un problema de recall y presupuesto |
| Fecha original, recuperar 60 y leer 4 | Se selecciona el párrafo del período, tramo «cualquier semana», con antecedente diciembre–marzo | Mejora el contexto visible; el tramo aislado sigue incompleto |
| Fecha original, leer 8 | Gana otra vez el prerrequisito de quinto semestre del glosario, preferencia 0,999866 | La mayor preferencia QA no mide qué relación pidió el usuario |
| Fecha con meses explícitos | Los padres correctos aparecen en puestos 27/43 de la búsqueda híbrida de 60; uno queda séptimo tras reranking | Con 60 recuperados y 8 leídos sí se extrae diciembre–marzo |
| Duración ambigua | QA prefiere el nombre de la práctica; el párrafo correcto leído directamente permite «4 semanas» | Ambigüedad, ranking y selección final interactúan |
| Duración explícita | QA encuentra «4» en el párrafo correcto; se muestra contexto con semanas y extensión | El modelo puede resolver la relación con unidad y pregunta adecuadas |

Para P1, la entrada contextual del reranker tiene 145 tokens y el límite es
512: no está truncada. Hay truncado en otros padres extensos, pero no explica
que P2 gane a P1. Puntuar todos los 13 padres tampoco corrige esa preferencia:
P1 queda séptima. Leer todos los ocho conservados puede hacer ganar otra
condición de aprobación con preferencia 0,99113.

## Modelos y representación

Se contrastó mMARCO MiniLM con BGE-v2-m3, usando los mismos padres, lector y
techo de 512 tokens. BGE coloca P1 primera para la pregunta original; MiniLM
favorece P2. Sin embargo, QA conserva el rechazo de la tabla correcta. En
preguntas ambiguas BGE tampoco corrige el pasaje final y puede añadir falsos
positivos. Esto identifica una debilidad del reranker actual, sin demostrar
que el alternativo sea un sustituto general mejor.

El contraste de formato usa los mismos valores y el mismo lector:

| Representación de la tabla P1 | Preferencia QA: pregunta original | Tramo |
|---|---:|---|
| Texto literal con barras | 0,007695 | Encabezados y primera fila |
| Mismo texto unido en una línea | 0,007695 | Encabezados y primera fila |
| Sección declarada antepuesta | 0,388553 | Título/encabezados |
| Filas «Instrumento: …; Ponderación: …» | 0,997423 | 20% |
| Literal, respuesta máxima de 30 a 128 tokens | 0,007727 | Casi toda la tabla |

La mejora observada procede de expresar encabezados y valores juntos;
juntar líneas por sí solo no cambia la lectura. Para la pregunta que nombra
literalmente «Práctica Profesional I», MiniLM coloca P1 primera, pero QA sigue
rechazando la tabla literal (0,375378). El formato por campos obtiene 0,999933
y señala de nuevo solo «20%».

Estos valores comparan tramo y token nulo, **no son probabilidades calibradas
de respuesta correcta**. El formato mejora la detección del primer porcentaje,
pero no extrae toda la ponderación 20/40/40. No cuenta como respuesta completa
ni puede citarse como un tramo contiguo del original: tiene etiquetas repetidas
y requiere mapas a celdas. Tomar la primera fila como nombres de campo es aquí
una hipótesis controlada, incluso cuando Word no la declara encabezado; no
es una capacidad universal validada.

La tarjeta del [reranker actual](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1)
describe entrenamiento de recuperación sobre mMARCO. La del
[lector](https://huggingface.co/timpal0l/mdeberta-v3-base-squad2) declara ajuste
en SQuAD2, cuyo [contrato](https://rajpurkar.github.io/SQuAD-explorer/) es un tramo
textual o ausencia de respuesta. Inferimos un desajuste con respuestas que
requieren varios valores/celdas. El contraste local respalda ese desajuste,
sin certificar su causa específica de entrenamiento.

Se observó también sensibilidad al lote/padding: para los mismos cinco padres,
el máximo cambio de logit entre puntuación conjunta e individual fue 0,224.
No se atribuye exclusivamente a cuantización sin control FP32. No altera la
conclusión principal: P1 pierde el ranking base y QA rechaza su tabla.

## Cambios que corresponde comparar después

1. Entregar al lector representaciones por fila/campo con referencias a
   encabezados, sujeto y celdas. Conservar texto y tablas originales para
   publicación; no reemplazar citas por prosa derivada sin trazabilidad.
2. Separar anotación QA de elección del pasaje. Su preferencia frente a nulo
   no debe desplazar automáticamente evidencia mejor ordenada y relacionada.
   Comparar recuperación con QA como destacado opcional y registrar conflictos
   entre modelos, sin patrones específicos sobre P1/P2.
3. Definir presupuestos propios de v2 y cobertura por padres distintos. Probar
   puntuar todos los padres recuperados y lectura acotada por ventanas/tiempo;
   medir CPU y falsas respuestas antes de cambiar los valores por defecto.
4. Contrastar modelos después de corregir la representación. Mantener BGE
   como control; no justificar su costo ni promoverlo por un caso ganado.
5. Evaluar variantes basadas en definiciones/alias explícitos del corpus:
   nombre documental y forma coloquial producen rankings distintos. Mantener
   la pregunta original y evitar convertir esa información en un filtro duro.

No se ha demostrado mejora en nuevos corpus, necesidad de cambiar el encoder
denso, efecto de duplicación documental ni superioridad global de un modelo.
Los casos conocidos sirven para diagnóstico; no sustituyen una evaluación
reservada. No se propone volver al foco ni activar la nueva ingesta por defecto.

## Reproducción y artefactos

```powershell
.venv/Scripts/python.exe herramientas/evaluacion/auditar_v2.py `
  --project C:/ruta/proyecto-estructural --questions C:/ruta/preguntas.json `
  --output .cache/motor-v2/auditoria `
  --alternate-reranker onnx-community/bge-reranker-v2-m3-ONNX --oracle-formats
```

Cada caso acepta `id`, `question` y opcionalmente `oracle_parent_ids`. Requiere
índice estructural con padres, reranker y lector; rechaza salida dentro del
proyecto servido. El alternativo debe estar en caché. Los formatos derivados
se identifican y nunca se publican en el motor real. Cada variante declara sus
overrides; los primeros metadatos de configuración corresponden a la base.

Artefactos privados, excluidos de Git:

- `.cache/motor-v2/audit-ablation/run-dqu4h_2d/audit.json`: siete casos y variantes.
- `.cache/motor-v2/audit-formats/run-8fqcefqg/audit.json`: formatos y nombre exacto.
- `.cache/motor-v2/read8-audit.json`: extensión; resultados previos idénticos y 16 inferencias nuevas.
- `.cache/motor-v2/probe-read8.py`: reproducción de esa extensión con los artefactos conservados.

Revisiones efectivas registradas por rutas de snapshot: MiniLM
`1427fd652930e4ba29e8149678df786c240d8825`; BGE ONNX
`6f5ff65298512715a1e669753bc754d2bc8f367b`. El primer llamado al alternativo
incluye su carga y los lotes difieren (16 frente a 2). No se comparan esos
tiempos como un benchmark de latencia de servicio.
