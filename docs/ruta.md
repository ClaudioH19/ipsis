# Ruta de trabajo

Este documento reemplaza el orden de las fases 3 a 7 de
[PLAN_V2.md](../PLAN_V2.md). La visión, las restricciones (respuestas
literales, sin LLM) y los ADR no cambian.

Principio rector: **primero un flujo correcto, intercambiable y observable;
después medir; solo entonces optimizar**. Los perfiles de instalación, extras y
umbrales definitivos se decidirán con evidencia. C.3 ya resolvió una decisión:
Qdrant es el único backend soportado para el lanzamiento.

El estado de ejecución, los commits y el siguiente paso se registran en
[avance.md](avance.md). Este documento describe el orden y los criterios de
cierre, no duplica la bitácora.

## Estado de partida

- El registry y los contratos de [rag/componentes.py](../rag/componentes.py)
  existen, pero el flujo de ejecución todavía no los consume por completo.
- `consultar()` en [rag/servicio/api.py](../rag/servicio/api.py) concentra
  orquestación y conoce implementaciones concretas.
- La recuperación ya tiene un contrato con filtros, señales e inventarios,
  pero falta conectarlo de punta a punta.
- `ChunkRecord` ya ganó los campos tipados necesarios y existen adaptadores de
  payload; falta usar esos tipos dentro del pipeline.
- La abstención, que es la lógica de seguridad más importante, sigue sin un
  contrato propio.
- Las pruebas de caracterización congelan el comportamiento actual y revelan
  problemas de calidad que deben medirse antes de optimizar.

---

## Fase 0: higiene y línea base

Esta fase deja el repositorio en condiciones de cambiar la arquitectura sin
confundir defectos previos con regresiones.

- Separar el trabajo previo en commits con sentido.
- Mantener una línea base reproducible de `pytest`.
- Retirar referencias internas que un colaborador externo no puede seguir.
- Mantener el dominio genérico libre de entidades académicas heredadas.
- Disponer de `CHANGELOG.md` y CI en Linux y Windows.
- Registrar cualquier cambio que obligue a reindexar.

La elección de licencia queda diferida. No bloquea el desarrollo local, aunque
sí debe resolverse antes de una publicación formal.

### Hecho cuando

- La suite tiene una línea base conocida y reproducible.
- Los cambios de esquema o normalización declaran si requieren reindexación.
- El repositorio puede empaquetarse y probarse en un entorno limpio.

---

## Fase A: arquitectura ejecutable e intercambiable

**Objetivo.** Que el flujo de consulta use contratos y componentes reales del
registry, sin conocer Qdrant ni modelos concretos, y que conserve el contrato
HTTP mientras se vuelve observable y comprobable.

### A.0 Red de seguridad

- Mantener pruebas de caracterización sobre un corpus sintético pequeño.
- Congelar, para preguntas representativas, `estado`, `plan`, texto y offsets.
- Cubrir respuesta exacta, relacionada, fuera de dominio, premisa falsa y
  conversación.

Estas pruebas definen el comportamiento heredado. Si una corrección de
fidelidad necesita cambiarlo, el cambio debe ser explícito, versionado y
justificado por una prueba nueva.

### A.1 Contrato de recuperación

El retriever debe resolver las tres necesidades reales del pipeline:

1. producir señales de confianza para abstención;
2. recuperar candidatos de producción;
3. ejecutar recuperaciones dirigidas por entidad.

El contrato incluye `FiltroEntidad`, `ResultadoRecuperacion`,
`SenalesRecuperacion`, candidatos con puntaje e inventarios propios del índice.
Cada backend traduce su señal a una escala documentada; no se presupone que
todos producen coseno denso.

### A.2 Política de abstención

Extraer la decisión por capas de `pipeline.py` y `consultar()` sin reescribirla
durante el traslado.

#### A.2a Caracterizar las capas

- Probar por separado fuera de dominio, premisa incompatible, zona gris y
  confianza alta.
