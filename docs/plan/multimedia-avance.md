# Avance del plan multimedia

Plan: [multimedia.md](multimedia.md). Tareas: [multimedia-tareas.md](multimedia-tareas.md).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado · ⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| M0.1 | ✅ | 2026-10-16 | (ver git log) | `ipsis/ingesta/fichas.py`: lee y valida `media/*.yaml`; 82 pruebas; 21 mensajes en EN/ES. Ver «M0.1» abajo. |
| M0.2 | ✅ | 2026-10-16 | (ver git log) | El usuario no tiene fichas ni preguntas reales: banco **sintético** (20 fichas, 90 preguntas) en `tests/datos/banco_multimedia/es/`. Ver «M0.2/M2.2» abajo. |
| M1 | ✅ | 2026-10-16 | (ver git log) | Las fichas se indexan en `…_v{n}__media` con su manifiesto; `ipsis index` y `ipsis sync` lo integran; el índice de documentos no cambia. La condición ⚠ (que cambie `hash_corpus` sin `media/`) **no se cumplió**. Ver «M1» abajo. |
| M2.1 | ✅ | 2026-10-16 | (ver git log) | `BuscadorMedia` (`ipsis/consulta/media.py`), bloque `media` del motor (apagado) y carril en `MotorV2`; las fuentes de documentos no cambian. Una desviación de la regla ficha/capítulo. Ver «M2.1» abajo. |
| M2.2 | ✅ | 2026-10-16 | (ver git log) | Objetivo del usuario: ≤ 5 %. `herramientas/evaluacion/carril_multimedia.py`; `min_score` **0,874**: 0/36 en dev y 1/24 (4,2 %) en test. Ver abajo. |
| M3 | ✅ | 2026-10-16 | (ver git log) | API pública `media` y tarjeta del widget (apagado: solo con `media.enabled` y `min_score`). Hecha sin M2.2 porque no cambia ninguna conducta por defecto. Ver «M3» abajo. |
| M4.1 | ⛔ | 2026-10-16 | | **No se hace**: el usuario duda de servir archivos por privacidad. Las fichas con `file` no se muestran; se usa `url` (ADR 0011). |
| M4.2 | ⬜ | | | Fichas desde el panel: no pedido. Se puede hacer solo con enlaces (sin subir archivos). |
| M5 | ✅ | 2026-10-16 | (ver git log) | Aprobada por el usuario: `ipsis init` escribe `media.enabled: true` y `min_score: 0.874`; ADR 0011, guías `media.md`/`multimedia.md`, CHANGELOG. Sin migración. |

## M0.1: esquema y validación de la ficha

- **Módulo:** `ipsis/ingesta/fichas.py` (`Ficha`, `Capitulo`, `LecturaFichas`, `validar_ficha`, `leer_fichas`,
  `a_segundos`). Solo lee y valida: no indexa, no sirve archivos y no abre el audio o el video. Rutas nuevas en
  `ipsis/configuracion/rutas.py`: `MEDIA = "media"` y `MEDIA_ARCHIVOS = "media/files"`. `ipsis init` no crea la carpeta todavía.
- **Desviación de la tarea (motivo):** se pidió un modelo pydantic; se usaron *dataclasses* con validación manual. Una prueba
  existente (`tests/cli/test_mensajes.py`) exige que cada clave de mensaje exista en inglés y español y se use en el código,
  y los errores de pydantic salen en inglés. Así cada error sale del catálogo (`media.*`, 21 claves, 1114 por idioma) en el
  idioma de la interfaz.
- **Reglas que valida** (todas con prueba): `id` = nombre del archivo, solo `[a-z0-9]` con guiones; claves desconocidas
  rechazadas; `title`, `kind` (`video`/`audio`) y `description` obligatorios; exactamente uno de `url` (solo `https://`) o
  `file`; `file` solo dentro de `files/`, sin `..`, sin ruta absoluta ni `\`; `keywords`, `language`, `version`, `active`,
  `duration` y `chapters` con su forma; capítulos con `at` estrictamente creciente y anterior a `duration`; `transcript`
  rechazado con un mensaje que dice que aún no se admite. Se informan **todos** los errores de una ficha, en orden estable.
- `leer_fichas()` además exige que el `file` exista; un archivo inválido no impide leer los demás, sus errores quedan por
  `id`; el orden es por `id` y no depende del orden de creación; solo se leen `*.yaml` (no `.yml`); sin carpeta no hay
  fichas ni errores.
- **Hallazgo de YAML que afecta a quien escriba fichas:** `14:32` sin comillas se lee como el **entero 872** (PyYAML lo trata
  como base 60), mientras que `06:45` queda como texto. Como ese entero ya son los segundos, `a_segundos` acepta ambas
  formas; la guía de M5 debe decir igualmente que se pongan entre comillas.
- **Comprobación de que las pruebas no son vacías:** se rompieron a propósito tres reglas (aceptar `http://`, aceptar
  capítulos repetidos, aceptar `file` fuera de `files/`) y las pruebas fallaron en las tres, en el caso exacto.
