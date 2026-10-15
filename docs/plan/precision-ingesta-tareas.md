# Tareas: precisión del primer resultado desde la ingesta

Análisis y fases: [precision-ingesta.md](precision-ingesta.md). Estado de
cada tarea: [precision-ingesta-avance.md](precision-ingesta-avance.md).

Este archivo está escrito para que cada tarea la ejecute un agente (Sonnet
5.5) en una sesión propia, sin depender del contexto de otra conversación.
Todo lo que el agente no podría deducir leyendo el código está escrito
abajo, en «Reglas fijas» y en los puntos ⚠ de cada tarea.

## Cómo trabajar una tarea

1. Leer este archivo completo, [precision-ingesta.md](precision-ingesta.md)
   y la fila de la tarea en el avance.
2. Trabajar **solo** en la rama `ccr-b2b5f6b8-7tipuk` (separada de `main`).
   No hacer merge a `main`, no abrir PR y no hacer push a otra rama sin
   pedido explícito del usuario.
3. Hacer una tarea por sesión. Si una tarea depende de otra que no está ✅,
   detenerse e informarlo.
4. Al llegar a un punto ⚠: **detenerse y preguntar al usuario**, con las
   opciones y una recomendación. No elegir por cuenta propia.
5. Al terminar: suite de pruebas en verde, commit con mensaje descriptivo,
   push a la rama y actualizar la fila en el avance (estado, fecha, commit,
   notas y cifras medidas).

Estados del avance: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado ·
⚠ espera al usuario.

## Convenciones

- `PY` = `.venv/bin/python` (Linux/macOS) o `.venv\Scripts\python.exe`
  (Windows). Preparar con `uv sync --extra test`.
- `PYTEST` = `PY -m pytest -q -p no:cacheprovider`. Suite completa, unos
  10 minutos. Durante el desarrollo, correr solo las carpetas afectadas
  (`tests/ingesta`, `tests/indice`, `tests/evaluacion`, `tests/consulta`);
  antes del commit, la suite completa.
- `MEDIR` = el script de F0.2 sobre el banco de F0.1, con los argumentos
  que indique cada tarea.
- Modelos: `IPSIS_MODELS_DIR=.cache/modelos`; descargar con
  `ipsis models download` o `--download` en los scripts que lo admiten.

## Reglas fijas (no se deducen del código)

Romper cualquiera de estas reglas invalida la tarea, aunque las pruebas
pasen.

1. **Nunca inventar cifras.** Si los modelos no se pueden descargar (por
   ejemplo, red bloqueada hacia huggingface.co), la tarea queda ⛔ con el
   error exacto. No estimar ni rellenar tablas con valores supuestos.
2. **Texto fuente y offsets literales.** `texto`/`texto_fuente` y
   `offset_inicio`/`offset_fin` siempre corresponden a caracteres exactos de
   `texto_completo`. Lo que se agrega para buscar (cabeceras, rasgos) va
   **solo** en `texto_embebido`/`texto_embedding`, nunca en el texto citado.
   La invariante de `tests/ingesta/test_chunking.py` (no perder ni duplicar
   contenido) se extiende a toda estrategia nueva.
3. **Sin modelos generativos** ([ADR 0001](../decisions/0001-non-generative-answers.md)).
   La metadata nueva se calcula con reglas o estadística. `descripcion_libre`
   sigue en `None`.
4. **Determinismo.** La misma entrada produce los mismos fragmentos,
   payloads e IDs. Ordenar siempre con desempate explícito (por ejemplo, por
   `chunk_id`).
5. **No cambiar comportamiento existente por defecto.** Toda estrategia o
   campo nuevo entra como opción nueva (por ejemplo, una estrategia
   `CH-F256S` nueva en vez de modificar `CH-F256`). Los valores por defecto
   de `ipsis/recursos/plantillas/engine.yaml` y de los perfiles solo
   cambian en F5.1, con aprobación del usuario. Así los índices y
   calibraciones existentes siguen siendo reproducibles.
