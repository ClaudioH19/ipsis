# Avance del plan de coherencia

Plan: [coherencia.md](coherencia.md).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado · ⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| C1 | ✅ | 2026-10-16 | (ver git log) | 7 pruebas nuevas en `tests/test_documentacion.py` (28 casos con las existentes); 12 casos `xfail(strict=True)` que la tarea indicada debe quitar. Detalle abajo. |
| C2 | ✅ | 2026-10-16 | (ver git log) | Tablas de perfiles, tamaños y latencia medidos, descripción del perfil, `heavy` fuera de `ranking_pasajes.py`, nota en ADR 0003. Decisiones del usuario: presupuesto = opción (a) (solo documentar); sin ADR 0010. Ver «C2» abajo. |
| C3 | ✅ | 2026-10-16 | (ver git log) | Ejemplos en `config_version: 8`; tabla de versiones completa (6, 7, 8); preparación estructural descrita como predeterminada; se quitaron los 5 `xfail` de C3. Ver «C3» abajo. |
| C4 | ✅ | 2026-10-16 | (ver git log) | Guía del widget en español con las mismas 14 secciones que la inglesa; 8 capturas regeneradas; README aclara que el menú se abre con el «?». Ver «C4» abajo. |
| C5 | ✅ | 2026-10-16 | (ver git log) | LaTeX en `README.es.md`; sección «Integración continua» en la guía de despliegue en español; `ipsis sync` y la migración a `config_version` 8 en los README (EN/ES); I15 e I17 corregidos con pruebas. Todas las pruebas de coherencia en verde, sin `xfail`. Ver «C5» abajo. |
| C6 | ✅ | 2026-10-16 | (ver git log) | Versión 1.1.0 (elegida por el usuario) en `pyproject.toml`, `uv.lock`, badges, textos de instalación fijada, CHANGELOG y `SECURITY.md`. **El tag `v1.1.0` no se creó.** Ver «C6» abajo. |
| C7 | ✅ | 2026-10-16 | (ver git log) | Estado de 15 notas de metodología (6 por evidencia propia, 9 según la propuesta aprobada), §14 de `motor-v2.md` e índice de planes. El plan V4 **no se cierra** (decisión del usuario). Ver «C7» abajo. |
| C8 | ✅ | 2026-10-16 | (ver git log) | Dos casillas en la plantilla de PR y la sección «Documentation follows the code» en `CONTRIBUTING.md`, con las pruebas por nombre. |

## C1: pruebas de coherencia

Estado sobre `e516d6a`: `tests/test_documentacion.py` termina en menos de 1 s con 28 aprobadas y 12 `xfail` estrictas.
Cada `xfail` se verificó con `--runxfail`: falla por el motivo del inventario y no por otro.

| Prueba | Caso | Falla hoy por | Inventario | La quita |
|---|---|---|---|---|
| `test_tabla_de_perfiles_nombra_los_modelos_vigentes` | README.md, README.es.md | la fila de `medium` no nombra `bge-reranker-v2-m3` | I1 | C2 |
| | installation.md, instalacion.md | además presenta el lector mDeBERTa, que v2 no carga | I2 | C2 |
| `test_ejemplos_usan_la_config_version_vigente` | configuration.md, configuracion.md, fuentes-v2.md | `config_version: 7`; el código está en 8 | I5 | C3 |
| `test_la_guia_de_configuracion_describe_la_version_vigente` | en, es | dice «vigente 7» y la tabla de versiones termina en la 5 (faltan 6, 7 y 8) | I5, **I14** | C3 |
| `test_formatos_soportados_en_los_readme` | README.es.md | no nombra LaTeX | I7 | C5 |
| `test_guias_en_y_es_tienen_las_mismas_secciones` | web | 14 secciones `##` en inglés y 12 en español | I9 | C4 |
| | deployment | 7 y 6 | I10 | C5 |

Pasan hoy: formatos en README.md, el resto de las guías (misma cantidad de secciones), la correspondencia de guías en
`docs/guide/` y `docs/es/guia/` (`test_hay_una_guia_en_ingles_y_otra_en_espanol_por_cada_par`) y el badge de versión
frente a `pyproject.toml` (1.0.0 en ambos).

### Hallazgos nuevos

