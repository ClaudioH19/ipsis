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

F0.2: aislar el directorio temporal de pytest fuera de OneDrive y fijar la línea base.

## Fase 0: higiene

| Paso | Estado | Commit | Notas |
|---|---|---|---|
| F0.1 Commitear el trabajo previo en commits con sentido | ✅ | `bd863fd`, `148044f`, `75a7b05` | Empaquetado, contratos V2 y documentación, por separado. |
| F0.2 Suite ejecutable y línea base anotada | 🔶 | | Ver "Línea base" abajo. |
| F0.3 Retirar referencias internas ("molde", "Etapa C/D") | ⬜ | | |
| F0.4 Entidades académicas fuera del dominio genérico | ⬜ | | `nota`, `plazo`, `articulo` en `rag/reglas_extraccion.py`. |
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

## Registro

- **2026-09-27** Se crea la rama `v2/ruta` desde `main` (`41ce65a`) y se
  commitea el trabajo previo sin cambios de contenido.
