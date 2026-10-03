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

Referencia: [lexico-y-multilenguaje.md](lexico-y-multilenguaje.md) §6. Al terminar P3, `rg -n "[áéíóúñ¿¡]" rag --glob "*.py"` solo encuentra comentarios y docstrings.

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
  - «¿Cuánto dura la garantía?»: el foco incluye el término de «garantía», y `s_foco` = 0 contra la oración del filtro de sedimentos y 1 contra la de la garantía.
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

---

## P9. Golden set estándar

Referencia: [comandos-y-golden.md](comandos-y-golden.md) §3.

### P9.1 Lectura e importación

- **Pasos:** en `rag/evaluacion/golden.py`: `FilaGolden`, `leer_csv` (`utf-8-sig`), `leer_jsonl`, `leer_squad2`, `ubicar_respuesta` (exacta y luego con espacios colapsados, con mapeo a los offsets originales), `separar_dev_test` y `a_banco`. La categoría `exacta`/`parafrasis` se decide con `s_cov`.
- **Aceptación:** pruebas de offsets, texto ausente o repetido, separación estable al reimportar y avisos de tamaño y balance. `PYTEST` en verde.

### P9.2 Plantilla para el cliente

- **Pasos:** `generar_plantilla(corpus, est, paquete, n=40)` usa MMR sobre TF-IDF para elegir secciones diversas, llena `terminos_clave`, agrega 35% de filas trampa y 3 conversacionales, y escribe `LEEME.txt`. Agrega `golden_instrucciones` a los paquetes es, en y pt.
- **Aceptación:** prueba: con `n=20` aparecen todos los documentos, alrededor de 35% de filas son trampa y el CSV se puede releer con `leer_csv`.

### P9.3 Comandos `rag golden`

- **Aceptación:** prueba de ida y vuelta: plantilla → completar 2 filas → importar → exportar squad2 → importar squad2 → mismo banco.

---

## P10. Evaluación, calibración y benchmark

### P10.1 Señales y cota de riesgo en las métricas

- **Pasos:** las observaciones guardan todas las señales de la política. Implementa `cota_superior_clopper_pearson(x, n, confianza)` con la CDF binomial y bisección.
- **Aceptación:** `x=0, n=50` → 0,0582 ± 0,001; un segundo valor coincide con una tabla de referencia (anota la fuente). `PYTEST` en verde.

### P10.2 Calibración

- **Pasos:** `rag/evaluacion/calibracion.py::calibrar(observaciones, alfa)` según §4, con `escribir_calibracion` y `cargar_calibracion` (validan la procedencia). Borra `calibrar_umbral`.
- **Aceptación:** pruebas: elige el umbral más bajo que cumple, devuelve 1,01 si ninguno cumple y rechaza otra procedencia. `PYTEST` en verde.

### P10.3 `rag calibrar`

- **Aceptación:** prueba de CLI con un motor falso; prueba lenta con `medium` sobre el banco v1.1.0.

### P10.4 Benchmark por perfiles

- **Pasos:** `rag benchmark --perfiles bm25,light,medium,heavy` ejecuta cada perfil sobre el mismo banco y reporta métricas, p50/p95 por etapa y cumplimiento del presupuesto. Termina con código ≠ 0 si alguno lo incumple o supera el límite de falsos `ok`.
- **Aceptación:** reporte JSON + Markdown en `golden/reportes/`, con la tabla copiada a [avance.md](avance.md).

### P10.5 Experimento: chunking `texttiling_v1`

- **Pasos:** implementa el chunker de [lexico-y-multilenguaje.md](lexico-y-multilenguaje.md) §5 como opción, y compáralo con el actual con `rag benchmark` sobre el banco v1.1.0.
- **Aceptación:** la decisión (adoptar o descartar) queda en [avance.md](avance.md) con los números. Si se descarta, borra el código.

---

## P11. CLI y operación

### P11.1 CLI con patrón Command

- **Pasos:** crea `rag/cli/base.py::Comando` y `rag/cli/comandos/<grupo>.py` (grupos de [comandos-y-golden.md](comandos-y-golden.md) §2). Pasa la lógica a `rag/aplicacion/*` y borra `rag/cli.py`. El script de entrada sigue siendo `rag.cli:main`.
- **Aceptación:** `tests/cli/` en verde, incluida «todas las opciones tienen ayuda».

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

## P12. Despliegue y CI

### P12.1 Imagen Docker por perfil

- **Pasos:** `ARG PERFIL=medium`; instala el wheel, ejecuta `rag modelos descargar --perfil $PERFIL` y define `HF_HUB_OFFLINE=1`. Usuario no root.
- **Aceptación:** `docker build --build-arg PERFIL=light .` funciona y `/health` responde sin red.

### P12.2 `rag desplegar preparar`

- **Aceptación:** genera en `dist/` la configuración, la calibración, el índice, `Dockerfile`, `docker-compose.yml` (desde `rag/recursos/despliegue/`) y un `LEEME_despliegue.md` en el idioma del proyecto. Prueba de CLI.

### P12.3 CI

- **Pasos:** `.github/workflows/ci.yml` (reemplaza `pruebas.yml`) con:
  - pruebas rápidas en Linux y Windows con Python 3.11 y 3.12, sin torch;
  - job `modelos` con caché de `RAG_MODELOS_DIR`;
  - wheel en entorno limpio;
  - imagen `light` con `/health`;
  - ejemplos web.
- **Aceptación:** el YAML es válido. La primera ejecución real requiere push, que decide el usuario.

### P12.4 API y widget

- **Pasos:** `/ready` informa perfil, modelos, compatibilidad del índice y calibración. El widget resalta `respuesta_exacta` con un `<mark>` creado por DOM, nunca con `innerHTML`.
- **Aceptación:** pruebas de API y de navegador.

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

- [ ] Golden set real de ≥ 50 preguntas, con ≥ 30% sin respuesta o premisa falsa, curado por una persona.
- [ ] `rag calibrar --alfa 0.05` aplicado; en `test`, la cota superior al 95% de falsos `ok` es ≤ 5%.
- [ ] `rag benchmark` cumple los presupuestos en la máquina de producción (light ≤ 150 ms, medium ≤ 1 s y heavy ≤ 5 s de p95).
- [ ] CI en verde (requiere push).
- [ ] Licencia del proyecto decidida.