6. **Tres idiomas.** Todo texto nuevo de cabecera o mensaje va en
   `ipsis/recursos/idiomas/{es,en,pt}.yaml` (ver `cabecera_embebido`). Las
   pruebas cubren los tres.
7. **Colecciones versionadas.** No se mezclan vectores de configuraciones
   distintas. Cada experimento indexa en un proyecto temporal o con
   `sufijo_coleccion` propio. Nunca escribir sobre `.ipsis/` del proyecto
   del usuario.
8. **Los bancos de `tests/datos` no sirven para medir este problema.** En
   ellos casi cada documento es un solo fragmento (verificado: `CH-F256` da
   26 fragmentos para unos 24 documentos; `banco_general`, 13 para 13). Solo
   cuentan las cifras del banco de F0.1 o del corpus real del usuario.
9. **Trampa del `hash_corpus` en modo legacy.** `ipsis/indice/manifiesto.py:44`
   solo usa `hash_texto` cuando no hay `preparacion`. Cambiar la cabecera o
   cualquier cosa de `texto_embebido` **no cambia** `hash_corpus`, así que una
   calibración vieja se aplicaría a vectores nuevos. Hasta que F1.5 lo
   resuelva, cada experimento corre con `ruta_calibracion=None` o en un
   proyecto sin `config/calibration.yaml`, y las notas lo dicen.
10. **Perfiles.** En `light` no hay reranker: el orden final es el RRF
    híbrido. En `medium` (motor v2, el predeterminado) el orden final lo da el
    reranker. Medir siempre los dos perfiles; una mejora en uno puede ser
    neutra en el otro.
11. **Latencia.** `v2.query_budget_ms` es 2500. Un cambio que lleve el p95 de
    `medium` por encima de ese presupuesto no se acepta, aunque mejore hit@1.

---

## F0. Medición

### F0.1 Banco de pasajes en documentos largos

- **Objetivo:** un banco donde la respuesta correcta compita con pasajes
  parecidos dentro del mismo documento y entre documentos.
- **⚠ Antes de empezar:** preguntar al usuario si puede aportar su corpus
  real con preguntas. Si lo aporta, el banco se arma sobre ese corpus (fuera
  del repo si es privado) y lo sintético queda como complemento.
- **Pasos (versión sintética, español primero):**
  - 6 documentos de 1500–4000 palabras en Markdown, con encabezados de dos
    niveles. Al menos 3 deben tener **secciones hermanas**: el mismo tema con
    distinto actor, condición o cifra (por ejemplo, plazos de reembolso para
    personal de planta y para personal a honorarios; garantía de dos
    productos distintos).
  - 2 pares de documentos «gemelos» sobre el mismo tema (dos reglamentos de
    distintas unidades).
  - Al menos 100 preguntas respondibles: 40 cuya respuesta está en la
    **segunda mitad** de una sección de más de 300 palabras, 40 que
    distinguen secciones hermanas, 20 paráfrasis. Más 15 no respondibles del
    mismo tema.
  - Formato de `ipsis/evaluacion/banco.py` (`CasoEvaluacion`, manifiesto con
    `corpus.archivos`). Evidencias con `doc_id` y offsets exactos.
  - Partición `dev`/`test` (60/40) fijada por ID. Los ajustes se hacen
    mirando solo `dev`.
- **Archivos:** `tests/datos/banco_pasajes/es/{corpus/,banco.jsonl,manifiesto.json,README.md}`;
  prueba estructural `tests/evaluacion/test_banco_pasajes.py`.
- **Aceptación:** `validar_evidencias_contra_corpus` pasa; la prueba
  estructural (conteos por tipo, evidencias literales, documentos de más de
  1500 palabras) pasa en menos de 5 s; con `CH-F256`, la mediana de
  fragmentos por documento es al menos 6.

### F0.2 Script de medición por etapa

