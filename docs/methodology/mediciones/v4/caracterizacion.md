# Cambios de estado frente a F1

La comparación usa el motor `39c7878` con **solo** la métrica literal
corregida. La pregunta efectiva anterior y posterior de cada turno queda
en `comparacion.json`; esta lista explica todos los cambios de estado de
F4. La comparación desde el comienzo de esta continuación se informa por
separado: esa base ya contenía la memoria de temas.

| Perfil | Turno | Antes → después | Explicación |
|---|---|---|---|
| light | es-conv-002:2 | relacionado → directa | Hereda `pedir teletrabajo`; F1 trataba la pregunta sobre días sin contexto. |
| light | es-conv-002:4 | relacionado → directa | Mantiene el núcleo y el último seguimiento `equipos`; encuentra la asignación. |
| light | es-conv-005:4 | relacionado → directa | El turno fuera de dominio conserva el tema `horario biblioteca`; recupera el sábado. |
| light | es-conv-007:3 | relacionado → directa | Conserva `resolucion firma compra` tras el turno fuera de dominio; recupera quién redacta. |
| light | es-conv-008:3 | relacionado → directa | Conserva `cumplo metas teletrabajando`; reconoce la revisión del acuerdo como seguimiento. |
| light | en-conv-002:4 | relacionado → directa | Conserva `apply remote work equipment`; recupera el subsidio. |
| light | en-conv-007:3 | sin respuesta → relacionado | Restituye `resolution signs purchase` tras el turno fuera de dominio; recupera evidencia, aunque la política no acepta una respuesta directa. |
| light | pt-conv-002:4 | relacionado → directa | Mantiene tema y último seguimiento sobre equipos; recupera el subsidio. |
| light | pt-conv-003:2 | directa → relacionado | El núcleo de tres términos descarta `valor` de la consulta anterior; la interpretación conserva `diaria dentro pais`. Se pierde una respuesta literal correcta. |
| light | pt-conv-003:4 | relacionado → directa | Conserva `diaria dentro pais exterior`; recupera la consecuencia de no rendir cuentas. |
| light | pt-conv-005:4 | relacionado → directa | El tema `horario biblioteca` sobrevive al turno fuera de dominio y permite recuperar el sábado. |
| light | pt-conv-007:3 | relacionado → directa | Conserva `resolucao assina compra` tras el turno fuera de dominio; recupera quién redacta. |
| light | pt-conv-016:2 | directa → relacionado | El núcleo descarta `conta` y `eu` de la consulta anterior; cambia el foco a `bloquearam minha faco`. Se pierde una respuesta literal correcta. |
| medium | es-conv-002:4 | directa → relacionado | F1 no heredaba; ahora añade el tema y `equipos`. Cambia la selección/aceptación, pero la antigua directa ya fallaba el literal del lector. |
| medium | es-conv-004:3 | relacionado → directa | Cambia el orden de términos heredados a `cambio contrasena vence`. Cambia el resultado del lector; no equivale por sí solo a un acierto literal. |
| medium | es-conv-007:3 | relacionado → directa | La memoria conserva el tema de la resolución tras el turno fuera de dominio; cambian recuperación y aceptación. |
| medium | en-conv-002:4 | directa → relacionado | Añade el tema y `equipment`, que F1 había perdido. La directa anterior ya fallaba el literal del lector. |
| medium | en-conv-010:3 | relacionado → directa | La consulta heredada pasa a `start purchase registers request`; el orden y la compactación cambian el lector/aceptación. |
| medium | en-conv-013:3 | directa → relacionado | La pregunta sobre producto dañado ahora hereda `refund request many until s paid`; cambia el foco y se pierde una respuesta literal correcta. |
| medium | pt-conv-002:4 | directa → relacionado | Retiene `equipamentos recebo` del seguimiento; cambia la selección/aceptación. La directa anterior ya fallaba el literal del lector. |
| medium | pt-conv-007:3 | relacionado → directa | Conserva `resolucao assina compra` tras el turno fuera de dominio; cambian recuperación y aceptación. |

También cambia el acierto sin cambiar de estado en **medium es-conv-013:3**:
la pregunta efectiva pasa de `pagan pedir reembolso` a `pedir reembolso
pagan`. La respuesta sigue siendo directa y cita «Si el producto llega
dañado, el envío de la devolución es gratuito», pero el lector selecciona
solo `gratuito`, sin el literal completo esperado. La inspección reproducible
queda en `inspeccion-f4-final-es-conv-013-medium.json`. No se cambia el orden
del núcleo para acomodar este caso: el defecto del tramo se registra.

No se cambiaron los umbrales de la política. **G4 mide herencias indebidas
y directas de los cuatro turnos negativos por idioma**; pasar ese criterio
no garantiza que toda respuesta positiva conserve su literal. Se informan
por separado las cuatro pérdidas de respuestas correctas frente a F1.

Cinco turnos positivos aparecen como nuevas directas sin el literal esperado
en el lector: medium es-conv-004:3 (`12`), es-conv-007:3 (`Director de
Administración`), es-conv-013:3 (`gratuito`), en-conv-010:3 (`ten`) y
pt-conv-007:3 (`Diretor de Administração`). Tres son tramos incompletos.
**Los dos casos -007 seleccionan un actor incorrecto**: se pregunta quién
redacta y el lector escoge a quien firma. La cita íntegra contiene ambas
funciones y la respuesta correcta, pero eso no corrige el tramo elegido.
Sus mensajes y spans quedan en los JSON finales. Esta limitación requiere
trabajo adicional del lector/relación; no se describe como una mejora de
exactitud de medium ni se oculta tras G4.

## Ronda anterior que falló G3

En la primera ronda completa, **medium es-parafrasis-019** («¿Qué pasa si
no rindo los gastos a tiempo?») cambió de directa correcta a relacionado:
F4 había añadido `tiempo` a las palabras genéricas globales. El total de
correctas del banco natural bajó de 46 a 45 y G3 falló. La comparación se
conserva en `comparacion-antes-separacion.json`.

La corrección separa `genericas_memoria` de `genericas`: `tiempo/tempo`
se ignoran solo al reconocer y compactar temas, mientras mantienen su
peso original para foco, selección y lector. La memoria conserva su
interpretación; la respuesta de un turno independiente recupera la
semántica anterior. Se repiten los tres bancos, G5 y la suite completa,
sin modificar umbrales de la política ni acomodar el orden de una pregunta.