- Cubrir los límites exactos de los umbrales heredados.
- Registrar qué candidato y señal provocan la decisión.

#### A.2b Extraer el contrato

Crear `AbstentionPolicy`: recibe análisis de pregunta, señales y candidatos, y
devuelve una `DecisionAbstencion` estructurada con, al menos:

- `estado` y `motivo`;
- capa que tomó la decisión;
- señal de confianza utilizada;
- candidato elegido, si corresponde.

La implementación heredada se registra como `layered_v1`.

#### A.2c Integrar mediante el registry

- Resolver la política desde `componentes.abstention_policy`.
- Fallar al arrancar y en `rag doctor` si el nombre u opciones son inválidos.
- Mantener verdes las pruebas de caracterización.

### A.3 Frontera de tipos

Aplicar los tipos en las fronteras entre componentes:

- el retriever entrega candidatos que contienen `ChunkRecord`;
- el selector produce `EvidenceSpan`;
- el verificador recibe evidencia tipada;
- la política de abstención recibe candidatos tipados;
- solo `chunk_desde_payload()` y `payload_desde_chunk()` conocen el formato
  persistido.

`doc_titulo`, `version`, `tiene_excepcion`, `tiene_condicion` y `entidades` son
campos tipados de `ChunkRecord`. Las funciones internas de redacción pueden
seguir usando estructuras simples mientras no crucen una frontera pública.

### A.4 `Motor` orquestador

Crear `rag/servicio/motor.py` en cortes pequeños.

#### A.4a Envolver el flujo existente

`Motor.consultar(pregunta, id_sesion) -> AssistantResult` reproduce primero el
flujo actual sin rediseñarlo.

#### A.4b Separar etapas

Dividir la consulta en análisis, recuperación, abstención, selección de
evidencia, verificación y construcción del resultado.

#### A.4c Resolver componentes

`Motor.desde_configuracion(cfg)` construye cada componente por nombre con el
registry y valida sus opciones al arrancar.

#### A.4d Añadir diagnóstico

Cada consulta produce un diagnóstico estructurado con backend, latencias por
etapa, candidatos, señales, decisión de abstención, evidencia y advertencias.
El diagnóstico sirve para pruebas y operación; no forma parte obligatoria del
contrato HTTP público.

### A.5 Aplicación sin estado global

- Introducir `crear_app(motor) -> FastAPI`.
- Dejar en `api.py` seguridad, admisión, endpoints, manejo de errores y mapeo
  de `AssistantResult` al contrato V1.
- Usar `lifespan` solo para `warmup()` y cierre de recursos.
- Inyectar plantillas y perfil en el `Motor`.
- Eliminar la dependencia del directorio de trabajo al cargar plantillas.
- Mantener una entrada de producción compatible para CLI y despliegues.
- Unificar `recuperacion.*` y `componentes.*` mediante una migración idempotente
  de `config_version`, con una sola fuente de verdad al terminar.

### A.6 Contratos e intercambio

Crear una matriz de pruebas por familia de componente:

| Componente | Invariantes |
|---|---|
| Retriever | orden determinista, filtros, señales válidas e inventarios |
| AbstentionPolicy | decisión y motivo deterministas para la misma entrada |
| Selector | texto literal y offsets exactos |
| Verificador | nunca acepta evidencia fuera del fragmento |
| Motor | resultado estable y diagnóstico completo |

Pruebas de intercambio obligatorias:

1. un retriever falso en memoria;
2. una política falsa que fuerce cada estado;
3. `Motor.consultar()` de punta a punta sin Qdrant, torch ni
   SentenceTransformers.

### A.7 Guardia mínima de fidelidad

Sin recalibrar todavía la recuperación, impedir que un resultado sea `ok` si
el dato solicitado no tiene respaldo literal suficiente en la evidencia. El
primer foco son entidades verificables como precios, fechas, porcentajes y
cantidades.

Esta tarea corrige falsos positivos de alto riesgo; no intenta mejorar recall,
ranking ni estilo. Todo cambio frente a la caracterización se documenta como
corrección deliberada.

