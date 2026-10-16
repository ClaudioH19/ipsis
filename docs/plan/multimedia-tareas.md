# Tareas: fichas multimedia en un carril aparte

Análisis y fases: [multimedia.md](multimedia.md). Estado de cada tarea:
[multimedia-avance.md](multimedia-avance.md).

Este archivo está escrito para que cada tarea la ejecute un agente (Sonnet
5.5) en una sesión propia, sin depender del contexto de otra conversación.
Todo lo que el agente no podría deducir leyendo el código está escrito
abajo, en «Reglas fijas» y en los puntos ⚠ de cada tarea.

## Cómo trabajar una tarea

1. Leer este archivo completo, [multimedia.md](multimedia.md) y la fila de la
   tarea en el avance.
2. Trabajar **solo** en la rama asignada a la sesión (nunca `main`). No hacer
   merge a `main`, no abrir PR y no hacer push a otra rama sin pedido
   explícito del usuario.
3. Hacer **una tarea por sesión**. Si depende de otra que no está ✅,
   detenerse e informarlo.
4. Al llegar a un punto ⚠: **detenerse y preguntar al usuario**, con las
   opciones y una recomendación. No elegir por cuenta propia.
5. Al terminar: pruebas en verde, commit con mensaje descriptivo, push a la
   rama y actualizar la fila del avance (estado, fecha, commit, notas y
   cifras medidas).

Estados del avance: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado ·
⚠ espera al usuario.

## Comandos

- Preparar: `uv sync --locked --extra test --extra browser`.
- `PYTEST` = `uv run --locked --extra test pytest -q -p no:cacheprovider`.
  Durante el desarrollo, solo las carpetas afectadas; antes del commit,
  `PYTEST -m "not slow and not modelos and not browser"` y, si se tocó el
  widget o el panel, `PYTEST -m browser`.
- Modelos: `IPSIS_MODELS_DIR=.cache/modelos`; descargar con
  `ipsis models download --profile medium`.

## Reglas fijas (no se deducen del código)

1. **Nunca inventar cifras.** Si los modelos no se descargan, la tarea queda
   ⛔ con el error exacto.
2. **Sin generación ni análisis del contenido**
   ([ADR 0001](../decisions/0001-non-generative-answers.md)). No se
   transcribe audio, no se describen imágenes ni escenas, no se leen los
   archivos multimedia más allá de validar su tipo y tamaño. Lo que se
   muestra de una ficha es su texto literal.
3. **El carril no toca los documentos.** Las fuentes de documentos, su orden,
   cantidad, puntajes y ventanas son idénticos con el carril encendido y
   apagado. Toda prueba del carril verifica esto.
4. **Colección propia.** Las fichas se indexan en una colección de Qdrant
   separada de la de documentos, con el mismo modelo denso y estadísticas
   léxicas propias. Nunca en la colección de documentos.
5. **Apagado por defecto hasta M5.** Sin carpeta `media/` o con
   `media.enabled: false`, todo funciona como hoy, incluida la salida de
   `ipsis index`. Los valores por defecto de la plantilla `engine.yaml` solo
   cambian en M5, con aprobación.
6. **Precisión antes que cobertura.** El riesgo principal es mostrar un video
   que no corresponde. El umbral se elige para limitar ese error (objetivo en
   M2.2), aunque se pierdan fichas correctas.
7. **Tres idiomas** para todo texto de interfaz (`ipsis/recursos/idiomas/`,
   `ipsis/recursos/voz/`) y mensajes de CLI (`ipsis/recursos/mensajes/`).
8. **Capas.** Respetar `tests/test_arquitectura.py`: el esquema de la ficha en
   `configuracion` o `nucleo`, la lectura de fichas en `ingesta`, el índice en
   `indice`, la búsqueda del carril en `consulta`, el armado en `aplicacion`,
   la API en `servicio`. Las capas livianas no importan librerías pesadas.
9. **Rutas solo en `ipsis/configuracion/rutas.py`** (agregar `MEDIA = "media"`
   y `MEDIA_ARCHIVOS = "media/files"`).
