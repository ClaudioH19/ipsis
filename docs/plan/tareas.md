# Tareas del plan V3

Lee primero [README.md](README.md) (reglas de ejecución) y
[arquitectura.md](arquitectura.md). Cada tarea dice qué leer, qué hacer y
cómo comprobar que terminó.

**Convenciones**

- `PYTEST` = `$env:HF_HUB_OFFLINE="1"; .venv\Scripts\python.exe -m pytest -m "not slow and not modelos" -q -p no:cacheprovider`
- `PYTEST_LENTO` = lo mismo sin el filtro `-m`. Úsalo solo cuando la tarea lo pida.
- «Mover» = `git mv` y actualizar **todos** los imports en el mismo cambio (`graphify query "<módulo>"` o `rg "rag\.viejo"`), sin módulos puente.
- Si una prueba antigua prueba algo que la tarea elimina a propósito, bórrala o reescríbela, y anótalo en [avance.md](avance.md).
- Tras cada fase: `graphify update .`.

---

## P0. Preparación

### P0.1 Commit del trabajo pendiente ⚠ requiere autorización del usuario

- **Pasos:**
  1. Ejecuta `PYTEST` y confirma que está en verde (línea base: 323).
  2. Pide autorización al usuario. Sin ella, detente aquí.
  3. Haz commits por tema: motor y abstención (A.2–A.7), evaluación (C.1–C.3), retiro de SQLite, web (D.1–D.7) y plan V3.
- **Aceptación:** `git status --short` solo muestra archivos ignorados.

### P0.2 Eliminar archivos obsoletos ⚠ el usuario aprueba la lista antes de borrar

- **Antes de borrar:** copia la tabla «Línea base C.3» de `docs/avance.md` a la sección «Historia» de `CHANGELOG.md` (es el único dato histórico que vale la pena conservar).
- **Eliminar:**

  | Archivo o carpeta | Motivo |
  |---|---|
  | `PLAN_V2.md`, `docs/ruta.md`, `docs/avance.md`, `docs/arquitectura.md` | Los reemplaza `docs/plan/` |
  | `requirements.txt`, `requirements-eval.txt` | Desactualizados; la fuente es `pyproject.toml` |
  | `rag/evaluacion.py`, `rag/metricas.py`, `tests/test_evaluador_factual_adversarial.py` | Evaluador del golden antiguo; nada vigente los usa |
  | `data/reportes/` | Artefactos de la comparación con SQLite; el resumen queda en `CHANGELOG.md` |
  | `build/`, `rag_extractivo.egg-info/`, `.cache/*` excepto `qdrant_local/`, `tests/__pycache__/` | Regenerables |

- **Actualizar referencias:**
  - `.dockerignore` y los comentarios de `docker-compose.yml:16` y `rag/servicio/seguridad.py:62`.
  - Docstrings de `rag/cli.py:11` y `rag/servicio/pipeline.py:863`.
  - `rag/diagnostico.py::verificar_golden_set`.
  - Enlaces en `README.md`, `docs/referencia/*`, `docs/metodologias/*` y `CHANGELOG.md`.
- **Aceptación:** `rg -l "PLAN_V2|docs/ruta|docs/avance|requirements(-eval)?\.txt|rag\.evaluacion\b|rag\.metricas\b"` solo devuelve `docs/plan/` o `CHANGELOG.md`. `PYTEST` en verde.

### P0.3 Configuración de pytest en `pyproject.toml`

- **Pasos:** mueve `pytest.ini` a `[tool.pytest.ini_options]` con `addopts = "--import-mode=importlib"`, los marcadores `slow` («más de 5 s») y `modelos` («necesita modelos ONNX en caché»), y borra `pytest.ini`. En `tests/conftest.py`, omite las pruebas `modelos` si el modelo no está en la caché, con un mensaje que diga `rag modelos descargar`.
- **Aceptación:** `PYTEST` en verde con el mismo número de pruebas.

---

## P1. Reorganizar `rag/` y retirar legado

No cambia el comportamiento. Al final de P1, la caracterización (lenta) sigue 18/18.

### P1.1 `rag/nucleo` y raíz de composición

- **Pasos:**
  1. Mueve `rag/esquemas.py` → `rag/nucleo/esquemas.py`.
  2. Divide `rag/componentes.py`: los `Protocol` van a `rag/nucleo/contratos.py`; `RegistroComponentes` y el registro global, a `rag/nucleo/registro.py`.
  3. Mueve `rag/registro.py` → `rag/aplicacion/registro_base.py`.
- **Aceptación:** `PYTEST` en verde. Importar `rag.nucleo.contratos` no carga `qdrant_client`, `onnxruntime` ni `torch` (comprobado con `sys.modules` en una prueba).

### P1.2 `rag/configuracion`

- **Pasos:** mueve `rag/esquemas_configuracion.py` → `rag/configuracion/esquemas.py` y `rag/configuracion.py` → `rag/configuracion/carga.py`. Haz el `git mv` del archivo antes de crear la carpeta.
- **Aceptación:** `PYTEST` en verde.

### P1.3 `rag/lenguaje`

- **Pasos:** mueve `rag/reglas_extraccion.py` → `rag/lenguaje/entidades.py`, `rag/texto_util.py` → `rag/lenguaje/texto.py` y `rag/dominio.py` → `rag/lenguaje/dominio.py`.
- **Aceptación:** `PYTEST` en verde.

### P1.4 Borrar legado del pipeline y del motor

- **Borrar:**
  - En `rag/servicio/pipeline.py`, los duplicados de `rag/abstencion.py`: `SenalesAbstencion`, `decidir_abstencion`, `ResultadoPremisa`, `verificar_premisa`, `separar_entidades_ausentes`, `tiene_grounding_lexico`, `tiene_grounding_dominio`, `DecisionAbstencion` y `decidir_capas_abstencion`. Las pruebas pasan a `rag.abstencion` o se borran si repiten `tests/test_abstencion.py`.
  - `PlanDeRespuesta`, `elegir_plan`, `extraer_slots`, el tipo `Plan` y la sección `planes:` de los dos `textos.yaml`.
  - En `rag/servicio/motor.py`: `EjecutorLegacy`, `desde_ejecutor_legacy`, `_adaptar_legacy`, `_ejecutor_legacy` y su prueba.
- **Mover:** `calibrar_umbral` y `ResultadoCalibracion` → `rag/evaluacion/calibracion.py`.
- **Aceptación:** `rg "desde_ejecutor_legacy|elegir_plan|decidir_capas_abstencion" rag tests` no devuelve nada. `PYTEST` en verde.

### P1.5 Desarmar `rag/servicio/pipeline.py`

- **Mover sin cambiar la lógica:**

  | Desde | Hacia |
  |---|---|
  | Conversacional (`detectar_conversacional`, `respuesta_conversacional`, `_patrones_…`) | `rag/consulta/etapas/conversacional.py` |
  | `NivelServicio`, `ConfiguracionAdmision`, `ControlAdmision` | `rag/consulta/admision.py` |
  | Redacción (`cargar_plantillas`, `_elegir_variante`, `_fragmentos_para_el_texto`, `_formatear_cita`, `_ensamblar_…`, `redactar`, `redactar_zona_gris`, `construir_mensaje_abstencion`) | `rag/consulta/etapas/redaccion.py` |
  | `ResultadoFidelidad`, `verificar_fidelidad`, `verificar_respaldo_dato_solicitado` | `rag/consulta/etapas/verificacion.py` |
  | `rag/servicio/motor.py` | `rag/consulta/motor.py` |
  | `rag/abstencion.py` | `rag/consulta/etapas/politica.py` |
  | `rag/recuperacion_qdrant.py` | `rag/consulta/etapas/recuperacion.py` |
  | `rag/seleccion_fragmento.py` | `rag/consulta/etapas/seleccion.py` |

  Borra `rag/servicio/pipeline.py`.
- **Aceptación:** `PYTEST` en verde.

### P1.6 `rag/ingesta` y `rag/indice`

- **Pasos:**
  - Mueve `parsear.py`, `chunking.py` y `metadata.py` → `rag/ingesta/`.
  - Mueve `payload.py` → `rag/indice/payload.py` (es el formato persistido).
  - Divide `rag/corpus.py`:
    - catálogo (`cargar_catalogo`, `_slug`, `generar_doc_id`, `inferir_titulo`, `plantilla_catalogo_vacio`, `_append_entrada_catalogo`, `DocumentoCargado`, `agregar_documentos_al_catalogo`) → `rag/ingesta/catalogo.py`;
    - orquestación (`parsear_corpus`, `construir_chunks_y_payloads`, `validar_payloads`, `ResumenDocumento`, `ResumenIngesta`, `ejecutar_ingesta`) → `rag/ingesta/ingesta.py`;
    - Qdrant, BM25, inventario y estadísticas, más todo `rag/indice.py` → `rag/indice/qdrant.py`.
  - Quita del docstring las referencias a `ingesta.indexar`, E1/E2/E3 y «molde».
- **Aceptación:** `PYTEST` en verde.

### P1.7 `evaluacion`, `servicio/widget` y `aplicacion/diagnostico`

- **Pasos:**
  - `banco_evaluacion.py` → `rag/evaluacion/banco.py`.
  - `metricas_banco.py` → `rag/evaluacion/metricas.py`.
  - `benchmark.py` → `rag/evaluacion/benchmark.py`, y `comparacion.py` se fusiona en `rag/evaluacion/benchmark.py`.
  - `temas_widget.py` + `exportar_widget.py` → `rag/servicio/widget.py`.
  - `diagnostico.py` → `rag/aplicacion/diagnostico.py`.
- **Aceptación:** en `rag/` solo quedan `__init__.py`, `cli.py` y carpetas. `PYTEST` en verde.

### P1.8 Prueba de arquitectura

- **Pasos:**
  1. Escribe un docstring de 2–4 líneas en cada `rag/<capa>/__init__.py` (responsabilidad y dependencias permitidas).
  2. Crea `tests/test_arquitectura.py`: recorre `rag/**/*.py` con `ast`, calcula la capa de cada import `rag.*` y falla si viola el orden de [arquitectura.md](arquitectura.md) §1.2. También verifica que `nucleo`, `configuracion` y `lenguaje` no importen `onnxruntime`, `qdrant_client` ni `fastapi` a nivel de módulo.
- **Aceptación:** la prueba pasa. Un import prohibido agregado a mano la hace fallar; compruébalo y revierte.

### P1.9 Cierre de P1

