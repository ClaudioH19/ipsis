# Evaluación del flujo de respuestas y sus barreras

Fecha: 2026-10-08. Código: árbol de trabajo sobre `db05f536b96a6fbdab08a0faa2998e8c3b62c4c4`.
Esta es la revisión inicial, con la métrica v1. Después se separaron la respuesta
completa y el tramo QA en el código: ver [evaluación v2](../evaluacion-v2/README.md).
Los artefactos de esta carpeta se conservan como evidencia histórica.
Se conservan los cambios previos del avatar. Esta revisión modifica documentación
y añade evidencia reproducible; no cambia la política de respuestas.

## Valoración

El diseño es efectivo para **copiar y rastrear evidencia**, pero todavía no
garantiza que una respuesta directa contenga la información pedida. Literalidad,
pertinencia temática y corrección de la relación preguntada son propiedades
distintas. El motor verifica bien la primera; las otras dependen de señales
léxicas, reglas y un lector que conserva fallos.

No lo consideraría validado para dar respuestas directas de confianza sin una
evaluación del corpus de destino. Tampoco hay evidencia en esta revisión para
afirmar que `heavy` resuelva esos fallos. El producto resulta útil como asistente
de consulta con citas y abstención, sujeto a los límites documentados.

## Flujo contrastado con el código

1. Separar conversación trivial mediante patrones y plantillas fijas.
2. Interpretar intención y seguimiento; expandir sinónimos con restricciones.
3. Medir recuperación densa y señales léxicas; recuperar candidatos mediante
   búsqueda híbrida por defecto y completar entidades ausentes con búsqueda dirigida.
4. Omitir modelos si no hay términos de foco en los candidatos. En `medium` y
   `heavy`, reordenar y leer ventanas pertinentes; se puede recuperar un candidato
   descartado si contiene mejores pistas de la relación.
5. Elegir evidencia, comprobar texto y offsets contra su chunk y medir el foco
   sobre la primera evidencia seleccionada.
6. Aplicar `cascade_v1`: premisa, dominio, foco y QA o cobertura léxica.
   En `heavy`, una discordancia de entidades puede rebajar `ok` a `related`.
7. Redactar con pasajes literales y plantillas fijas; comprobar entidades de la
   salida contra las citas. Publicar estado, evidencia y diagnóstico.
8. Guardar vocabulario del primer pasaje fuente que superó las guardias para
   próximos turnos. Una abstención proactiva puede mostrar alternativas explícitas
   sin convertirlas en respuesta directa ni incorporarlas como evidencia de memoria.

Referencias: motor (`ipsis/consulta/motor.py`, retirado),
[construcción del motor](../../../ipsis/aplicacion/consulta.py) y
[perfiles efectivos](../../../ipsis/configuracion/perfiles.py).
Esta secuencia corresponde a los perfiles incluidos; los componentes y etapas
son configurables, por lo que una instalación personalizada necesita otra validación.

## Medidas existentes y qué protegen