- **I14.** La tabla «Version / What changed» de `docs/guide/configuration.md` y de `docs/es/guia/configuracion.md`
  termina en la versión 5; el código está en la 8 (faltan 6, 7 y 8). C3 debe describirlas, con el contenido de
  `ipsis/configuracion/migraciones.py` y del CHANGELOG, sin inventar. Añadí una prueba para esto y otra de correspondencia de guías, además de las cinco
  del plan.
- **I15.** La fila de `ipsis load` de `docs/guide/usage.md:166` y `docs/es/guia/uso.md:169` lista los formatos sin
  LaTeX («PDF con texto, DOCX, MD, TXT, XLSX, XLS, CSV, TSV»), aunque la misma guía menciona LaTeX en otro lugar
  (`usage.md:43`, `uso.md:45`). La tarea C5 solo cubre el README; **no la incluí en la prueba de formatos** para no
  salirme del plan. ⚠ Recomendación: que C5 la corrija y que la prueba de formatos también revise las guías de uso.
- La prueba de perfiles localiza la fila de `medium` por su inicio (`| \`medium\` |`) y acepta tablas con sangría, que es
  como las escriben las guías de instalación. Los nombres de los modelos en la documentación se declaran en
  `ALIAS_DE_MODELOS`; un modelo nuevo sin alias se busca por su nombre corto.
- Para C2: al quitar el `xfail`, la prueba exigirá que **ninguna** fila de `medium` mencione el lector mDeBERTa.

### Suite rápida al cerrar C1

`pytest -m "not slow and not modelos and not browser"` sobre `c6cb2fc`: **1567 aprobadas, 2 fallidas, 7 omitidas,
12 xfail** (73 s). Las dos fallas son del entorno de la sesión, que no tiene `intfloat/multilingual-e5-small` en la
caché (`/root/.cache/ipsis/models`), y fallan igual sin los cambios de C1 (comprobado en la base con `git stash`):

- `tests/consulta/test_motor.py::test_crear_app_aisla_estado_y_lifespan_calienta_y_cierra_motor`: `/ready` devuelve 503
  porque el diagnóstico del proyecto marca `models: missing from the cache`.
- `tests/integracion/test_portabilidad.py::test_portabilidad_init_cargar_indexar_subprocesos`: `ipsis index` termina con
  «el modelo intfloat/multilingual-e5-small no está en la caché».

Ninguna lleva la marca `modelos(...)`, así que no se omiten cuando la caché está vacía. No se tocaron (regla 1 del
plan). Con el modelo descargado (`ipsis models download --profile light`) deberían pasar; si no se puede descargar,
anotarlo como ⛔ y no como regresión.

## C2: perfiles, modelos y cifras

**Hecho.** Tablas de perfiles de `README.md`, `README.es.md`, `docs/guide/installation.md` y
`docs/es/guia/instalacion.md`: `medium` = e5-small + reranker (bge-reranker-v2-m3 en español y portugués, mMiniLM en
los demás idiomas), sin lector. `ipsis models list` y `ipsis models download` confirman que v2 solo baja el denso y el
reranker. La prueba `test_tabla_de_perfiles_nombra_los_modelos_vigentes` ya no es `xfail` y pasa en los cuatro archivos.

**Tamaños medidos** (2026-10-16, `ipsis models download`, tamaño del `.onnx` en disco con `find -L`):

| Modelo | Archivo | Bytes | MB |
|---|---|---|---|
| intfloat/multilingual-e5-small | `onnx/model.onnx` | 470 268 510 | 470 |
| onnx-community/bge-reranker-v2-m3-ONNX | `onnx/model_int8.onnx` | 570 727 094 | 571 |
| cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 | `onnx/model_quint8_avx2.onnx` | 118 620 016 | 119 |

Totales: `light` 0,47 GB; `medium` español/portugués 1,04 GB; `medium` otros idiomas 0,59 GB. La guía decía 1,7 GB
porque contaba el lector mDeBERTa (1,1 GB), que v2 no descarga.

**Latencia medida** (2026-10-16, `herramientas/evaluacion/ranking_pasajes.py --perfil medium --particion todas`, banco
sintético `banco_pasajes`, 116 preguntas respondibles, preparación estructural, Intel Xeon 2,1 GHz de 4 CPU, un solo
proceso, `light`/`medium` sin calibración). Se verificó que español resuelve a `bge-reranker-v2-m3` con 10 candidatos
(`ajustes_de_idioma("medium", None, "es")`, usado en `ipsis/aplicacion/consulta.py:80`) e inglés a mMiniLM.