- **Aceptación:**
  - `PYTEST_LENTO -k caracterizacion` 18/18.
  - El wheel (`python -m pip wheel . --no-deps -w $env:TEMP\w`) contiene `rag/recursos/**` y `rag/servicio/estaticos/*`.
  - `graphify update .` ejecutado.

---

## P2. Repositorio y proyecto mínimos

### P2.1 Pruebas espejo de `rag/`

- **Pasos:**
  - Mueve cada `tests/test_*.py` a `tests/<capa>/` según el módulo que prueba, y las pruebas punta a punta (`test_portabilidad`, `test_caracterizacion_consultar`, `test_widget_browser`, `test_ejemplos_web`) a `tests/integracion/`.
  - Mueve los datos: `tests/caracterizacion/corpus/` → `tests/datos/corpus/`; `tests/evaluacion/sintetico/` → `tests/datos/banco/`; `tests/caracterizacion/consultar_esperado.json` → `tests/datos/caracterizacion/light.json`.
  - Fusiona `test_contratos_v2`, `test_frontera_tipos` e `test_intercambio_componentes` en `tests/consulta/test_contratos.py` y `tests/consulta/test_intercambio.py`, sin perder casos (cuenta las pruebas antes y después).
  - Borra `tests/__init__.py`.
- **Aceptación:** mismo número de casos de prueba que antes (salvo duplicados exactos, listados en [avance.md](avance.md)). `PYTEST` en verde.

### P2.2 Sacar el proyecto de prueba de la raíz

- **Pasos:**
  1. En `tests/conftest.py`, crea la fixture `proyecto` (`tmp_path` + `rag init` + corpus de `tests/datos/corpus/`, con `monkeypatch.chdir`).
  2. Cambia las pruebas que leen `configuracion/…` o `documentos/…` desde la raíz (`test_metadata`, `test_estilos`, `test_cli`, `test_diagnostico`, `test_seguridad` y `test_api_seguridad`) para que usen esa fixture.
  3. Borra `configuracion/` y `documentos/` de la raíz.
  4. El `Dockerfile` deja de copiar `configuracion/`: la configuración llega como volumen o desde `rag desplegar preparar`.
  5. En CI, cambia las comprobaciones `test -f configuracion/…` por un `rag init` en una carpeta temporal.
- **Aceptación:** `PYTEST` en verde, y la raíz ya no tiene `configuracion/` ni `documentos/`.

### P2.3 Estructura del proyecto del cliente

- **Pasos:** implementa la estructura de [arquitectura.md](arquitectura.md) §1.5 en `rag init` y en la carga de configuración:
  - `configuracion/dominio.yaml` une `dominios/<n>/perfil.yaml` y `categorias.yaml`.
  - `golden/` reemplaza a `data/golden/`.
  - `.rag/indice/` reemplaza a `.cache/qdrant_local`, `.cache/vocab_bm25`, etc.
  - La caché de modelos es global (`RAG_MODELOS_DIR`).
  - `config_version: 3`, con una migración idempotente en `rag/configuracion/migraciones.py` que mueve los archivos de un proyecto v2 y avisa de lo que hizo.
- **Aceptación:** prueba de migración que parte de un proyecto v2 (fixture con la estructura antigua) y llega a v3, y una segunda ejecución no cambia nada. `PYTEST` en verde.

### P2.4 Documentación y ejemplos mínimos

- **Pasos:**
  - Crea `docs/README.md` (índice + mapa de carpetas del repositorio, una línea por carpeta).
  - Mueve `docs/metodologias/` → `docs/metodologia/` y `docs/referencia/configuracion.md` → `docs/guia/configuracion.md`.
  - Mueve `docs/referencia/instalacion-web.md` → `docs/guia/web.md`.
  - Lleva el contenido de `data/golden/README.md` a `docs/guia/golden.md` y borra `data/`.
  - Fusiona `ejemplos/react/README.md` y `ejemplos/wordpress/README.md` en `ejemplos/README.md` (una sección por ejemplo).
  - Mueve `docker-compose.yml` a `rag/recursos/despliegue/docker-compose.yml.plantilla`.
- **Aceptación:**
  - En la raíz solo quedan `README.md`, `CHANGELOG.md`, `pyproject.toml`, `Dockerfile`, `.gitignore`, `.gitattributes`, `.dockerignore`, `.github/`, `rag/`, `tests/`, `ejemplos/` y `docs/`.
  - `tests/integracion/test_ejemplos_web.py` en verde.

---

## P3. Multilenguaje

Referencia: [lexico-y-multilenguaje.md](lexico-y-multilenguaje.md) §6. Al terminar P3 no quedan en Python reglas, patrones ni textos para el usuario final atados a un idioma. Los mensajes para quien opera (CLI, `rag doctor`, errores de configuración) siguen en español. Quedan pendientes, con su tarea: el tokenizador de BM25 (P4.3), `STOPWORDS_ES` de `palabras_contenido` (P4.4/P4.5) y la guardia regex (P8.3).

### P3.1 Paquetes de idioma

- **Pasos:**
  - Crea `rag/lenguaje/paquete.py`: `PaqueteIdioma` (Pydantic, esquema §6), `idiomas_disponibles()` y `cargar_paquete(codigo, proyecto=None)`, que fusiona `configuracion/idioma.yaml` si existe.
  - Crea `rag/recursos/idiomas/es.yaml` migrando los datos de `textos.yaml` y de los marcadores, **sin** palabras generales (las reemplaza el IDF).
  - `rag init --idioma` valida contra `idiomas_disponibles()`.
  - Borra `escribir_idioma_es_si_falta`, `cargar_palabras_generales` y `rag/recursos/plantillas/dominios/idiomas/`.
  - Agrega `rag/recursos/idiomas/*.yaml` al `package-data`.
- **Aceptación:** `tests/lenguaje/test_paquete.py` (carga, código inexistente con mensaje claro, sobrescritura parcial). `PYTEST` en verde.

### P3.2 `terminos()` y `dividir_oraciones()`

- **Pasos:**
  - En `rag/lenguaje/texto.py`:
    - `tokenizar(texto)`: `\w+` Unicode + `casefold`.
    - `normalizar(token)`: quita tildes solo si todos los caracteres son latinos.
    - `terminos(texto, paquete)`: tokeniza, normaliza y aplica el stem de `snowballstemmer` según `paquete.stemmer`, con caché del stemmer por idioma.
    - `dividir_oraciones(texto) -> list[tuple[ini, fin]]` con los delimitadores de §6 #9.
  - `chunking.py` y `seleccion.py` usan `dividir_oraciones`; borra sus regex propias.
  - Agrega `snowballstemmer` a las dependencias.
- **Aceptación:** pruebas parametrizadas en es, en, pt, ru y ja: los offsets son exactos, «documentos» y «documento» comparten término en español, y un idioma sin stemmer funciona. `PYTEST` en verde.

### P3.3 Entidades universales

- **Pasos:** en `rag/lenguaje/entidades.py`, conserva `decimal` y `porcentaje`, y agrega `fecha_numerica` (`dd/mm/aaaa`, `dd-mm-aaaa` y `aaaa-mm-dd` → `aaaa-mm-dd`) y `monto` (`$ € £ ¥ R$` o código ISO de 3 letras junto a un número → `monto_<n>`).
- **Aceptación:** pruebas con la invariante de offsets. `PYTEST` en verde.

### P3.4 Entidades y marcadores desde el paquete

- **Pasos:**
  - Las regex de plazos, fechas con nombre, referencias a documentos y marcadores se compilan desde el paquete, con caché por idioma. Borra `NUMEROS_TEXTO`, `MESES`, `ORDINALES`, `_DIAS_SEMANA` y `_UNIDADES_PLAZO`.
  - `valor_norm` independiente del idioma: `30_dia` y `aaaa-mm-dd`/`dd-mm` con el mes como número.
  - La firma pasa a `extraer_entidades(texto, paquete=None)`.
- **Aceptación:** las pruebas existentes de entidades pasan con `es`, ajustando solo los `valor_norm` de fechas. Nota en `CHANGELOG.md`: **requiere reindexar**. `PYTEST` en verde.

### P3.5 Conversación y mensajes desde el paquete

- **Pasos:** las etapas `conversacional` y `redaccion` leen el paquete. Borra `configuracion/textos.yaml` y su plantilla, y `rag doctor` deja de exigirlo.
- **Aceptación:** `PYTEST` en verde. La caracterización (lenta) no cambia.

### P3.6 Textos del widget

- **Pasos:** `/config` agrega `interfaz` del paquete. `widget.js` la usa y conserva los textos actuales como respaldo.
- **Aceptación:** prueba de API. La prueba de navegador sigue en verde si Playwright está disponible.

### P3.7 Paquetes `en` y `pt`

- **Aceptación:** `rag/recursos/idiomas/en.yaml` y `pt.yaml` completos, con pruebas de entidades y conversación parametrizadas por idioma (al menos 3 casos por regla y por idioma). `PYTEST` en verde.

---

## P4. Capa léxica (BM25 y TF-IDF)

Referencia: [lexico-y-multilenguaje.md](lexico-y-multilenguaje.md) §2–§5.

### P4.1 `EstadisticasLexicas`

- **Pasos:** en `rag/indice/estadisticas.py`, `EstadisticasLexicas` (Pydantic: `n_chunks`, `largo_medio`, `df`, `superficie`, `stemmer`, `hash_corpus` y `version`) con `construir(chunks, paquete)`, `idf(termino)`, `guardar(ruta)` y `cargar(ruta)`. La escritura es atómica (temporal + `os.replace`).
- **Aceptación:** pruebas: IDF de la fórmula §3 con valores calculados a mano; ida y vuelta JSON; `superficie` guarda la forma más frecuente. `PYTEST` en verde.

### P4.2 Funciones BM25 y TF-IDF

- **Pasos:** en `rag/lenguaje/lexico.py` (puro, sin E/S): `bm25_doc(terminos_doc, est, k1, b) -> dict[id, valor]`, `id_termino(t)` (`zlib.crc32`), `bm25_puntaje(terminos_q, terminos_doc, est)`, `tfidf_vector(terminos, est)`, `coseno(a, b)` y `mmr(vectores, k, lambda_)`.
- **Aceptación:** pruebas con un corpus de 3 documentos y valores calculados a mano (incluye saturación de TF y normalización por largo). `PYTEST` en verde.

### P4.3 BM25 en Qdrant con IDF del servidor

