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
- Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⏸ pospuesto · ❌ descartado.

## Siguiente paso

D.8: verificar en CI que el wheel y la imagen Docker se construyen y funcionan
desde artefactos limpios.

El extra visual solicitado queda incorporado a D.3–D.5: presets configurables
por consola, mockup de todos los estados y citas, y API pública de configuración
solo de lectura. No se reutilizará la clave pública del widget para mutaciones
administrativas.

## Decisiones diferidas

No se resuelven durante el replanteamiento de la ruta. Se tomarán en la puerta
de fase correspondiente, con evidencia o una necesidad concreta de publicación.

- **Licencia** (bloquea publicar, no bloquea trabajar). Opciones habituales:
  MIT o Apache-2.0 (permisivas; Apache añade concesión de patentes) o
  AGPL-3.0 (obliga a publicar cambios incluso si se ofrece como servicio).
  Las dependencias actuales son permisivas; PyMuPDF se descartó por AGPL.
- **Publicar la rama**: `git push -u origin v2/ruta` activa la CI. No se ha
  hecho push; todo el avance está solo en este equipo.

Decisión tomada con la evidencia de C.3: **Qdrant es el único backend soportado
para el lanzamiento**. SQLite FTS5 se retiró por un falso `ok` bloqueante.

## Fase 0: higiene

La columna Commit se completa en el commit siguiente; mientras tanto,
`git log --grep "^F0.3"` encuentra el commit de un paso.

| Paso | Estado | Commit | Notas |
|---|---|---|---|
| F0.1 Commitear el trabajo previo en commits con sentido | ✅ | `bd863fd`, `148044f`, `75a7b05` | Empaquetado, contratos V2 y documentación, por separado. |
| F0.2 Suite ejecutable y línea base anotada | ✅ | `90ce53e` | Temporal de pytest en `%LOCALAPPDATA%`. |
| F0.3 Retirar referencias internas ("molde", "Etapa C/D") | ✅ | `52795c8` | Hecho fuera de `api.py`, `pipeline.py`, `corpus.py`, `indice.py`, `test_pipeline.py` y `test_api_seguridad.py` (≈70 referencias): se limpian dentro de la Fase A, que reescribe esos archivos. Las etiquetas E1–E6/P1–P7 de `metricas.py` y `evaluacion.py` quedan para la Fase C. |
| F0.4 Entidades académicas fuera del dominio genérico | ✅ | `d25fac8` | `nota` (escala 1,0–7,0) pasa a ser `decimal` genérico; la escala se declara en el perfil (ejemplo en la plantilla, cubierto por una prueba). `plazo`, `fecha`, `porcentaje` y `articulo` se quedan: son genéricos. |
| F0.4b Porcentajes con decimales | ✅ | `a4b6b03` | Hallado durante F0.4: "12,5%" daba "5_pct" y respaldaba en falso una pregunta por el 5%. |
| F0.5 `CHANGELOG.md` y CI en GitHub Actions | ✅ | `a668f8d` | CI sin ejecutar todavía (requiere push). Validado localmente: YAML, contenido del wheel y `rag init` en carpeta vacía. |
| F0.6 `LICENSE` | ⏸ | | Decisión del autor, ver arriba. |

## Fase A: arquitectura ejecutable e intercambiable