| Idioma | Reranker | hit@1 final | p50 ms | p95 ms | Reranking p50 / p95 ms |
|---|---|---|---|---|---|
| es | bge-reranker-v2-m3 | 0,991 | 604 | 749 | 555 / 707 |
| en | mMiniLM | 1,000 | 349 | 620 | 316 / 575 |

El banco tiene pasajes cortos y los dos idiomas rozan el techo de hit@1; sirve para latencia, no para comparar
calidad. Con documentos reales en español el p95 medido fue de 1,7 s (ADR 0003). Falta la cifra de portugués (no se
midió) y la de inglés con documentos reales (no hay).

**Otros cambios.** `medium.yaml::description` ya no promete el lector. `ranking_pasajes.py --perfil` ya no acepta
`heavy` (I13). ADR 0003: nota de que la tabla de «1 s» es de v1. **No se creó un ADR 0010**: el ADR 0003 ya tiene la
sección «Update 2026-10-15: reranker per language» con sus mediciones; ⚠ confirmar con el usuario.

**Decisiones del usuario (2026-10-16).** (1) Presupuesto de `medium`: **opción (a)**, solo documentación. La columna
pasa a llamarse «p95 objetivo (`ipsis benchmark`)` y las guías de instalación explican que `p95_budget_ms` es la
referencia con que `ipsis benchmark` marca si un perfil cumple (también lo muestran `ipsis profile` y el panel), que v2
no lo aplica a las consultas y que una consulta v2 se acota con `v2.query_budget_ms` (2500 ms) para los dos perfiles.
El código no cambió. (2) No se crea un ADR 0010: lo cubre la sección «Update 2026-10-15» del ADR 0003.

**Observación (no es de este plan).** Como `ipsis benchmark` compara contra `p95_budget_ms` (1000 ms en `medium`), su
columna «Meets» seguirá marcando que `medium` no cumple con documentos reales (p95 de 1,7 s) aunque dentro de v2 sí
cabe en 2500 ms. Si se quiere que el benchmark use el presupuesto de v2, es un cambio de código aparte (la opción (b)
descartada).

**Entorno.** Con los modelos descargados, las dos fallas de la suite de C1 (`test_crear_app_aisla_estado…` y
`test_portabilidad_init_cargar_indexar_subprocesos`) pasan: era solo la caché vacía.

## C3: versión de configuración y preparación estructural

- `config_version: 7` → `8` en `docs/guide/configuration.md` (2 bloques), `docs/es/guia/configuracion.md` (2) y
  `docs/methodology/fuentes-v2.md` (1). El bloque `v2:` de `fuentes-v2.md` es un subconjunto exacto del de
  `ipsis/recursos/plantillas/engine.yaml`, así que no necesitó más cambios.
- **I14 resuelto.** La frase «versión vigente» pasa a `8` y la tabla de versiones de las dos guías añade las filas 6, 7 y 8,
  tomadas de las ramas de migración de `ipsis/configuracion/esquemas.py:279-297` (no del historial, que está aplastado
  en un commit): 6 = `engine.yaml` sin `pipeline` pasa a `pipeline: v2`; 7 = se elimina `v2.council`; 8 = los v2 sin
  preparación elegida pasan a la estructural y piden `ipsis index` (ADR 0009).
- **I6 resuelto.** `fuentes-v2.md` ya no dice «optativa y experimental»: la estructural es la predeterminada (ADR 0009),
  con `retrieval.preparation.mode: legacy` como vuelta atrás.
- Otras menciones vigentes encontradas con `grep experimental` y corregidas (paso 3 de la tarea):
  `docs/methodology/preparacion-estructural.md` (estado y última frase: decía que v2 y la preparación seguían
  experimentales y que no cambiaba proyectos existentes) y `docs/methodology/README.md` (decía «v1 remains the default»).
  Se dejó dicho que la nota se escribió cuando era experimental. Quedan sin tocar, para C7 (estado de cada nota de
  metodología): `motor-v2.md`, `motor-v2-diagnostico.md`, `motor-v2-mejoras-lectura.md`, `reranker.md`,
  `multilingual.md`, `modelos-heavy-2026-10-08/`.
- Pruebas: quitados los `xfail` de `test_ejemplos_usan_la_config_version_vigente` (3 casos) y de
  `test_la_guia_de_configuracion_describe_la_version_vigente` (2). Quedan 3 `xfail`: web (C4), deployment y
  README.es (C5).

## C4: widget en español

- `docs/es/guia/web.md` pasa de 12 a 14 secciones `##`, igual que `docs/guide/web.md`: se tradujeron «Probar el widget y
  configurar el proyecto» y «Orientación separada de los resultados» (con las etiquetas reales del pack de voz en
  español: «Cómo buscar», «Qué puedo hacer», «Sobre el asistente», «Alcance», «Mostrar completo», «Contraer»; el conteo
  se escribe «3 resultados» / «1 resultado», como en `ipsis/recursos/idiomas/es.yaml`). Además: la fila de
  `GET /config` con `response_mode`, `assistant_messages` y `animations_enabled`, el punto de «Orientación de v2» en
  «Textos» y la mención del icono «?» en el párrafo del menú.
