# Avance: precisión del primer resultado desde la ingesta

Tareas: [precision-ingesta-tareas.md](precision-ingesta-tareas.md).
Rama de trabajo: `ccr-b2b5f6b8-7tipuk` (separada de `main`).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado ·
⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| F0.1 | ✅ | 2026-10-15 | 2d2b536 | Usuario sin corpus real: banco sintético en `tests/datos/banco_pasajes` (116 respondibles + 15 trampas, 10 documentos). |
| F0.2 | ✅ | 2026-10-15 | (ver git log) | Corrió de punta a punta en `light` y `medium` con e5-small y el reranker mMiniLM (modelos descargados al habilitar la red). |
| F0.3 | ⬜ | | | Requiere modelos en caché. |
| F0.4 | ✅ | 2026-10-15 | (ver git log) | Línea base medida (abajo). Brecha hit@5 − hit@1 tras el reranker en `medium`: 22 puntos (≥ 5): el problema se reproduce. JSON en `/tmp/claude-0/medidas/` del entorno efímero; las tablas de abajo son el registro. |
| F1.1 | ✅ | 2026-10-15 | (ver git log) | Cabecera: ver tabla. |
| F1.2 | ✅ | 2026-10-15 | (ver git log) | `CH-PAR` y `CH-SEC`: ver tabla. |
| F1.3 | ✅ | 2026-10-15 | (ver git log) | `reranker_max_tokens: 512`: ver tabla. |
| F1.4 | ✅ | 2026-10-15 | (ver git log) | Combinaciones y recomendación abajo. Valores por defecto sin cambiar (F5.1). |
| F1.5 | ✅ | 2026-10-15 | (ver git log) | Opción (b) aprobada por el usuario: `hash_corpus` legacy incluye `texto_embebido` solo si difiere de `texto`. 4 pruebas en `tests/indice/test_manifiesto.py` y 1 en `tests/ingesta/test_cabecera.py`. Un índice hecho antes con `with_header: true` muestra otra huella y conviene reindexarlo. La regla 9 de las tareas queda resuelta: ya no hace falta correr los experimentos sin calibración. |
| F2.1 | ✅ | 2026-10-15 | (ver git log) | `CH-F256S` medida: ver tabla. |
| F2.2 | ⚠ | | | Decidir (a), (b) o (c) tras F0.3 y F1.3. |
| F2.3 | ✅ | 2026-10-15 | (ver git log) | Preparación estructural de Markdown medida: ver tabla. Habilita evaluar F2.4. |
| F2.4 | ✅ | 2026-10-15 | (ver git log) | `preparar_pdf` (outline o tamaño de letra, listas, avisos de OCR; escaneado sin OCR sigue rechazado). Medido con `banco_general` (abajo): la estructural ya indexa el corpus mixto md/pdf/docx/txt, que antes fallaba por el PDF. |
| F3.1 | ✅ | 2026-10-15 | (ver git log) | Cabecera extendida medida: ver tabla. |
| F3.2 | ⚠ | | | Decidir la similitud; depende de F1.5. |
| F3.3 | ⬜ | | | Condicional. |
| F4.1 | ⬜ | | | |
| F4.2 | ⬜ | | | Condicional. |
| F4.3 | ⚠ | | | Requiere aprobación. |
| F5.1 | ⚠ | 2026-10-15 | (ver git log) | Candidata medida una vez en `test` y verificada (abajo). Espera la aprobación del usuario para cambiar valores por defecto. |
| F5.2 | ⬜ | | | |

## Línea base (F0.4)

Banco `tests/datos/banco_pasajes/es`, partición `dev` (72 preguntas respondibles), `CH-F256`, sin
cabecera, `reranker_max_tokens: 256`, e5-small, CPU de 4 núcleos, sin calibración. Herramienta:
`herramientas/evaluacion/ranking_pasajes.py`.

| Perfil | Etapa | hit@1 | hit@3 | hit@5 | MRR | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| light | híbrido = final | 0,792 | 0,986 | 1,000 | 0,890 | 97 | 229 |
| medium | híbrido | 0,792 | 0,986 | 1,000 | 0,890 | | |
| medium | final (reranker) | 0,736 | 0,875 | 0,958 | 0,816 | 2 322 | 2 402 |

La fuente correcta siempre está entre las 5 primeras del orden híbrido, y en `medium` el reranker la
empeora. En `medium` el reranker agota el presupuesto de 2 500 ms con 26 a 30 de 60 candidatos
puntuados en esta CPU (los puntuados van primero), así que la latencia está acotada por el presupuesto.
F0.3 (tokens por fragmento) aún no se escribió.

