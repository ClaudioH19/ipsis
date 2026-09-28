# Plan V2: infraestructura primero, calibración al final

## Decisión de producto

La V2 seguirá siendo un asistente documental **extractivo y no generativo**.
No habrá un LLM redactando respuestas, completando hechos ni parafraseando la
fuente. Una respuesta factual solo puede contener texto literal con offsets,
datos estructurados extraídos de ese texto y conectores declarados en templates.

El golden set, la comparación cuantitativa y la calibración de umbrales quedan
para la **última fase**. Antes se construirá una infraestructura modular capaz
de ejecutar todas las técnicas candidatas.

Esto no elimina las pruebas tempranas: habrá pruebas unitarias, de contratos,
offsets, migraciones, Docker y navegador. Se posterga la evaluación de
relevancia con preguntas reales y el ajuste de thresholds.

## Repositorios estudiados y prácticas aprovechables

No se copiará ningún framework completo; se tomarán patrones concretos:

| Repositorio | Práctica útil | Qué no copiar |
|---|---|---|
| Qdrant examples | dense + sparse + fusión dentro del motor, named vectors y prefetch | lógica acoplada a una demo |
| Vespa sample apps | recuperación/ranking por fases y señales de documento + chunk | migrar a una plataforma mayor |
| Pyserini | primera etapa reproducible y separación sparse/dense/hybrid | Java/Lucene en el core |
| Haystack | componentes pequeños conectados por contratos; retriever separado del reader | framework completo y generación |
| DrQA | arquitectura retriever -> extractive reader | stack antiguo como implementación final |
| txtai | ejecución local, configuración declarativa y extras opcionales | orquestación LLM/agents |
| Docling | documento estructurado y chunking jerárquico/token-aware | dependencia pesada obligatoria |
| Unstructured | adapters por formato y extras por tipo documental | instalar todos los parsers |
| RAGFlow | combinar límites de tokens con títulos/secciones | pipeline generativo/VLM |
| Sentence Transformers | retrieve-and-rerank con CrossEncoder | rerankear todo el corpus |
| Hugging Face TEI | servir embeddings/reranker fuera del proceso | volverlo requisito local |
| Rasa | intención, entidades y diálogo como estado explícito | framework conversacional completo |
| interact.js / Floating UI | drag, resize, snap y posicionamiento | añadirlos si Pointer Events basta |

La conclusión común es una tubería multietapa, observable y con componentes
intercambiables, no una función monolítica de “pregunta -> respuesta”.

## Arquitectura objetivo

```text
                         INGESTA
archivo -> parser -> documento estructurado -> chunker -> enriquecedores
        -> embeddings/sparse -> índice versionado -> alias activo

                         CONSULTA
pregunta -> normalizador -> intención/entidades/filtros
         -> búsqueda lexical + densa en paralelo
         -> fusión -> deduplicación -> reranker opcional
         -> expansión parent/vecinos -> selector o reader extractivo
         -> verificación de evidencia -> estado estructurado
         -> renderer de templates -> API -> widget
```

Principios:

- cada etapa recibe y devuelve un esquema versionado;
- ninguna etapa conoce detalles internos de la siguiente;
- las técnicas importantes se seleccionan mediante registry/configuración;
- los índices se construyen inmutables y se activan por alias;
- el modo básico funciona local y offline;
- las dependencias pesadas viven en extras opcionales;
- un componente opcional que falla produce modo degradado explícito.

## Metodología y documentación obligatoria

La metodología no quedará escondida en comentarios del código. Cada técnica
implementada debe tener una ficha técnica mantenida junto con la librería.
Ningún parser, chunker, retriever, fusionador, reranker, extractor o regla de
decisión se considera terminado sin esa ficha.

Plantilla mínima de cada ficha metodológica:

1. **Propósito:** problema concreto que resuelve y por qué existe.
2. **Alcance y no-alcance:** qué casos cubre y cuáles deja fuera.
3. **Entradas y salidas:** esquema, unidades, campos obligatorios y versión.
4. **Algoritmo:** pasos exactos, fórmulas y criterios de desempate.
5. **Supuestos:** idioma, formato, tokenizer, modelo y características del
   corpus de las que depende.
