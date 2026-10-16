# Planes de trabajo

Cada plan se borra al cerrarse; lo que quede vale se resume en `CHANGELOG.md`, los
ADR y `docs/methodology/` (como el plan V3). Estado al 2026-10-16, tomado de la tabla
de avance de cada plan:

| Plan | Estado | Documentos |
|---|---|---|
| Coherencia entre código y documentación | terminado (C1–C8); queda una acción del usuario: el tag `v1.1.0` | [coherencia.md](coherencia.md), [tareas](coherencia-tareas.md), [avance](coherencia-avance.md) |
| Presentación por forma de resultados | terminado salvo P5 (opcional, solo a pedido): la forma de la página y los caminos de corrección están activos en los proyectos nuevos (ADR 0010) | [presentacion.md](presentacion.md), [tareas](presentacion-tareas.md), [avance](presentacion-avance.md) |
| Multimedia | M0.1, M1, M2.1 y M3 hechos (carril apagado); quedan M0.2, M2.2, M4 y M5 (⚠ esperan al usuario) | [multimedia.md](multimedia.md), [tareas](multimedia-tareas.md), [avance](multimedia-avance.md) |
| Precisión desde la ingesta | casi cerrado: quedan F3.3 (condicional, sin iniciar) y F4.3 (⚠ espera al usuario) | [precision-ingesta.md](precision-ingesta.md), [tareas](precision-ingesta-tareas.md), [avance](precision-ingesta-avance.md) |
| Motor v2 | v2 es el predeterminado desde el 2026-10-12; faltan la evaluación general y el retiro de v1 | [motor-v2.md](motor-v2.md), [avance](motor-v2-avance.md) |

## Plan de coherencia

[coherencia.md](coherencia.md) inventaría las contradicciones entre código,
perfiles y documentación que dejaron los cambios de octubre, y propone pruebas
que las detecten antes de corregirlas. Las [tareas](coherencia-tareas.md)
están escritas para ejecutarse una por sesión; su estado está en el
[avance](coherencia-avance.md).

## Plan de presentación

[presentacion.md](presentacion.md) propone que el motor describa la forma de
cada página de resultados (clara, variantes, documentos) para que el widget
elija plantillas y disposición, sin cambiar el ranking: así una segunda
fuente correcta se lee como «depende de tu caso» y no como un error. Empieza
midiendo; [tareas](presentacion-tareas.md) y [avance](presentacion-avance.md).

## Plan multimedia

[multimedia.md](multimedia.md) agrega fichas de audio y video con metadata
escrita por personas, indexadas en una colección propia y mostradas en un
carril aparte cuando superan un umbral medido; no se transcribe ni analiza el
contenido. [Tareas](multimedia-tareas.md) y [avance](multimedia-avance.md).

## Plan de precisión desde la ingesta

[precision-ingesta.md](precision-ingesta.md) analiza por qué la fuente
correcta aparece entre las primeras pero no siempre primera, y propone
experimentos sobre fragmentado, cabecera, metadata y modelo denso. Las
[tareas](precision-ingesta-tareas.md) están escritas para ejecutarse una por
sesión; su estado está en el [avance](precision-ingesta-avance.md).

## Plan de motor v2

[motor-v2.md](motor-v2.md) define el trabajo experimental solicitado el
2026-10-11: frontera común, motor sin heurísticas semánticas de v1,
comparación con casos reales, preparación estructurada y reemplazo limpio
condicionado a resultados. La primera implementación está en curso; consultar
el [avance del motor v2](motor-v2-avance.md). Desde el 2026-10-12, v2 es el
motor predeterminado; la evaluación general y el retiro de v1 siguen pendientes.

El plan V4 (bancos, memoria, sinónimos e intención) se cerró el 2026-10-16: lo que vale está en `CHANGELOG.md`,
[ADR 0007](../decisions/0007-versioned-lexical-sources.md), `ipsis/recursos/sinonimos/FUENTES.md` y
[docs/methodology/v4-results.md](../methodology/v4-results.md); sus archivos de plan se borraron.
