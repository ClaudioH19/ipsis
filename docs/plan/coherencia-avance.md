# Avance del plan de coherencia

Plan: [coherencia.md](coherencia.md).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado · ⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| C1 | ✅ | 2026-10-16 | (ver git log) | 7 pruebas nuevas en `tests/test_documentacion.py` (28 casos con las existentes); 12 casos `xfail(strict=True)` que la tarea indicada debe quitar. Detalle abajo. |
| C2 | ✅ | 2026-10-16 | (ver git log) | Tablas de perfiles, tamaños y latencia medidos, descripción del perfil, `heavy` fuera de `ranking_pasajes.py`, nota en ADR 0003. Decisiones del usuario: presupuesto = opción (a) (solo documentar); sin ADR 0010. Ver «C2» abajo. |
| C3 | ✅ | 2026-10-16 | (ver git log) | Ejemplos en `config_version: 8`; tabla de versiones completa (6, 7, 8); preparación estructural descrita como predeterminada; se quitaron los 5 `xfail` de C3. Ver «C3» abajo. |
| C4 | ✅ | 2026-10-16 | (ver git log) | Guía del widget en español con las mismas 14 secciones que la inglesa; 8 capturas regeneradas; README aclara que el menú se abre con el «?». Ver «C4» abajo. |
| C5 | ⬜ | | | |
| C6 | ⬜ | | | ⚠ número de versión |
| C7 | ⬜ | | | ⚠ cierre de F5.1 del plan V4 |
| C8 | ⬜ | | | |

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
  que el usuario decida si borrarlas.
- Prueba: quitado el `xfail` de `web` en `test_guias_en_y_es_tienen_las_mismas_secciones`; queda el de `deployment` (C5).

### Hallazgo nuevo

- **I16.** `docs/guide/web.md` y `docs/es/guia/web.md` no describen el diseño de búsqueda del [Unreleased]: buscador abajo
  como un chat con los resultados desplazándose encima, mensaje del asistente sobre el buscador con el avatar a su derecha
  (`avatar.placement: message`, ya documentado en las guías de personalidad), esqueletos de carga y la página de demostración
  a pantalla completa en teléfonos. Es contenido nuevo para los dos idiomas, no una traducción, así que no se agregó en C4.
  ⚠ Recomendación: una sección corta «Diseño de búsqueda» en ambas guías, tomada del CHANGELOG, en C5 o aparte.