## Resultados por experimento

`dev`, un cambio respecto de la base salvo indicación. Ganados/perdidos = casos que pasan a rango 1 o dejan
de serlo en el orden final.

**Perfil light** (el orden final es el híbrido)

| Experimento | hit@1 | hit@3 | MRR | p95 ms | ganados / perdidos |
|---|---|---|---|---|---|
| base `CH-F256` | 0,792 | 0,986 | 0,890 | 229 | |
| F1.1 cabecera básica | 0,833 | 0,986 | 0,913 | 196 | 8 / 5 |
| F3.1 cabecera extendida | 0,847 | 1,000 | 0,921 | 224 | 8 / 4 |
| F1.2 `CH-PAR` | 0,931 | 1,000 | 0,965 | 210 | 11 / 1 |
| F1.2 `CH-SEC` | 0,972 | 1,000 | 0,986 | 231 | 14 / 1 |
| F2.1 `CH-F256S` | 0,792 | 1,000 | 0,889 | 114 | 11 / 11 |
| F2.3 estructural (Markdown) | 1,000 | 1,000 | 1,000 | 65 | 15 / 0 |

**Perfil medium** (el orden final lo da el reranker)

| Experimento | hit@1 | hit@3 | hit@5 | MRR | p95 ms | ganados / perdidos |
|---|---|---|---|---|---|---|
| base `CH-F256` | 0,736 | 0,875 | 0,958 | 0,816 | 2 402 | |
| F1.1 cabecera básica | 0,750 | 0,875 | 0,958 | 0,823 | 2 396 | 1 / 0 |
| F3.1 cabecera extendida | 0,750 | 0,875 | 0,958 | 0,823 | 2 412 | 1 / 0 |
| F1.2 `CH-PAR` | 0,694 | 0,792 | 0,833 | 0,739 | 2 475 | 13 / 16 |
| F1.2 `CH-SEC` | 0,833 | 0,972 | 0,986 | 0,895 | 2 404 | 16 / 9 |
| F1.3 reranker 512 | 0,861 | 0,986 | 1,000 | 0,922 | 2 361 | 11 / 2 |
| F2.1 `CH-F256S` | 0,889 | 1,000 | 1,000 | 0,942 | 2 392 | 16 / 5 |
| F2.3 estructural | 0,986 | 1,000 | 1,000 | 0,991 | 1 063 | 18 / 0 |
| F1.4 `CH-SEC` + 512 | 0,986 | 1,000 | 1,000 | 0,991 | 2 336 | 19 / 1 |
| F1.4 `CH-F256S` + 512 | 0,931 | 1,000 | 1,000 | 0,965 | 2 380 | 18 / 4 |
| F1.4 `CH-F256S` + cabecera extendida + 512 | 0,931 | 1,000 | 1,000 | 0,965 | 2 399 | 18 / 4 |
| F1.4 estructural + 512 | 0,986 | 1,000 | 1,000 | 0,991 | 1 109 | 18 / 0 |

### Recomendación (F1.4), sin cambiar valores por defecto

1. **Causa dominante en `medium`: el reranker no ve el final del fragmento (C1).** Subir
   `reranker_max_tokens` a 512 es el cambio más barato y casi cierra la brecha (0,736 → 0,861) sin costo
   de latencia medible. Con fragmentos de una sola sección se acerca a 0,93 a 0,99.
2. **La preparación estructural es la mejor opción**: 0,986 en `medium` con p95 de 1,1 s (mitad del
   presupuesto) y 1,000 en `light`. 512 no le añade nada. Es la candidata para F5.1 y justifica evaluar F2.4
   (PDF).
3. **Sin preparación estructural**, la mejor combinación es `CH-SEC` + 512 (0,986 en `medium`), pero en
   `light` `CH-SEC` solo tiene 0,972 y sus fragmentos llegan a 400 palabras; `CH-F256S` + 512 queda en 0,931.
4. **La cabecera aporta poco aquí** (+4 a 5 puntos en `light`, +1 caso en `medium`): no se recomienda por sí
   sola. `CH-PAR` no se recomienda: empeora `medium`.
5. F3.2 (hermanos) y F3.3 no se justifican todavía: con estos fragmentos el rango 2 a 5 casi desaparece.

Cautelas: el banco es sintético, lo generé yo y su corpus es muy regular; `light` ya está casi saturado y
varias diferencias son de 1 a 3 casos sobre 72. Nada de esto sustituye una medición en `test` (F5.1) ni en un
corpus real. La latencia de `medium` aquí está acotada por el presupuesto en una CPU de 4 núcleos.