- Suite rápida: **1683 aprobadas, 0 fallidas, 2 omitidas** (77 s).

## M1: índice del carril

- **Módulo nuevo** `ipsis/ingesta/indice_media.py`: `unidades_de_fichas` (una unidad por ficha activa y una por capítulo, con
  `texto` literal y `texto_embebido` para buscar), `indexar_fichas`, `huella_fichas`, `media_desactualizado`,
  `nombre_coleccion_media` y `es_coleccion_media`. Colección propia `{base}_{modelo}_v{n}__media`, mismo modelo denso,
  estadísticas léxicas propias (`.stats.json`) y **manifiesto propio** (`hash_archivos` = huella de `media/*.yaml`).
- **El ⚠ de la tarea no se cumplió.** El manifiesto es por colección, así que el del carril no toca el de documentos: con y sin
  `media/` coinciden `hash_corpus`, `n_chunks`, modelo, dimensión, stemmer e inventario de entidades (prueba de integración con
  el modelo real) y sin `media/` la salida de `ipsis index` no menciona el carril.
- **Integración:** `ejecutar_ingesta` indexa el carril después de los documentos, con el mismo cliente Qdrant y el mismo
  codificador (el Qdrant local toma un candado exclusivo de su carpeta); `ResumenIngesta.media` es `None` sin `media/`.
  `permitir_recrear` sigue al de documentos (no se recrea en preparación estructural; el carril comparte versión, así que
  `sync` lo renueva junto con ellos). `ipsis index` y `ipsis sync` imprimen cuántas fichas y capítulos se indexaron y los
  errores por ficha (4 mensajes nuevos en EN/ES); una ficha inválida no impide indexar las demás.
- **`ipsis sync`** detecta que las fichas cambiaron (`ResultadoSync.media_cambio`, también en `--dry-run`) y reindexa aunque los
  documentos no hayan cambiado; `--prune` poda también la serie del carril. Coste conocido: con la preparación estructural, un
  cambio solo en una ficha crea una versión nueva **de las dos colecciones** (se reindexan los documentos). Indexar solo el
  carril sería una optimización posterior.
- **Dos hallazgos que corregí en el camino:**
  1. `ipsis/aplicacion/proyecto.py::estado_indice` recorre todos los manifiestos cuyo nombre empieza por la base; el del carril
     se colaba como «otro índice» y un proyecto sin índice de documentos se diagnosticaba `incompatible` en vez de
     `sin_indice`. Ahora se excluye con `es_coleccion_media` (prueba fallaba sin el filtro: comprobado).
  2. Mi primera versión de `sync` leía la configuración siempre, y 3 pruebas de `tests/cli/test_sync.py` (proyecto mínimo sin
     `engine.yaml`) fallaron. Ahora solo se lee si `media/` tiene fichas.
- **No se tocó el diagnóstico** (`ipsis doctor` y `/ready`): tiene un orden fijo de chequeos y un contrato público en `/ready`;
  añadir una clave sería un cambio de API. La detección de fichas desactualizadas vive en `sync`. Queda para M2/M3 decidir si el
  diagnóstico debe avisar.
- **Pruebas nuevas:** `tests/ingesta/test_indice_media.py` (22, con un codificador falso y Qdrant local) y
  `tests/integracion/test_media_indexacion.py` (2, `slow` + `modelos`, con e5-small: documentos idénticos con y sin media; `sync`
  y `--prune` con las dos series). Suite rápida: **1705 aprobadas, 0 fallidas**.

### Fallos previos adicionales (también sin mis cambios, comprobado en la base)

Al correr las carpetas con pruebas lentas, `tests/integracion/test_portabilidad.py::test_portabilidad_preguntar_de_punta_a_punta[v1]`
(«el servicio no quedó listo en 90 s») y `::test_portabilidad_pythonioencoding_cp1252_no_falla` (`UnicodeDecodeError`) fallan igual
sobre `bd6c24e`. Pueden depender de este entorno (CPU, codificación de la terminal); no se investigaron.

## M2.1: búsqueda del carril y contrato interno

