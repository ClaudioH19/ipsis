# Plan V4: bancos, memoria de conversación, sinónimos e intención

Plan de trabajo vigente. Se borra al cerrarse; lo que quede vale se resume en
`CHANGELOG.md`, los ADR y `docs/methodology/` (como el plan V3).

- [tareas.md](tareas.md): cada tarea con sus pasos y su criterio de aceptación.
- [avance.md](avance.md): estado, fecha, commit y medición de cada tarea.
- [sinonimos.md](sinonimos.md): propuesta concreta de fuentes, formato,
  conversión reproducible y activación medida de F2.

## Plan de motor v2

[motor-v2.md](motor-v2.md) define el trabajo experimental solicitado el
2026-10-11: frontera común, motor sin heurísticas semánticas de v1,
comparación con casos reales, preparación estructurada y reemplazo limpio
condicionado a resultados. La primera implementación está en curso; consultar
el [avance del motor v2](motor-v2-avance.md). Desde el 2026-10-12, v2 es el
motor predeterminado; la evaluación general y el retiro de v1 siguen pendientes.
Este documento conserva el
historial y los criterios del plan V4.

## Objetivo

Que la comprensión de la pregunta y la conversación se apoyen en evidencia
medida y no en reglas validadas con pocos casos:

1. bancos de evaluación del tamaño mínimo acordado, con conversaciones;
2. memoria de toda la conversación, con vencimiento, compactación y
   protección frente a cambios de tema;
3. sinónimos por idioma desde recursos léxicos abiertos, versionados en el
   repositorio;
4. reconocimiento de la intención con un respaldo por similitud cuando los
   patrones no alcanzan.

## Reglas de ejecución

1. **Medir antes y después.** Ningún cambio de comportamiento entra sin
   medirse contra la línea base de F1.4 en los bancos de consultas, de
   conversaciones y universal (light y medium × es/en/pt). La medición queda
   en [avance.md](avance.md) y en el mensaje del commit.
2. **Criterios globales** (abajo): una tarea que cambia el motor no se cierra
   si alguno falla, salvo que el usuario acepte la excepción.
3. **Sin entrenamiento.** Los datos solo eligen umbrales. Nada aprende pesos.
4. **Umbrales de la política:** no se cambian sin consultar al usuario.
5. **Documentación en el mismo commit:** CHANGELOG, ADR o
   `docs/methodology/`, guías y diagramas si cambia el flujo.
6. **Commits** como ClaudioH19, uno por tarea o grupo coherente; push solo
   cuando el usuario lo pida.
7. **Tareas marcadas ⚠** requieren la aprobación del usuario antes de
   ejecutarse.

## Requisitos (lo que pidió el usuario)

| ID | Requisito | Origen |
|---|---|---|
| R1 | Bancos de consultas del tamaño mínimo acordado (60 por idioma) | 2026-10-06 |
| R2 | Banco que mida conversaciones (seguimiento, cambio de tema) | 2026-10-06 |
| R3 | Memoria de **toda** la conversación, no solo del turno anterior | 2026-10-06 |
| R4 | Vencimiento por inactividad en vez de borrar la sesión menos usada | 2026-10-06 |
| R5 | Compactación de la conversación para mejorar la calidad | 2026-10-06 |
| R6 | Salvaguarda frente a un cambio de tema deliberado | 2026-10-06 |
| R7 | Reinicio al salir de la página o por inactividad | 2026-10-06 (D2) |
| R8 | Sinónimos por idioma desde diccionarios de instituciones, **escritos en el repo** (no descargados al instalar), con un plan para descargarlos, subirlos y mantenerlos | 2026-10-06 |
| R9 | Respaldo por similitud para la intención | 2026-10-06 |
| R10 | Documentación y diagramas al día en cada cambio | 2026-10-06 |

## Decisiones

| ID | Decisión | Quién / cuándo |
|---|---|---|
| D1 | 60 casos por idioma en el banco de consultas (≈ 34 respondibles: sirve para detectar regresiones; certificar α = 0,05 exige ≥ 59 aceptados y solo se alcanza sumando idiomas) | Usuario, 2026-10-06 |
| D2 | La conversación se reinicia al salir de la página o por inactividad; cerrar o minimizar el panel la conserva | Usuario, 2026-10-06 |
| D3 | Orden de fases: F1 → F4 → F2 → F3 | Propuesto, sin objeción |
| D4 | Los sinónimos no van en una base vectorial: la similitud de vectores junta antónimos («aceptar» / «rechazar»), que son justamente las trampas medidas. Van como tablas de consulta | Propuesto y aceptado, 2026-10-06 |
| D5 | Para D2, el widget usa un `session_id` nuevo en cada carga de página y el servidor olvida por vencimiento. Un aviso de salida (`sendBeacon`) no puede llevar la clave del widget. Consecuencia: **navegar a otra página del mismo sitio también empieza una conversación nueva** | Usuario, 2026-10-06 |
| D6 | El trabajo sigue en `v2/ruta`: los commits del plan se suman al PR #7 | Usuario, 2026-10-06 |