6. **Invariantes:** por ejemplo, offsets exactos, texto literal y orden
   determinista.
7. **Configuración:** parámetros, defaults provisionales y efecto esperado.
8. **Complejidad y recursos:** costo de ingesta/consulta, memoria y modelos.
9. **Modos de fallo y fallback:** cómo se degrada sin inventar respuestas.
10. **Seguridad y privacidad:** datos procesados, persistidos o registrados.
11. **Pruebas técnicas:** contratos e invariantes que demuestran que funciona.
12. **Limitaciones conocidas:** sin ocultar heurísticas o valores sin calibrar.
13. **Procedencia:** papers, repositorios y versiones que inspiraron el método.
14. **Estado:** experimental, estable, deprecado o pendiente de calibración.

Estructura documental propuesta:

```text
docs/
├── arquitectura.md
├── metodologias/
│   ├── parsing.md
│   ├── chunking.md
│   ├── recuperacion.md
│   ├── fusion-y-reranking.md
│   ├── analisis-de-pregunta.md
│   ├── extraccion-y-fidelidad.md
│   ├── estados-y-templates.md
│   └── widget.md
├── decisiones/              # ADR: una decisión técnica por archivo
├── referencia/
│   ├── configuracion.md
│   ├── api-http.md
│   └── widget-web.md
└── ejemplos/
```

Los ADR documentarán alternativas consideradas, decisión, consecuencias y
condiciones para revisarla. Los comentarios del código explicarán el “cómo”
local; las fichas y ADR explicarán el “por qué” del sistema.

## Distribución como librería para sitios web

La V2 se distribuirá como un producto con dos artefactos coordinados. El
navegador no ejecuta el motor Python: el sitio instala el cliente web y este se
conecta al servicio instalado con Python o Docker.

### Motor Python

- wheel `rag-extractivo` instalable desde PyPI o GitHub;
- CLI `rag` para init, carga, indexación, doctor y servicio;
- API HTTP versionada y documentada con OpenAPI;
- ejecución local, como servicio del sitio o mediante imagen Docker;
- extras opcionales para parsing y precisión sin engordar el core.

### Cliente web

Ofrecer tres formas equivalentes:

1. `<script src="https://servidor/widget.js">` para integración inmediata;
2. paquete npm `@rag-extractivo/widget` para bundlers modernos;
3. bundle ESM/UMD autocontenido para self-hosting/CDN.

El widget evolucionará a un Web Component (`<rag-extractivo-chat>`) para
aislar markup/estilos y funcionar con HTML, React, Vue, Svelte o cualquier CMS.
La API JavaScript debe aceptar endpoint, clave pública del widget, tema,
idioma, posición y callbacks sin exigir un framework.

Requisitos de compatibilidad:

- SemVer y matriz widget/API soportada;
- contrato HTTP estable y tipos TypeScript publicados;
- CSS aislado mediante Shadow DOM y tokens configurables;
- ninguna dependencia de rutas del checkout;
- assets incluidos en wheel, npm y release de GitHub;
- configuración por atributos HTML y JavaScript;
- CSP, CORS y autenticación por origen documentados;
- la clave embebida en el navegador se considera identificador público, no
  secreto; la seguridad real combina origen permitido, rate limit y backend;
- ejemplos mínimos para HTML estático, React y WordPress/CMS;
- pruebas del paquete publicado desde un proyecto web vacío.

La documentación de instalación debe distinguir claramente: instalar el
backend, desplegarlo, conectar el widget y personalizar templates/estilos.

## Fase 1 — fundación de la librería

### Contratos y registries

Crear protocolos para `DocumentParser`, `Chunker`, `DenseEncoder`,
`SparseEncoder`, `Retriever`, `FusionStrategy`, `Reranker`,
`IntentClassifier`, `AnswerExtractor`, `EvidenceVerifier` y
`ResponseRenderer`.

Cada implementación se registra con un nombre estable:

```yaml
ingesta:
  parser: builtin
  chunker: hierarchical
recuperacion:
  dense_encoder: e5-small
  sparse_encoder: bm25
  fusion: rrf
  reranker: disabled
extraccion:
  metodo: sentence_selector
```

Así se podrá añadir Docling, otro embedding o un reader extractivo sin
reescribir API ni CLI.

### Esquemas internos versionados

Definir con Pydantic:

- `DocumentRecord` y `ElementRecord`;
- `ChunkRecord` con parent/prev/next;
- `QueryAnalysis`;
- `RetrievalCandidate` con todas sus señales;
- `EvidenceSpan` con offsets absolutos;
- `AssistantResult` con estado, motivo y acciones.

Los payloads Qdrant no deben seguir siendo diccionarios informales repartidos
por el código. Un cambio exige `schema_version` y migrador o reindexación.

### Configuración robusta

- validar todos los YAML al arrancar y con `rag doctor`;
- rechazar claves desconocidas y placeholders inválidos;
- introducir `config_version` y migraciones idempotentes;
- separar ingesta, consulta, presentación y operación;
- generar un snapshot de configuración efectiva;
- reservar variables de entorno para secretos/despliegue.

### Extras de dependencias

```text
rag-extractivo                 # core
rag-extractivo[documentos]     # parsing estructural/OCR
rag-extractivo[precision]      # reranker y reader extractivo
rag-extractivo[servidor]       # despliegue/observabilidad
rag-extractivo[test]           # desarrollo
```

Inspiración de Unstructured: instalar solo formatos/capacidades necesarios.

### Empaquetado y Docker

- corregir `COPY config/`: esa carpeta ya no existe;
- instalar el wheel en la imagen en vez de copiar módulos sueltos;
- obtener la versión FastAPI desde el paquete, no fijar `0.6.0`;
- usar build multi-stage y usuario sin privilegios;
- separar imagen `core` de `precision` si cambia mucho el peso;
- healthcheck desde Python;
- cache de modelos en volumen explícito y modo offline;
- pruebas CI de build, arranque, `/ready` e ingesta;
- mantener documentos, `.env`, caches, tests e índices fuera del contexto
  mediante `.dockerignore`.

### Empaquetado del widget

- separar el código fuente web de los bundles generados;
- producir ESM, UMD y paquete npm sin duplicar la lógica;
- mantener `/widget.js` como vía simple servida por FastAPI;
- generar tipos TypeScript y una API pública pequeña;
- alinear versiones y publicar una matriz de compatibilidad;
- comando `rag widget exportar <carpeta>` para self-hosting;
- smoke tests en proyectos vacíos HTML y Vite;
- releases con wheel, imagen Docker y bundle web de la misma versión.

**Salida:** wheel, imagen y widget web reproducibles; registries,
configuración validada/migrable y documentación metodológica base.

## Fase 2 — ingesta documental sólida

### Parsing mediante adapters

Mantener `builtin` y añadir opcionalmente:

- Docling para PDF/DOCX con layout, headings y tablas;
- Unstructured como alternativa multiformato;
- OCR separado para escaneos;
- Markdown/HTML preservando jerarquía;
- CSV/XLSX como tablas, no párrafos concatenados.

Todos producen el mismo `DocumentRecord`; retrieval no conoce al parser.

### Chunker jerárquico y token-aware

Implementar `hierarchical` como estrategia principal:

1. usar el tokenizer real del encoder;
2. respetar documento > sección > subsección > elemento;
3. no mezclar secciones para alcanzar tamaño mínimo;
4. dividir bloques grandes por oración y después por tokens;
5. mantener listas completas cuando quepan;
6. dividir tablas por filas repitiendo encabezado;
7. conservar captions y títulos como contexto;
8. mantener offsets exactos y mapa serializado-fuente;
9. registrar parent, vecinos, página y tipo;
10. separar `texto_fuente` literal de `texto_embedding` contextualizado.

Estrategias experimentales bajo el mismo contrato:

- `parent_child`: recuperar child y presentar parent acotado;
- `multi_granularity`: chunks cortos/largos en named vectors;
- `late_chunking`: solo para encoders compatibles;
- `line_table`: tablas, código, logs y listados.

