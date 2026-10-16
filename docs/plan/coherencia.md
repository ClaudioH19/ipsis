# Plan de coherencia: código, perfiles y documentación

Abierto el 2026-10-16. Tareas para ejecutar una por sesión:
[coherencia-tareas.md](coherencia-tareas.md). Estado: [coherencia-avance.md](coherencia-avance.md).

## Por qué

Los cambios recientes (v2 predeterminado, reranker por idioma, preparación
estructural por defecto, nuevo diseño del widget, `ipsis sync`, LaTeX) se
documentaron en `CHANGELOG.md` y en las guías en inglés, pero no siempre en el
resto. La promesa del proyecto es **no afirmar nada que no esté en la fuente**;
una documentación que contradice al código debilita esa misma promesa.

## Causa raíz

1. **Edición en inglés primero.** El CHANGELOG y `docs/guide/` se actualizan;
   `README.es.md` y `docs/es/guia/` quedan atrás.
2. **Valores por defecto escritos a mano en varios lugares.** Modelos, tamaños,
   latencias y `config_version` se copian en README, guías, ADR y perfiles; al
   cambiar el perfil nadie avisa del resto.
3. **Notas fechadas sin estado.** Metodología y planes describen el sistema en
   una fecha, sin marcar si siguen vigentes.
4. **Las pruebas de documentación cubren poco.** `tests/test_documentacion.py`
   solo verifica comandos de la CLI y enlaces relativos.

## Inventario (2026-10-16, commit `60649e0`)

| # | Dónde | Dice | Realidad |
|---|---|---|---|
| I1 | `README.md:95`, `README.es.md` (tabla de perfiles) | `medium` = e5-small + mMiniLM | En es/pt usa `bge-reranker-v2-m3` con 10 candidatos (`ipsis/recursos/perfiles/medium.yaml:44-49`) |
| I2 | `docs/guide/installation.md:17`, `docs/es/guia/instalacion.md:17` | `medium` = mMiniLM + lector mDeBERTa, 1,7 GB, 1 s | v2 no carga el lector; es/pt usan bge (571 MB); presupuesto v2 de 2500 ms |
| I3 | `medium.yaml` (`description`, `p95_budget_ms: 1000`), panel (`ipsis/aplicacion/panel.py:143`) | «reranker y lector QA», presupuesto 1000 ms | En v2 rige `v2.query_budget_ms: 2500` y no hay lector por defecto |
| I4 | `docs/decisions/0003-onnx-and-profiles.md:41` | medium 1 s | Cifra de v1; falta nota sobre v2 y el reranker por idioma |
| I5 | `docs/guide/configuration.md:35,84`, `docs/es/guia/configuracion.md:36,86`, `docs/methodology/fuentes-v2.md:19` | `config_version: 7` | `CONFIG_VERSION = 8` (`ipsis/configuracion/esquemas.py:11`) |
| I6 | `docs/methodology/fuentes-v2.md:13-14` | Preparación estructural «optativa y experimental» | Predeterminada desde ADR 0009 |
| I7 | `README.es.md:44` | Formatos sin LaTeX | `.tex` soportado (`ipsis/ingesta/parsear.py:58`); `README.md` sí lo dice |
| I8 | `README*.md:53,206`, `docs/es/guia/web.md:218` | Menú «Ayuda» | Ahora es un icono «?» en la cabecera (`docs/guide/web.md:43`) |
| I9 | `docs/es/guia/web.md` (287 líneas) vs `docs/guide/web.md` (335) | Sin buscador abajo, mensaje del asistente, `avatar.placement: message`, `response_mode`, `assistant_messages` en `/config` | Documentado solo en inglés |
| I10 | `docs/es/guia/despliegue.md` | Sin sección «Integración continua» | Existe en `docs/guide/deployment.md:3` |
| I11 | README (ambos) | Inicio rápido y «Actualizar» no mencionan `ipsis sync`; badge y tag 1.0.0 | `ipsis sync` es la vía soportada; `[Unreleased]` trae migración a `config_version` 8 y reindexación |
| I12 | `docs/plan/` | Plan V4 con F5.1 ⚠ abierto; `README.md` del plan dice «Plan de trabajo vigente» | El motor v2 y la precisión desde la ingesta ya reemplazaron ese foco |
| I13 | `herramientas/evaluacion/ranking_pasajes.py:313` | `--perfil heavy` aceptado | El perfil `heavy` se retiró el 2026-10-08 |

El inventario no es exhaustivo: la tarea C1 existe para que las pruebas
encuentren el resto.

## Principios del arreglo

- **El código es la fuente de verdad.** Si un valor se puede leer de
  `ipsis/recursos/perfiles/*.yaml` o de `esquemas.py`, una prueba lo compara
  con la documentación; no se confía en la memoria de quien edita.
- **Inglés y español en el mismo commit.** Ningún cambio de documentación
  queda en un solo idioma.