| Paso | Estado | Commit | Notas |
|---|---|---|---|
| A.0 Pruebas de caracterización de `/consultar` | ✅ | `1176878`, `9007a2d` | `tests/test_caracterizacion_consultar.py` (marcada `slow`, ~100 s): 16 preguntas sobre un corpus sintético, servidor real en subproceso. Cubre `ok`, `relacionado`, `sin_respuesta` (fuera de dominio y premisa) y `conversacional`. |
| A.1 Contrato de recuperación con filtro y señales | ✅ | | `Retriever` separa `estimar_confianza` de `recuperar(filtro=...)` y expone inventarios. `RetrieverQdrant` en `rag/recuperacion_qdrant.py`, registrado como `retriever/qdrant`; caché LRU del vector de la pregunta. Probado con Qdrant en memoria y codificador falso. |
| A.2a Caracterizar las capas de abstención | ✅ | | Límites exactos, precedencia de premisa, grounding y los dos modos de zona gris cubiertos. |
| A.2b Extraer `AbstentionPolicy` (`layered_v1`) | ✅ | | `rag/abstencion.py`: decisión estructurada con estado, motivo, capa, señal y candidato; `pipeline.py` conserva adaptadores compatibles. |
| A.2c Integrar la política mediante el registry | ✅ | | Seleccionada por `componentes.abstention_policy`; validación al arrancar y en `rag doctor`. |
| A.3 Frontera de tipos `ChunkRecord`/`EvidenceSpan` | ✅ | | Candidatos tipados desde la salida de Qdrant; recuperación dirigida, política, selector y verificador usan contratos. La redacción heredada recibe diccionarios solo mediante `payload_desde_evidencia()`. |
| A.4a Envolver el flujo actual en `Motor` | ✅ | | `Motor.consultar()` devuelve `AssistantResult`; `/consultar` delega en él y conserva el contrato HTTP V1 mediante un adaptador transitorio. |
| A.4b Separar las etapas del flujo | ✅ | | `Motor` ejecuta análisis, señales, recuperación normal y dirigida, abstención, evidencia, verificación, redacción y resultado. La copia heredada en `api.py` ya no participa del endpoint y se retirará al adelgazar la API. |
| A.4c Resolver componentes desde configuración | ✅ | | `Motor.desde_configuracion()` valida toda la selección declarativa antes de construir, instancia los componentes de consulta y la API deja de ensamblarlos manualmente. |
| A.4d Diagnóstico estructurado por consulta | ✅ | | `QueryDiagnostic` versiona backend, latencias, candidatos, señales, decisión, evidencia y advertencias; permanece excluido de la serialización pública. |
| A.5 `crear_app(motor)` sin estado global | ✅ | | Estado por instancia en `app.state`, `lifespan` para arranque/cierre, API delgada, plantillas y perfil inyectados; `config_version: 2` unifica `reranker`. |
| A.6 Matriz de contratos e intercambio | ✅ | | Contratos de retriever, política, selector, verificador y motor; corte en memoria probado bloqueando Qdrant, torch, transformers y SentenceTransformers. |
| A.7 Guardia mínima de fidelidad | ✅ | | Precios, duraciones y cantidades reconocibles exigen evidencia del tipo solicitado antes de permitir `ok`; un caso falso conocido pasa deliberadamente a `sin_respuesta`. |

## Fase B: backend léxico SQLite FTS5 — descartada

La fase se implementó y se probó completa para obtener evidencia. C.3 mostró
que SQLite respondía como válida la pregunta ambigua «¿Cuánto dura?», un falso
`ok` bloqueante. Como el lanzamiento usará Qdrant, el backend, su configuración,
pruebas y documentación operativa se retiraron antes de publicar. Se conserva
esta bitácora para no perder la decisión ni repetir el experimento sin evidencia
nueva.

| Paso | Estado | Commit | Notas |
|---|---|---|---|
| B.1 Índice mínimo válido SQLite FTS5 | ❌ | | Implementado y probado; retirado tras C.3. |
| B.2 Recuperación FTS segura | ❌ | | Implementada y probada; retirada tras C.3. |
| B.3 Confianza léxica experimental | ❌ | | Implementada, no apta para la decisión de abstención observada; retirada. |
| B.4 Corte vertical de ingesta y CLI | ❌ | | Implementado y probado; retirado del producto. |
| B.5 Aislamiento y contratos por backend | ❌ | | Sirvió para comparar; la superficie SQLite y su CI fueron eliminadas. |

## Fase C: evaluación y calibración reproducibles

| Paso | Estado | Commit | Notas |
|---|---|---|---|
| C.1 Banco de evaluación versionado | ✅ | | Esquema estricto; 12 casos sintéticos balanceados entre `dev`/`test`; golden manual separado y pendiente de curación humana. |
| C.2 Métricas por etapa | ✅ | | Recall@k, MRR, estados, abstención, falsos `ok`, literalidad, offsets, longitud y latencias con desgloses. |
| C.3 Comparación y calibración | ✅ | | La ejecución inicial comparó SQLite y los dos modos Qdrant; tras descartar SQLite, el comando compara Qdrant denso e híbrido y conserva banco, configuración, índice, observaciones e informe. |