### Hecho cuando

- `api.py` es una capa HTTP delgada y `Motor` contiene la orquestación.
- `api.py`, `pipeline.py` y `motor.py` no importan Qdrant,
  SentenceTransformers ni `ColeccionQdrant`.
- Cambiar un componente en configuración cambia la implementación ejecutada.
- El flujo completo puede probarse en memoria sin dependencias pesadas.
- Los payloads solo aparecen en los adaptadores autorizados.
- La caracterización sigue verde, salvo correcciones de fidelidad explícitas y
  versionadas.
- La suite rápida corre en CI.

### Fuera de alcance

Recalibrar umbrales, añadir técnicas nuevas, rediseñar el widget y corregir el
prefijo `passage:` de E5. Todo ello requiere medición o reindexación y se trata
en fases posteriores.

---

## Fase B: backend léxico SQLite FTS5 — experimento descartado

**Decisión (2026-09-30).** La fase se implementó y probó completa, pero C.3
detectó un falso `ok` bloqueante ante la pregunta ambigua «¿Cuánto dura?». Para
el lanzamiento se elige Qdrant y se retiran la implementación SQLite, su
configuración, pruebas, CI y documentación operativa. El detalle siguiente se
conserva como registro histórico del experimento, no como funcionalidad vigente.

**Objetivo.** Construir una segunda implementación completa que no necesite
Qdrant ni embeddings, demostrar que la abstracción de la Fase A es real y
obtener una línea base léxica medible.

El objetivo se cumplió como experimento; SQLite no pasa a producto.

> Todo el contenido B.1–B.5 que sigue es histórico. Describe lo que se evaluó,
> no instrucciones ni componentes disponibles en la versión vigente.

### B.1 Índice mínimo válido

Crear `.cache/indice/<nombre>.sqlite` con:

- `chunks` y payload completo en JSON;
- tabla virtual `chunks_fts` con `unicode61 remove_diacritics 2`;
- relación `entidades(valor_norm, chunk_id)`;
- manifiesto con esquema, chunker, pipeline, hash del corpus, fecha y
  estadísticas léxicas.

La escritura se hace en un archivo temporal y se renombra al terminar. El
servicio abre el índice en solo lectura. Se prueban versión incompatible,
índice incompleto, corrupción detectable y lectores concurrentes.

### B.2 Recuperación FTS segura

- Tokenizar y quitar stopwords con las utilidades comunes.
- Entrecomillar cada término antes de formar la consulta FTS.
- Ordenar con `bm25()` y desempatar por `chunk_id`.
- Aplicar filtros mediante la tabla de entidades.
- Cubrir consulta vacía, solo stopwords, acentos, mayúsculas, operadores FTS,
  comillas, asteriscos, términos repetidos e intentos de inyección.

### B.3 Confianza léxica experimental

Implementar la cobertura de términos ponderada por IDF como señal inicial,
identificada como `idf_coverage_v1`:

- valor acotado en `[0, 1]`;
- términos encontrados y ausentes disponibles en diagnóstico;
- margen entre los dos primeros candidatos;
- estado explícito `sin_calibrar`;
- umbrales separados de los del backend denso.

La señal no se presenta como probabilidad. Su permanencia y sus umbrales se
deciden en la Fase C.

### B.4 Corte vertical de ingesta y CLI

Completar primero el ciclo:

```text
cargar -> indexar -> consultar -> doctor
```

Después adaptar `/ready`, warmup y detalles de CLI:

- separar en `corpus.py` lo genérico de la escritura Qdrant;
- construir el almacén correspondiente al retriever configurado;
- informar backend activo y verificaciones específicas;
- no cargar ni calentar un encoder si el backend no lo necesita.

### B.5 Aislamiento y contratos por backend

- Parametrizar invariantes de pipeline y API para Qdrant y SQLite.
- Envenenar importaciones pesadas durante pruebas unitarias.
- Ejecutar en CI un entorno limpio sin Qdrant, torch ni
  SentenceTransformers.
