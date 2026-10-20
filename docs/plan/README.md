# Planes de trabajo

Un plan se borra al cerrarse: lo que vale queda en `CHANGELOG.md`, los
[ADR](../decisions/) y [docs/methodology/](../methodology/). Este documento reúne el
estado de todos, y el detalle de lo que sigue abierto. Estado al 2026-10-20.

## Estado

| Plan | Estado | Dónde quedó lo que vale |
|---|---|---|
| Coherencia entre código y documentación | cerrado (C1–C8); versión 1.1.0 etiquetada | `tests/test_documentacion.py`, `CONTRIBUTING.md` |
| Presentación por forma de resultados | cerrado; queda P5 (opcional, solo a pedido) | [ADR 0010](../decisions/0010-presentation-by-result-shape.md) |
| Multimedia | cerrado; no se hace M4 (servir archivos) ni M4.2 (panel, no pedido) | [ADR 0011](../decisions/0011-media-records-in-a-separate-lane.md) |
| Precisión desde la ingesta | casi cerrado; quedan F3.3 (condicional) y F4.3 (espera al usuario) | [precision-ingesta.md](../methodology/precision-ingesta.md), [ADR 0009](../decisions/0009-structural-preparation-by-default.md) |
| Plan V4 (bancos, memoria, sinónimos, intención) | cerrado el 2026-10-16 | [v4-results.md](../methodology/v4-results.md), [ADR 0007](../decisions/0007-versioned-lexical-sources.md) |
| **Motor v2** | v2 es el predeterminado desde el 2026-10-12; faltan evaluación general y retiro de v1 | abajo |
| **Conversación en v2** | abierto el 2026-10-19, sin iniciar | abajo |
| **Fuentes tabulares** | propuesta sin implementar | abajo |

Las pruebas que hoy fallan en el motor v1 por snapshots anteriores a v2 (`test_caracterizacion`,
`test_banco_universal::test_falsos_ok_no_superan_la_linea_base`, `test_general_regresion`,
`test_tono_no_cambia_estados`, `test_portabilidad_pythonioencoding_cp1252_no_falla`) fallan también
sin cambios y conviene corregirlas aparte.

## Motor v2: lo que falta

Contexto: [mapa de capas](../methodology/motor-v2.md), [fuentes ordenadas](../methodology/fuentes-v2.md),
[diagnóstico](../methodology/motor-v2-diagnostico.md) y [mejoras de lectura](../methodology/motor-v2-mejoras-lectura.md).
Hecho: frontera común de motor, recorrido mínimo, comparador pareado (`herramientas/evaluacion/comparar_motores.py`),
preparación estructural, navegación de fuentes y presupuesto de consulta (2 500 ms). El «consejo» de rerankers
se retiró.

Pendiente, y todavía sin criterios cumplidos:

1. **Evaluación reservada.** Separar familias de documentos entre desarrollo y reserva, congelar criterios antes de
   abrirla, y revisar a mano casos reales (sujeto, valores, unidades, completitud, citas). Un LLM no es juez.
2. **Puerta de promoción.** Mejora neta sin fallos críticos nuevos; regresiones por idioma, perfil y estructura
   explicadas; p95 y memoria dentro de lo fijado para la CPU objetivo; regresión general con modelos; instalación,
   migración, reindexación y rollback probados en una copia de proyecto.
3. **Presentación completa.** Bloques de párrafos, listas y tablas con referencia por celda en API y widget;
   conversación e idiomas anunciados acreditados.
4. **Retiro de v1** solo con evidencia: selector, paquete v1, cascada y reglas antiguas fuera; migrador de
   configuración histórica en la frontera; ADR de comprensión, cascada y memoria actualizados.
5. **Preparación documental:** comparar el parser propio con Docling por fidelidad y costo en CPU.

## Conversación en v2

**Problema.** Con v2 como predeterminado tres cosas no funcionan:

1. **No hay memoria de conversación.** `MemoriaConversacion` solo se crea en la rama v1 de
   `construir_motor_del_proyecto` (`ipsis/aplicacion/consulta.py`). «¿Y para extranjeros?» se busca sola. Las
   cifras del [ADR 0006](../decisions/0006-conversation-memory.md) (36/38 seguimientos en español) son de v1.
2. **Ambigüedad sin umbral.** La forma `variants` dice «Depende de tu caso» aunque la pregunta ya nombre el caso
   («¿cuántas horas tiene la Práctica II?»).
3. **Ni abstención ni aviso de «parecido».** «¿Capital de Mongolia?» muestra tres tarjetas; «tornillo M8 inox» muestra
   «M8 zincado» sin avisar.

**Invariantes de la memoria** (no se negocian; si una medición mejora rompiendo uno, no se adopta):

- **I1–I2 Aislamiento.** La conversación la emite el servidor (token opaco `secrets.token_urlsafe(24)`). Un token
  desconocido o vencido no recupera memoria. `session_id` solo pagina. Se prueba con hilos intercalados.
- **I3–I5 Qué entra.** Solo raíces del corpus con `df > 0` (núcleo ≤ 3 términos, ≤ 4 temas previos), nunca texto libre. El
  vocabulario de los pasajes no se toma sin señal: solo por `context_source` (un `chunk_id` abierto por la persona y
  publicado en el último turno de esa conversación).
- **I6–I7 Sin distracción.** Al heredar se busca con la pregunta interpretada y con la propia, intercaladas sin sumar
  votos. Qué texto recibe el reranker se decide midiendo; el lector destaca sobre la pregunta propia.
- **I8–I9 Reglas.** Las de ADR 0006: un cambio de tema deliberado no arrastra el anterior, una pregunta fuera de dominio no
  cambia el tema. Solo una pregunta nueva avanza la conversación (no la continuación, la ayuda, la cortesía ni un error).