- **Objetivo:** saber si el error es de recuperación o de orden.
- **Pasos:**
  - `herramientas/evaluacion/ranking_pasajes.py`: recibe banco, perfil(es),
    configuración de recuperación (estrategia, cabecera, preparación,
    `reranker_max_tokens`, modelo denso) y carpeta de salida.
  - Copia el corpus a un proyecto temporal, indexa con
    `ejecutar_ingesta(..., cfg_rec=...)`, arma el motor v2 como
    `ipsis/aplicacion/consulta.py` y, por pregunta, registra:
    - rango de la primera evidencia correcta en el **orden híbrido**
      (el de `motor.retriever.recuperar`, como hace
      `ipsis/aplicacion/evaluacion.py:73`);
    - rango en el **orden final publicado** por v2 (fuentes ordenadas);
    - latencia total y por etapa.
  - Un candidato es correcto si se solapa con alguna evidencia (misma lógica
    que `_solapa` en `ipsis/evaluacion/metricas.py:125`). Para candidatos
    ampliados al padre, usar los offsets del fragmento recuperado, no los del
    padre.
  - Salida JSON y Markdown: hit@1, hit@3, hit@5 y MRR por etapa, perfil y
    partición; p50/p95; lista de casos con rango ≠ 1. Opción `--comparar
    base.json` que liste casos ganados y perdidos.
  - Sin calibración (regla 9).
- **Archivos:** el script y `tests/evaluacion/test_ranking_pasajes.py`, con
  un retriever y un reranker falsos (sin modelos).
- **Aceptación:** las pruebas pasan sin modelos; el script corre de punta a
  punta en `light` con e5-small.

### F0.3 Diagnóstico de longitud en tokens

- **Objetivo:** medir C1 (truncado) en vez de estimarlo.
- **Pasos:** `herramientas/evaluacion/tokens_fragmentos.py` indexa en
  memoria (sin Qdrant) con la configuración dada y, con el tokenizador real
  de cada modelo (`ModeloOnnx.tokenizar`), reporta por fragmento:
  - tokens del `texto_embebido` frente a `max_tokens` del modelo denso;
  - tokens de pregunta + pasaje del reranker frente a `reranker_max_tokens`,
    usando las preguntas del banco;
  - porcentaje truncado y **posición de la evidencia**: si cae después del
    punto de corte del reranker.
- **Aceptación:** tabla por estrategia (`CH-F256`, `CH-PAR`, `CH-SEC`) con
  el porcentaje de casos cuya evidencia queda después del corte.

### F0.4 Línea base

- **Depende de:** F0.1–F0.3. Requiere modelos.
- **Pasos:** `MEDIR` con la configuración por defecto actual (`CH-F256`, sin
  cabecera, `reranker_max_tokens: 256`, e5-small) en `light` y `medium`.
  F0.3 sobre la misma configuración.
- **Aceptación:** tablas en el avance; JSON guardado fuera del repo y su
  ruta anotada. Si hit@5 − hit@1 tras el reranker es menor a 5 puntos, el
  problema descrito no se reproduce en el banco: **⚠ detenerse** y revisar
  el banco con el usuario antes de seguir.

---

## F1. Experimentos de configuración (sin código)

Cada experimento: `MEDIR` con un solo cambio respecto de la línea base,
`light` y `medium`, partición `dev`. Anotar hit@1, hit@5, MRR, p95 y casos
ganados/perdidos. La partición `test` se mide solo en F5.

| Tarea | Cambio | Causa que prueba |
|---|---|---|
| F1.1 | `with_header: true` | C2 |
| F1.2 | `chunking_strategy: CH-PAR` y, aparte, `CH-SEC` | C3 |
| F1.3 | `reranker_max_tokens: 512` (solo `medium`) | C1 |
| F1.4 | la mejor combinación de F1.1–F1.3 | conjunto |

