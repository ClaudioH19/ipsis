# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto sigue [SemVer](https://semver.org/lang/es/). Mientras la versión
sea 0.x, un cambio menor puede romper compatibilidad y se indica como tal.

## [0.8.0] - 2026-10-04

Cierra el plan V3: cascada con señales léxicas, modelos ONNX por perfil,
multilenguaje, calibración con riesgo controlado, personalidad del widget y
despliegue propio. La historia detallada (tareas, mediciones y hallazgos)
queda en git; las decisiones, en `docs/decisiones/` y `docs/metodologia/`.

**Requiere reindexar** y migra la configuración sola (`config_version` 4).

### Agregado

- **Perfiles de instalación** `light`, `medium` y `heavy` (más `bm25`, solo
  para diagnóstico), con presupuesto de latencia, modelos y umbrales propios.
  `rag perfil mostrar|cambiar`. Ver [ADR 0003](docs/decisiones/0003-onnx-y-perfiles.md).
- **Modelos ONNX en CPU** sin torch: codificador e5, reranker cross-encoder y
  lector QA extractivo (estilo SQuAD 2.0), con caché global y uso sin red.
  `rag modelos listar|descargar|verificar|exportar`.
- **Cascada de etapas** y política `cascada_v1` con señales explicables
  (`s_ret`, `s_oov`, foco, `s_foco`, `s_cov`, `s_rr`, `s_qa`), salida temprana
  sin modelos y concordancia en heavy. Ver
  [ADR 0004](docs/decisiones/0004-cascada-lexica-y-retiro-de-guardias-regex.md).
- **Capa léxica propia:** un único `terminos()` con stem Snowball, BM25 con ids
  por hash e IDF en Qdrant, estadísticas del corpus legibles y TF-IDF.
- **Multilingüe:** paquetes de idioma `es`, `en` y `pt` (stemmer, entidades
  con palabras, patrones conversacionales, mensajes y textos del widget);
  otros idiomas con reglas universales.
- **Golden del cliente:** `rag golden plantilla|importar|validar|exportar`
  (CSV, JSONL y SQuAD 2.0), con pares mínimos «mismo tema, dato ausente».
- **Calibración** `rag calibrar [--alfa] [--aplicar]`: elige umbrales en `dev`
  con cota de Clopper-Pearson ≤ α, verifica en `test` y distingue
  `CALIBRADO`, `MUESTRA_INSUFICIENTE` y `SIN_UMBRAL_SEGURO`. Se aplica solo si
  su procedencia coincide con el perfil, los modelos y el corpus indexado.
- **Evaluación:** banco universal de regresión (90 casos en tres idiomas),
  métricas de cobertura y riesgo, `rag benchmark --perfiles`.
- **Operación:** `rag doctor` con acciones, `rag preguntar --diagnostico`,
  registro de consultas opcional y `rag auditar [--desde] [--hasta]`, que
  verifica que cada evidencia siga siendo literal.
- **Personalidad:** 7 tonos × 18 situaciones × 5 variantes por idioma (1.890
  plantillas con linter y neutralidad), avatar animado «Folio» que reacciona a
  cada evento y sigue el puntero, `rag personalidad …`.
- **Widget** responsive con ubicación configurable, citas siempre visibles
  con el tramo marcado, `RagChat.avatar` y enlace «Código fuente».
- **Administración:** API `/admin` y panel `/admin/panel` con token, HTTPS en
  producción, bloqueo tras intentos fallidos y auditoría; modos `desarrollo` y
  `produccion`.
- **Despliegue:** imagen Docker por perfil con los modelos incluidos,
  `rag desplegar preparar` (proyecto, índice, compose con Caddy y LEEME en el
  idioma del proyecto) y `/ready` con el diagnóstico del proyecto.
- CI: pruebas en Linux y Windows, navegador, build reproducible del motor del
  avatar, wheel limpio e imagen sin red.

### Cambiado

- **Licencia:** AGPL-3.0-only.
- Estructura de proyecto: `configuracion/dominio.yaml` reemplaza a
  `dominios/<perfil>/perfil.yaml` y `categorias.yaml`; los textos pasan al
  paquete de idioma (sobrescribibles en `idioma.yaml`); el índice vive en
  `.rag/indice/` y el golden en `golden/`. Cualquier comando migra un proyecto
  anterior.
- Código por capas (`nucleo`, `configuracion`, `lenguaje`, `ingesta`,
  `modelos`, `indice`, `consulta`, `evaluacion`, `aplicacion`, `cli`,
  `servicio`) con una prueba que impide dependencias hacia capas superiores;
  CLI con un comando por clase.
- Las entidades con palabras se generan desde el paquete y su `valor_norm` ya
  no depende del idioma (`2024-03-15`, `6_mes`). Nuevas entidades universales:
  fechas numéricas y montos con moneda. El tipo `nota` se reemplaza por
  `decimal`.
- En `ok`, la respuesta muestra primero la oración que responde; en
  `relacionado` nunca se presenta un tramo como respuesta.

### Eliminado

- Las guardias regex por tipo de pregunta y la lista de «palabras
  generales»: las reemplazan `s_foco` y `s_oov`.
- torch y sentence-transformers en producción (quedan en el extra de
  desarrollo `[exportar]`).
- La política `layered_v1` (los proyectos migran a `cascada_v1`).
- Planes y bitácoras anteriores, `requirements*.txt` y el evaluador antiguo.

### Descartado tras medirlo

- Backend SQLite FTS5: produjo un falso `ok` ante una pregunta ambigua.
  Qdrant queda como único backend.
- Chunking por cohesión léxica (`texttiling_v1`): mismos estados que cortar
  por sección y más falsos `ok` que el chunker actual.
- `acuerdo` (denso frente a BM25) como señal de la política: sin efecto
  medible y +4,6 ms de p95.

### Corregido

- El wheel no incluía los perfiles (`rag/recursos/perfiles/`): una
  instalación normal fallaba con «perfil desconocido».
- `12,5%` se extraía como el porcentaje `5`.
- La selección de oraciones perdía el texto anterior a un punto no seguido de
  espacio (por ejemplo, «1.5»).
- Los pasajes se indexaban sin el prefijo `passage: ` que exige e5.
- Los archivos de despliegue generados en Windows salían con CRLF.

## [0.7.0]

Versión inicial publicada en el repositorio.