- **Pasos:**
  - `rag/indice/qdrant.py` crea el vector disperso con `modifier: idf` e indexa `bm25_doc` de cada chunk. La consulta envía 1,0 por término único.
  - Borra `tokenizar_bm25`, `construir_vocabulario_bm25`, `texto_a_vector_sparse`, los archivos `vocab_bm25` y las funciones de inventario y estadísticas antiguas: el inventario de entidades queda en el manifiesto.
  - La indexación guarda `estadisticas.json`.
- **Aceptación:** prueba lenta: indexa `tests/datos/corpus`; «¿Cada cuánto se cambia el filtro de sedimentos?» recupera el chunk correcto en el top 1 solo con BM25. Nota en `CHANGELOG.md`: **requiere reindexar**.

### P4.4 Señales léxicas

- **Pasos:**
  - En `rag/lenguaje/lexico.py`: `terminos_foco(terminos_q, est, k=2)` (mayor IDF entre los que existen en el corpus), `s_oov`, `s_cov`, `s_foco(foco, terminos_oracion)`, `s_lex` y `acuerdo(ids_denso, ids_bm25)`.
  - Agrega `SenalesLexicas` a `nucleo/esquemas.py`.
  - Reemplaza `tiene_grounding_lexico` y `tiene_grounding_dominio` por `s_oov`.
- **Aceptación:** pruebas con el corpus sintético:
  - «¿Cuánto dura la garantía?»: el foco incluye el término de «garantía», y `s_foco` = 0 contra la oración del filtro de sedimentos y ≥ 0,5 contra la de la garantía (el foco también contiene «dura», que esa oración no repite; por eso el umbral por defecto es 0,5).
  - Una pregunta sobre asados da `s_oov` > 0,6.

  `PYTEST` en verde.

### P4.5 Selección de oración por `s_lex`

- **Pasos:** en light, la etapa de selección elige, dentro de cada candidato, el tramo contiguo de oraciones con mayor `s_lex` (tf-isf), en lugar de Jaccard. Borra el método Jaccard y la ruta densa de selección.
- **Aceptación:** pruebas de `tests/consulta/test_seleccion.py` adaptadas; la oración correcta queda elegida en los 4 casos de prueba. `PYTEST` en verde.

### P4.6 Palabras clave por TF-IDF

- **Pasos:** `metadata.extraer_keywords` usa el top TF-IDF de `terminos()` y devuelve la forma de superficie. La clasificación por categoría usa las palabras clave de `dominio.yaml` pasadas por `terminos()`.
- **Aceptación:** `PYTEST` en verde.

---

## P5. Modelos ONNX, índice y perfiles

### P5.1 Verificar los modelos (investigación, sin código)

- **Pasos:** completa [modelos-y-perfiles.md](modelos-y-perfiles.md) sin ⚠. Para cada modelo anota la URL de la ficha, la licencia exacta, los parámetros, los archivos ONNX (y si hay int8) y la longitud máxima.
- **Aceptación:** la tabla queda verificada. Si un default no cumple, propone el reemplazo en [avance.md](avance.md) y **detente para que el usuario decida**.

### P5.2 Catálogo y descarga

- **Pasos:** `rag/modelos/catalogo.py` (`ModeloSpec` y `CATALOGO`) y `rag/modelos/descarga.py` (`ruta_cache`, `descargar` con `snapshot_download(allow_patterns=…)`, `esta_en_cache`, respetando `HF_HUB_OFFLINE`). Agrega `huggingface-hub` a las dependencias.
- **Aceptación:** pruebas con la descarga simulada. `PYTEST` en verde.

### P5.3 `ModeloOnnx` y codificador denso

- **Pasos:** `rag/modelos/onnx.py::ModeloOnnx` y `rag/modelos/denso.py::CodificadorDenso` (prefijos del spec, pooling promedio con la máscara de atención y L2). Regístralo como `dense_encoder: onnx`. Agrega `onnxruntime` y `tokenizers`.
- **Aceptación:** prueba `modelos`: e5-small produce 384 dimensiones con norma 1 ± 1e-3, y el coseno entre dos frases parafraseadas supera al de dos frases no relacionadas. `PYTEST` en verde.

### P5.4 Índice con el codificador nuevo y manifiesto

- **Pasos:**
  - La indexación usa `CodificadorDenso` con el prefijo `passage: `, lo que corrige el defecto del prefijo E5.
  - `rag/indice/manifiesto.py` escribe `.rag/indice/manifiesto.json` (modelo denso, idioma, stemmer, hash del corpus, versión del payload, inventario de entidades y fecha), y `es_compatible(manifiesto, perfil)`.
- **Aceptación:** prueba lenta de indexación y recuperación (3 preguntas) y pruebas de `es_compatible`.

### P5.5 Retirar torch y sentence-transformers

- **Pasos:**
  - Borra `DenseEncoderSentenceTransformers`, la caché LRU basada en sentence-transformers y todo import de `sentence_transformers`.
  - Saca el paquete de `pyproject.toml`, y quita torch del `Dockerfile` y de la CI.
  - Crea el extra `[exportar]` (`optimum[onnxruntime]`, `torch`).
- **Aceptación:**
  - En un venv nuevo, tras `pip install .`, `import torch` falla y `rag init → indexar → preguntar` funciona.
  - Caracterización lenta: las diferencias (por E5 y BM25) quedan explicadas en [avance.md](avance.md) y el archivo esperado de `light` se actualiza deliberadamente.

### P5.6 Perfiles

- **Pasos:**
  - Crea `rag/recursos/perfiles/{light,medium,heavy,bm25}.yaml`.
  - `rag/configuracion/perfiles.py`: carga y fusión perfil ← `motor.yaml` ← `calibracion.yaml`, esta última solo si su procedencia coincide.
  - `asistente.yaml` gana el campo `perfil`. La migración v2 → v3 asigna `light`.
  - `rag init --perfil` usa `medium` por defecto.
- **Aceptación:** pruebas de fusión y de rechazo de una calibración con otra procedencia. `PYTEST` en verde.

---

## P6. Motor por etapas

### P6.1 `ContextoConsulta` y etapas, sin cambiar el comportamiento

- **Pasos:**
  - Crea `rag/consulta/contexto.py` y el protocolo `Etapa`.
  - Convierte cada bloque de `Motor._consultar_en_contexto` en una clase de `consulta/etapas/`.
  - `Motor.consultar` recorre `self.etapas`, mide `diagnostico["etapas"][f"{nombre}_ms"]` y se detiene cuando hay `ctx.resultado`. La admisión envuelve el recorrido.
- **Aceptación:** pruebas del motor sin cambios en verde. Caracterización igual a la salida de P5.5.

### P6.2 Etapas desde el perfil y salida temprana

- **Pasos:**
  - Registra las etapas (tipo `etapa`). `Motor.desde_configuracion` arma la lista desde `perfil.etapas` y falla al arrancar si falta una etapa o una dependencia, con un mensaje accionable.
  - La etapa `filtros` calcula `SenalesLexicas` y, con `salida_temprana_sin_foco`, marca `ctx.saltar_modelos`. `reranking` y `lectura` respetan esa marca.
- **Aceptación:** pruebas: perfil con una etapa inexistente → error; pregunta sin términos foco en los candidatos → el reranker falso no se llama. `PYTEST` en verde.

### P6.3 Diagnóstico ampliado

- **Pasos:** nueva versión de `QueryDiagnostic` con `perfil`, `senales_lexicas` (foco, encontrados, ausentes, con su IDF), `puntajes_rerank`, `lecturas`, `regla` y `salto_modelos`.
- **Aceptación:** pruebas de esquema. `PYTEST` en verde.

---

## P7. Reranker, lector y proximidad

### P7.1 Reranker

- **Pasos:** `rag/modelos/reranker.py::RerankerOnnx(ModeloOnnx)` y la etapa `consulta/etapas/reranking.py`: ordena por logit, desempata por `chunk_id`, guarda `puntajes_rerank` y deja `rerank_k` candidatos.
- **Aceptación:** pruebas con un reranker falso; prueba `modelos`: el pasaje del filtro de sedimentos queda primero para su pregunta. `PYTEST` en verde.

### P7.2 Lector QA

- **Pasos:** `rag/modelos/lector.py::LectorOnnx(ModeloOnnx)`:
  1. Codifica el par con offsets, truncando solo el pasaje, en ventanas `max_tokens_pasaje` con `stride`.
  2. Busca el mejor (inicio ≤ fin, largo ≤ 30 tokens) solo dentro de tokens del pasaje.
  3. Puntaje nulo = `start[0] + end[0]`. Aplica softmax sobre {mejor tramo, nulo} y se queda con la mejor ventana.
  4. Mapea a offsets de carácter y verifica `pasaje[ini:fin] == texto`.
- **Aceptación:** pruebas con una sesión falsa (tramo correcto, nulo gana, varias ventanas, tramo inválido); prueba `modelos`: la pregunta del filtro de sedimentos devuelve un tramo que contiene «6 meses». `PYTEST` en verde.

### P7.3 Etapa de lectura

- **Pasos:** lee los `leer_m` primeros candidatos. La mejor lectura se convierte en `EvidenceSpan` global (`chunk.offset_inicio + ini`). La evidencia mostrada es la **oración que contiene el tramo**. El contrato HTTP gana `respuesta_exacta` (tramo + offsets), opcional.
- **Aceptación:** pruebas con un lector falso: offsets globales, oración contenedora y verificador literal. `PYTEST` en verde.

### P7.4 Proximidad del foco

- **Pasos:** la etapa de selección calcula `s_foco` y `s_cov` sobre la oración que contiene el tramo del lector (o la elegida en light) y los guarda en `ctx.lexicas`.
- **Aceptación:** prueba con un lector falso que devuelve «6 meses» del pasaje del filtro ante «¿Cuánto dura la garantía?» → `s_foco = 0`. `PYTEST` en verde.

### P7.5 Extras de `heavy`

- **Pasos:** recuperación dirigida por entidad (lógica actual de `_completar_premisa`) y **concordancia**: si los dos mejores tramos de pasajes distintos tienen entidades del mismo tipo con valores distintos, la decisión baja a `relacionado`.
- **Aceptación:** prueba con un lector falso y dos plazos distintos → `relacionado`. `PYTEST` en verde.

### P7.6 Latencia por perfil

- **Pasos:** `rag benchmark --solo-latencia --repeticiones 20` mide p50 y p95 por etapa sobre `tests/datos/corpus`. Ejecútalo en la máquina del usuario para los tres perfiles.
- **Aceptación:** tabla en [avance.md](avance.md). Si un perfil supera su presupuesto, ajusta `rerank_k`/`leer_m` o usa la alternativa de la tabla y mide otra vez. Si ni así cumple, **detente y repórtalo**.