- **Corrección a I8.** El menú «Ayuda» **no se eliminó**: el icono «?» del encabezado lo abre (`widget.js:1362`). Los
  README conservan «menú Ayuda» y ahora dicen cómo se abre.
- **Corrección a I9.** `avatar.placement` sí está documentado, en inglés y en español, en
  `docs/guide/personality.md:35` y `docs/es/guia/personalidad.md:34`. Lo que falta, **en los dos idiomas**, está solo en el
  CHANGELOG: ver I16.
- **Capturas.** Las 8 `docs/assets/widget-{sources,sources-dark,mobile,faq}-{en,es}.png` eran del 2026-10-13, anteriores
  al icono «?», al mensaje del asistente sobre el buscador y al buscador abajo. Se regeneraron con
  `herramientas/capturas_widget.py` (sin modificarlo) usando el Chromium preinstalado en `/opt/pw-browsers/chromium`,
  porque la versión de Playwright del proyecto espera otro build. No se regeneraron `widget-mobile.png`, `widget-answer.png` y `widget-answer-dark.png` (del 2026-10-10): ese
  script no las produce y **ningún documento las referencia** (comprobado con `grep`); quedaron huérfanas y se dejan para
  que el usuario decidió borrarlas (2026-10-16).
- Prueba: quitado el `xfail` de `web` en `test_guias_en_y_es_tienen_las_mismas_secciones`; queda el de `deployment` (C5).

### Hallazgo nuevo

- **I16.** `docs/guide/web.md` y `docs/es/guia/web.md` no describen el diseño de búsqueda del [Unreleased]: buscador abajo
  como un chat con los resultados desplazándose encima, mensaje del asistente sobre el buscador con el avatar a su derecha
  (`avatar.placement: message`, ya documentado en las guías de personalidad), esqueletos de carga y la página de demostración
  a pantalla completa en teléfonos. Es contenido nuevo para los dos idiomas, no una traducción, así que no se agregó en C4.
  ⚠ Recomendación: una sección corta «Diseño de búsqueda» en ambas guías, tomada del CHANGELOG, en C5 o aparte.

## C5: README y despliegue

- **I7.** `README.es.md` nombra LaTeX entre los formatos.
- **I10.** `docs/es/guia/despliegue.md` gana la sección «Integración continua» (traducción de la inglesa) y las dos guías
  quedan con 7 secciones `##`. En la guía en inglés, esa sección estaba **delante** del párrafo introductorio («How to put
  the assistant on a server…»), que así parecía pertenecerle; el párrafo pasó arriba, en los dos idiomas.
- **I11.** Los dos README («Inicio rápido» y «Actualizar un proyecto existente»): `ipsis sync` como forma de reflejar
  cambios de `documents/`, con enlace a la guía de uso; y un párrafo que explica que un proyecto v2 con `config_version` 7
  o anterior se migra en su siguiente comando `ipsis` a la 8 y, si no había elegido preparación, a la estructural (ADR 0009):
  hay que ejecutar `ipsis index`, el servicio informa «no listo» hasta entonces, el índice anterior se conserva y
  `retrieval.preparation.mode: legacy` vuelve atrás. Se redactó sin número de versión del paquete: C6 aún no fija cuál es.
- **I15 resuelto** (decisión que tomé siguiendo mi recomendación; es un cambio trivial y reversible): la fila de
  `ipsis load` de `docs/guide/usage.md` y `docs/es/guia/uso.md` ahora lista LaTeX.