| Medida | Implementación | Alcance y límite |
|---|---|---|
| Texto fuente y posiciones exactas | [Parser](../../../ipsis/ingesta/parsear.py), [chunking](../../../ipsis/ingesta/chunking.py) | Los offsets apuntan al texto extraído, no a los bytes del PDF. No corrige un OCR equivocado ni un documento incorrecto. |
| Intenciones y relaciones | [Consultas](../../../ipsis/lenguaje/consultas.py), intenciones (`ipsis/lenguaje/intenciones.py`, retirado) | Patrones, similitud y compatibilidad evitan ciertas confusiones; reconocer una intención no prueba que exista respuesta. |
| Sinónimos restringidos | [Sinónimos](../../../ipsis/lenguaje/sinonimos.py), análisis (`ipsis/consulta/etapas/analisis.py`, retirado) | Expansión automática OOV, monosemia, bloqueo de colisiones y formas presentes en el corpus. Reduce asociaciones indiscriminadas; no elimina ambigüedad contextual. |
| Foco y vocabulario ausente | Filtros (`ipsis/consulta/etapas/filtros.py`, retirado) | El foco favorece términos informativos; por defecto como máximo dos. La ausencia de términos en todo el corpus es señal de abstención, no validación de relaciones. |
| Confianza separada del ranking | Recuperación (`ipsis/consulta/etapas/recuperacion.py`, retirado) | Usa coseno denso para confianza, no el score de fusión híbrida. Ninguno representa directamente probabilidad de respuesta correcta. |
| Premisa con entidades cerradas | Política (`ipsis/consulta/etapas/politica.py`, retirado) | Detecta fechas, importes, plazos y otras entidades reconocidas ausentes. Busca presencia en el conjunto de candidatos, no asociación con el sujeto o acción preguntados. |
| Búsqueda dirigida por entidad | Motor (`ipsis/consulta/motor.py`, retirado) | Evita rechazar una entidad existente que quedó fuera de la búsqueda inicial. Encontrarla en otro pasaje no demuestra que responda la pregunta. |
| Reranker | Reordenamiento (`ipsis/consulta/etapas/reranking.py`, retirado) | Mejora pertinencia entre candidatos; puede descartar evidencia correcta. Su señal puede confirmar dominio, no certificar contenido. |
| Lector QA con opción nula | [Lector](../../../ipsis/modelos/lector.py), lectura (`ipsis/consulta/etapas/lectura.py`, retirado) | Compara el mejor tramo con «sin respuesta». Una probabilidad alta del modelo puede acompañar un tramo incompleto o una relación incorrecta. |
| Selección de evidencia | Selección (`ipsis/consulta/etapas/seleccion.py`, retirado) | Prioriza entidades exactas, oraciones o filas enteras, limita cruces de sección y elimina duplicados. Amplía ciertas salvedades contiguas; no comprueba condiciones distantes. |
| Completar tramos | Bordes de respuesta (`ipsis/lenguaje/respuestas.py`, retirado) | Recupera unidades, calificadores y acciones inmediatas en seguimientos. No sustituye una cifra o actor seleccionado por otro. No se aplica a las preguntas iniciales. |
| Foco sobre evidencia local | Selección: `_proximidad_del_foco` (`ipsis/consulta/etapas/seleccion.py`, retirado) | Evita respaldar la respuesta con términos dispersos por todo el chunk. Solo mide la primera evidencia; otros pasajes mostrados no reciben esa misma comprobación. |
| Política de tres estados | Cascada (`ipsis/consulta/etapas/politica.py`, retirado) | `related` no se presenta como respuesta directa. Con lector, QA alta y respaldo léxico bastan para `ok`; no exige `s_cov` ni una prueba explícita de relación. |
| Concordancia de `heavy` | Lectura: `hay_discordancia` (`ipsis/consulta/etapas/lectura.py`, retirado) | Compara los dos mejores tramos confiables de pasajes distintos por tipos y valores de entidades. No detecta negaciones generales ni revisa todos los pasajes. |
| Literalidad y guardia final | [Verificador de offsets](../../../ipsis/aplicacion/registro_base.py), fidelidad (`ipsis/consulta/etapas/verificacion.py`, retirado) | Comprueba la evidencia contra su chunk y las entidades de salida contra las citas. No verifica implicación lógica ni asociación sujeto–acción–dato. |
| Memoria controlada | [Seguimiento](../../../ipsis/consulta/seguimiento.py), verificación (`ipsis/consulta/etapas/verificacion.py`, retirado) | Aislamiento por sesión, caducidad, bloqueo y protección ante turnos tardíos. Solo recuerda evidencia publicada, aunque guarda el vocabulario del chunk completo y también puede recordar `related`. |
| Calibración y procedencia | Calibración (`ipsis/evaluacion/calibracion.py`, retirado), aplicabilidad (`ipsis/configuracion/calibracion.py`, retirado) | Misma regla en producción y calibración; rechaza bancos de regresión para calibrar proyectos. Controla perfil, modelos, corpus y huella léxica, con los límites detallados abajo. |
| Evaluación y auditoría | [Métricas](../../../ipsis/evaluacion/metricas.py), [registro](../../../ipsis/aplicacion/registro.py) | Diferencia falsos `ok`, tramos incompletos, estados, offsets y latencia. `ipsis audit` comprueba citas contra el corpus actual; no demuestra corrección de la respuesta. |

## Hallazgos prioritarios

### 1. La presencia de los términos no prueba la relación pedida

Confirmado con modelos reales: ante «¿Quién firma la Resolución de compra?»,
`light` devuelve «La Resolución firmada se adjunta al expediente de compra» y
añade la recepción de productos y la firma de un acta. No identifica al firmante
de la Resolución. Ante el rechazo de productos, responde con la recepción
conforme y con la devolución de un formulario incompleto: acciones distintas.
Ambas salidas llevan `respuesta_directa` y regla `ok_lexico`.