## Fase D: integración web mínima verificable

| Paso | Estado | Notas |
|---|---|---|
| D.1 `rag servir <carpeta>` | ✅ | Una carpeta documental crea `.rag-extractivo/`; un proyecto existente se completa sin sobrescribir configuración. El índice se reutiliza si está vigente y `--reindexar` fuerza su reconstrucción. |
| D.2 `/health` y `/ready` | ✅ | Liveness independiente del motor; readiness entrega backend, colección, inventario y capacidad, o 503 con la causa de arranque. |
| D.3 Presets visuales por consola | ✅ | `clasico`, `minimal`, `editorial` y `contraste`; listado, aplicación atómica y validación de valores. |
| D.4 Vista previa con mockups | ✅ | HTML autónomo con los estados, respuestas y citas, sin requerir API ni índice. |
| D.5 API pública de presentación | ✅ | `/config` de solo lectura expone preset, densidad, modo de citas y etiquetas; el widget aplica esas opciones. |
| D.6 Exportación y Web Component | ✅ | `rag widget exportar` produce JS y snippet; `<rag-extractivo-chat>` acepta atributos públicos y emite eventos de ciclo y consulta. |
| D.7 Ejemplos y pruebas de navegador | ✅ | Ejemplos HTML, React/Vite y plugin WordPress; suite Chromium separada para teclado, ARIA/foco, móvil, citas y errores de red. La CI la ejecuta con Playwright. |
| D.8 Distribución verificada | ⬜ | Wheel e imagen Docker en CI. |

### Línea base C.3 (`aqualis_sintetico@1.0.0`)

| Backend | Recall@3 | MRR | Falsos `ok` | Exactitud de estado | p95 |
|---|---:|---:|---:|---:|---:|
| `sqlite_fts` (histórico, descartado) | 1,000 | 1,000 | 0,125 | 0,500 | 9 ms |
| `qdrant_vectorial` | 1,000 | 0,750 | 0,000 | 0,583 | 22 ms |
| `qdrant_hibrida` | 1,000 | 0,750 | 0,000 | 0,583 | 13 ms |

Es una muestra sintética de solo 12 casos. No elige backend ni publica los
umbrales: SQLite responde indebidamente la pregunta ambigua «¿Cuánto dura?»;
los umbrales sugeridos en `dev` también muestran alta abstención falsa. La
decisión queda diferida hasta disponer del golden set manual.

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

## Hallazgos de calidad (para A.7 y la Fase C)

Observados al construir la caracterización (A.0) sobre
`tests/caracterizacion/corpus` (dos documentos cortos). La caracterización
solo cambia cuando una corrección deliberada incluye su propia prueba.

1. **Corregido en A.7: respuesta falsa con estado `ok`.** "¿Cuánto cuesta el
   purificador?" ahora devuelve `sin_respuesta`: la evidencia no contiene un
   importe monetario. El ranking no se modificó.
2. **Respuestas demasiado largas.** Las respuestas `ok` miden ~1.100
   caracteres cuando el dato cabe en una oración. Con documentos cortos,
   `CH-F256` produce chunks que abarcan varias secciones, y el recorte de
   `seleccion_fragmento.py` no basta.
3. **`relacionado` en exceso.** 6 de 12 preguntas del dominio caen en
   `relacionado` aunque el dato exacto está en el texto mostrado. Los cosenos
   de e5-small quedan comprimidos entre 0,78 y 0,87, justo alrededor de los
   umbrales 0,80/0,85, que no están calibrados.
4. "¿Cuánto dura la garantía?" dio `relacionado` mostrando el párrafo de
   presión en lugar del de garantía (no está en la caracterización por quedar
   a 0,001 del umbral).

Conclusión provisional: A.7 cubre el falso `ok` cuantitativo conocido. La
Fase C debe medir chunking, recuperación y umbrales antes de añadir técnicas.

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
- **2026-09-27** F0.5: `CHANGELOG.md` y `.github/workflows/pruebas.yml`
  (rápidas en Linux/Windows × py3.11/3.12, integración con modelo real, wheel
  en entorno limpio). torch se instala desde el índice CPU en CI.