### Ingesta incremental e índices inmutables

- fingerprint por archivo y contenido;
- detectar agregado, cambio, renombre y eliminación;
- reindexar solo documentos afectados;
- crear colección nueva antes de activarla;
- alias Qdrant para swap atómico y rollback;
- manifiesto con parser, chunker, tokenizer, modelo y hashes;
- comandos `--dry-run`, listar, activar y eliminar índices.

### Enriquecimiento determinista

Precalcular entidades, fechas, importes, porcentajes, códigos, unidades,
keywords, categoría, relaciones internas y, opcionalmente, embeddings de
oraciones/filas. Conservar siempre el texto original.

**Salida:** corpus estructurado, incremental y listo para varias técnicas sin
reparsear cada experimento.

## Fase 3 — recuperación multietapa

### Correcciones base

- añadir `passage: ` al documento para E5; ya se usa `query: `;
- separar `dense_candidate_k`, `sparse_candidate_k`, `fusion_k`, `rerank_k`
  y `final_k`;
- ejecutar dense/sparse como legs independientes observables;
- conservar rank y score de cada leg;
- usar pools amplios configurables y pocos resultados finales.

### Query processing

Crear `QueryAnalysis` con pregunta original/normalizada, intención provisional,
entidades, restricciones, términos exactos protegidos, filtros de documento o
versión, aliases, posible typo y contexto estructurado.

RapidFuzz puede sugerir correcciones contra entidades/vocabulario. Una
corrección dudosa produce aclaración, nunca reemplazo silencioso.

### Retrieval paralelo y fusión

- BM25 para nombres, códigos y coincidencias exactas;
- dense para paráfrasis;
- filtros Qdrant solo con restricciones inequívocas;
- RRF como opción robusta independiente de escalas;
- DBSF como opción adicional;
- collapse por documento/sección/parent;
- diversidad para no devolver vecinos casi idénticos;
- expansión de vecinos tras identificar el ancla.

Vespa, Pyserini y Faiss convergen en el patrón: primera etapa barata con alto
recall y etapa cara sobre shortlist.

### Reranker opcional

Implementaciones `disabled`, `cross_encoder` local, endpoint TEI y, más tarde,
late-interaction/ColBERT. Candidatos multilingües iniciales:

- `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`;
- `BAAI/bge-reranker-v2-m3` como alternativa más pesada.

El reranker solo asigna scores. Debe tener timeout y fallback al orden
fusionado con estado `degradado`.

### Cache y serving

- una instancia por modelo;
- LRU de embeddings de consultas normalizadas;
- batches durante ingesta;
- servidor separado opcional para encoder/reranker;
- circuit breaker, timeout y límites CPU/GPU;
- warm-up verificable en `/ready`.

**Salida:** recuperación multietapa extensible, todavía sin thresholds
calibrados con golden set.

## Fase 4 — comprensión, extracción y templates

### Identificación de preguntas

Taxonomía: definición, dato puntual, lista, requisito, procedimiento,
comparación, condición/excepción, sí/no, ubicación documental,
aclaración/seguimiento, conversacional/meta y genérica.

Capas:

1. reglas configurables de alta precisión;
2. slots y entidades del dominio;
3. clasificador pequeño opcional (TF-IDF + logística o spaCy `textcat`);
4. salida `desconocida`, que usa el flujo extractivo genérico.

### Contexto conversacional acotado

Guardar solo intención anterior, entidades/filtros confirmados, documento o
sección activa, opciones presentadas e IDs de templates recientes. Esto permite
“¿y para el X200?” mediante una máquina de estados, sin conversación abierta.

### Extracción exacta

Implementaciones de `AnswerExtractor`:

- `sentence_lexical`;
- `sentence_dense` con unidades precalculadas;
- `span_reader` de QA extractiva;
- `table_cell` con headers;
- `multi_evidence` para listas/comparaciones.

Guardias: span literal, offsets válidos, no unir spans como una frase,
conservar negación/condición/excepción, detectar contradicciones y fallback al
selector literal.

