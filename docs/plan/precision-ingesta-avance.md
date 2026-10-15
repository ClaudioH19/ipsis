# Avance: precisión del primer resultado desde la ingesta

Tareas: [precision-ingesta-tareas.md](precision-ingesta-tareas.md).
Rama de trabajo: `ccr-b2b5f6b8-7tipuk` (separada de `main`).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado ·
⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| F0.1 | ✅ | 2026-10-15 | 2d2b536 | Usuario sin corpus real: banco sintético en `tests/datos/banco_pasajes` (116 respondibles + 15 trampas, 10 documentos). |
| F0.2 | 🔶 | 2026-10-15 | (ver git log) | Script `herramientas/evaluacion/ranking_pasajes.py` y 8 pruebas con motor falso en verde. La corrida de punta a punta no se pudo completar: `ipsis index` falla porque `intfloat/multilingual-e5-small` no está en caché y huggingface.co responde 403 por el proxy. Con `init`, `load` y fragmentado (97 fragmentos con `CH-F256`) sí llegó. Pendiente: correrlo en un entorno con modelos y pasar a ✅. |
| F0.3 | ⬜ | | | Requiere modelos en caché. |
| F0.4 | ⬜ | | | Requiere modelos. |
| F1.1 | ⬜ | | | |
| F1.2 | ⬜ | | | |
| F1.3 | ⬜ | | | |
| F1.4 | ⬜ | | | |
| F1.5 | ✅ | 2026-10-15 | (ver git log) | Opción (b) aprobada por el usuario: `hash_corpus` legacy incluye `texto_embebido` solo si difiere de `texto`. 4 pruebas en `tests/indice/test_manifiesto.py` y 1 en `tests/ingesta/test_cabecera.py`. Un índice hecho antes con `with_header: true` muestra otra huella y conviene reindexarlo. La regla 9 de las tareas queda resuelta: ya no hace falta correr los experimentos sin calibración. |
| F2.1 | 🔶 | 2026-10-15 | (ver git log) | `CH-F256S` implementada y probada (16 pruebas nuevas). Sobre el corpus del banco de pasajes: `CH-F256` 97 fragmentos, 56 cruzan sección, máx. 307 palabras; `CH-F256S` 122 fragmentos, 0 cruzan, máx. 255. Falta `MEDIR` en `dev` frente a F0.4/F1 (sin modelos en este entorno). |
| F2.2 | ⚠ | | | Decidir (a), (b) o (c) tras F0.3 y F1.3. |
| F2.3 | 🔶 | 2026-10-15 | (ver git log) | `preparar_markdown` y `preparar_texto` (reutilizan `parsear_markdown`/`parsear_texto_plano`), despacho por extensión, huella con la versión de cada parser, `ipsis prepare` y la ingesta estructural funcionan sobre `.md` (9 pruebas). Falta `MEDIR` con `preparacion.modo: estructural_v1` en `dev` (sin modelos). Además corregí que `hash_archivos` del manifiesto omitía `header_detail` (F3.1). |
| F2.4 | ⬜ | | | Solo si F2.3 mejora. |
| F3.1 | 🔶 | 2026-10-15 | (ver git log) | `header_detail: extended` implementado (cabecera en es/en/pt, entidades y marcas calculadas una vez, huella solo cambia con `extended`) con 11 pruebas. Falta `MEDIR` en `dev` (sin modelos en este entorno). Ojo regla 9: como `hash_corpus` legacy no incluye `texto_embebido`, no invalida la calibración; depende de F1.5. |
| F3.2 | ⚠ | | | Decidir la similitud; depende de F1.5. |
| F3.3 | ⬜ | | | Condicional. |
| F4.1 | ⬜ | | | |
| F4.2 | ⬜ | | | Condicional. |
| F4.3 | ⚠ | | | Requiere aprobación. |
| F5.1 | ⬜ | | | Valores por defecto: aprobación del usuario. |
| F5.2 | ⬜ | | | |

## Línea base (F0.4)

Pendiente.

## Resultados por experimento

Pendiente.

## Hallazgos

- 2026-10-15: desde el entorno de nube usado para el análisis no se pudo
  descargar desde huggingface.co (proxy 403). F0.3 en adelante necesita un
  entorno con acceso a los modelos o una caché `IPSIS_MODELS_DIR`.