- **Configuración** (`ipsis/configuracion/esquemas.py::MediaConfig`, nombres en inglés en `engine.yaml` vía `glosario.py`): bloque
  `media` con `enabled: false`, `max_results: 1`, `min_score: null` y `budget_ms: 150`. Es un campo opcional con valor por
  defecto: no sube `config_version` ni se añadió a la plantilla de `engine.yaml`. `min_score: null` significa «no se publica
  nada»: la búsqueda corre y queda en el diagnóstico, pero ninguna ficha sale.
- **Buscador** (`ipsis/consulta/media.py::BuscadorMedia`): reutiliza el cliente Qdrant, el codificador y los vectores ya
  memoizados del recuperador de documentos (el Qdrant local toma un candado exclusivo). Busca en híbrido (RRF) para el **orden** y
  calcula el **coseno denso** de cada candidata (filtro por id en Qdrant) para el **puntaje**: el RRF es relativo a la consulta
  (el primero siempre vale lo mismo) y no sirve para decidir «no mostrar videos que no corresponden». Acepta la variante
  ortográfica. `candidatos_agrupados()` devuelve todo sin umbral (es lo que medirá M2.2) y `buscar()` aplica `min_score` y
  `max_results`.
- **Contrato interno** (`contrato_http["multimedia"]`): `media_id`, `title`, `kind`, `url`, `file`, `start_seconds`,
  `chapter_title`, `chapter_description`, `description`, `duration`, `version`, `score` (coseno) y `fusion_rank`; todo texto de
  la ficha, literal. **Todavía no sale por la API pública** (eso es M3): `respuesta_publica` ignora la clave.
- **Motor** (`MotorV2._anadir_multimedia`): corre **después** de publicar las fuentes, solo en la primera página (`continuar` no
  lo llama), omite el carril con una advertencia si no queda `budget_ms` del presupuesto de la consulta, y atrapa cualquier error
  del carril (advertencia `carril multimedia falló: …`): nunca tumba una consulta de documentos. `construir_motor` lo abre solo si
  `media.enabled` y la colección existe.
- **Las fuentes de documentos no cambian** (regla 3), comprobado de dos formas: con dobles (fragmentos, evidencias y bloques
  idénticos con el carril encendido, apagado, fallando o sin presupuesto) y de punta a punta con e5-small (mismos `chunk_id`,
  rango, score y offsets con `enabled: false`, `enabled: true` sin umbral y con umbral).
- **Desviación de la regla del plan (a confirmar con M2.2).** El plan decía «si coinciden la ficha y un capítulo, quedarse con el
  capítulo de mayor puntaje». Eso manda al minuto de un capítulo cualquiera una pregunta sobre el video entero. Se implementó:
  entre las unidades de la ficha que aparecen, se muestra la de **mayor coseno** (el capítulo si la pregunta es sobre él, la
  ficha —sin minuto— si es sobre todo el video). Dos mutantes (siempre ficha; siempre capítulo, la regla literal) rompen
  pruebas distintas. M2.2 mide el acierto del capítulo y puede ajustar la regla (por ejemplo, con un margen).
- **Primera mirada a los cosenos de e5-small (8 preguntas y 4 fichas; NO es una medición):** preguntas pertinentes 0,87–0,91;
  ajenas al dominio 0,76–0,80; pero una pregunta del mismo dominio **sin** ficha («¿Cómo solicito un certificado de notas?»)
  dio 0,853, casi igual a una pertinente informal (0,867). Un umbral de coseno por sí solo tendrá ese compromiso; M2.2 debe
  medirlo con el banco de M0.2 y, si hace falta, probar señales adicionales (términos de la pregunta presentes en la ficha, o
  el reranker sobre las 3 mejores).
- **Pruebas:** `tests/consulta/test_media.py` (24: buscador con Qdrant local y un codificador falso, configuración, y el motor con
  dobles) y una prueba más en `tests/integracion/test_media_indexacion.py` (3 en total, `slow` + `modelos`). Tres mutantes
  iniciales (publicar sin umbral, no atrapar errores, regla de capítulo) y dos de la regla final: los cinco rompen pruebas.
  Carpetas tocadas con modelo real: **1048 aprobadas, 0 fallidas**; suite rápida completa: **1729 aprobadas, 0 fallidas, 2 omitidas**.

## M3: API pública y tarjeta del widget

- `ipsis/servicio/api.py`: `FichaMedia` y `RespuestaConsulta.media` (opcional). `respuesta_publica` lo llena desde el contrato interno
  `multimedia` solo en la primera página y solo con fichas que tengan `url` (las de `file` esperan a M4). Campos: `media_id`, `title`,
  `kind`, `url`, `start_seconds`, `chapter_title`, `chapter_description`, `description`, `duration`, `version`. Sin `score` (desviación leve del
  plan: añade `chapter_description`, que es texto literal de la ficha, y no expone el puntaje). Sin fichas, la clave no existe.