---

## P8. Política en cascada

### P8.1 `cascada_v1`

- **Pasos:** `consulta/etapas/politica.py::CascadaV1` implementa [arquitectura.md](arquitectura.md) §2.1 y se registra como `abstention_policy: cascada_v1`. La decisión guarda la regla y las señales.
- **Aceptación:** pruebas por tabla: un caso por regla, uno por cada límite de umbral y uno por cada perfil (con y sin lector). `PYTEST` en verde.

### P8.2 Activar la cascada

- **Pasos:** los perfiles usan `cascada_v1`. Regenera deliberadamente `tests/datos/caracterizacion/{light,medium}.json` y documenta en [avance.md](avance.md) cada cambio de estado.
- **Aceptación:** con `medium` no hay falsos `ok`; «¿Cuánto dura?» y «¿Cuánto dura la garantía?» (sin el dato) no dan `ok`; con `light`, tampoco.

### P8.3 Retirar la guardia regex y `layered_v1`

- **Pasos:** borra `verificar_respaldo_dato_solicitado` y sus regex, `LayeredV1`, `decidir_capas` y sus claves de configuración, que se eliminan en la migración.
- **Aceptación:** `rg "_RE_SOLICITUD|layered_v1|verificar_respaldo|palabras_generales" rag tests` no devuelve nada. `PYTEST` en verde.

### P8.4 Banco con casos trampa

- **Pasos:** crea `tests/datos/banco` v1.1.0 con casos «mismo tema, dato ausente» en español e inglés (garantía vs. filtro, dónde comprar repuestos, quién autoriza el reembolso, cuándo vence la garantía y si sirve para agua de pozo), con al menos 30% sin respuesta.
- **Aceptación:** `rag evaluar` con `medium` y con `light` da 0 falsos `ok`. Anota la cobertura de `ok` de cada perfil en [avance.md](avance.md).

### P8.5 Presentación de la evidencia

- **Pasos:**
  - La ventana de `seleccionar_texto_pertinente` pone la oración ancla
    **primero** y agrega contexto solo a la derecha. La ancla es la misma que
    usa `oracion_ancla` para `s_foco`.
  - El lector QA usa una ventana centrada (`centrada=True`): lee mejor con el
    contexto previo, y su ventana no se muestra.
  - Prueba que en `relacionado` el contrato HTTP no trae `respuesta_exacta` y
    el texto lleva el encabezado de no-respuesta.
- **Aceptación:**
  - Con light, «¿En cuántos días hábiles se paga el reembolso?» empieza por la
    oración del Artículo 8.
  - Caracterización regenerada y diferencias documentadas.
  - `PYTEST` en verde.

### P8.6 Conservar las paráfrasis difíciles

- **Pasos:** `test_portabilidad` mantiene dos casos:
  - el literal («¿Cuántos meses cubre…?» → `ok`);
  - la paráfrasis («¿Cuánto dura la garantía del equipo X100?» → hoy
    `relacionado`), cuyos fragmentos deben seguir conteniendo «18 meses».
- **Aceptación:** si una regresión hace que la paráfrasis pierda la evidencia,
  la suite falla. `PYTEST` en verde.

---

## P9. Golden set estándar

Referencia: [comandos-y-golden.md](comandos-y-golden.md) §3.

### P9.1 Lectura e importación

- **Pasos:** en `rag/evaluacion/golden.py`: `FilaGolden`, `leer_csv` (`utf-8-sig`), `leer_jsonl`, `leer_squad2`, `ubicar_respuesta` (exacta y luego con espacios colapsados, con mapeo a los offsets originales), `separar_dev_test` y `a_banco`. La categoría `exacta`/`parafrasis` se decide con `s_cov`. Acepta la columna opcional `subtipo` (`trampa_mismo_tema`) y `par` (id de la fila respondible con la que forma un par mínimo); ambas son metadata de evaluación. SQuAD 2.0 se acepta como formato de intercambio, no como datos de entrenamiento.
- **Aceptación:** pruebas de offsets, texto ausente o repetido, separación estable al reimportar y avisos de tamaño y balance. `PYTEST` en verde.

### P9.2 Plantilla para el cliente

- **Pasos:** `generar_plantilla(corpus, paquete, n=40)` usa MMR sobre TF-IDF (calculado sobre las secciones) para elegir secciones diversas, llena `terminos_clave`, agrega 35% de filas trampa como **pares mínimos** (`subtipo: trampa_mismo_tema`, `par` = fila respondible de la misma sección) y 3 conversacionales, y escribe `LEEME.txt`. Agrega `golden_instrucciones` a los paquetes es, en y pt.
- **Aceptación:** prueba: con `n=20` aparecen todos los documentos, alrededor de 35% de filas son trampa, cada trampa tiene `par` y el CSV se puede releer con `leer_csv`.

### P9.3 Comandos `rag golden`

- **Aceptación:** prueba de ida y vuelta: plantilla → completar 2 filas → importar → exportar squad2 → importar squad2 → mismo **contenido QA** (ver [comandos-y-golden.md](comandos-y-golden.md) «SQuAD 2.0: qué se conserva»; las conversacionales no pasan por SQuAD). Por CSV, mismo banco.

### P9.4 Banco universal de regresión (solo CI)

- **Pasos:**
  - Crea `tests/datos/banco_universal/` con microdocumentos ficticios propios
    de dominios variados (garantía, reembolsos, manual técnico, riego,
    horarios, logística, protocolo de laboratorio, reglamento, ficha de
    maquinaria, precios) en es, en y pt.
  - Unos 90 casos: 30 por idioma. Por idioma: 10 literales, 5 paráfrasis,
    10 «mismo tema, dato ausente» en pares mínimos, 3 fuera de dominio y 2
    ambiguas o con premisa falsa.
  - Un banco por idioma (`es/`, `en/`, `pt/`): el formato tiene un corpus por
    manifiesto. Fuentes editables (`corpus/*.md`, `casos.yaml`) y derivados
    (`banco.jsonl`, `manifiesto.json`) que genera `construir.py`. La categoría
    la fija el autor (no `s_cov`).
  - El manifiesto declara `uso: regresion`; `exigir_calibrable` lo rechaza
    (P10 lo llama antes de calibrar).
  - Un proyecto por idioma (sin cruce de idiomas).
  - **Nunca se usa para entrenar ni para calibrar**: detecta optimizaciones
    que solo funcionan con el corpus de `tests/datos/corpus`.
- **Aceptación:**
  - `rag evaluar` con light y medium en cada idioma: falsos `ok` y cobertura
    por categoría anotados en [avance.md](avance.md).
  - Prueba lenta (`modelos`) que falla si aparece un falso `ok` **nuevo**
    respecto de `linea_base.json`. P9.4 mide el estado actual y no corrige:
    los falsos `ok` de hoy quedan registrados para P10.

---

## P10. Evaluación, calibración y benchmark

### P10.1 Señales y cota de riesgo en las métricas

- **Pasos:**
  - Las observaciones guardan todas las señales de la política (`SenalesObservadas`, tal como decidió; `None` si no aplica), la regla, el idioma y el tramo del lector.
  - Implementa `cota_superior_clopper_pearson(x, n, confianza)` con la CDF
    binomial y bisección, y `n_minimo(errores, alfa, confianza)`.
  - El reporte agrega, en global y **por categoría** (exacta, parafrasis,
    trampa_mismo_tema, sin_respuesta, premisa_falsa, ambigua):
    - `tasa_falsos_ok`, `cobertura_directa` (respondibles con `ok`) y
      `cobertura_relacionada`;
    - `recall_sin_respuesta`, `coincidencia_tramo_exacto` y literalidad;
    - p50 y p95.
- **Aceptación:**
  - `x=0, n=50` → 0,0582 ± 0,001; `x=0, n=59` → 0,0495 ± 0,001;
    `n_minimo(0, 0.05, 0.95) == 59`.
  - Un segundo valor coincide con una tabla de referencia (anota la fuente).
  - `PYTEST` en verde.

### P10.2 Calibración

- **Pasos:**
  - `rag/evaluacion/calibracion.py::calibrar(observaciones, alfa)` según
    [comandos-y-golden.md](comandos-y-golden.md) §4. Devuelve
    `CALIBRADO`, `MUESTRA_INSUFICIENTE` o `SIN_UMBRAL_SEGURO`.
  - Agrega `escribir_calibracion` y `cargar_calibracion`, que validan la
    procedencia.
  - Separa el umbral `oov` en `oov_dominio` (regla 2) y `oov_ok` (regla 3) en
    `cascada_v1`, en los perfiles y en la migración.
  - Borra `calibrar_umbral`.
  - Solo selecciona umbrales escalares entre valores observados: sin pesos,
    sin cambiar modelos ni índices.
- **Aceptación:**
  - Pruebas: elige el umbral más bajo que cumple; devuelve
    `SIN_UMBRAL_SEGURO` (y `τ_ok = 1,01`) si ninguno cumple con muestra
    suficiente; devuelve `MUESTRA_INSUFICIENTE` y no aplica nada si n < `n_minimo`;
    rechaza otra procedencia.
  - Con el banco v1.1.0, se anota en [avance.md](avance.md) si separar
    `oov_ok` mejora la cobertura de paráfrasis sin falsos `ok`.
  - `PYTEST` en verde.

### P10.3 `rag calibrar`

- **Aceptación:** prueba de CLI con un motor falso; prueba lenta con `medium` sobre el banco v1.1.0.

### P10.4 Benchmark por perfiles

- **Pasos:** `rag benchmark --perfiles bm25,light,medium,heavy` ejecuta cada perfil sobre el mismo banco y reporta métricas, p50/p95 por etapa y cumplimiento del presupuesto. Termina con código ≠ 0 si alguno lo incumple o, con un banco de evaluación del cliente, da falsos `ok` (la guardia de `rag evaluar`, que exige 0). Un banco de regresión no tiene límite propio de falsos `ok`: lo vigila su línea base. Las variantes experimentales (`--experimentos`) nunca cortan.
- **Aceptación:** reporte JSON + Markdown en `golden/reportes/`, con la tabla copiada a [avance.md](avance.md). El reporte muestra juntas seguridad, cobertura, latencia y memoria/modelos por perfil: no se elige un perfil solo por precisión.

### P10.5 Experimento: chunking `texttiling_v1`