Son fallos relevantes para el objetivo del usuario: existe vocabulario parecido
y texto literal, pero falta la información correcta. La comprobación del foco
y los umbrales no bastan. Ante «cuando parte la compra?», también devuelve una
nueva compra tras el rechazo del proveedor y añade un pasaje sobre riego del
invernadero. Esto confirma que pueden entrar pasajes ajenos a la pregunta.
Los conectores de condición usan metadata del chunk
y pertenencia al mismo documento; tampoco prueban que esa condición matice
la respuesta principal.

### 2. La calibración se aplica aunque `test` falle

El estado `calibrado` se determina en `dev`. La comprobación independiente se
guarda como `verificacion_test`, pero no cambia ese estado ni impide aplicar
los umbrales. El sondeo crea 70 aceptadas correctas en `dev` y 60 trampas
incorrectas aceptadas en `test`: obtiene `calibrado`, `test=excede` y umbrales
aplicables. Es una reproducción de la lógica real con señales sintéticas,
no una estimación del riesgo de una instalación.

No usar `test` para elegir umbrales es correcto. **Eso no obliga a aplicar unos
umbrales que fallaron la verificación**. Falta una condición de habilitación.
Además, el código explora múltiples combinaciones en `dev` y no implementa
una corrección por esa selección. La cota calculada en el conjunto utilizado
para elegir no acredita por sí sola el riesgo de producción.

### 3. La procedencia no cubre todos los cambios que alteran las respuestas

`motivo_no_aplicable` compara perfil, modelos, corpus y huella léxica. No compara
la configuración completa de la cascada, etapas o selección. El sondeo cambia
`leer_m` de 2 a 1 y la ventana de 600 a 100 caracteres: la calibración sigue
aplicándose. Estos parámetros pueden cambiar qué evidencia se lee y sus scores.
Debe incluirse una huella de la configuración efectiva de decisión y selección.

### 4. Entidades y concordancia tienen cobertura parcial

En sondeos de funciones aisladas, «¿La garantía dura 12 meses?» supera la
premisa con fuentes que dicen garantía de 6 meses y mantenimiento cada 12 meses.
La guardia de fidelidad también acepta una salida sintética que atribuye esos
12 meses a la garantía. Esto demuestra el límite de las guardias; **no demuestra
que el motor por defecto genere esa frase sintética**.

Asimismo, `hay_discordancia` no detecta «El cliente paga el envío» frente a
«El cliente no paga el envío». La concordancia de `heavy` no debe describirse
como verificación semántica general de contradicciones.

### 5. La métrica estricta y la respuesta completa necesitan distinguirse

La evaluación exige que el tramo QA incluya el literal esperado; una cita amplia
no compensa un tramo insuficiente. Es útil para detectar resaltados como «dos»
sin «días hábiles». Sin embargo, también marca casos donde el actor seleccionado
es correcto y la oración completa publicada contiene su acción.

Por eso no se debe interpretar automáticamente toda `directa_sin_literal` como
un hecho falso en toda la respuesta. Se inspeccionaron los 17 casos de `medium`:
**todos contienen el literal esperado en la prosa completa publicada**. Los
ejemplos reales incluyen preguntas por
el Supervisor de Compras y por el Director de Administración cuya prosa sí
contiene la respuesta, aunque el literal exigido sea más largo que el tramo QA.
La evaluación necesita etiquetas separadas para dato/relación incorrectos,
tramo incompleto, contexto omitido y respuesta completa suficiente.

## Validación de esta revisión

Se repitió el banco español de consultas naturales con los modelos locales,
sin descargas, en proyectos temporales aislados. Hay 60 preguntas: 34
respondibles y 26 no respondibles. No se usó este banco para calibrar.

| Perfil | Directas | Aciertos con criterio literal estricto | Fallos con ese criterio | Falsos `ok` en no respondibles | Directas sin literal completo |
|---|---:|---:|---:|---:|---:|
| light | 17 | 14 | 3 | 1 | 2 |
| medium | 25 | 8 | 17 | 0 | 17 |