- `widget.js`: bloque `.rw-media` después de las fuentes y de «Mostrar más resultados»: encabezado por tipo («También hay un video/audio sobre esto»,
  «audio y video» si hay mezcla), tarjeta con tipo, duración, versión, título, capítulo y minuto, descripción (la del capítulo si la ficha salió
  por un capítulo), «Según la descripción del video» y un botón que abre el enlace en otra pestaña (`noopener noreferrer`, `aria-label` con el
  aviso de pestaña nueva). YouTube (`t=…s`) y Vimeo (`#t=…s`) llevan el minuto; el resto, el enlace tal cual. Sin iframe ni reproductor, y solo
  enlaces `http`/`https` (un `javascript:` o `data:` no se muestra). 12 textos de interfaz nuevos en en/es/pt.
- Se muestra también si no hay fuentes de documentos (una ficha publicada ya superó su umbral por sí misma).
- Pruebas: 4 de API en `tests/consulta/test_media.py` y 10 de navegador (`test_widget_browser.py`). Capturas revisadas en claro y oscuro a 420 px.
- Guías web EN/ES: campo `media` en la tabla de `/ask` y viñeta «Multimedia lane / Carril multimedia».

## M0.2 y M2.2: banco sintético y umbral

- **Banco** (`tests/datos/banco_multimedia/es/`, README propio): 20 fichas (14 videos y 6 audios, 10 con capítulos) sobre los 11 documentos de
  `banco_terminos/validacion/es/corpus/`; 90 preguntas: 30 que llevan a una ficha (cuatro con capítulo), 30 `mismo_tema` (el tema está en un documento pero
  ninguna ficha lo responde, a propósito con palabras de una ficha cercana) y 30 `fuera`; 10 informales. Particiones 54 `dev` / 36 `test` por orden de id,
  con los tres tipos repartidos. `tests/evaluacion/test_banco_multimedia.py` (5 pruebas) valida la estructura y que cada ficha tenga una pregunta.
  Es sintético y lo escribió el mismo asistente que el carril: **las cifras son optimistas**.
- **Herramienta** `carril_multimedia.py`: proyecto temporal, `ipsis index` con el modelo real y, por pregunta, el mejor candidato de
  `BuscadorMedia.candidatos_agrupados`. Informa la curva en `dev` y dos umbrales elegidos solo con `dev`, con su resultado en `test`. 6 pruebas de las cuentas.
- **Hallazgo:** el menor umbral que cumple el 5 % en `dev` (0,857) cae en el borde de un puntaje (1 falsa) y en `test` da 3/24 (12,5 %). Por eso el
  recomendado es el menor con **cero** falsas en `dev`, redondeado hacia arriba: **0,874** → `dev` 0/36 falsas y 14/18 fichas correctas; `test` 1/24 (4,2 %;
  Wilson 95 % superior 20 %) y 11/12 correctas; capítulo correcto 4/4 y 4/5. Los cosenos de e5 están comprimidos (0,73 a 0,92), así que el margen entre
  una ficha buena y una ajena es de centésimas. Sin ficha equivocada en ninguna pregunta que sí tiene ficha. Latencia de la búsqueda del carril: p50 ≈ 11 ms, p95 ≈ 14 ms.
- Informes: `docs/methodology/mediciones/multimedia/carril.{md,json}`. `light` y `medium` comparten el modelo denso y el carril no rerankea: una sola medición.
- No cubierto: otros idiomas, fichas reales, ni preguntas escritas por personas. 36 negativas en `dev` no certifican el 5 % (cero errores deja un 9,6 % superior).

## M4 y M5

- **M4.1 no se hace** (decisión del usuario, 2026-10-16: servir archivos puede comprometer la privacidad del asistente). Se aceptan los tipos y el tamaño
  propuestos (mp4, webm, mp3, m4a, ogg; 500 MB) por si se retoma, pero hoy ipsis no sirve ni muestra archivos: las fichas con solo `file` se indexan y no se publican.
- **M5:** la plantilla `engine.yaml` de los proyectos nuevos trae `media: enabled: true, min_score: 0.874, max_results: 1, budget_ms: 150`. Sin migración ni `config_version` nueva
  (el valor por defecto del esquema sigue apagado): un proyecto existente lo enciende agregando el bloque. Con la configuración por defecto, un proyecto nuevo
  muestra la ficha que corresponde y no una ajena (`tests/integracion/test_media_indexacion.py`, prueba lenta con el modelo real).