- **Pasos:** implementa el chunker de [lexico-y-multilenguaje.md](lexico-y-multilenguaje.md) §5 como opción, y compáralo con el actual con `rag benchmark` sobre el banco v1.1.0.
- **Aceptación:**
  - Se adopta solo si mejora la calidad, no empeora los falsos `ok` y
    mantiene el presupuesto de latencia.
  - La decisión queda en [avance.md](avance.md) con los números.
  - Si se descarta, borra el código.

---

## P11. CLI y operación

### P11.1 CLI con patrón Command

- **Pasos:** crea `rag/cli/base.py::Comando` y `rag/cli/comandos/<grupo>.py` (grupos de [comandos-y-golden.md](comandos-y-golden.md) §2). Pasa la lógica a `rag/aplicacion/*` y borra `rag/cli.py`. El script de entrada sigue siendo `rag.cli:main`.
- **Aceptación:** `tests/cli/` en verde, incluida «todas las opciones tienen ayuda». `tests/test_arquitectura.py` gana la regla «`cli` y `servicio` solo importan `aplicacion`, `nucleo` y `recursos`», y pasa.

### P11.2 `rag perfil mostrar|cambiar`

- **Aceptación:** pruebas: de light a medium no pide reindexar; de medium a heavy sí; siempre avisa que la calibración quedó obsoleta.

### P11.3 `rag modelos listar|descargar|verificar|exportar`

- **Aceptación:** pruebas con la descarga simulada. `exportar` sin el extra falla indicando el `pip install` correcto.

### P11.4 `rag doctor` ampliado

- **Pasos:** chequeos de perfil, modelos en caché, índice compatible (manifiesto), calibración vigente, paquete de idioma, golden con el hash de corpus vigente, y stemmer disponible para el idioma.
- **Aceptación:** una prueba sana y una con fallo por chequeo, y cada fallo sugiere un comando.

### P11.5 `rag preguntar --diagnostico`

- **Aceptación:** muestra etapas con latencia, señales, términos foco (encontrados y ausentes), regla y tramo exacto. Prueba con un motor falso.

### P11.6 Registro de consultas y `rag auditar`

- **Pasos:** registro JSONL opcional en `.rag/registros/consultas.jsonl` (apagado por defecto; [arquitectura.md](arquitectura.md) §4). `rag auditar` comprueba cada evidencia contra el corpus vigente y resume estados y reglas.
- **Aceptación:** pruebas: con el registro apagado no se escribe nada; una evidencia alterada a mano se reporta.

---

## P12. Personalidad, widget, avatar y despliegue

P12 agrega la capa de presentación: tonos de respuesta con varias formulaciones
por situación, un widget embebible y responsive, y un avatar animado que
reacciona a lo que pasa en el chat. Todo se configura primero por terminal,
después por API y al final con un panel gráfico que solo llama a esa API.
Cierra con el despliegue (imagen, `rag desplegar`, CI y `/ready`).

### Decisiones del usuario (resueltas el 2026-10-04)