10. **Nombres.** Código en español; lo que ve la persona y la API pública, en
    inglés, con la traducción en `glosario.py` y en `respuesta_publica`.
11. **Seguridad.** Un `id` de ficha es un slug (`[a-z0-9-]+`); `file` solo
    puede apuntar dentro de `media/files/`; `url` solo `https://`. Ningún
    camino permite leer fuera de `media/`.

---

## M0. Ficha y banco

### M0.1 Esquema y validación de la ficha

- **Objetivo:** leer y validar fichas, sin indexar todavía.
- **Pasos:**
  - Modelo pydantic de la ficha con los campos de
    [multimedia.md](multimedia.md#ficha-propuesta): `title`, `kind`
    (`video`/`audio`), exactamente uno de `url` o `file`, `description`
    (obligatoria, no vacía), `keywords`, `language`, `version`, `duration`
    (`HH:MM:SS` o `MM:SS`), `active` (por defecto `true`) y `chapters`
    (`at` con el mismo formato, `title` obligatorio, `description` opcional;
    `at` crecientes y menores que `duration` si existe). `transcript`
    rechazado con un mensaje que diga que aún no se admite.
  - Módulo en `ipsis/ingesta/` (por ejemplo `fichas.py`) que lee `media/*.yaml`,
    usa el nombre del archivo como `id` y devuelve fichas válidas y errores
    por archivo (un archivo inválido no impide leer los demás).
  - Mensajes de error en `ipsis/recursos/mensajes/{en,es}.yaml`.
- **Pruebas:** `tests/ingesta/test_fichas.py`: válidas, cada error, `url` no
  https, `file` fuera de `media/files/`, capítulos desordenados, `transcript`,
  `id` inválido, determinismo del orden (por `id`).
- **Aceptación:** pruebas en verde; nada lo usa todavía.

### M0.2 Banco de evaluación multimedia

- **Depende de:** M0.1.
- **Objetivo:** medir cuándo el carril debe mostrar una ficha y cuándo no.
- **⚠ Antes de empezar:** preguntar si el usuario puede aportar fichas y
  preguntas reales. Si las aporta, quedan fuera del repo y lo sintético es
  complemento.
- **Pasos (sintético, español primero):**
  - 20 fichas sobre los temas del corpus de
    `tests/datos/banco_terminos/validacion/es/corpus/` (biblioteca, viáticos,
    teletrabajo, titulación, etc.), 10 con 2 a 5 capítulos.
  - 90 preguntas: 30 que deben llevar a una ficha (indicando ficha y, si
    aplica, capítulo), 30 sobre el mismo tema que **no** tienen ficha
    adecuada (solo documentos) y 30 fuera de dominio. Incluir 10 informales.
  - Partición `dev`/`test` 60/40 fijada por ID.
  - Formato: `tests/datos/banco_multimedia/es/{fichas/,casos.jsonl,README.md}`
    con un esquema simple, documentado en el README.
- **Pruebas:** estructura del banco (conteos, que cada ficha esperada exista
  y valide, particiones), en menos de 5 s.
- **Aceptación:** prueba estructural en verde.

## M1. Índice del carril

- **Depende de:** M0.1.
- **Pasos:**
  - Unidades a indexar por ficha activa: una unidad de ficha (`title`,
    `description`, `keywords`) y una por capítulo (`title` de la ficha +
    `title` y `description` del capítulo). Payload con `media_id`, `kind`,
    `version`, `chapter_index` (o `None`), `start_seconds`, y los textos
    literales que se van a mostrar.
  - Colección propia: reutilizar `indexar_qdrant` (`ipsis/indice/qdrant.py`)
    con un `sufijo_coleccion` (por ejemplo `media`), y estadísticas léxicas en
    su propio archivo (`ruta_estadisticas` ya depende del nombre de
    colección).
  - `ipsis index` y `ipsis sync` (`ipsis/ingesta/ingesta.py`,
    `ipsis/aplicacion/sincronizar.py`): si existe `media/` con fichas, indexar
    también el carril e informar cuántas fichas y capítulos; si una ficha es
    inválida, informar su error y seguir con las demás. Sin `media/`, la
    salida es idéntica a la actual.
  - Manifiesto (`ipsis/indice/manifiesto.py`): incluir una huella de las
    fichas para que un cambio en `media/` se detecte como índice
    desactualizado. ⚠ Si eso cambia `hash_corpus` de proyectos sin `media/`,
    detenerse y preguntar (no debe cambiarlo).
- **Pruebas:** índice en un proyecto temporal con y sin `media/`; la
  colección de documentos es idéntica en ambos casos; ficha inválida
  informada; reindexar dos veces da el mismo resultado.
- **Aceptación:** suite rápida en verde; caracterización sin cambios.

## M2. Búsqueda del carril

### M2.1 Búsqueda y contrato interno

- **Depende de:** M1.
- **Pasos:**
  - Configuración opcional `media` en el esquema del motor (con su nombre
    público en `glosario.py`): `enabled: false`, `max_results: 1`,
    `min_score: null` (null = no se muestra nada hasta M2.2),
    `budget_ms: 150`.
  - Módulo de consulta del carril (`ipsis/consulta/` o `ipsis/consulta/v2/`):
    búsqueda híbrida en la colección del carril con la misma pregunta (y la
    variante ortográfica si v2 la generó). Sin reranker en esta tarea.
    Agrupar por `media_id`: si coinciden la ficha y un capítulo, quedarse con
    el capítulo de mayor puntaje.
  - Llamarlo desde `MotorV2` **después** de publicar las fuentes de la primera
    página y solo si queda presupuesto (`_limite`); si no, omitirlo y
    registrar una advertencia en el diagnóstico. No en `continuar`.
  - Contrato interno: lista `multimedia` con `media_id`, `title`, `kind`,
    `url` o `file`, `start_seconds`, `chapter_title`, `description`,
    `duration`, `version`, `score`.
- **Pruebas:** motor con retrievers falsos: con el carril apagado o sin
  colección, la respuesta es idéntica a la actual; con el carril encendido,
  las fuentes de documentos son idénticas (regla 3); presupuesto agotado →
  carril omitido; agrupación ficha/capítulo.
- **Aceptación:** suite rápida en verde.

### M2.2 Umbral medido

- **Depende de:** M0.2 y M2.1.
- **Pasos:**
  - Herramienta `herramientas/evaluacion/carril_multimedia.py`: crea un
    proyecto temporal con el corpus de `banco_terminos/validacion/es` y las
    fichas del banco, indexa y, por pregunta, registra el mejor candidato del
    carril (ficha, capítulo, puntaje) y si es el esperado.
  - Curva por umbral: tasa de **ficha mostrada sin corresponder** (sobre las
    60 preguntas que no deben mostrar ficha) y cobertura (sobre las 30 que
    sí). Capítulo correcto como métrica aparte.
  - ⚠ Preguntar el objetivo; recomendación: ficha incorrecta en ≤ 5 % de las
    preguntas que no deben mostrarla, elegida en `dev`, informada en `test`.
  - Medir en `light` y `medium` (el carril no usa reranker, pero el modelo
    denso y el idioma sí cuentan) y la latencia p50/p95 del carril.
  - Si la cobertura con ese objetivo es menor al 50 %, medir una variante con
    el reranker del perfil sobre los 3 mejores candidatos del carril y
    comparar latencia; no activarla sin aprobación.
- **Aceptación:** tablas en el avance y `min_score` recomendado por perfil.

## M3. API y widget

- **Depende de:** M2.2.
- **Pasos:**
  - `RespuestaConsulta` y `respuesta_publica` (`ipsis/servicio/api.py`): campo
    opcional `media` (lista) con nombres públicos en inglés
    (`media_id`, `title`, `kind`, `url`, `start_seconds`, `chapter_title`,
    `description`, `duration`, `version`). Para `file`, la `url` es la ruta
    pública de M4 (hasta M4, las fichas con `file` no se publican).
  - Widget (`ipsis/servicio/estaticos/widget.js`): bloque después de las
    fuentes, con un encabezado de interfaz nuevo («También hay un video sobre
    esto» / «…un audio…», tres idiomas) y una tarjeta: tipo, título,
    duración, capítulo y minuto si los hay, la descripción literal y una
    línea «Según la descripción del video». Botón que abre el enlace en una
    pestaña nueva (`rel="noopener"`); para YouTube y Vimeo, con el parámetro
    de tiempo del capítulo. Sin iframes (no ampliar la CSP).
  - Temas, modo oscuro, teclado, móvil y `prefers-reduced-motion`.
  - Documentar el campo en la tabla de la API de `docs/guide/web.md` y
    `docs/es/guia/web.md`.
- **Pruebas:** navegador con respuestas simuladas: con y sin `media`; la lista
  de fuentes no cambia; enlace con tiempo para YouTube/Vimeo y sin tiempo
  para otros; accesibilidad del botón.
- **Aceptación:** pruebas en verde; capturas si hay Chromium.

## M4. Archivos locales y panel

- **Depende de:** M3.
- **⚠ Antes de empezar:** confirmar tipos y tamaño máximo. Recomendación:
  `mp4`, `webm`, `mp3`, `m4a`, `ogg`; 500 MB por archivo, configurable.

### M4.1 Servir archivos

- Ruta `GET /media/{media_id}` que entrega el archivo de una ficha activa
  con `file`, con soporte de peticiones por rango (HTTP 206) para poder
  saltar al minuto. Verificar si `FileResponse` de la versión instalada de
  Starlette ya lo soporta; si no, implementarlo y probarlo.
- Aplicar los mismos controles de acceso y CORS que el resto de las rutas
  públicas del widget (ver `_verificar_seguridad` en `ipsis/servicio/api.py`
  y el modo de servicio). ⚠ Si el control por clave del widget no se puede
  aplicar a un `<video src>`, explicar la opción y preguntar.
- En el widget, para fichas con `file`: reproductor `<video>`/`<audio>` con
  `preload="none"` que empieza en `start_seconds`.
- **Pruebas:** 200 y 206 con `Range`, 404 para ficha inactiva o inexistente,
  intento de salir de `media/files/` rechazado, cabeceras de tipo correctas.

### M4.2 Fichas desde el panel

- Sección «Multimedia» en el panel (`ipsis/servicio/estaticos/admin/`,
  rutas en `ipsis/servicio/admin.py` junto a `/documents`): listar fichas,
  crear y editar con un formulario (mismos campos y validación de M0.1),
  subir el archivo opcional con límite de tamaño y tipo, y reindexar con la
  tarea existente (`/reindex`).
- La escritura de la ficha preserva comentarios cuando se edita a mano
  (mismo criterio que `_append_entrada_catalogo` en
  `ipsis/ingesta/catalogo.py`); si no es posible, avisar en el panel que se
  reescribe el archivo.
- **Pruebas:** `tests/integracion/test_panel_admin.py`: crear, editar,
  rechazar ficha inválida, rechazar archivo grande o de otro tipo, token
  requerido.

## M5. Activación, ADR y documentación

- **Depende de:** M2.2, M3 (y M4 si se aprobó).
- **⚠ Pedir aprobación** con las cifras de M2.2 para `media.enabled: true` y
  `min_score` por perfil en proyectos nuevos. Si cambia la plantilla de
  `engine.yaml`: subir `config_version` con su migración y pruebas.
- ADR nuevo (siguiente número libre): «Fichas multimedia en un carril
  aparte», con por qué no se mezclan con los documentos y por qué la
  metadata escrita por personas cumple el ADR 0001.
- Guía nueva EN/ES (`docs/guide/media.md`, `docs/es/guia/multimedia.md`):
  cómo escribir una buena ficha (descripción con las palabras que usaría
  quien pregunta, capítulos con títulos concretos), formatos, límites.
- README (ambos), `CHANGELOG.md`, `docs/guide/configuration.md` y su par
  (carpeta `media/` y bloque `media`).
- Si se agregó un comando de CLI, documentarlo en ambas guías de uso (lo
  exige `tests/test_documentacion.py`).