- **I17 (nuevo, resuelto).** La tabla de comandos de `docs/guide/usage.md` tenía **dos filas idénticas de `ipsis sync`**
  (con descripciones distintas); la española tenía una. Se dejó la primera, que es la equivalente a la española.
- Pruebas: quitados los últimos `xfail` (README.es en formatos y `deployment`); nuevas
  `test_la_fila_de_ipsis_load_lista_todos_los_formatos` y `test_la_tabla_de_comandos_no_repite_filas` (comparan la firma
  completa del comando dentro de la tabla de referencia: `ipsis ask` con y sin `--diagnostics` es legítimo, y `ipsis doctor`
  también aparece en la tabla de problemas frecuentes). `tests/test_documentacion.py`: **44 aprobadas, 0 `xfail`**.
- **Suite rápida** (`-m "not slow and not modelos and not browser"`) sobre este cambio: **1596 aprobadas, 0 fallidas,
  2 omitidas** (78 s), con los modelos de `medium` descargados.

### Pendiente del plan

- **I16 sigue abierto** (⚠ decisión del usuario): `web.md` en inglés y en español no describen el diseño de búsqueda del
  [Unreleased].
- C7 (estado de las notas de metodología y cierre del plan V4), C8 (plantilla de PR y CONTRIBUTING) y C6 (versión).

## C8: que no vuelva a pasar

- `.github/PULL_REQUEST_TEMPLATE.md`, sección «Impact»: casilla «Changes a default, a profile or a supported format: the
  consistency tests in `tests/test_documentacion.py` pass (profile models, `config_version`, formats, EN/ES sections,
  version badge)» y casilla «English and Spanish documentation changed in the same commit».
- `CONTRIBUTING.md`: nueva sección «Documentation follows the code» con las cuatro fuentes de verdad (perfiles,
  `CONFIG_VERSION`, `EXTENSIONES_SOPORTADAS`, `pyproject.toml`), cada prueba de `tests/test_documentacion.py` por su
  nombre y qué hacer con un modelo o formato nuevo (`ALIAS_DE_MODELOS`, `NOMBRE_DE_FORMATO`). Se comprobó que todas las
  pruebas citadas existen. La viñeta de «Style» que describía a mano lo que verificaba la prueba ahora remite a la sección.

## C7: historia y planes

**Hecho.**

- Estado añadido o corregido en las notas donde la propia nota decide (cada afirmación se respaldó con algo comprobado):
  `fuentes-v2.md` (vigente), `consejo-v2.md` (histórico: experimento retirado con `config_version` 7),
  `motor-v2-diagnostico.md` y `motor-v2-mejoras-lectura.md` (histórico, 2026-10-11: decían «se conserva v1 como motor por
  defecto»), `v4-results.md` (histórico: mide v1; v2 no ejecuta memoria de conversación ni la política de respuestas, según
  `docs/guide/configuration.md`) y la sección «14. Estado» de `motor-v2.md` (decía «implementación experimental»).
  `preparacion-estructural.md` ya se había corregido en C3.
- `docs/plan/README.md` pasa de «Plan V4 … vigente» a un índice de los seis planes con su estado, tomado de la tabla de
  avance de cada uno. El texto completo del plan V4 se conserva debajo, bajado de nivel, hasta su cierre.

**⚠ Para el usuario: notas de metodología donde no hay evidencia suficiente.** Las notas numeradas (plantilla de 14 puntos)
ya tienen su sección «14. Status» y dicen «Stable», lo que es cierto para el motor v1 pero puede leerse como si rigieran el
motor predeterminado (v2). Propuesta, sin aplicar:

| Nota | Dice hoy | Propuesta |
|---|---|---|
| `policy.md` (política `cascade_v1`) | Stable | Estable, **solo motor v1**: v2 no aplica la política de respuestas |
| `calibration.md` | Stable | Estable, **solo motor v1**: la calibración no controla el ranking de v2 (README, «Compatibilidad: motor v1») |
| `reader.md` (lector QA) | Stable | Estable, motor v1; v2 no lo carga por defecto (`qa_highlights` opcional) |
| `lexical.md` (señales `s_oov`, `s_foco`…) | Stable | Estable; las señales son de v1, el BM25 lo comparten v1 y v2 |
| `retrieval.md` | Stable | Vigente: la búsqueda híbrida la usa v2; los umbrales con `s_ret` son de v1 |
| `reranker.md` | Stable | Vigente, pero su tabla de `medium` (mMiniLM, 4 candidatos) no recoge el reranker por idioma (ADR 0003) |
| `evaluation.md` | Stable | Vigente para los bancos de regresión; las métricas de «respuesta directa» son de v1 |
| `multilingual.md` | Stable | Vigente |
| `informal-paraphrases.md` | informe fechado 2026-10-08 | Histórico (medición), con los recursos léxicos aún en uso |