- **I10–I11 Visible y acotada.** La API publica lo heredado (`interpreted`); el widget muestra «También busqué: *…*» con un
  botón para quitarlo y «Nueva conversación». Se mantienen `expiry_minutes` (30) y `max_sessions` (1 024).

**Reglas fijas:** sin generación (ADR 0001; texto nuevo solo en `recursos/voz` o `recursos/idiomas`, en los tres idiomas);
apagado hasta M3 (`conversation.enabled_v2: false` deja v2 exactamente como hoy); `herencia_indebida` = 0 en los tres
idiomas es condición de cualquier cambio; v1 no cambia; medir en `dev`, informar en `test`; documentos reales fuera del repo;
nunca inventar cifras.

**Fases** (una tarea por sesión; las marcadas con ⚠ cambian la conducta por defecto y piden aprobación):

| Fase | Contenido | Pendiente de decidir |
|---|---|---|
| M0.1 | `tests/datos/banco_conversaciones/medir.py` con `--pipeline v1\|v2`: herencia correcta, indebida y perdida, hit@1/@3 | |
| M0.2 | Banco encadenado (`encadenado.py`): las preguntas independientes de `banco_consultas` y `banco_informal`, aisladas frente a seguidas en una conversación | |
| M0.3 | Seguimientos informales por idioma, con métrica aparte | ⚠ quién los escribe (recomendado: el agente propone 10 por idioma y la persona corrige) |
| M1.1 | Conversación emitida por el servidor (`MemoriaConversacion.emitir`, campo `conversation`) | ⚠ si `conversation` aparece con la opción apagada (recomendado: no) |
| M1.2 | Resolución en `MotorV2._consultar` tras cortesía y ortografía, con intercalado | |
| M1.3 | Experimento: vocabulario del pasaje (sí/no) y reranker con la interpretada o la propia. Se descarta toda variante con `herencia_indebida > 0` o delta encadenado negativo | ⚠ elección de variante a la vista de la tabla |
| M2.1 | `context_source` validado y señal desde el widget | |
| M2.2 | Lo heredado visible y reversible | |
| M3 | Activación por defecto, ADR 0012, nota en ADR 0006, CHANGELOG, README | ⚠ aprobación |
| A1 | `variants` exige que la pregunta no nombre el alcance ni los rasgos de las fuentes 1 y 2; en `medium`, además `margen < ambiguity_margin` | ⚠ banco real y valor de `ambiguity_margin` (recomendado: activar la regla y el margen solo si separa en `test`) |
| A2 | El caso elegido en «Elige tu caso» queda en el tema (requiere M2.1 y A1) | |
| S1 | Abstención fuera de dominio: ningún término de contenido con `df > 0` tras ortografía, sinónimos y alias. 0 abstenciones falsas en los bancos respondibles | ⚠ aprobación con la tabla |
| S2 | «No encontré exactamente eso; esto es lo más parecido» cuando los términos distintivos (códigos, cifras, medidas) no están en ninguna fuente | ⚠ forma del mensaje (recomendado: repetir solo términos con dígitos o códigos) |

**Límites.** La memoria vive en el proceso: con varias réplicas una conversación solo sigue si cae siempre en el mismo
proceso (hoy Docker corre uno). Recargar la página empieza otra conversación. Los bancos son pequeños y los escribió el
mismo asistente que construye el sistema: las cifras orientan, no prueban. No se agrega un umbral de puntaje para abstenerse
sin calibrar con preguntas de personas reales.

## Fuentes tabulares

Propuesta, sin implementar. Hoy `ipsis` lee XLSX, XLS, CSV y TSV y localiza registros (fila con encabezados y
coordenadas); no calcula existencias ni suma filas, no tiene conector de base de datos ni sincronización, y repetir `load` no
reemplaza con seguridad un inventario. La clave del widget es pública: no separa datos por persona, rol ni bodega. Lo único
hecho es neutralizar el banco de ayuda de v2 (asistente multipropósito que recupera de las fuentes configuradas y muestra
su procedencia).

Principios de la propuesta:

- **Consulta exacta, no ranking.** Registro por clave y campos configurados, con su origen y fecha de corte. Estados:
  `ok`, `not_found`, `ambiguous`, `field_unavailable`, `stale`, `source_unavailable`. Un cero, una celda vacía y la ausencia
  de registro son estados distintos. El ranking documental nunca decide valores ni agregaciones.
- **Mapeo explícito por fuente.** El administrador declara clave, campos, tipos, unidades y alias (válidos solo en esa
  fuente). Si cambia una columna, la actualización falla; no se elige otra por parecido.
- **Vista aprobada, solo lectura.** Se lee una vista con tablas, columnas y filas listadas; todo lo no configurado se deniega.
  Lo excluido no llega a exportaciones, embeddings, payloads, contexto, logs ni copias. Públicos distintos exigen índices
  separados o autenticación que cubra todas las rutas de lectura. Los secretos viven en el entorno; las consultas están
  predefinidas y parametrizadas.
- **Snapshots completos y atómicos.** Se prepara el índice nuevo fuera del activo y se publica junto con registros, catálogo y
  manifiesto. Si falla, se conserva la generación anterior con su fecha y se rechazan valores exactos al vencer el límite. Una
  revocación de permisos bloquea de inmediato. Un escaneo periódico no es «tiempo real».

Orden: (1) ayuda neutral del motor, hecho; (2) migrar identidad y tonos de v1 preservando nombres elegidos; (3) contrato
tabular con pruebas de alias, claves compuestas, nulos y cambio de esquema; (4) consulta exacta con aislamiento por audiencia;
(5) conector y sincronización sobre un motor de base de datos concreto. Por definir al implementar: el primer motor, la
audiencia del inventario y la antigüedad máxima admisible.