- Verificar carga, indexación y consulta completas en ese entorno.
- Documentar metodología, limitaciones y señal de confianza en
  `docs/metodologias/recuperacion-lexica.md`.

### Hecho cuando

- `rag init && rag cargar && rag indexar && rag servir` funciona con
  `sqlite_fts` sin dependencias pesadas instaladas.
- Los invariantes de literalidad, offsets, guardias y estados pasan en ambos
  backends.
- Un fallo a mitad de indexación no reemplaza un índice válido.
- La señal léxica está documentada como experimental y sin calibrar.

### Fuera de alcance

Lematización, BM25 propio en memoria, vectores dentro de SQLite, modo en el
navegador y elección del backend predeterminado.

---

## Fase C: evaluación y calibración reproducibles

**Objetivo.** Convertir opiniones sobre recuperación y calidad en decisiones
respaldadas por datos.

### C.1 Banco de evaluación versionado

- Definir un formato con pregunta, estado esperado, respuesta literal y
  offsets.
- Etiquetar preguntas exactas, paráfrasis, sin respuesta, premisa falsa,
  ambiguas y conversacionales.
- Mantener separados un conjunto sintético reproducible y un golden set manual
  de 30–50 preguntas sobre un corpus concreto.
- Evitar que los casos usados para calibrar sean los únicos usados para medir.

### C.2 Métricas por etapa

`rag eval` informa, al menos:

- Recall@k y MRR;
- tasa de falsos `ok`;
- precisión y distribución de abstención;
- exactitud literal y de offsets;
- longitud excesiva de respuesta;
- latencia por etapa;
- resultados por backend y categoría de pregunta.

La tasa de falsos `ok` es bloqueante: una mejora de recall no compensa una
degradación relevante de fidelidad.

### C.3 Comparación y calibración

- Comparar inicialmente SQLite, Qdrant denso e híbrido con el mismo banco;
  después de la decisión, mantener reproducible la comparación entre los modos
  vectorial e híbrido de Qdrant.
- Calibrar por combinación de backend, corpus o perfil y versión de señal.
- Guardar configuración, versión de índice y dataset junto a cada resultado.
- Emitir un informe reproducible que permita decidir backend predeterminado,
  umbrales iniciales, utilidad del híbrido y separación de extras.

Al terminar esta fase se eligió Qdrant como único backend soportado. Los
umbrales definitivos siguen diferidos hasta contar con el golden set manual.

### Hecho cuando

- Otra persona puede reproducir la tabla comparativa desde un comando.
- Cada umbral publicado tiene dataset, métrica y versión asociados.
- Los defectos conocidos de calidad tienen una medición inicial.

---

## Fase D: integración web mínima verificable

**Objetivo.** Servir un corpus y conectar una web con el menor número de pasos,
sin ampliar todavía la superficie de distribución.

Orden de entrega:

1. `rag servir <carpeta>` crea o completa el proyecto necesario en caliente.
2. `/health` informa que el proceso vive y `/ready` diagnostica el backend.
3. Presets del widget (`minimal`, `editorial`, `contraste`) administrables con
   `rag widget tema listar|aplicar|vista-previa`; aplicar un preset fusiona un
   tema validado y no obliga a editar YAML a mano.
4. La vista previa genera un mockup local con respuestas `ok`, relacionadas,
   sin respuesta y conversacionales, incluidas citas cortas y extensas.
5. `/config` expone de forma pública y solo lectura el preset y las opciones de
   presentación que necesita el widget. Cualquier futura escritura HTTP exigirá
   autenticación administrativa distinta de la clave pública del widget.
6. `rag widget exportar <carpeta>` genera `widget.js` y un snippet verificable.
7. Web Component `<rag-extractivo-chat>` con Shadow DOM, atributos y eventos.
8. Ejemplos ejecutables para HTML estático, React y WordPress.
9. Pruebas de navegador para teclado, móvil, accesibilidad y errores de red.
10. Wheel en entorno limpio e imagen Docker en CI.