¿Aplico la propuesta tal cual, o prefieres otra redacción o dejar alguna sin cambio?

**⚠ Para el usuario: cierre del plan V4.** La tabla de avance de `docs/plan/avance.md` tiene todo en ✅ salvo F5.1
(«espera al usuario»). Si se aprueba, la regla del plan manda resumir lo valioso en `CHANGELOG.md`, los ADR y
`docs/methodology/`, y borrar `tareas.md`, `avance.md`, `sinonimos.md` y la última sección de `docs/plan/README.md`
(más los enlaces rotos que queden, que la prueba de enlaces detecta). No lo hice sin tu aprobación.

### C7: decisiones del usuario y cierre (2026-10-16)

- **Notas dudosas: se aplicó la propuesta tal cual.** `policy.md`, `calibration.md`, `reader.md` y `lexical.md` quedan como
  «estable, solo motor v1» (la de léxico: las señales son de v1 y el BM25 lo comparten v1 y v2); `retrieval.md`,
  `reranker.md` (con aviso de que su tabla de `medium` es anterior al reranker por idioma, ADR 0003), `evaluation.md` y
  `multilingual.md` quedan como vigentes; `informal-paraphrases.md` como histórico. Se añadió una línea de estado bajo cada
  título y se ajustó su sección «14. Status». No se tocó el contenido técnico.
- **Plan V4: no se cierra por ahora.** Se conservan `tareas.md`, `avance.md`, `sinonimos.md` y su sección en
  `docs/plan/README.md` hasta que el usuario lo apruebe; el índice ya lo marca «terminado, a la espera del cierre F5.1».
- **I16 resuelto.** Las dos guías del widget ganan la sección «Search layout» / «Diseño de búsqueda» (buscador abajo,
  mensaje del asistente con `avatar.placement: message`, esqueletos de carga con los textos reales de
  `search_stage_*`, etiqueta de alcance y página de demostración a pantalla completa en teléfonos), tomada del CHANGELOG
  y de `widget.js` (el modo búsqueda lo activa `response_mode: ranked_sources`). Siguen teniendo las mismas secciones:
  15 y 15.

## C6: versión 1.1.0

- **Número elegido por el usuario: 1.1.0** (cambios de comportamiento por defecto y una migración automática compatible
  con 1.0.0, con la reindexación destacada).
- `pyproject.toml` y `uv.lock` en 1.1.0 (`uv lock --check` resuelve sin cambios; `importlib.metadata` informa 1.1.0).
  Badges y titular («ipsis 1.1») de los dos README, y la instalación fijada `@v1.1.0` en los README y en las guías de
  instalación (EN/ES).
- `CHANGELOG.md`: `[Unreleased]` queda vacío y se abre `[1.1.0] - 2026-10-16` con una nota «Upgrading from 1.0.0» que
  pide ejecutar `ipsis index` tras el primer comando, más las entradas de documentación y de las pruebas de coherencia.
- **I18 (nuevo, resuelto).** `SECURITY.md` listaba como soportada solo la serie 0.9.x, sin la 1.0 ni la 1.1. Se siguió su
  propio patrón (solo la última serie): `1.1.x ✅` y `< 1.1 ❌`. ⚠ Es una política del mantenedor: si 1.0.x también debe
  recibir correcciones, hay que agregarla.
- **No se creó el tag ni la release.** Los badges enlazan a `releases/tag/v1.1.0`, que dará 404 hasta que el usuario lo
  cree tras revisar.
- Suite rápida: **1596 aprobadas, 0 fallidas, 2 omitidas**.

## Cierre del plan

Con C1–C8 hechas, el plan de coherencia está terminado. Pendiente solo lo que es del usuario: crear el tag `v1.1.0`,
decidir si 1.0.x sigue soportada en `SECURITY.md`, y cerrar el plan V4 (F5.1). Siguiendo la regla de los planes, este
puede borrarse al cerrarse (resumido en el CHANGELOG, que ya lo recoge).