- **2026-09-27** A.0: caracterización de `/consultar` generada y verificada
  dos veces con índices nuevos (18/18). Ver "Hallazgos de calidad".
- **2026-09-27** A.1: contrato `Retriever` nuevo, `FiltroEntidad`,
  `SenalesRecuperacion`, `RetrievalCandidate.score`, `RetrieverQdrant` y
  adaptador de payload. `api.py` todavía no los usa. 239 rápidas en verde.
- **2026-09-28** Se replantea `ruta.md`: la Fase A se divide en entregas
  verificables, SQLite pasa a ser un corte vertical, la evaluación gana métricas
  bloqueantes de fidelidad y las decisiones de producto quedan diferidas.
- **2026-09-28** A.2: protocolo `AbstentionPolicy`, implementación
  `layered_v1`, decisión estructurada, selección por registry y validación en
  `rag doctor`. La API usa `SenalesRecuperacion` y candidatos tipados para la
  decisión; la recuperación dirigida queda en la orquestación hasta A.4.
  Verificación: 248 rápidas y 18/18 de caracterización en verde. En este
  entorno se usó modo offline de Hugging Face para evitar reintentos de red.
- **2026-09-28** A.3: la API cruza la frontera de Qdrant una sola vez hacia
  `RetrievalCandidate`/`ChunkRecord`; la recuperación dirigida conserva esos
  tipos, `SentenceSelectorExtractor` produce `EvidenceSpan` con el mismo
  recorte y orden global, y `LiteralOffsetsVerifier` coteja texto y offsets
  contra el chunk fuente. Verificación: 253 rápidas y 18/18 de
  caracterización en verde.
- **2026-09-29** A.4a: se crea `rag/servicio/motor.py`. El `Motor` envuelve el
  ejecutor actual, traduce estados y evidencias a `AssistantResult`, y conserva
  internamente el contrato HTTP heredado para que FastAPI lo adapte sin
  diferencias. Verificación: 260 rápidas y 18/18 de caracterización en verde.
- **2026-09-29** A.4b: el flujo activo se traslada a métodos pequeños de
  `Motor`. Usa el contrato `Retriever` para señales, recuperación normal y
  dirigida; la API solo traduce `MotorNoListo`/`MotorSaturado` y adapta el
  resultado al contrato V1. El diagnóstico ya registra latencias por etapa,
  candidatos, señales y decisión. Verificación: 261 rápidas y 18/18 de
  caracterización en verde.
- **2026-09-29** A.4c: `Motor.desde_configuracion()` valida primero todos los
  nombres del registry y luego construye retriever, clasificador de intención,
  política, extractor, verificador, renderer y control de admisión. El arranque
  de FastAPI se limita a crear y calentar el motor; el extractor reutiliza el
  codificador del retriever. Se registra `response_renderer/templates` y se
  prueba el fallo previo a conexiones ante nombres desconocidos. Verificación:
  263 rápidas y 18/18 de caracterización en verde.
- **2026-09-29** A.4d: se incorpora `QueryDiagnostic` con versión de esquema,
  backend, tiempos por etapa, candidatos con sus señales, decisión, evidencias
  y advertencias. `Motor` lo valida para conversación, abstención y respuesta,
  mientras `AssistantResult` lo mantiene fuera del contrato serializado.
  Verificación: 264 rápidas y 18/18 de caracterización en verde.
- **2026-09-29** A.5: `crear_app(motor)` aísla motor, seguridad y disponibilidad
  en `app.state`; `lifespan` construye la entrada de producción, calienta y
  cierra recursos. Se elimina `_consultar_legacy` y `api.py` queda como
  adaptador HTTP. Las plantillas se cargan por ruta absoluta y se inyectan
  junto al perfil en cada motor; un `ContextVar` evita mezclar perfiles entre
  consultas concurrentes. `config_version: 2` migra y elimina
  `recuperacion.reranker`, dejando `componentes.reranker` como fuente única.
  Verificación: 266 rápidas y 18/18 de caracterización en verde.