## F5.1: candidata medida en `test`

Partición `test` (44 preguntas), medida una sola vez por configuración; hit@1 final.

| Configuración | Perfil | hit@1 | hit@3 | hit@5 | MRR | p95 ms | ganados / perdidos |
|---|---|---|---|---|---|---|---|
| base `CH-F256` | light | 0,864 | 0,977 | 1,000 | 0,926 | 175 | |
| base `CH-F256` | medium | 0,727 | 0,818 | 0,886 | 0,785 | 2 417 | |
| **estructural (Markdown)** | light | **1,000** | 1,000 | 1,000 | 1,000 | 88 | 6 / 0 |
| **estructural (Markdown)** | medium | **0,977** | 1,000 | 1,000 | 0,989 | 1 104 | 11 / 0 |
| `CH-SEC` + `reranker_max_tokens: 512` | medium | 0,955 | 1,000 | 1,000 | 0,977 | 2 329 | 11 / 1 |

Verificaciones con los valores por defecto actuales (no se cambió ninguno):

- `general.py --no-baseline`: 0 fallos, 6 bancos (light y medium × bueno/medio/malo).
- Suite completa con modelos: 1 493 pasan. Fallan 44 pruebas que **también fallan en el commit de release
  `2390901` sin ningún cambio de este plan**: `test_caracterizacion` (snapshots anteriores al motor v2 por
  defecto), `test_banco_universal::test_falsos_ok_no_superan_la_linea_base`, `test_general_regresion`,
  `test_tono_no_cambia_estados` y `test_portabilidad_pythonioencoding_cp1252_no_falla`. No son regresiones de
  este plan, pero conviene corregirlas aparte.

### Propuesta (no aplicada)

Dos opciones, de menor a mayor alcance. Ninguna cambia nada hasta que el usuario apruebe.

- **A. Preparación estructural por defecto** (`retrieval.preparation.mode: structural_v1`). Mejor resultado y menor
  latencia, pero cambia colección e índice (`_estructura1`), obliga a reindexar, y hoy el PDF sigue en legacy
  (F2.4), de modo que un proyecto con PDF fallaría al indexar: habría que degradar por formato o terminar F2.4
  antes. Requiere migración en `ipsis/configuracion/migraciones.py` (`config_version: 7`) para los proyectos con
  `config/engine.yaml`.
- **B. Solo `reranker_max_tokens: 512` y `CH-SEC`**: sin tocar la preparación, mismo formato y latencia que hoy
  (0,955 en `test`), pero también cambia el fragmentado y exige reindexar.
- Mínimo y sin reindexar: solo `reranker_max_tokens: 512` (0,861 en `dev`, `medium`).

## F2.4: preparación estructural con PDF (banco general)

`tests/datos/banco_general/{bueno,medio,malo}` (12 preguntas respondibles cada uno, 4 documentos:
Markdown, PDF, DOCX y texto), partición `todas`, legacy frente a `estructural_v1`. Antes de F2.4 la
estructural no podía indexar este corpus por el PDF.

| Calidad | Perfil | hit@1 legacy | hit@1 estructural | hit@3 | Ganados / perdidos |
|---|---|---|---|---|---|
| bueno | light | 1,000 | 0,917 | 1,000 | 0 / 1 (`logistica-2`, `.txt`: rango 2) |
| bueno | medium | 1,000 | 1,000 | 1,000 | 0 / 0 |
| medio | light | 1,000 | 1,000 | 1,000 | 0 / 0 |
| medio | medium | 1,000 | 1,000 | 1,000 | 0 / 0 |
| malo | light | 1,000 | 1,000 | 1,000 | 0 / 0 |
| malo | medium | 1,000 | 1,000 | 1,000 | 0 / 0 |

Este banco está saturado (un documento por tema, 12 preguntas): no puede mostrar mejoras, solo regresiones.
No hubo ninguna en `medium`; en `light`/bueno un caso de un `.txt` bajó del rango 1 al 2, sin afectar hit@3.
La latencia de `medium` bajó (p95 545 → 310 ms en "bueno"). Para el PDF en sí (outline, tamaño de letra,
listas, escaneado) la evidencia son las pruebas unitarias; falta un corpus real con PDF largos.

## Hallazgos

- 2026-10-15: desde el entorno de nube usado para el análisis no se pudo
  descargar desde huggingface.co (proxy 403). F0.3 en adelante necesita un
  entorno con acceso a los modelos o una caché `IPSIS_MODELS_DIR`.
