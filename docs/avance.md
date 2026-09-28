# Avance de la ruta

Bitácora de ejecución de [ruta.md](ruta.md). Se actualiza **en el mismo commit**
que cada paso, así que el último commit de la rama siempre describe el estado real.

## Cómo retomar

1. `git switch v2/ruta && git log --oneline main..` muestra los pasos hechos.
2. Leer la sección **Siguiente paso** de este archivo.
3. Verificar la línea base: `.venv\Scripts\python.exe -m pytest -m "not slow" -q`.
4. Cualquier cambio sin commit en `git status` es trabajo a medias del paso en curso;
   el paso en curso está marcado 🔶 abajo.

Convenciones:

- Rama de trabajo: `v2/ruta` (se integra a `main` al cerrar cada fase).
- Un commit por paso, con el identificador del paso al inicio (`F0.2: ...`).
- Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⏸ pospuesto.

## Siguiente paso

F0.5: `CHANGELOG.md` y CI en GitHub Actions. La licencia queda pendiente de decisión del autor.

## Fase 0: higiene

La columna Commit se completa en el commit siguiente; mientras tanto,
`git log --grep "^F0.3"` encuentra el commit de un paso.

| Paso | Estado | Commit | Notas |
|---|---|---|---|
| F0.1 Commitear el trabajo previo en commits con sentido | ✅ | `bd863fd`, `148044f`, `75a7b05` | Empaquetado, contratos V2 y documentación, por separado. |
| F0.2 Suite ejecutable y línea base anotada | ✅ | `90ce53e` | Temporal de pytest en `%LOCALAPPDATA%`. |
| F0.3 Retirar referencias internas ("molde", "Etapa C/D") | ✅ | `52795c8` | Hecho fuera de `api.py`, `pipeline.py`, `corpus.py`, `indice.py`, `test_pipeline.py` y `test_api_seguridad.py` (≈70 referencias): se limpian dentro de la Fase A, que reescribe esos archivos. Las etiquetas E1–E6/P1–P7 de `metricas.py` y `evaluacion.py` quedan para la Fase C. |
| F0.4 Entidades académicas fuera del dominio genérico | ✅ | `d25fac8` | `nota` (escala 1,0–7,0) pasa a ser `decimal` genérico; la escala se declara en el perfil (ejemplo en la plantilla, cubierto por una prueba). `plazo`, `fecha`, `porcentaje` y `articulo` se quedan: son genéricos. |
| F0.4b Porcentajes con decimales | ✅ | | Hallado durante F0.4: "12,5%" daba "5_pct" y respaldaba en falso una pregunta por el 5%. |
| F0.5 `LICENSE`, `CHANGELOG.md`, CI en GitHub Actions | ⬜ | | La licencia la elige el autor. |

## Fase A: registry conectado (Trabajo 1)

| Paso | Estado | Commit | Notas |
|---|---|---|---|
| A.0 Pruebas de caracterización de `/consultar` | ⬜ | | |
| A.1 Contrato de recuperación con filtro y señales | ⬜ | | |
| A.2 Protocolo `AbstentionPolicy` (`layered_v1`) | ⬜ | | |
| A.3 Frontera de tipos `ChunkRecord`/`EvidenceSpan` | ⬜ | | Decisión abierta 1 de ruta.md. |
| A.4 `Motor` orquestador | ⬜ | | |
| A.5 `crear_app(motor)` sin estado global | ⬜ | | |
| A.6 Pruebas de contrato e intercambio | ⬜ | | |

## Fase B: retriever léxico SQLite (Trabajo 2)

| Paso | Estado | Commit | Notas |
|---|---|---|---|
| B.1 Almacén de índice SQLite FTS5 | ⬜ | | |
| B.2 Retriever `sqlite_fts` | ⬜ | | |
| B.3 Señal de confianza léxica | ⬜ | | Decisión abierta 2 de ruta.md. |
| B.4 Ingesta y CLI por backend | ⬜ | | |
| B.5 Pruebas por backend y de aislamiento | ⬜ | | |

## Línea base de pruebas

**2026-09-27, antes de F0.2** (`.venv`, Python 3.12.4, suite completa):
162 pasan, 58 errores, 278 s. Los 58 errores son todos `PermissionError` al
limpiar `--basetemp=.cache/pytest_tmp`: OneDrive bloquea esa carpeta (queda vacía
pero no se puede borrar). El temporal del sistema también está denegado en esta
máquina, por eso `pytest.ini` usaba una carpeta local. No son fallos de código.

**2026-09-27, tras F0.2**: suite completa **220 pasan**, 0 fallos, 232 s.
Subconjunto rápido (`-m "not slow"`): **217 pasan**, 3 deseleccionadas, 57 s.
Advertencias conocidas (5 en el rápido, 7 en la completa): `get_sentence_embedding_dimension` renombrado en
sentence-transformers 6, e índices de payload sin efecto en Qdrant local.

## Registro

- **2026-09-27** Se crea la rama `v2/ruta` desde `main` (`41ce65a`) y se
  commitea el trabajo previo sin cambios de contenido.
- **2026-09-27** F0.2: `tests/conftest.py` elige el temporal de pytest
  (`RAG_PYTEST_BASETEMP`, o `%LOCALAPPDATA%\rag-extractivo\pytest` en Windows).
  `pytest.ini` deja de fijar `--basetemp`. Suite en verde.
- **2026-09-27** F0.3: se quitan las etiquetas de proceso de comentarios y
  docstrings en 19 archivos, y las menciones a módulos que ya no existen
  (`rag/paquete_revision_externa.py`, `rag/deteccion_evidencia.py`,
  `rag/medicion_normalizacion.py`, `eval/*.py`). Solo cambian comentarios;
  217 pruebas rápidas en verde.
- **2026-09-27** F0.4: tipo `nota` reemplazado por `decimal` (coma o punto,
  normaliza a punto; no recorta números con varios separadores). Cambia el
  comportamiento: la verificación de premisa ahora protege cualquier cifra
  decimal, no solo 1,0–7,0. **Los índices existentes deben reindexarse** para
  que su inventario de entidades use el tipo nuevo. 224 rápidas y 3 lentas en
  verde.
- **2026-09-27** F0.4b: `extraer_porcentajes` no recorta decimales
  ("12,5%" → `12.5_pct`). Error de fidelidad: la verificación de premisa
  aceptaba "5%" contra un texto con 12,5%. También requiere reindexar.
  227 rápidas en verde.