- **2026-09-29** A.6: `tests/test_intercambio_componentes.py` fija la matriz
  de invariantes para retriever, política, selector, verificador y motor. Un
  retriever y una política en memoria fuerzan respuesta, relacionado, premisa
  y fuera de dominio con diagnóstico validado. Un subproceso bloquea
  `qdrant_client`, `torch`, `transformers` y `sentence_transformers` y completa
  igualmente una consulta directa. Verificación: 276 rápidas y 18/18 de
  caracterización en verde.
- **2026-09-29** A.7: la guardia detecta solicitudes de precio, duración y
  cantidades asociadas a un objeto, y exige evidencia del tipo correspondiente
  antes de emitir `ok`. Un porcentaje sobre una tarifa no cuenta como importe.
  La pregunta de caracterización por el costo del purificador cambia de `ok` a
  `sin_respuesta`; las otras 17 conservan su salida. Verificación: 284 rápidas
  y 18/18 de caracterización en verde.
- **2026-09-29** B.1: `rag/indice_sqlite.py` construye el índice en un archivo
  temporal vecino, sincroniza y publica con `os.replace`. Persiste chunks con
  payload JSON completo, `chunks_fts` con `unicode61 remove_diacritics 2`, la
  relación de entidades y un manifiesto versionado con chunker, pipeline, hash,
  fecha, conteos y estadísticas léxicas. La apertura usa `mode=ro` y comprueba
  `quick_check`, tablas, versión, conteos, claves foráneas, alineación FTS y
  payloads Pydantic. Se cubren fallos de publicación y 24 lectores concurrentes.
  Verificación: 293 rápidas y 18/18 de caracterización en verde.
- **2026-09-29** B.2: `rag/recuperacion_sqlite.py` transforma la pregunta en
  términos normalizados, únicos y entrecomillados antes de ejecutar FTS5. La
  consulta usa parámetros para `MATCH`, filtros de entidad y límite; ordena por
  `bm25()` y desempata por `chunk_id`, reconstruyendo cada payload como
  `ChunkRecord`. Operadores, comillas, asteriscos e intentos de inyección se
  tratan como texto. Verificación: 16 pruebas específicas, 25 de B.1+B.2,
  309 rápidas y 18/18 de caracterización en verde.
- **2026-09-29** B.3: los índices SQLite nuevos persisten frecuencia
  documental normalizada por término. `RetrieverSQLiteFTS` calcula
  `idf_coverage_v1` sobre los mejores candidatos: valor en `[0, 1]`, margen
  entre las dos mejores coberturas y listas de términos encontrados y ausentes
  en el diagnóstico. La señal se identifica como `sin_calibrar`; no se trata
  como probabilidad ni comparte silenciosamente los umbrales del coseno denso.
  Verificación: 32 pruebas de B.1–B.3, 46 de contratos del motor, 316 rápidas y
  18/18 de caracterización en verde.
- **2026-09-29** B.4: `componentes.retriever: sqlite_fts` activa el corte
  completo. `rag indexar` publica `.cache/indice.sqlite`, el registry lo abre
  en solo lectura, el motor consulta con `idf_coverage_v1`, `/ready` informa el
  backend y `rag doctor` valida SQLite mientras declara que el modelo denso no
  es necesario. Los umbrales léxicos viven en un perfil separado y permanecen
  `sin_calibrar`. Una prueba punta a punta ejecuta `init -> cargar -> indexar ->
  doctor -> API /consultar` con Qdrant, Torch, Transformers y
  SentenceTransformers bloqueados. Verificación: 86 pruebas focales y 318
  rápidas en verde; 18/18 de caracterización sin cambios.
- **2026-09-29** B.5: una matriz parametrizada aplica a Qdrant y SQLite los
  mismos invariantes de protocolo, determinismo, payload tipado, offsets,
  límites, confianza y filtros. La CI incorpora un entorno virtual mínimo que
  confirma la ausencia de `qdrant_client`, Torch, Transformers y
  SentenceTransformers antes de ejecutar el corte SQLite. La ficha
  `docs/metodologias/recuperacion-lexica.md` documenta algoritmo, IDF,
  desempates, seguridad, atomicidad, recursos y limitaciones. Verificación: 58
  pruebas focales, 320 rápidas y 18/18 de caracterización en verde.