- **Lo histórico se marca, no se borra.** Las cifras de v1 o de `heavy` se
  conservan con una línea de estado y fecha.
- **No cambiar comportamiento.** Este plan corrige documentación, descripciones
  y pruebas. Si un número publicado resulta falso, se mide de nuevo; no se
  ajusta el motor para que coincida con el texto.

## Tareas

Cada tarea se hace en una sesión, con la suite en verde al terminar.

### C1. Pruebas de coherencia (primero, para que fallen)

Ampliar `tests/test_documentacion.py`:

- **Perfiles:** cada modelo de `models` y de `language_rerankers` de cada perfil
  aparece en la tabla de perfiles de `README.md`, `README.es.md` y las dos
  guías de instalación. Lo histórico queda fuera de la tabla vigente.
- **Versión de configuración:** todo bloque YAML de `docs/` (salvo
  `docs/plan/` y las secciones de historial) con `config_version` de
  `engine.yaml`/`assistant.yaml` usa `CONFIG_VERSION`.
- **Formatos:** cada extensión de `EXTENSIONES_SOPORTADAS` se nombra en los dos
  README y en las dos guías de uso.
- **Paridad EN/ES:** cada guía de `docs/guide/` tiene su par en `docs/es/guia/`
  con el mismo número de encabezados `##` y los mismos bloques de código de
  CLI (`ipsis ...`). Las diferencias permitidas se declaran en una lista
  explícita dentro de la prueba.
- **Versión publicada:** el badge de versión de los README coincide con
  `pyproject.toml`.

Criterio: las pruebas nuevas fallan sobre `60649e0` mostrando al menos I1, I2,
I5, I7, I9 e I10, y no fallan por motivos espurios.

### C2. Perfiles y cifras (I1–I4)

- Tabla de perfiles en los README y en las guías de instalación: modelos por
  idioma, sin lector en v2, tamaño en disco de lo que realmente se descarga.
- ⚠ **Presupuesto de `medium`:** hoy hay dos números (`p95_budget_ms: 1000`
  del perfil y `query_budget_ms: 2500` de v2). Opciones: (a) que el panel y la
  documentación muestren el de v2 cuando el motor es v2; (b) unificarlos en un
  solo campo con migración. Recomendación: (a), sin migración.
- Medir de nuevo p95 de `medium` en es (con bge) y en en (con mMiniLM) con
  `ipsis benchmark` y publicar esas cifras, con fecha y máquina.
- `medium.yaml::description` en inglés y su traducción, sin el lector.
- Nota de actualización en ADR 0003 que apunte a la decisión del reranker por
  idioma (o un ADR 0010 si se considera una decisión nueva; ⚠ preguntar).

### C3. Configuración y preparación (I5, I6)

- Ejemplos con `config_version: 8` en las guías y en `fuentes-v2.md`.
- `fuentes-v2.md`: la preparación estructural es la predeterminada (ADR 0009);
  `legacy` es la vuelta atrás.

### C4. Widget en español (I8, I9)

- Sincronizar `docs/es/guia/web.md` con `docs/guide/web.md`: buscador abajo,
  mensaje del asistente con `{count}`, icono «?», `avatar.placement`,
  `response_mode` y `assistant_messages` en `/config`.
- README (ambos): icono «?» en lugar de «menú Ayuda».
- Regenerar capturas si alguna muestra el menú antiguo
  (`herramientas/capturas_widget.py`).

### C5. README y despliegue (I7, I10, I11)

- `README.es.md`: LaTeX en formatos.
- `docs/es/guia/despliegue.md`: sección de integración continua.
- Inicio rápido y «Actualizar»: `ipsis sync` como forma de reflejar cambios de
  `documents/`, y la reindexación que pide la migración a `config_version` 8.

### C6. Versión 1.1.0

- ⚠ Confirmar número: `[Unreleased]` cambia valores por defecto y migra la
  configuración, pero de forma automática; recomendación: **1.1.0**.
- Mover `[Unreleased]` a `[1.1.0]`, actualizar `pyproject.toml`, badges e
  instrucciones de instalación fijada, y crear el tag.

### C7. Historia y planes (I12)

- Cabecera de estado en cada nota de `docs/methodology/`: `Vigente`,
  `Histórico (motor v1)` o `Histórico (perfil heavy)`, con fecha.
- Cerrar el plan V4 según su propia regla (resumir en CHANGELOG/ADR y borrar),
  previa aprobación de F5.1 por el usuario (⚠).
- `docs/plan/README.md`: índice de planes vigentes.

### C8. Evitar que vuelva a pasar

- Plantilla de PR: casillas «cambié un valor por defecto o un perfil → corrí
  las pruebas de coherencia» y «EN y ES en el mismo commit».
- `CONTRIBUTING.md`: un párrafo con la regla de la fuente de verdad.

## Orden

C1 → C2 → C3 → C4 → C5 → C7 → C8 → C6. La versión se publica al final, cuando
las pruebas de coherencia estén en verde.
