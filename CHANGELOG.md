# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto sigue [SemVer](https://semver.org/lang/es/). Mientras la versión
sea 0.x, un cambio menor puede romper compatibilidad y se indica como tal.

## [Sin publicar]

### Cambiado

- **Requiere reindexar.** El tipo de entidad `nota` (escala 1,0–7,0) se
  reemplaza por `decimal`, que reconoce cualquier número con coma o punto
  decimal y lo normaliza a punto. Una escala propia se declara en el perfil;
  la plantilla `dominios/_generico/perfil.yaml` trae un ejemplo.
- Imagen Docker multi-stage construida desde el wheel, con usuario sin
  privilegios y healthcheck contra `/ready`.
- La versión que informa la API se lee del paquete instalado.
- Las pruebas usan un directorio temporal fuera del checkout (en Windows,
  `%LOCALAPPDATA%\rag-extractivo\pytest`); `RAG_PYTEST_BASETEMP` lo cambia.

### Corregido

- **Requiere reindexar.** `12,5%` se extraía como el porcentaje `5`, lo que
  hacía pasar la verificación de premisa a una pregunta por el 5 %.
- Las preguntas que solicitan precios, duraciones o cantidades reconocibles ya
  no producen `ok` si la evidencia carece del tipo de dato solicitado.

### Descartado

- El backend experimental SQLite FTS5 se retira antes de publicar. Aunque se
  implementó y verificó técnicamente, en C.3 produjo un falso `ok` bloqueante
  ante una pregunta ambigua. Qdrant queda como único backend soportado.
  Línea base de esa comparación (banco `aqualis_sintetico@1.0.0`, 12 casos):

  | Backend | Recall@3 | MRR | Falsos `ok` | Exactitud de estado | p95 |
  |---|---:|---:|---:|---:|---:|
  | `sqlite_fts` (descartado) | 1,000 | 1,000 | 0,125 | 0,500 | 9 ms |
  | `qdrant_vectorial` | 1,000 | 0,750 | 0,000 | 0,583 | 22 ms |
  | `qdrant_hibrida` | 1,000 | 0,750 | 0,000 | 0,583 | 13 ms |
- Planes y bitácoras anteriores (`PLAN_V2.md`, `docs/ruta.md`,
  `docs/avance.md`, `docs/arquitectura.md`), `requirements*.txt` y el
  evaluador del golden antiguo (`rag/evaluacion.py`, `rag/metricas.py`). Los
  reemplaza el plan V3 en `docs/plan/`.

### Agregado

- Contratos de componentes, esquemas versionados y registry
  (`rag.componentes`, `rag.esquemas`, `rag.registro`), conectados
  progresivamente al pipeline; ver `docs/plan/`.
- Protocolo `AbstentionPolicy` e implementación `layered_v1`, seleccionable
  desde `componentes.abstention_policy`, con decisiones estructuradas y
  validación temprana en el arranque y en `rag doctor`.
- Frontera tipada de consulta: recuperación y selección trabajan con
  `RetrievalCandidate`, `ChunkRecord` y `EvidenceSpan`; el verificador coteja
  texto y offsets contra el chunk fuente antes de redactar.
- Primer corte de `Motor.consultar() -> AssistantResult`; `/consultar` delega
  en el motor mientras un adaptador transitorio preserva el contrato HTTP V1.
- El flujo activo de consulta pasa al `Motor`, separado en análisis,
  recuperación normal y dirigida, abstención, selección, verificación y
  construcción del resultado, con diagnóstico básico por etapa.
- `Motor.desde_configuracion()` valida la selección completa del registry y
  centraliza la construcción de los componentes de consulta; FastAPI solo crea
  y calienta el motor durante el arranque.
- Diagnóstico interno versionado por consulta con backend, latencias,
  candidatos, señales, decisión, evidencia y advertencias, excluido de la
  respuesta pública de `AssistantResult`.
- Fábrica `crear_app(motor)` con estado aislado por aplicación y ciclo de vida
  para calentamiento y cierre; se elimina el pipeline HTTP heredado duplicado.
- Plantillas y perfil de dominio inyectados en `Motor`, con perfil contextual
  por consulta y sin lecturas relativas de plantillas durante la ejecución.
- `config_version: 2` unifica la selección de reranker bajo
  `componentes.reranker` y migra configuraciones anteriores.
- Matriz de intercambio de componentes y ejecución completa del motor en
  memoria, verificada sin importar Qdrant ni las dependencias de modelos.
- Banco de evaluación versionado con manifiesto, hash del corpus, categorías,
  splits `dev`/`test`, respuestas literales y evidencias con offsets; incluye
  un conjunto sintético balanceado y mantiene separado el golden set manual.
- Evaluación del backend activo con Recall@k, MRR, estados, abstención,
  falsos `ok`, literalidad, offsets, longitud y latencias; `rag evaluar` puede
  persistir el reporte y bloquea ante cualquier falso `ok`.
- Benchmark reproducible de Qdrant denso e híbrido contra el mismo banco; los
  artefactos incluyen hash del dataset completo, configuración,
  índice, observaciones y calibración exclusiva de `dev`. `rag comparar`
  valida que los resultados sean compatibles y no toma decisiones automáticas.
- `rag servir <carpeta>` prepara automáticamente una carpeta documental en un
  proyecto privado `.rag-extractivo/`, o completa un proyecto existente sin
  sobrescribir su configuración. Reutiliza el índice vigente y acepta
  `--reindexar`; `/health` y `/ready` mantienen semánticas separadas.
- Presets `clasico`, `minimal`, `editorial` y `contraste` para el widget,
  administrables mediante `rag widget tema`; la vista previa HTML muestra
  estados y citas sin API. `/config` expone en lectura el preset, densidad,
  comportamiento de citas y etiquetas que consume el widget real.
- Web Component `<rag-extractivo-chat>` compatible con la integración anterior,
  con atributos y eventos públicos. `rag widget exportar` genera `widget.js` y
  un snippet escapado listo para integrar.
- Ejemplos ejecutables para HTML, React/Vite y WordPress, más pruebas del
  widget en Chromium para teclado, foco y ARIA, vista móvil, citas y errores
  de red. Los fallos de transporte muestran un mensaje estable en español.
- `config_version` en `asistente.yaml` y `motor.yaml`, con validación estricta
  y migración de archivos sin versión.
- `rag snapshot-config`: escribe la configuración efectiva con defaults.
- CI en GitHub Actions: pruebas rápidas en Linux y Windows, integración con
  modelo real y prueba del wheel en un entorno limpio.
- Documentación: ADR, metodología de recuperación y plan V3 (`docs/plan/`).

## [0.7.0]

Versión inicial publicada en el repositorio.