- **D1. Licencia: AGPL-3.0 para todo el repositorio.**
  - El proyecto será público y libre en GitHub, así que se adopta la misma
    licencia que `@bible-strong/avatar-web` y `@bible-strong/avatar-core`
    0.1.0 (de
    [bible-strong-avatar-lab](https://github.com/smontlouis/bible-strong-avatar-lab)),
    que son AGPL-3.0-only.
  - Una licencia AGPL no se tramita: se aplica, agregando el texto
    `LICENSE` y los avisos (P12.8).
  - Consecuencia: quien ofrezca una versión **modificada** como servicio
    de red debe publicar sus cambios. Quien solo la instala en su VPS sin
    modificarla no tiene obligaciones nuevas.
- **D2. Avatar por defecto: «Folio», diseñado por el agente** (P12.10).
- **D3. Tono `directo`:** seco, imperativo y sin cortesías, pero nunca
  insulta, ni culpa al usuario, ni usa sarcasmo, mayúsculas sostenidas o
  amenazas.
- **D4. Self-hosted en un VPS:** el panel `/admin` se usa en remoto, con
  token y HTTPS obligatorio (P12.6). En el `docker-compose` va un proxy con
  TLS automático (P12.13).
- **Seguir el puntero:** la librería no lo trae, así que lo implementa el
  widget con mirada real (ver «Eventos del avatar»).

### Modos de ejecución: desarrollo y producción

El servicio corre en uno de dos modos, con `rag servir --modo` o
`RAG_MODO`. **Por defecto es `produccion`**: seguro sin configurar nada.

| Aspecto | `desarrollo` | `produccion` |
|---|---|---|
| `/admin` por HTTP plano | permitido desde cualquier IP, con aviso en consola, en el panel y en `rag doctor` | solo desde loopback; desde fuera exige HTTPS (403 si no) |
| Token de `/admin` | obligatorio; si falta `RAG_ADMIN_TOKEN`, `rag servir` genera uno temporal por ejecución y lo imprime | obligatorio; sin `RAG_ADMIN_TOKEN`, `/admin` no existe (404) |
| Encabezados del proxy (`X-Forwarded-*`) | se aceptan de loopback | solo del proxy en `RAG_PROXY_CONFIABLE` |
| `/docs` (OpenAPI) | habilitado | deshabilitado salvo `RAG_DOCS=1` |
| Estáticos (`widget.js`, `avatar.js`, panel) | `Cache-Control: no-store`; cambios visibles al recargar | caché larga con versión en la URL |
| Detalle de errores 500 | en la respuesta | solo en el log; la respuesta trae un id |
| `/widget/demo.html` | disponible | disponible solo con `RAG_DEMO=1` |
| `/health` y `/ready` | informan `modo: desarrollo` | informan `modo: produccion` |

En los dos modos se mantienen: CORS según `cors_origenes` (nunca `*`),
claves de widget, limitador de peticiones, registro de consultas apagado por
defecto e invariantes extractivos. El modo no cambia ninguna respuesta del
asistente.

`rag doctor` gana el chequeo `modo`:
- aviso si el servicio está configurado en `desarrollo`;
- error en `produccion` con `/admin` activo si `RAG_PROXY_CONFIABLE` no está
  definido y el host no es loopback. Acción: configurar el proxy o
  `--host 127.0.0.1`.

### Documentación de la fase

Cada tarea de P12 actualiza, en el mismo commit, las guías que tocan sus
comandos y opciones:
- `docs/guia/instalacion.md`: instalación, perfiles, modelos, VPS, HTTPS y
  modos;
- `docs/guia/uso.md`: ciclo de trabajo y referencia de todos los comandos;
- además, `configuracion.md`, `web.md` y `personalidad.md`.

Una prueba (`tests/test_documentacion.py`) recorre el árbol de comandos de
la CLI y falla si alguno no aparece en `docs/guia/uso.md`.

### Invariantes de toda la fase

1. **Extractivo.** Una plantilla solo enmarca: el texto del corpus va
   literal, en su propio bloque, y la verificación de fidelidad no cambia.
   Ninguna plantilla afirma algo del contenido.
2. **Citas siempre abajo.**
   - Toda respuesta con evidencias muestra, debajo del mensaje: documento,
     sección, offsets y el texto literal, con el tramo exacto resaltado.
   - Ninguna opción estética oculta las citas ni la etiqueta de estado.
3. **Estados honestos.** Las plantillas de `relacionado` y `sin_respuesta`
   nunca sugieren que hubo una respuesta directa.
4. **Presentación, no decisión.**
   - Tono, avatar y estilos no cambian el estado, la regla, las señales, los
     umbrales, el índice, la calibración ni el golden.
   - Por eso cambiar el tono no exige reindexar ni recalibrar.
   - `rag evaluar` da los mismos estados y la misma literalidad con
     cualquier tono.
5. **Auditable.**
   - La variante se elige de forma determinista: misma sesión, turno y
     situación dan la misma variante.
   - El `plantilla_id` (p. ej. `cordial.sin_respuesta.3`) queda en el
     diagnóstico y en el registro de consultas.
6. **Sin texto de un idioma en Python ni en JavaScript.**
   - Los tonos viven por idioma en `rag/recursos/tonos/<idioma>/`.
   - Un idioma con respaldo usa los de `en`.
7. **Seguridad web.**
   - Todo texto de la API se pinta con `textContent`, nunca con
     `innerHTML`.
   - La administración está apagada por defecto.
8. **Primero CLI, después API, al final interfaz gráfica.**

### Catálogo de situaciones

Cada tono tiene **5 variantes por situación**. Con 18 situaciones son 90 por
tono e idioma.

| # | Situación | Dónde | Variables permitidas | Regla propia |
|---|---|---|---|---|
| 1 | `saludo` | motor (conversacional) | `{nombre_asistente}`, `{descripcion_dominio}` | ofrece ayuda; no promete respuestas |
| 2 | `agradecimiento` | motor | `{descripcion_dominio}` | — |
| 3 | `despedida` | motor | — | — |
| 4 | `capacidad` | motor | `{nombre_asistente}`, `{descripcion_dominio}` | dice que cita el texto exacto del documento |
| 5 | `apertura` | motor, antes del texto literal | — | termina en «:»; no anticipa contenido |
| 6 | `complemento` | motor, entre fragmentos | — | termina en «:» |
| 7 | `condicion` | motor | — | termina en «:» |
| 8 | `excepcion` | motor | — | termina en «:» |
| 9 | `relacionado_intro` | motor, estado relacionado | — | dice que no es una respuesta directa; termina en «:» |
| 10 | `foco_ausente` | motor, relacionado | `{termino}` | ídem, y nombra `{termino}` |
| 11 | `sin_respuesta` | motor | — | dice que no está en los documentos; no sugiere fuentes externas |
| 12 | `premisa_no_encontrada` | motor | `{entidad}` | ídem, y nombra `{entidad}` |
| 13 | `bienvenida` | widget, al abrir | `{nombre_asistente}` | — |
| 14 | `esperando` | widget, mientras responde | — | breve |
| 15 | `invitacion_citas` | widget, sobre el bloque de citas | — | invita a comprobar la cita |
| 16 | `error_red` | widget | — | — |
| 17 | `error_limite` | widget (429) | — | pide esperar unos segundos |
| 18 | `error_servicio` | widget (503) | — | — |

Los conectores `secuencia` y `contraste_version`, los encabezados de cita y
las etiquetas de estado son estructurales: siguen siendo únicos por idioma y
no varían con el tono.

**Reglas para todas las plantillas** (las comprueba un linter en las
pruebas):
- forma: una línea, ≤ 200 caracteres;
- contenido prohibido: dígitos, URLs, HTML, Markdown y emojis;
- solo las variables permitidas de su situación;
- variedad: las 5 variantes son distintas entre sí tras normalizar y
  ninguna se repite en otra situación del mismo tono;
- en el tono `directo`, nada de la lista prohibida de D3.

### Tonos

| Tono | Carácter | Ejemplo para `sin_respuesta` |
|---|---|---|
| `cordial` (por defecto) | el actual: amable y claro | «No encontré esa información en los documentos disponibles.» |
| `formal` | «usted», sin exclamaciones | «Lamentablemente, esa información no figura en los documentos disponibles.» |
| `serio` | sobrio, frases cortas | «Esa información no está en los documentos.» |
| `animoso` | entusiasta, positivo sin exagerar hechos | «¡Busqué a fondo, pero eso no aparece en los documentos! Prueba con otra pregunta.» |
| `cercano` | tuteo, coloquial suave | «Uy, eso no lo encuentro en tus documentos.» |
| `empatico` | reconoce lo que el usuario necesita | «Entiendo que lo necesitas; no aparece en los documentos disponibles.» |
| `directo` | tajante, imperativo («agresivo» de D3) | «No está en los documentos. Pregunta otra cosa.» |

Son 7 tonos × 3 idiomas × 90 = 1.890 plantillas. Los ejemplos son
ilustrativos; los textos finales salen de P12.3.

### Eventos del avatar

El widget tiene una máquina de estados. Cada evento se asigna a una clave de
animación o de expresión del avatar; si el avatar no la define, rige la
columna «Si falta».

| Evento | Disparador | Tipo | Prioridad | Clave sugerida | Si falta |
|---|---|---|---|---|---|
| `inactivo` | panel abierto sin actividad | persistente (loop) | 0 | `inactivo` | expresión `neutral` |
| `lanzador` | panel cerrado (avatar en el botón, opcional) | persistente | 0 | `inactivo` | ícono actual |
| `saludo` | primera apertura de la sesión | transitorio (once) | 3 | `saludo` | `inactivo` |
| `atento` | foco en el campo de texto | persistente | 1 | `atento` | `inactivo` |
| `escribiendo` | tecleo, que se apaga 1,2 s después del último | persistente | 2 | `escuchando` | `atento` |
| `enviado` | se envía la pregunta | transitorio | 4 | `asentir` | `pensando` |
| `pensando` | esperando la respuesta | persistente | 3 | `pensando` | `inactivo` |
| `pensando_largo` | más de 3 s sin respuesta | persistente | 3 | `pensando-largo` | `pensando` |
| `respuesta_ok` | estado `ok` | transitorio | 5 | `contento` | `inactivo` |
| `respuesta_relacionada` | estado `relacionado` | transitorio | 5 | `dudoso` | `inactivo` |
| `sin_respuesta` | estado `sin_respuesta` | transitorio | 5 | `apenado` | `inactivo` |
| `conversacional` | estado `conversacional` (saludo o agradecimiento) | transitorio | 5 | `amable` | `contento` |
| `despedida` | respuesta de despedida o cierre del panel | transitorio | 3 | `despedida` | `inactivo` |
| `error` | error de red, 429 o 503 | transitorio | 6 | `preocupado` | `apenado` |
| `mirando_citas` | foco, paso del puntero o despliegue de una cita | transitorio | 4 | la celda de la grilla que apunta a la cita | — |
| `seguir_puntero` | el puntero se mueve (panel abierto; en táctil, el último toque o el campo con foco) | continuo | — | grilla de mirada generada por el widget (ver abajo) | la grilla solo necesita `neutral`: funciona con cualquier avatar |
| `somnoliento` | sin actividad por N minutos (2 por defecto) | persistente | 0 | `somnoliento` | `inactivo` |
| `despertar` | actividad después de `somnoliento` | transitorio | 2 | `despertar` | `atento` |
| `oculto` | la pestaña se oculta | sistema | — | `pause()` al ocultarse, reanuda al volver | — |
| `movimiento_reducido` | `prefers-reduced-motion` | sistema | — | expresión estática por estado; sin loops ni seguir el puntero | — |

Reglas de la máquina de estados:
- **Prioridad:** gana el evento de mayor prioridad.
- **Transitorios:**
  - vuelven al persistente vigente al terminar (`onAnimationEnd`) o tras
    un tope de 4 s;
  - se muestran al menos 600 ms;
  - mientras duran, se suspende el seguimiento del puntero.
- **Puntero:** el seguimiento usa `requestAnimationFrame`, a lo sumo 30
  veces por segundo, y solo escucha mientras el panel está abierto.
- **Una sola instancia:** un controlador por widget, y se destruye al
  desmontar.
- **Integración con el sitio:** cada cambio emite `rag:avatar`
  `{evento, clave}`.

**Seguir el puntero: lo implementa el widget.** La librería no lo trae,
pero cada expresión del avatar define el giro de la cabeza (`head.x/y/z`) y
la posición de cada ojo (`eyes.left/right.x/y`). Con eso hay mirada real:

1. **Grilla de mirada.** Al cargar la definición, y antes de
   `createAvatar`, el widget genera 15 expresiones `mirada-c<col>-f<fila>`
   (5 columnas × 3 filas) a partir de `neutral`:
   - los ojos se desplazan hasta `amplitud_ojos`;
   - la cabeza gira hasta `amplitud_cabeza` grados;
   - el resto de la expresión no cambia.

   No se modifica la librería ni el archivo del avatar: las expresiones se
   agregan a la copia en memoria. Respeta el límite de 128 expresiones.
2. **Del puntero a una celda.** El ángulo y la distancia del puntero
   respecto del centro del avatar eligen la celda:
   - con una zona muerta central y con histéresis, para que no tiemble;
   - a lo sumo 30 actualizaciones por segundo (`requestAnimationFrame`);
   - `setExpression` con la transición `smooth` del avatar.
3. **Vuelta al centro:** tras 1,5 s con el puntero quieto, o si sale de la
   ventana, mira al frente.
4. **Cuándo no sigue:**
   - durante un transitorio;
   - con `prefers-reduced-motion`;
   - con el panel cerrado, salvo que el avatar esté en el lanzador.
5. **En táctil:** mira hacia el último toque y, al escribir, hacia el
   campo de texto.
6. **Configuración:** `avatar.mirada` en `personalidad.yaml`:
   ```yaml
   mirada: {activa: true, amplitud_ojos: 6, amplitud_cabeza: 8, zona_muerta: 24}
   ```
   Si un avatar trae sus propias expresiones `mirada-*`, se usan las suyas.

### P12.1 Contrato de tonos

- **Pasos:**
  1. `rag/lenguaje/tonos.py`:
     - `cargar_tono(idioma, tono, proyecto)`: `rag/recursos/tonos/<idioma>/<tono>.yaml`
       con las sobrescrituras de `configuracion/personalidad.yaml::tono.plantillas`;
     - `situaciones()` y `tonos_disponibles(idioma)`.
     Un idioma con respaldo usa `en`.
  2. Esquema Pydantic estricto por tono: las 18 situaciones con 5 variantes
     o más cada una. Linter con las reglas del catálogo; también se aplica a
     las sobrescrituras del proyecto.
  3. Migración exacta: los textos actuales de `mensajes`, `conectores` y
     `conversacional.respuestas` pasan al tono `cordial` y dejan el paquete
     de idioma (que conserva patrones, interfaz fija y estructura).
     Completar `cordial` hasta 5 variantes por situación.
  4. Capas: `lenguaje/tonos.py` (lenguaje) y el esquema en
     `configuracion/personalidad.py`. `rag/recursos/tonos/*/*.yaml` entra en
     `package-data`.
- **Aceptación:**
  - el linter rechaza cada infracción con un caso sintético por regla;
  - la caracterización no cambia con `cordial`, salvo variantes nuevas
    declaradas en `avance.md`;
  - `PYTEST` en verde.

### P12.2 Redacción con tonos

- **Pasos:**
  1. `EtapaRedaccion` usa el tono activo.
  2. Elección de variante:
     - determinista por `(id_sesion, turno, situación)`;
     - sin repetir la última variante de esa situación en la sesión;
     - la memoria es acotada (LRU de sesiones), solo guarda ids y no
       persiste;
     - sin sesión (`evaluar`, benchmark), la semilla es la pregunta, como
       hoy.
  3. `plantilla_id` y `tono` van al diagnóstico, a
     `rag preguntar --diagnostico` y al registro de consultas.
  4. Contrato HTTP, campo opcional y aditivo: `categoria_conversacional`
     (saludo, agradecimiento, despedida, capacidad), para el avatar.
  5. `rag auditar` muestra el conteo por tono.
  6. `incluir_apertura` pasa a `true` por defecto, porque la apertura es
     parte del tono. La caracterización se regenera y el cambio se declara
     en `avance.md`.
  7. Los artefactos de `rag evaluar` y `rag benchmark` registran el tono.
  8. Con varios procesos (workers) la memoria anti-repetición es por
     proceso: se acepta, porque es solo variedad, no corrección.
- **Aceptación:**
  - una sesión de 6 preguntas que caen en `sin_respuesta` no repite
    variante entre turnos seguidos;
  - mismos `id_sesion` y turno dan el mismo texto;
  - la verificación de fidelidad pasa con los 7 tonos;
  - `rag evaluar` sobre el banco universal da estados y literalidad
    idénticos con cada tono (prueba parametrizada con motor falso; la
    real, lenta);
  - toda respuesta con evidencias trae `fragmentos` con texto literal y
    offsets.

### P12.3 Redactar los siete tonos

- **Pasos:**
  1. Redactar `formal`, `serio`, `animoso`, `cercano`, `empatico` y
     `directo` en `es`, `en` y `pt`: 90 variantes por tono e idioma.
  2. Para revisarlos: `rag personalidad tono probar` (P12.4) imprime las
     variantes con las variables del proyecto.
  3. Lista de revisión humana en `docs/guia/personalidad.md`:
     - tono reconocible;
     - honestidad en `relacionado` y `sin_respuesta`;
     - nada que se lea como contenido del documento;
     - naturalidad en cada idioma.
- **Aceptación:**
  - el linter pasa en los 21 archivos;
  - la revisión del usuario sobre una muestra (2 situaciones por tono)
    queda anotada en `avance.md`.

### P12.4 `configuracion/personalidad.yaml` y CLI

- **Archivo** (esquema estricto, `config_version: 1`; `rag init` lo crea
  comentado):

  ```yaml
  tono:
    activo: cordial            # cordial | formal | serio | animoso | cercano | empatico | directo
    variedad: rotativa         # rotativa | fija (siempre la primera variante)
    plantillas: {}             # sobrescrituras por situación, validadas con el linter
  avatar:
    activo: true
    definicion: folio          # rag/recursos/avatares/<n>.avatar.json o configuracion/avatares/<n>.avatar.json
    ubicacion: cabecera        # cabecera | esquina-superior | esquina-inferior
    tamano: 56                 # px, 32 a 160
    en_lanzador: true
    mirada: {activa: true, amplitud_ojos: 6, amplitud_cabeza: 8, zona_muerta: 24}
    inactividad_min: 2
    colores: {}                # {cuerpo: "#rrggbb", ojos: "#rrggbb"}; se aplican al servir la definición
    eventos: {}                # sobrescrituras evento → clave (tabla de eventos)
  ```

- **Comandos** (patrón Command; la lógica en `aplicacion/personalidad.py`):

  ```text
  rag personalidad mostrar | validar
  rag personalidad tono listar | aplicar <tono> | probar [--tono T] [--situacion S]
  rag personalidad avatar listar | importar <archivo.avatar.json> [--nombre N] | aplicar <nombre>
  rag personalidad avatar eventos            # mapa efectivo y claves que le faltan al avatar
  rag personalidad avatar asignar <evento> <clave>
  rag personalidad avatar colores [--cuerpo #rrggbb] [--ojos #rrggbb]
  ```

- **Además:**
  - `rag doctor` gana el chequeo `personalidad`:
    - error si el archivo es inválido o el avatar no carga;
    - aviso si al avatar le faltan claves del mapa.
  - Escritura atómica.
  - `rag snapshot-config` incluye la personalidad.
  - La personalización del avatar es elegir o importar la definición,
    ubicarla, darle tamaño, colores y mapa de eventos. Los colores se
    fusionan sobre `colors.body` y `colors.eyes` al servir, sin modificar
    el archivo original.
  - Guía nueva `docs/guia/personalidad.md`: tonos, situaciones, avatar y
    eventos.
- **Aceptación:**
  - pruebas de CLI por comando: válido, inválido sin escribir nada, y
    `probar` imprime 5 variantes;
  - `importar` rechaza un JSON de más de 256 KiB, con claves duplicadas, sin
    `expressions.neutral` o con claves que no cumplen
    `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`;
  - un cambio de tono no toca índice ni calibración, y `doctor` sigue igual.

### P12.5 Widget embebible y responsive

- **Pasos:**
  1. Ubicación, en `estilos.yaml::ubicacion` y por atributo:
     - `posicion`: las 4 esquinas, o `incrustado` dentro de un contenedor
       del sitio (`<rag-extractivo-chat modo="incrustado">`);
     - `desplazamiento` x e y, `z_index` y `tamano`
       (compacto / normal / amplio);
     - `lanzador`: burbuja, pestaña u oculto. Con `oculto`, el sitio abre
       el chat con `window.RagChat.abrir()`.
     - Los atributos actuales (`data-posicion`, `data-color`, `data-titulo`
       y `data-saludo`) siguen funcionando.
  2. Responsive:
     - ≤ 480 px: hoja a pantalla completa, con `safe-area-inset`, ajuste
       al teclado virtual (`visualViewport`) y apaisado;
     - de 481 a 1024 px: panel adaptado;
     - ≥ 1024 px: panel flotante.
     Además: modo oscuro, `prefers-reduced-motion` y contraste alto
     (`forced-colors`).
  3. Bloque de citas bajo cada respuesta con evidencias:
     - arriba, la línea `invitacion_citas` del tono;
     - por cada cita: documento, sección, offsets y texto literal;
     - el tramo exacto resaltado con un `<mark>` creado por DOM.
     La presentación solo elige `acordeon` o `lista`; no hay opción para
     ocultar las citas.
  4. Microcopia del tono (`bienvenida`, `esperando` y errores) desde
     `/config`. `esperando` y los errores se anuncian por una región
     `aria-live`. `invitacion_citas` solo aparece si hay citas.
  5. API JS del sitio: `window.RagChat.abrir()`, `cerrar()` y
     `estado()`. Se supone un widget por página.
  6. `rag widget exportar` incluye todo lo necesario para servir el widget
     estático: `avatar.js`, la definición del avatar y su configuración.
  7. `rag widget snippet`: imprime la etiqueta `<script>` (o el Web
     Component) según `estilos.yaml`.
  8. Guía de inserción con CSP: el sitio debe permitir `script-src` y
     `connect-src` del servidor del asistente.
- **Aceptación:**
  - pruebas de navegador (marcador `browser`): 3 viewports (360×640,
    768×1024 y 1280×800) × 4 esquinas + modo incrustado, sin
    desbordamiento horizontal y con el campo visible con el teclado
    abierto;
  - foco atrapado y Escape;
  - prueba estática: `widget.js` no usa `innerHTML`, `outerHTML` ni
    `insertAdjacentHTML`;
  - la pantalla con citas muestra el `<mark>` exacto;
  - `widget.js` sin el avatar pesa ≤ 40 KB gzip.

### P12.6 API de personalidad

- **Públicos** (sin token):
  - `GET /config` ahora incluye la microcopia del tono y la configuración
    del avatar (activo, URLs de definición y motor, ubicación, tamaño,
    mapa de eventos, seguimiento e inactividad);
  - `GET /avatares/<nombre>.avatar.json`: el nombre se valida con el
    patrón de clave, solo se buscan las dos carpetas permitidas y se
    aplican los colores del proyecto;
  - `GET /avatar.js`.
- **Administración** (`/admin/...`):
  - endpoints:
    - `GET/PUT /admin/personalidad` (fusión parcial validada; responde con
      la configuración efectiva);
    - `POST /admin/personalidad/vista-previa` `{tono, situacion?}`;
    - `GET/POST /admin/avatares`;
    - `GET/PUT /admin/estilos`.
  - solo existen si `RAG_ADMIN_TOKEN` está definido (≥ 32 caracteres); si
    no, responden 404;
  - autenticación `Authorization: Bearer`, comparada con
    `hmac.compare_digest`;
  - sin CORS: el middleware no aplica a `/admin`;
  - límites: cuerpo ≤ 256 KiB y limitador de peticiones;
  - auditoría en `.rag/registros/admin.jsonl`: fecha, IP, acción y claves
    cambiadas, nunca el token;
  - **remoto en un VPS (D4):**
    - HTTPS obligatorio: con la petición en HTTP plano responde 403,
      salvo que venga de loopback;
    - `X-Forwarded-Proto` y la IP del cliente solo se aceptan del proxy
      declarado en `RAG_PROXY_CONFIABLE` (uvicorn `forwarded_allow_ips`);
    - lista opcional de IPs en `RAG_ADMIN_IPS`;
    - bloqueo de 15 min por IP tras 5 tokens incorrectos;
    - la guía explica cómo rotar el token.
- **Modos:** las reglas de HTTPS, proxy, `/docs`, caché y errores siguen
  la tabla «Modos de ejecución»: `rag servir --modo desarrollo|produccion`
  y `RAG_MODO`.
- **Recarga en caliente:**
  - el servicio relee `personalidad.yaml` y `estilos.yaml` si cambió su
    mtime (un `stat` por petición, sin reiniciar);
  - el motor cambia sus plantillas de forma atómica, sin cortar consultas
    en curso.
- **Aceptación:** pruebas de API:
  - sin token da 404;
  - token incorrecto da 401;
  - un cuerpo inválido da 422 y no escribe nada;
  - tras un `PUT` válido, la siguiente `/consultar` usa el tono nuevo;
  - un cambio por CLI también se ve sin reiniciar;
  - el `Origin` de un sitio con CORS permitido no obtiene encabezados CORS
    en `/admin`;
  - `/avatares/../motor.yaml` da 404;
  - por HTTP plano desde una IP no local da 403 en `produccion` y 200 en
    `desarrollo`;
  - en `desarrollo` sin `RAG_ADMIN_TOKEN` se imprime un token temporal que
    funciona solo en esa ejecución;
  - `/docs` responde en `desarrollo` y da 404 en `produccion`;
  - el sexto token incorrecto da 429 aunque el séptimo sea correcto.

### P12.7 Panel gráfico `/admin`

- **Pasos:**
  1. Página estática servida por el servicio, en vanilla JS: solo llama a
     la API de P12.6 y nunca usa `innerHTML` con datos. CSP estricta
     (`default-src 'self'`).
  2. El token se pide al entrar y vive en `sessionStorage`. Los archivos
     del panel entran en `package-data`.
  3. Pestañas:
     - **Tono:** selector, vista previa de las 5 variantes por situación y
       editor de sobrescrituras con los errores del linter.
     - **Avatar:** selector, subida de `.avatar.json`, colores de cuerpo y
       ojos, mapa evento → clave con las claves del avatar, y botones que
       disparan cada evento en la vista previa en vivo con
       `RagChat.avatar.disparar`.
     - **Widget:** preset, colores, posición, tamaño y lanzador, con vista
       previa del widget real en un `iframe` de la demo.
- **Aceptación:** pruebas de navegador:
  - cambiar el tono actualiza la vista previa;
  - asignar un evento y dispararlo llama a `play` o `setExpression` con
    la clave (avatar falso);
  - un JSON inválido muestra el error sin guardar;
  - sin token no se ve nada.

### P12.8 Licencia AGPL-3.0 (D1)

- **Pasos:**
  1. `LICENSE` con el texto oficial de la AGPL-3.0, y
     `license = "AGPL-3.0-only"` en `pyproject.toml`.
  2. `README.md`, sección Licencia:
     - qué permite;
     - qué exige a quien modifica y ofrece el servicio;
     - que instalarlo sin cambios en un VPS no obliga a nada nuevo.
  3. El panel y la API muestran «Código fuente» con el enlace al
     repositorio público, como pide el §13 de la AGPL a los servicios de
     red. `GET /fuente` redirige a la URL de `RAG_URL_FUENTE`; por defecto,
     la del repositorio.
  4. `avatar.js.LICENSE.txt` con los avisos de `@bible-strong/*` y de `ajv`
     (MIT).
- **Aceptación:**
  - el wheel incluye `LICENSE` y `avatar.js.LICENSE.txt`;
  - `GET /fuente` responde con la URL configurada;
  - en P13.3, la casilla «Licencia del proyecto decidida» queda marcada.

### P12.9 Motor del avatar empaquetado

- **Pasos:**
  1. `herramientas/avatar/` (solo desarrollo, fuera del wheel):
     - `package.json` con `@bible-strong/avatar-web` en versión exacta
       `0.1.0` y `package-lock.json`;
     - script de esbuild que genera un solo ESM minificado en
       `rag/servicio/estaticos/avatar.js`, con su aviso de licencia y el
       sha256 en `avatar.js.sha256`.
  2. El widget carga `avatar.js` con `import()` dinámico, solo si
     `avatar.activo`:
     - al abrir el panel por primera vez;
     - o, con `en_lanzador: true`, cuando el navegador está ocioso
       (`requestIdleCallback`), para no frenar la carga del sitio. Lo monta dentro
     del Shadow DOM (`createAvatar(elemento, …)`).
  3. Si `avatar.js` o la definición fallan (red, CSP sin `unsafe-eval`
     porque `avatar-core` compila con ajv, o JSON inválido), queda el
     ícono actual y se emite `rag:avatar` con el error. El chat nunca se
     rompe.
  4. `avatar.js`, `avatar.js.LICENSE.txt` y `rag/recursos/avatares/`
     entran en `package-data`.
  5. Presupuesto de tamaño medido y anotado. Objetivo: ≤ 150 KB gzip,
     cargado bajo demanda.
- **Aceptación:**
  - el build es reproducible: el CI compara el sha256;
  - prueba de navegador con el avatar real en una página con CSP estricta,
    donde se ve el ícono de respaldo y el chat funciona;
  - prueba con CSP permisiva, donde se monta el avatar.

### P12.10 Avatar «Folio» y máquina de estados

- **Diseño de Folio (D2).**
  - Es una hoja de papel viva: un rectángulo redondeado, levemente
    inclinado y con la esquina doblada (un nodo), y dos ojos de tinta
    ovalados. No tiene boca: la librería expresa con la forma de los ojos,
    el giro de la cabeza y el movimiento ambiental.
  - Encarna lo que es el proyecto: lee documentos, mira la cita antes de
    afirmar y no exagera.
  - Colores: cuerpo `#f5f1e8` (papel) y ojos `#1e293b` (tinta). Se cambian
    con `avatar.colores`.
  - Honestidad también en el gesto:
    - `contento` es sobrio, no celebra;
    - en `dudoso` y `apenado` nunca hay gesto de éxito;
    - en `respuesta_ok` primero mira hacia las citas, y recién después se
      alegra.
- **Pasos:**
  1. Contrato de claves de animación: `inactivo`, `saludo`, `atento`,
     `escuchando`, `asentir`, `pensando`, `pensando-largo`, `contento`,
     `dudoso`, `apenado`, `amable`, `despedida`, `preocupado`,
     `somnoliento` y `despertar`. La expresión `neutral` es obligatoria; la
     mirada la genera el widget.
  2. Expresiones de Folio, para orientar el diseño:

     | Expresión | Ojos | Cabeza | Movimiento |
     |---|---|---|---|
     | `atento` | grandes | — | — |
     | `contento` | entrecerrados, en arco | levemente arriba | — |
     | `dudoso` | uno más chico | inclinada | — |
     | `apenado` | ángulo hacia abajo | gacha | — |
     | `pensando` | arriba a un lado | — | `slowDrift` |
     | `somnoliento` | casi cerrados | — | — |
     | `preocupado` | — | — | ojos con `shake` breve |

     El parpadeo es el automático de la librería.
  3. `rag/recursos/avatares/folio.avatar.json`, validado con
     `parseAvatarDefinition` de la librería en `herramientas/avatar/`. Una
     página de muestra con todas las animaciones queda como vista previa
     para revisión humana.
  4. Máquina de estados en `widget.js`, con la tabla de eventos, sus
     prioridades, sus reglas y la grilla de mirada. El mapa efectivo viene
     de `/config`. `window.RagChat.avatar.disparar(evento)` lo usan el panel
     y los sitios que quieran reaccionar a sus propios eventos.
  5. Móvil (≤ 480 px):
     - el avatar baja a 40 px;
     - con el teclado abierto se oculta para no quitar espacio al campo.
  6. Accesibilidad:
     - el avatar es decorativo (`aria-hidden`); los estados ya tienen
       texto y etiqueta;
     - ninguna animación parpadea más de 3 veces por segundo (WCAG 2.3.1).
- **Aceptación:**
  - Folio pasa `parseAvatarDefinition` y define todas las claves del
    contrato.
  - Pruebas de navegador con un `avatar.js` falso que registra las
    llamadas:
    - la secuencia de cada evento de la tabla;
    - las prioridades: un error durante `pensando` gana, y un transitorio
      vuelve al persistente;
    - el tecleo con su retraso;
    - la inactividad acelerada con el reloj falso de Playwright;
    - `visibilitychange` pausa;
    - con `prefers-reduced-motion` no se sigue el puntero;
    - una clave faltante cae a su respaldo.
  - La grilla de mirada:
    - se generan 15 expresiones válidas a partir de `neutral` (la librería
      real las acepta);
    - el puntero en cada esquina elige la celda correcta;
    - en la zona muerta mira al centro;
    - la histéresis evita el cambio con movimientos de 2 px;
    - tras 1,5 s quieto vuelve al centro.

### P12.11 `/ready` informa el estado del proyecto

- **Pasos:** `/ready` reutiliza el `ReporteDoctor` (P11.4). Informa perfil,
  modelos, compatibilidad del índice, calibración y personalidad, y separa
  lo que bloquea de lo opcional.
- **Aceptación:** pruebas de API: sano; índice incompatible (`listo: false`
  con la acción); sin calibración (`listo: true` con aviso).

### P12.12 Imagen Docker por perfil

- **Pasos:**
  - `ARG PERFIL=medium`;
  - instala el wheel (que incluye `avatar.js`, avatares y tonos);
  - ejecuta `rag modelos descargar --perfil $PERFIL` y define
    `HF_HUB_OFFLINE=1`;
  - usuario no root;
  - `RAG_ADMIN_TOKEN` sin definir: la administración queda apagada;
  - `RAG_MODO=produccion` explícito.
- **Aceptación:** `docker build --build-arg PERFIL=light .` funciona, y
  `/health` y `/widget.js` responden sin red.

### P12.13 `rag desplegar preparar`

- **Aceptación:**
  - genera en `dist/`, sin dejar fuera nada de esta lista:
    - la configuración, incluidas `personalidad.yaml` y `estilos.yaml`;
    - los avatares importados, la calibración y el índice;
    - `Dockerfile` y `docker-compose.yml` (desde
      `rag/recursos/despliegue/`);
    - un `LEEME_despliegue.md` en el idioma del proyecto, con el snippet
      del widget y cómo activar `/admin`;
    - en `docker-compose.yml`, un servicio `caddy` opcional (perfil
      `https`) con TLS automático para el dominio del VPS, y
      `RAG_PROXY_CONFIABLE` apuntando a él;
  - prueba de CLI.

### P12.14 CI

- **Pasos:** `.github/workflows/ci.yml` (reemplaza `pruebas.yml`) con:
  - pruebas rápidas en Linux y Windows con Python 3.11 y 3.12, sin torch;
  - linter de tonos;
  - job `modelos` con caché de `RAG_MODELOS_DIR`;
  - job `web` con Node:
    - build reproducible de `avatar.js` (compara el sha256);
    - validación de los avatares con la librería;
    - pruebas de navegador del widget y del panel;
  - wheel en un entorno limpio, que debe contener tonos, avatares y
    estáticos;
  - imagen `light` con `/health`;
  - ejemplos web.
- **Aceptación:** el YAML es válido. La primera ejecución real requiere
  push, que decide el usuario.

### Orden sugerido

```text
P12.1 → P12.2 → P12.3        (tonos)
P12.4                        (CLI de personalidad; necesita P12.1)
P12.5                        (widget; independiente de los tonos salvo la microcopia)
P12.6 → P12.7                (API y luego panel)
P12.8 → P12.9 → P12.10       (licencia, motor del avatar y Folio)
P12.11 → P12.12 → P12.13 → P12.14
```

---

## P13. Documentación y puerta de lanzamiento

### P13.1 Documentación final

- **Pasos:**
  - `README.md` (instalación por perfil y ciclo).
  - `docs/guia/*` (instalacion, uso, golden, configuracion, web, despliegue).
  - `docs/metodologia/*` (recuperacion, lexico, reranker, lector, politica, calibracion, multilenguaje), con la plantilla de fichas.
  - ADR `0003-onnx-y-perfiles` y `0004-cascada-lexica-y-retiro-de-guardias-regex`.
  - Versión `0.8.0` en `CHANGELOG.md`.
- **Aceptación:** `rg -n "torch|sentence-transformers|layered_v1|textos.yaml|vocab_bm25|data/golden|palabras_generales" README.md docs ejemplos` no devuelve nada, salvo en ADR o CHANGELOG como historia.
- **Además:** quita de comentarios y docstrings de `rag/` las etiquetas históricas («Etapa …», «Fase …», «E1–E8», «molde», «coordinador»), reescribiendo la frase si hace falta. Aceptación: `rg -n "Etapa [A-Z0-9]|E[1-8]|molde|coordinador" rag` no devuelve nada.

### P13.2 Cerrar el plan

- **Pasos:** resume el plan en `CHANGELOG.md` y en los ADR, y borra `docs/plan/`. La historia queda en git.
- **Aceptación:** `docs/` contiene solo `README.md`, `guia/`, `metodologia/` y `decisiones/`.

### P13.3 Puerta de lanzamiento (decide el usuario)

Con el corpus real de un cliente:

- [ ] Golden set real curado por una persona, con ≥ 30% sin respuesta o premisa falsa y pares mínimos «mismo tema».
- [ ] `rag calibrar --alfa 0.05` da `CALIBRADO`: en `test`, la cota superior al 95% de falsos `ok` es ≤ 5% (con 0 errores exige ≥ 59 respuestas aceptadas en `test`). Si da `MUESTRA_INSUFICIENTE`, se lanza con los umbrales del perfil y sin afirmar el 5%.
- [ ] `rag benchmark` cumple los presupuestos en la máquina de producción (light ≤ 150 ms, medium ≤ 1 s y heavy ≤ 5 s de p95).
- [ ] CI en verde (requiere push).
- [x] Licencia del proyecto decidida: AGPL-3.0 (D1, se aplica en P12.8).