Los fallos estrictos son 3/17 (17,6 %) y 17/25 (68 %) de las respuestas directas,
no del total de preguntas. **El 68 % no es una tasa medida de afirmaciones falsas
en la prosa completa**. La métrica mezcla fallos de selección e insuficiencia del
tramo. Los conteos coinciden con los [resultados anteriores](../mediciones/v4-correcciones/tablas.md).
Contando presencia del literal esperado en la prosa publicada, `medium` alcanza
25/25 directas con el dato esperado (8 que ya cumplían el criterio de tramo y
17 confirmadas en la inspección); `light`, 14/17. Frente a las 34 preguntas
respondibles, son 25/34 (73,5 %) y 14/34 (41,2 %) con respuesta directa que contiene
el dato esperado. No se cuenta `related` como acierto directo.
En este banco, **`medium` sí mejora la respuesta completa respecto a `light`**,
aunque su selección del tramo QA necesita ajustes. Esta comprobación de presencia
literal en la prosa no constituye una evaluación semántica independiente ni una
garantía sobre otros bancos; debe medirse como resultado adicional, junto al tramo.

La suite pertinente terminó con **570 aprobadas, cero fallos, cero omitidas y
tres avisos** en 554,75 s. Los avisos son de dependencias y de índices de payload
sin efecto en Qdrant local. No se repitió la suite completa histórica ni el
banco de `heavy`. Un test de regresión verde acredita comportamiento esperado,
incluidos límites conocidos; no acredita ausencia de errores semánticos.

Artefactos de esta revisión:

- [Consultas medidas](consultas-es.json): casos, estados, reglas y señales.
- [Respuestas completas inspeccionadas](ejemplos.json) y [reproductor](ejemplos.py).
- [Límites aislados reproducidos](sondeos.json) y [reproductor](sondeos.py).
- [Validación y huellas de componentes](validacion.json).

La medición del banco corrió en paralelo con pytest: sus latencias se conservan
en el JSON, pero no sirven para comparar rendimiento con rondas anteriores.
Estos documentos y preguntas son sintéticos; el banco ya ha sido utilizado en
desarrollo y no es una muestra independiente representativa de producción.

Reproducción desde la raíz, con los modelos ya descargados (PowerShell):

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:IPSIS_ONNX_THREADS = '2'
.venv/Scripts/python.exe -m pytest tests/consulta tests/lenguaje tests/evaluacion -q
.venv/Scripts/python.exe tests/datos/banco_consultas/medir.py .cache/auditoria-consultas-es.json light,medium es
.venv/Scripts/python.exe docs/methodology/auditoria-2026-10-08/sondeos.py
.venv/Scripts/python.exe docs/methodology/auditoria-2026-10-08/ejemplos.py
```

## README y mejoras recomendadas

Se actualizaron [README.es.md](../../../README.es.md) y
[README.md](../../../README.md): promesas de exactitud, flujo con las guardias,
conversación trivial, alternativas, alcance de `heavy`, límites de calibración,
presupuesto de `heavy` de 4 s y uso de `ask` antes de `serve` para evitar el bloqueo
del índice local. Las guías de personalidad ya describen las animaciones y su
configuración. El banner conserva el eslogan «nunca inventadas»: debe entenderse
como ausencia de generación de hechos, no como garantía de respuestas correctas.

Prioridades para una siguiente intervención:

1. Separar selección en `dev` de habilitación mediante una comprobación independiente
   que cumpla el riesgo objetivo; un resultado `test=excede` debe bloquear la aplicación.
2. Invalidar calibraciones si cambia la configuración efectiva del flujo y selección.
3. Exigir respaldo de la relación preguntada en la evidencia publicada: sujeto,
   acción, dato, unidad y condición. Probar pares mínimos con los mismos términos
   y acciones distintas; una condición de cobertura sola no resuelve este problema.
4. Validar cada pasaje añadido y sus conectores, no únicamente la primera evidencia.
5. Revisar el completado de tramos en preguntas iniciales y medir separadamente
   resaltado, respuesta completa y corrección semántica. Revalidar los perfiles
   sobre un golden del corpus real con negativos, negaciones y versiones en conflicto.

La conclusión es favorable a la trazabilidad y cautelosa respecto a la exactitud:
**el sistema tiene defensas reales, pero todavía permite responder con información
parecida que no contesta lo solicitado**. La evidencia actual no sostiene una
promesa de «nunca responde incorrectamente» ni de riesgo ≤ 5 % en producción.
