# Avance del plan de coherencia

Plan: [coherencia.md](coherencia.md).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado · ⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| C1 | ✅ | 2026-10-16 | (ver git log) | 7 pruebas nuevas en `tests/test_documentacion.py` (28 casos con las existentes); 12 casos `xfail(strict=True)` que la tarea indicada debe quitar. Detalle abajo. |
| C2 | ⬜ | | | ⚠ presupuesto de `medium`; ⚠ ADR 0003 o 0010 |
| C3 | ⬜ | | | |
| C4 | ⬜ | | | |
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