- **Aceptación de F1.4:** tabla comparativa y una recomendación escrita en el
  avance. **⚠ No cambiar valores por defecto**: queda para F5.1.

### F1.5 `hash_corpus` legacy y la cabecera

- **Problema:** regla 9. Activar la cabecera o enriquecerla no cambia
  `hash_corpus`, así que la calibración no se invalida.
- **⚠ Decisión del usuario antes de implementar** (cambia el contrato del
  manifiesto):
  - (a) Incluir `texto_embebido` en la huella legacy. Correcto, pero
    invalida la calibración de **todos** los proyectos existentes al
    actualizar, aunque no hayan cambiado nada. Requiere nota en el CHANGELOG
    y que `ipsis doctor` lo explique.
  - (b) Incluirlo solo cuando `texto_embebido != texto` (cabecera activa).
    Los proyectos con la configuración por defecto conservan su huella.
    **Recomendada.**
- **Archivos:** `ipsis/indice/manifiesto.py`, `tests/indice/test_manifiesto.py`.
- **Aceptación:** prueba de que activar la cabecera cambia `hash_corpus` y
  de que la configuración por defecto no lo cambia (con (b)).

---

## F2. Fragmentado

### F2.1 Estrategia fija que respeta secciones y oraciones

- **Pasos:** nueva estrategia `CH-F256S` en `ipsis/ingesta/chunking.py`.
  Igual que `CH-F256`, pero:
  - corta siempre al cambiar `seccion_path`;
  - no agrega un bloque que haga pasar el máximo: lo parte en oraciones y
    deja el resto para el fragmento siguiente;
  - el solape es en oraciones completas, no en bloques.
  - Para partir un bloque, `_construir_chunk` hoy trabaja con bloques
    enteros: crear sub-bloques con offsets exactos dentro de
    `texto_completo`.
  - Registrarla en `ESTRATEGIAS`. No tocar `CH-F256`.
- **Separación de oraciones:** con una regla simple (`.`, `?`, `!`, `;` y
  salto de línea, seguidos de espacio y mayúscula), sin dependencias nuevas.
  Probar abreviaturas comunes de los tres idiomas («art.», «Nº», «p. ej.»,
  «e.g.», «Sr.»).
- **Aceptación:** invariante de contenido (regla 2); ningún fragmento cruza
  sección; ningún fragmento supera el máximo salvo una única oración más
  larga que el máximo; pruebas en `tests/ingesta/test_chunking.py`; `MEDIR`
  en `dev` comparado con F0.4 y F1.

### F2.2 Presupuesto en tokens del modelo

- **⚠ Decisión del usuario antes de implementar.** El chunking hoy es
  determinista y no depende de modelos (docstring de `chunking.py`). Medir en
  tokens exige el tokenizador del modelo:
  - (a) usar el `tokenizer.json` del modelo denso en caché. Exacto, pero la
    ingesta pasa a depender del modelo, y cambiar de modelo cambia los
    fragmentos;
  - (b) una razón palabras→tokens fija por idioma, medida en F0.3 y guardada
    en la configuración. Sin dependencia, aproximada. **Recomendada para
    empezar**;
  - (c) no hacerla, si F1.3 (reranker a 512) ya cierra la brecha dentro del
    presupuesto de latencia.
- **Pasos con (b):** parámetro `max_tokens` en `CH-F256S` que convierte con
  la razón; la razón y el presupuesto (`reranker_max_tokens` menos el p95 de
  tokens de pregunta) en el esquema de recuperación
  (`ipsis/configuracion/esquemas.py`, con su nombre público en
  `glosario.py`). Incluir los parámetros en `huella_archivos`
  (`ipsis/ingesta/ingesta.py:130`) para que cambiar la razón obligue a
  reindexar.
- **Aceptación:** con F0.3, menos del 5 % de los fragmentos supera la ventana
  del reranker; `MEDIR` en `dev`.

### F2.3 Preparación estructural para Markdown y texto