### Planificador real

Reemplazar el plan siempre `extractivo`:

- intención + slots -> plan;
- slots faltantes -> `necesita_aclaracion`;
- valores incompatibles -> `conflicto_documental`;
- evidencia parcial -> `respuesta_parcial`;
- intención desconocida -> extractivo genérico.

### Templates V2

```yaml
schema_version: 2
presets:
  cercano:
    respuesta_directa:
      aperturas:
        - "Encontré el dato exacto:"
        - "El documento indica lo siguiente:"
    necesita_aclaracion:
      mensajes:
        - "Encontré varias opciones. ¿A cuál te refieres?"
planes:
  procedimiento:
    conectores: ["Primero", "Luego", "Finalmente"]
    requiere_orden: true
```

Incluir presets `breve`, `cercano`, `formal`, `accesible`; variantes por
estado/intención; no repetición por sesión; formatters de unidades/fechas;
bloques de apertura, evidencia, salvedad, cita y acción; validación Pydantic.
Ningún placeholder introduce un valor sin evidencia.

### Estados V2

`respuesta_directa`, `respuesta_parcial`, `relacionado`,
`necesita_aclaracion`, `multiples_respuestas`, `conflicto_documental`,
`sin_respuesta`, `fuera_dominio`, `conversacional`, `degradado`, `saturado`,
`no_listo` y `error_temporal`.

Separar `estado`, `motivo`, `mensaje_usuario`, `opciones`,
`puede_reintentar`, `confianza` y `evidencias`.

**Salida:** respuesta literal específica y aclaración antes que elección
arbitraria.

## Fase 5 — widget y estilos

### Interacción

- drag desde header con Pointer Events;
- clamp al viewport y snap opcional;
- posición/tamaño versionados en `localStorage`;
- restablecer posición y resize opcional;
- drawer/fullscreen móvil sin drag;
- chips de aclaración/múltiples respuestas;
- copiar con cita, abrir fuente, retry y feedback;
- exportar conversación con fuentes;
- eventos `ready`, `open`, `answer`, `citation-open`, `feedback`.

Primero Pointer Events nativo. `interact.js` solo para resize + inercia + snap
+ multitouch; Floating UI para previews, menús y tooltips.

### Styles V2 y accesibilidad

- posición, z-index, breakpoints y tamaños min/preferido/max;
- colores/iconos por estado y densidad compacta/cómoda;
- bubble, drawer/fullscreen;
- claro, oscuro, sistema y alto contraste;
- avatar/launcher configurables;
- foco visible, `prefers-reduced-motion`, skeleton y errores;
- teclado completo, focus trap y devolución de foco;
- drag nunca como única forma de posicionar;
- zoom 200%, viewport estrecho y Shadow DOM;
- CSP compatible, sin `eval` ni HTML en respuestas.

### Integración web estable

- custom element con ciclo de vida `connectedCallback`/`disconnectedCallback`;
- múltiples widgets en una misma página sin IDs globales ni estilos cruzados;
- carga diferida del widget y del historial;
- destrucción limpia de listeners, timers y peticiones;
- API de eventos y métodos documentada;
- fallback visible cuando el backend no está disponible;
- ejemplos copiables de `<script>`, npm, React y CMS;
- compatibilidad comprobada en navegadores soportados.

**Salida:** widget movible, adaptable, accesible, tematizable e instalable en
sitios web sin depender del framework anfitrión.

## Fase 6 — operación y mantenibilidad

### Observabilidad sin calibrar

Registrar request, versión de pipeline/índice, intención/filtros, latencia por
etapa, candidatos por etapa, estado/motivo y fallbacks. No registrar pregunta
o documento completo por defecto. Añadir diagnóstico protegido y telemetría
opt-in. Se recolectan señales, todavía no se eligen thresholds finales.

### Resiliencia y seguridad