## Trazabilidad

| Requisito | Tareas | Cómo se verifica |
|---|---|---|
| R1 | F1.1, F1.4, F1.7 | `tests/evaluacion/test_banco_consultas.py`; medición en avance.md |
| R2 | F1.2, F1.3 | Mismo archivo de pruebas; `banco_conversaciones/medir.py` |
| R3 | F4.1 | Conversaciones que vuelven a un tema de 2 turnos atrás (es/en/pt-conv-007 y -015) |
| R4 | F4.2 | Prueba con reloj inyectado; `engine.yaml` → `conversation.expiry_minutes` |
| R5 | F4.1 | Prueba unitaria del núcleo del tema; conversaciones de 4 turnos (-002, -003) |
| R6 | F4.1 | `herencia_indebida` en el banco de conversaciones (-006, -014, -020) |
| R7 | F4.3 | Prueba del widget (id por carga de página) y vencimiento (F4.2) |
| R8 | F2.1–F2.8 | Archivos en `ipsis/recursos/sinonimos/`, pruebas de formato, atribución y reproducibilidad |
| R9 | F3.1–F3.5 | Intenciones reconocidas por similitud en el diagnóstico; medición |
| R10 | todas | Revisión del commit; `tests/test_documentacion.py` |

## Métricas

- **Correcta:** respuesta directa que muestra el texto literal esperado.
- **Directa errónea:** falso ok (directa en un caso sin respuesta) o directa
  sin el literal esperado.
- **Herencia:** correcta / indebida (heredó en un cambio de tema) / perdida
  (no heredó en un seguimiento), sobre los turnos con `hereda`.
- **Latencia:** media de light por idioma en el banco universal.

## Criterios globales de aceptación

| ID | Criterio |
|---|---|
| G1 | Suite completa en verde |
| G2 | Banco universal: ningún falso ok nuevo y ninguna respuesta correcta perdida (6 combinaciones) |
| G3 | Banco de consultas: las directas erróneas no suben en ninguna combinación perfil × idioma y las correctas no bajan en total |
| G4 | Banco de conversaciones: la herencia indebida y las directas indebidas no suben |
| G5 | Latencia media de light ≤ línea base + 10 % (el ruido medido es de ese orden) |
| G6 | Caracterización: cada cambio de estado explicado en el commit |

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un diccionario general trae todos los sentidos («banco») y sube los falsos ok | Guarda actual (solo palabras ausentes del corpus, hacia formas presentes, nunca la relación) + límites de tamaño de grupo; medición aislada en F2.7 |
| Licencias share-alike (CC-BY-SA) en datos dentro de un repo AGPL-3.0 | F2.1 releva licencias; ⚠ el usuario aprueba cada fuente antes de versionarla; atribución junto al archivo |
| WordNet trae lemas y el stemmer no une formas irregulares («requieren») | Formas regulares generadas + grupos escritos a mano como corrección |
| Retomar un tema anterior por coincidencia de vocabulario | Retomar exige que **todos** los términos propios estén en ese tema; medido con -015 |
| La memoria guarda palabras que escribió el usuario | Solo términos y formas de la pregunta, nunca respuestas; en RAM, con vencimiento; documentado |
| La similitud de intención acierta poco con preguntas muy cortas | Solo actúa si ningún patrón reconoce; umbral y margen elegidos en `dev`, reportados en `test` |
| 60 casos por idioma no certifican α por idioma | Se dice así en la documentación (D1) |

## Fuera de alcance (pendiente aparte)

- P5 de la propuesta original: expansión a pasajes padre y vecinos.
- En light: «cuando parte la compra?», «¿Quién firma la Resolución de
  compra?» y «Quem assina a Resolução de compra?» responden con otra oración
  del mismo tema; «Quando se começa a comprar?» no recupera el chunk que
  responde con 3 candidatos.
- ~~Medir el perfil heavy.~~ Medido y retirado: no superó a medium (ADR 0003).