- **Contexto:** `estructural_v1` (hijos de ~80 palabras con cabecera; padre
  completo para el reranker y la cita) solo admite DOCX y tabulares
  (`ipsis/ingesta/preparacion.py:22`). Ver
  [preparacion-estructural.md](../methodology/preparacion-estructural.md).
- **Pasos:** `preparar_markdown` y `preparar_texto` que produzcan un
  `DocumentoPreparado` (`ipsis/nucleo/documentos.py`) con elementos
  `titulo`/`parrafo`, `seccion_path` y offsets sobre el texto canónico.
  Reutilizar el parseo de encabezados de `ipsis/ingesta/parsear.py` en lugar
  de duplicarlo. Nueva `PARSER_VERSION` por formato. Despachar por extensión
  en `preparar_documento`.
- **No hacer:** PDF (F2.4); tablas Markdown como tablas (quedan como
  párrafos, y se anota en la documentación).
- **Aceptación:** pruebas en `tests/ingesta/test_preparacion.py` (offsets,
  secciones, hijos que no cruzan sección); `ipsis prepare` funciona sobre un
  proyecto con `.md`; `MEDIR` con `preparacion.modo: estructural_v1` en
  `dev`.

### F2.4 Preparación estructural para PDF

- **⚠ Iniciar solo si F2.3 mejora hit@1 en `dev`.** El PDF no declara
  estructura de forma confiable. Reutilizar la detección de outline y de
  encabezados por tamaño de letra de `parsear.py`, y conservar sus
  advertencias.
- **Aceptación:** como F2.3, con los PDF de `tests/datos/banco_general`.

---

## F3. Metadata que distingue fragmentos parecidos

### F3.1 Cabecera enriquecida

- **Pasos:** variante de `construir_texto_embebido`
  (`ipsis/ingesta/chunking.py:270`) activada con una opción nueva
  (`header_detail: basic | extended`, por defecto `basic` = comportamiento
  actual). `extended` agrega, a partir de lo que `construir_payload` ya
  calcula: tipos de entidad presentes (plazo, monto, fecha, etc., según
  `entidades[].tipo`) y marcas de condición o excepción. Etiquetas en los
  tres idiomas (regla 6). Orden fijo y sin repetir tipos.
- **Cuidado:** hoy el texto embebido se construye **antes** que el payload
  (`ipsis/ingesta/ingesta.py:75-79`). Calcular primero entidades y marcas y
  después la cabecera, sin calcular dos veces.
- **Aceptación:** pruebas de la cabecera en los tres idiomas; texto citado
  intacto (regla 2); `MEDIR` en `dev`.

### F3.2 Grupos de hermanos y rasgos distintivos

- **⚠ Decisión del usuario sobre la similitud** antes de implementar:
  - (a) coseno TF-IDF con las `EstadisticasLexicas` que la ingesta ya
    construye. Determinista, sin modelo y sin una segunda pasada de
    codificación. **Recomendada**;
  - (b) coseno de los embeddings. Más fiel, pero obliga a codificar dos
    veces (agrupar y luego codificar el texto con rasgos), y la ingesta
    se vuelve más lenta.
- **Pasos con (a):**
  - Tras construir los payloads y antes de codificar, agrupar fragmentos con
    similitud ≥ umbral (componentes conexas; umbral en la configuración,
    inicial 0,5, a ajustar en `dev`).
  - Para cada fragmento de un grupo, `rasgos_distintivos`: hasta 5 términos
    con mayor TF-IDF en el fragmento y ausentes o raros en el resto del grupo
    (forma superficial, como `extraer_keywords`).
  - Payload: `grupo_similar` (ID estable: el menor `chunk_id` del grupo) y
    `rasgos_distintivos`. Agregar los rasgos a la cabecera con
    `header_detail: extended` (etiqueta en tres idiomas).
  - Los nuevos campos entran en `hash_corpus` (depende de F1.5).
