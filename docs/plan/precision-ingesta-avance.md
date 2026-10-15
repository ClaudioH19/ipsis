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
| F1.5 | ⚠ | | | Decidir (a) o (b). |
| F2.1 | ⬜ | | | |
| F2.2 | ⚠ | | | Decidir (a), (b) o (c) tras F0.3 y F1.3. |
| F2.3 | ⬜ | | | |
| F2.4 | ⬜ | | | Solo si F2.3 mejora. |
| F3.1 | ⬜ | | | |
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