Se posponen npm, ESM/UMD y tipos TypeScript hasta estabilizar el Web Component.

### Hecho cuando

- Una carpeta de documentos puede servirse y consultarse con un comando.
- Paleta, tipografía, forma, respuestas y citas pueden previsualizarse antes de
  publicar, y el preset seleccionado es reproducible desde consola.
- Los ejemplos se prueban automáticamente, no solo se documentan.
- El widget es utilizable con teclado y en una pantalla móvil.

---

## Fase E: calidad guiada por experimentos

**Objetivo.** Introducir una técnica por vez y conservarla solo si mejora las
métricas de la Fase C sin degradar fidelidad.

Cada experimento registra:

```text
hipótesis -> cambio aislado -> evaluación -> decisión
```

Orden inicial recomendado, sujeto a los resultados de C:

1. corregir el prefijo `passage:` de E5 y reindexar;
2. medir y ajustar chunking, incluidas tablas y jerarquía;
3. añadir análisis de intención, slots y desambiguación;
4. incorporar contexto conversacional acotado;
5. evaluar un reranker opcional.

No se combinan varias técnicas nuevas en una misma medición si eso impide
atribuir el resultado.

### Hecho cuando

- Cada técnica tiene comparación antes/después reproducible.
- Las técnicas sin mejora neta se descartan o quedan documentadas como
  experimentales.
- Ninguna mejora aumenta de manera inaceptable los falsos `ok`.

---

## Fase F: producto y diferenciación

Esta fase se divide para que observabilidad, nuevas fuentes y distribución no
se bloqueen entre sí.

### F.1 Observabilidad y auditoría

- Registrar preguntas sin respuesta para detectar vacíos documentales.
- Dar al mantenedor un panel o informe accionable.
- Implementar `rag audit` para verificar que las respuestas son subcadenas
  literales del corpus.

### F.2 Fuentes y citas

- Ingesta desde sitemap, sitio y Markdown de documentación.
- Citas con resalte exacto y enlace al pasaje de origen.

### F.3 Integraciones

- Servidor MCP como herramienta de recuperación literal.

### F.4 Distribución

- Definir perfiles y extras a partir de los resultados de la Fase C.
- Mantener comprobaciones de instalación mínima por perfil.

## Secuencia y puertas de fase

El orden previsto es:

```text
Fase 0 -> A.0/A.1 -> A.2 -> A.3 -> A.4 -> A.5 -> A.6 -> A.7
       -> Fase B -> Fase C -> Fase D -> Fase E -> Fase F
```

- B no empieza hasta que el intercambio de componentes esté probado en A.6.
- C puede preparar datasets antes, pero no calibra hasta que B esté completo.
- D puede avanzar tras A, pero su cierre exige un backend verificado.
- E depende de la línea base y las métricas de C.
- F.1 puede adelantarse si no altera el pipeline; F.4 y F.5 dependen de C.

Cada paso debe cerrar con:

- commit identificado por el paso;
- pruebas ejecutadas y resultado;
- cambios observables deliberados;
- migraciones o reindexación necesarias;
- actualización simultánea de [avance.md](avance.md).

## Fuera de alcance hasta tener evidencia

Se posponen Docling/Unstructured, ColBERT, servidor TEI, circuit breakers,
`late_chunking`, `multi_granularity`, `interact.js`, Floating UI, exportación
de conversación, SBOM, la taxonomía completa de estados y el plan definitivo
de extras. No se abandonan; se reconsideran cuando una métrica o necesidad de
producto los justifique.

## Decisiones diferidas

No se resuelven durante este replanteamiento:

1. licencia del proyecto;
2. momento y destino de publicación de la rama;
3. umbrales definitivos por modo y perfil de Qdrant;
4. separación de dependencias en extras;
5. técnicas de calidad que pasarán de experimento a producto.

Cada decisión se tomará en la puerta de fase correspondiente, con resultados
reproducibles o una necesidad concreta de distribución.