- **Aceptación:** pruebas con un corpus mínimo de dos secciones hermanas
  (los rasgos de cada una contienen su actor o cifra distintiva);
  determinismo; `MEDIR` en `dev` con foco en las 40 preguntas de hermanos.

### F3.3 Revisión de la categoría

- **Iniciar solo si** el análisis de F0.4 muestra que los errores de rango 2–5
  comparten categoría con el acierto. En ese caso, proponer en el avance
  reemplazar `clasificar_categoria` por la sección declarada o por los rasgos
  de F3.2. **⚠ No implementar sin aprobación.**

---

## F4. Representación vectorial

### F4.1 Comparación de modelos densos

- **Pasos:** `MEDIR` con la mejor configuración hasta el momento y cada
  modelo denso del catálogo: e5-small (384), e5-base (768), granite-311m
  (768) y EmbeddingGemma (768). Registrar el tamaño en disco y la latencia de
  codificación.
- **Cuidado:** `coseno_piso` es distinto por modelo y los umbrales de
  abstención de v1 dependen de él. En v2 no afecta el orden, pero cualquier
  conclusión sobre abstención exige recalibrar.
- **Aceptación:** tabla en el avance. **⚠ Cambiar el modelo de un perfil es
  decisión del usuario** (F5.1).

### F4.2 Cuantización del modelo

- **Pasos:** si granite-311m queda entre los mejores en F4.1, comparar en x86
  su variante `quint8_avx2` contra fp32 (forzando el archivo `"*"` del
  catálogo, sin cambiar el catálogo).
- **Aceptación:** diferencia de hit@1 y de latencia anotada.

### F4.3 Vectores por oración (multivector MaxSim)

- **⚠ Iniciar solo con aprobación del usuario**: multiplica el tamaño del
  índice y toca `ipsis/indice/qdrant.py`.
- **Antes de implementar, verificar en la práctica** (no suponer) que el
  modo local de `qdrant-client` (`QdrantClient(path=...)`) acepta
  `MultiVectorConfig(comparator=MAX_SIM)` con la versión del `uv.lock`, con
  un script mínimo. Si no lo acepta, ⛔ e informar.
- **Pasos:** vector con nombre `oraciones` opcional (opción
  `dense_granularity: chunk | sentences`); oraciones con el separador de
  F2.1; el prefijo de pasaje del modelo en cada oración; en modo híbrido, un
  tercer `prefetch`. El vector `denso` por fragmento se mantiene.
- **Aceptación:** `MEDIR` en `dev`; tamaño del índice y p95 anotados.

---

## F5. Cierre

### F5.1 Propuesta de valores por defecto

- **Pasos:** con todas las cifras en `dev`, elegir la configuración
  candidata y medirla **una sola vez** en `test`, en `light` y `medium`.
  Correr también `herramientas/evaluacion/general.py --no-baseline` y la
  suite completa.
- **⚠ El usuario aprueba** cualquier cambio de valores por defecto en
  `engine.yaml` o en los perfiles. Si cambia el fragmentado por defecto,
  evaluar con el usuario si hace falta una migración en
  `ipsis/configuracion/migraciones.py` (hoy `config_version: 7`) para los
  proyectos que ya tienen `config/engine.yaml`.
- **Aceptación:** hit@1 en `test` mejora sin bajar hit@5 ni la cobertura
  literal; p95 dentro del presupuesto; sin regresiones en la suite ni en la
  regresión general.

### F5.2 Documentación

- **Pasos:**
  - corregir en `docs/methodology/retrieval.md` la afirmación «un
    fragmento nunca cruza secciones» (falsa para `CH-F256`);
  - documentar estrategias y opciones nuevas, el banco de pasajes y los
    resultados;
  - entrada en `CHANGELOG.md`;
  - un ADR nuevo si cambian valores por defecto o el contrato del
    manifiesto (F1.5).
- **Aceptación:** `tests/test_documentacion.py` pasa.