- timeouts y concurrencia por etapa;
- circuit breaker para Qdrant/model server;
- readiness separado de liveness;
- backpressure y cola acotada;
- cierre limpio de clientes/locks;
- límites de archivo, páginas, chunks y tiempo;
- API keys rotables, CORS estricto y URLs allowlisted/firmadas;
- protección contra zip bombs/PDF gigantes y contenido activo;
- SBOM y escaneo de dependencias.

### Pruebas de infraestructura

Antes del golden set: contratos, offsets/substring, chunking sin pérdida,
tablas/headings, incremental/rollback, migraciones, fallbacks, wheel externo,
Docker build/health, compatibilidad API, Playwright/accesibilidad, carga básica
y cierre de recursos. También se prueba cada modalidad de instalación web
desde un proyecto vacío y la compatibilidad entre versiones de widget/API.

**Salida:** sistema operable y resistente, listo para medir calidad.

## Fase 7 — golden set y calibración final

Solo al terminar las fases anteriores:

1. construir preguntas reales por intención, formato y dificultad;
2. separar desarrollo/prueba;
3. marcar documentos, secciones y offsets;
4. comparar chunkers, fusión, pools, rerankers y extractores;
5. medir Recall@k, MRR, nDCG, exact match, token-F1, falsas respuestas y
   falsas abstenciones;
6. medir p50/p95, memoria, índice e ingesta;
7. calibrar estados/confianza;
8. elegir defaults `core` y `precision`;
9. congelar configuración y publicar decisión.

Hasta aquí, cualquier threshold se marca `sin_calibrar` y no se presenta como
garantía de calidad.

## Orden exacto

1. contratos, schemas y registry;
2. fichas metodológicas base, ADR y referencia de contratos;
3. configuración y migraciones;
4. wheel/Docker/widget/CI y extras;
5. modelo documental estructurado;
6. chunker jerárquico token-aware;
7. ingesta incremental + índices inmutables/alias;
8. corrección E5 `passage:`;
9. legs y candidate pools separados;
10. fusión, collapse, diversidad y parent/neighbor;
11. reranker y model serving opcional;
12. query analysis, intención y contexto acotado;
13. extractores de oración/span/tabla;
14. planner, templates y estados V2;
15. widget drag/mobile/styles/accesibilidad e integraciones web;
16. observabilidad, resiliencia y seguridad;
17. golden set y calibración final.

## Definición de “lista para calibrar”

- cambiar parser/chunker/fusión/reranker/extractor requiere registry/config;
- toda respuesta conserva evidencia y offsets;
- cada fallo tiene estado y fallback;
- índices reproducibles, activables y reversibles;
- core local/offline y precision opcional;
- wheel, Docker, npm y widget standalone probados automáticamente;
- cada metodología tiene ficha, limitaciones y ADR cuando corresponde;
- instalación documentada para backend y sitios web;
- señales necesarias para comparar técnicas registradas;
- ningún camino genera afirmaciones libres.

## Referencias primarias

- Qdrant examples: <https://github.com/qdrant/examples>
- Qdrant: <https://github.com/qdrant/qdrant>
- Vespa sample apps: <https://github.com/vespa-engine/sample-apps>
- Pyserini: <https://github.com/castorini/pyserini>
- Haystack: <https://github.com/deepset-ai/haystack>
- DrQA: <https://github.com/facebookresearch/DrQA>
- txtai: <https://github.com/neuml/txtai>
- Docling: <https://github.com/docling-project/docling>
- Unstructured: <https://github.com/Unstructured-IO/unstructured>
- RAGFlow chunker: <https://github.com/infiniflow/ragflow/blob/main/docs/guides/agent/ingestion_pipeline/configure_chunker_component.md>
- Sentence Transformers CrossEncoder: <https://www.sbert.net/docs/cross_encoder/usage/usage.html>
- Hugging Face TEI: <https://github.com/huggingface/text-embeddings-inference>
- Hugging Face QA extractiva: <https://huggingface.co/docs/transformers/tasks/question_answering>
- Rasa: <https://github.com/RasaHQ/rasa>
- ColBERT: <https://github.com/stanford-futuredata/ColBERT>
- interact.js: <https://github.com/taye/interact.js>
- Floating UI: <https://github.com/floating-ui/floating-ui>