- **2026-09-29** C.1: `rag/banco_evaluacion.py` define el manifiesto y los
  casos versionados con validación semántica, hash del corpus, IDs únicos,
  separación `dev`/`test` y evidencias literales con offsets. El banco
  `aqualis_sintetico@1.0.0` contiene 12 casos: un caso por split para cada una
  de las seis categorías. `data/golden/` solo contiene las reglas para curar
  posteriormente 30–50 preguntas reales; no se inventaron datos para llenarlo.
  Verificación: 6 pruebas específicas, 18 relacionadas, 326 rápidas y 18/18
  de caracterización en verde.
- **2026-09-29** C.2: `rag/metricas_banco.py` calcula Recall@k, MRR, falsos
  `ok`, precisión de abstención, exactitud de estado/literalidad/offsets,
  longitud excesiva y latencias globales y por etapa, con desgloses por backend
  y categoría. `rag evaluar --banco ... --salida ...` ejecuta la configuración
  activa y devuelve código no cero cuando la tasa de falsos `ok` supera cero.
  El corte real sobre SQLite formó parte de las pruebas de la comparación
  inicial y fue retirado con el backend. Verificación histórica: 13 pruebas
  C.1–C.2, 332 rápidas y 18/18 de caracterización en verde.
- **2026-09-29** C.3: `rag benchmark` creó un proyecto temporal, cargó una sola
  copia del corpus y evaluó SQLite, Qdrant denso e híbrido contra el mismo
  banco. Cada artefacto conserva el hash del banco completo, configuración,
  índice, señal de confianza, calibración exclusiva de `dev`, métricas y
  observaciones; `rag comparar` comprueba identidad de dataset y `k`. El informe
  deja `decisiones: []`. La línea base muestra el falso `ok` léxico descrito
  arriba, por lo que no se cambian defaults ni umbrales. Artefactos en
  `data/reportes/aqualis_sintetico_v1/`. Verificación: 18 pruebas focales,
  337 rápidas y 18/18 de caracterización en verde.
- **2026-09-30** Decisión posterior a C.3: SQLite FTS5 se descarta por su falso
  `ok` bloqueante ante «¿Cuánto dura?». Se eliminan implementación, registro,
  configuración, pruebas, CI, artefacto y documentación operativa. El benchmark
  activo compara únicamente Qdrant vectorial e híbrido. El dato histórico se
  mantiene en esta bitácora; no se presenta SQLite como opción disponible.
  Verificación posterior a la retirada: 56 pruebas focales, 301 rápidas y
  18/18 de caracterización en verde.
- **2026-09-30** D.1–D.2: `rag servir <carpeta>` distingue proyectos de carpetas
  documentales, crea `.rag-extractivo/`, completa recursos faltantes sin pisar
  personalizaciones, cataloga, indexa solo si hace falta y restaura el directorio
  al apagar. `--reindexar` fuerza reconstrucción. Las versiones modificadas de
  un archivo conservan la copia anterior. `/health` permanece vivo si el motor
  falla y `/ready` expone el fallo mediante 503.
- **2026-09-30** D.3–D.5: se añaden cuatro presets reproducibles y los comandos
  `rag widget tema listar|aplicar|vista-previa`. El mockup autónomo muestra los
  cuatro estados y citas. `/config` publica solo opciones de presentación y el
  widget consume densidad, citas en acordeón/abiertas/ocultas y visibilidad de
  etiquetas sin insertar HTML. `rag doctor` valida también estas opciones.
  Verificación D.1–D.5: 66 pruebas focales, 317 rápidas y 18/18 de
  caracterización en verde.
- **2026-09-30** D.6: el host pasa a ser `<rag-extractivo-chat>` sin romper el
  script de integración anterior. Atributos: `api`, `widget-key`, `color`,
  `titulo`, `saludo` y `posicion`. Eventos: `rag:abierto`, `rag:cerrado`,
  `rag:pregunta`, `rag:respuesta` y `rag:error`. `rag widget exportar` copia el
  cliente y genera un snippet con valores escapados. Verificación D.1–D.6:
  320 pruebas rápidas y 18/18 de caracterización en verde.
