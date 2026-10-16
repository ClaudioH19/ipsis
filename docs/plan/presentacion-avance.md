# Avance del plan de presentación

Plan: [presentacion.md](presentacion.md). Tareas: [presentacion-tareas.md](presentacion-tareas.md).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado · ⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| P0.1 | ✅ | 2026-10-16 | (ver git log) | `--volcar-publicados` en `ranking_pasajes.py` (un JSONL por perfil, sin texto de pasajes ni de la pregunta); 5 pruebas nuevas. Ver «P0.1» abajo. |
| P0.2 | 🔶 | 2026-10-16 | (ver git log) | Herramienta `forma_resultados.py` lista y probada (13 pruebas). **El análisis sobre documentos reales lo corre el usuario en su máquina** (los documentos no están en este entorno): ver «P0.2» abajo. ⚠ precisión objetivo (0,98 por defecto). |
| P1.1 | ✅ | 2026-10-16 | (ver git log) | `ipsis/consulta/v2/forma.py` (`forma_de_pagina`, `margen`, `relacion`) y bloque `v2.presentation` (apagado, sin `engine.yaml` ni `config_version` nuevos). 22 pruebas. Ver «P1.1» abajo. |
| P1.2 | ⬜ | | | |
| P2.1 | ⬜ | | | |
| P2.2 | ⬜ | | | |
| P3.1 | ⬜ | | | ⚠ confirmar caminos de corrección |
| P3.2 | ⬜ | | | |
| P4 | ⬜ | | | ⚠ activación por defecto |
| P5 | ⬜ | | | Opcional; solo a pedido |

## P0.1: volcar las fuentes publicadas

- `herramientas/evaluacion/ranking_pasajes.py`: opción `--volcar-publicados RUTA` y clase `GrabadorPublicados`. Escribe un
  JSONL **por perfil** (`RUTA-light.jsonl`, `RUTA-medium.jsonl`; el volcado de candidatos existente sí se pisa entre
  perfiles). Una fila por pregunta: `id`, `split`, `perfil`, `rango_final` y, por cada fuente publicada, `rango`,
  `chunk_id`, `doc_id`, `seccion_path`, `score`, `tipo_puntaje`, `alcance`, `rasgos` y `correcto`. **No escribe el texto de
  los pasajes ni el de la pregunta**: el banco real es privado y para el análisis bastan los IDs. `correcto` usa los offsets
  del fragmento recuperado, igual que `rango_final`, y no los de la ventana ampliada.
- Pruebas (`tests/evaluacion/test_ranking_pasajes.py`, de 8 a 13): orden, puntaje y `correcto`; ausencia de texto y de
  pregunta en el archivo; resultado sin contrato HTTP; sin grabador no se registra nada; un archivo por perfil.
- **Aceptación comprobada** con una corrida real: `banco_pasajes/es`, perfil `light`, partición `todas`: 116 filas con 5
  fuentes cada una; hit@1 final 1,000 (híbrido 0,931). El archivo vive fuera del repositorio.

### Lo que esa corrida ya dice para P0.2

- En `light` el `score` publicado es de recuperación y está **normalizado respecto a la primera fuente** (vale 1,0 en 104
  de 116 primeras y los segundos van de 0,34 a 0,67), así que el margen entre las dos primeras sí informa y está acotado a
  [0, 1]. En `medium` será un logit del reranker, de otra escala: el umbral se mide por perfil, como ya estaba previsto.
- En el banco sintético ninguna fuente publicada tiene `alcance` (580 de 580 vacías): sus documentos no tienen tablas con un
  párrafo previo ni líneas enfatizadas que lo originen. La forma `variants` debe apoyarse en la sección padre
  (`seccion_path[:-1]`), no solo en `alcance`; la regla por alcance solo se podrá probar con el banco real.
- Con 116 de 116 primeros correctos en `light`, el banco sintético casi no tiene errores que estudiar: el análisis útil
  necesita el banco real (⚠ P0.2).

### Fallos previos que aparecieron al correr `tests/evaluacion` completo

Con los modelos de `medium` descargados, 5 pruebas `slow` + `modelos` fallan **también sin los cambios de P0.1**
(comprobado sobre `bd6c24e`): `test_banco_universal.py::test_falsos_ok_no_superan_la_linea_base[es|en|pt-light]`,
`test_general_regresion.py::test_regresion_documental_real[light]` y
`test_tono_no_cambia_estados.py::test_otro_tono_no_cambia_estados_reglas_ni_literalidad`. Son pruebas del motor v1
(exigen `senales` y aciertos de «respuesta directa»); desde que v2 es el predeterminado ya no producen eso. En CI sin
modelos se omiten, por eso no se veían. No se tocaron (fuera del alcance).

## P1.1: función de forma y configuración

- **`ipsis/consulta/v2/forma.py`**: función pura sobre lo ya publicado; no cambia qué se publica ni su orden.
  `margen` (primera menos segunda; `None` si faltan puntajes o son de tipos distintos, porque un logit del reranker y un
  puntaje de recuperación no se restan), `relacion` (`documentos` / `variantes` / `otra`) y `forma_de_pagina`
  (`clara` → `variantes` → `documentos` → `neutral`; apagada o con una sola fuente es siempre `neutral`).
- **Definición de `variantes`, más estricta que la del plan.** Mismo documento y (alcances distintos en ambas, o rutas de sección
  distintas con una **sección padre común no vacía**). Sin exigir padre no vacío, dos secciones de primer nivel de un mismo
  documento («Plazos» y «Montos», padre `()` en las dos) se habrían llamado «variantes». Dos unidades de una misma sección, o con el
  mismo alcance, son `otra`.
- **Configuración** (`PresentacionConfig`, dentro de `PipelineV2Config`; en el archivo, `v2.presentation`): `enabled: false`,
  `clear_margin: null` y `clear_margin_by_profile` (`{medium: 4.0, light: 0.3}`; el del perfil manda sobre el general, resuelto por
  `margen_claro_efectivo`). Es un campo con valor por defecto: **no se añadió a la plantilla de `engine.yaml` ni se subió
  `config_version`** (la pregunta ⚠ de la tarea: lo prudente es esperar a P4). Márgenes negativos y claves desconocidas se
  rechazan.
- Todavía **nada la llama**: el motor y la API son P1.2.

## P0.2: análisis de la separación de puntajes

- **Herramienta** `herramientas/evaluacion/forma_resultados.py` (sin modelos; usa la misma `forma_de_pagina` que el motor, para
  que el análisis y el producto no puedan divergir): por perfil, (1) hit@1 y hit@3 por relación entre las dos primeras fuentes,
  (2) curva por margen τ con cobertura, precisión del primer resultado y **límite inferior de Wilson al 95 %**, (3) el menor τ que
  cumple precisión y cobertura **elegido en `dev` e informado en `test`**, y las formas resultantes. Si ningún τ cumple, dice
  que `clara` queda desactivada.
- **Advertencia cuando no hay errores que estudiar.** Con menos de 10 errores de primer resultado en `dev`, el informe lo avisa:
  cualquier umbral «cumple» porque casi nada falla y la recomendación no prueba que el margen separe aciertos de errores. Se añadió
  después de ver el resultado de abajo.
- **Corrida sobre el banco sintético** (`banco_pasajes/es`, 116 preguntas: dev 72, test 44) con `light` y `medium` (bge): hit@1
  `light` 1,000 y `medium` 0,991; **0 y 1 errores en `dev`**. Los márgenes recomendados (τ = 0,33 para `light`, 0,16 para
  `medium`) cubren el 100 % de las páginas y no significan nada: no hay errores donde el margen pueda fallar. Dato de escala útil:
  en `light` el margen está en [0, 1] (puntaje normalizado a la primera fuente) y en `medium` va de ~3 a ~10 (logit del reranker).
  **Conclusión: el banco sintético no sirve para decidir `clara`; hace falta el banco con documentos reales.**
- **Qué debe correr el usuario, en su máquina** (con sus documentos y sus 56 preguntas adversarias; no se copia nada al repo):

  ```bash
  uv run python herramientas/evaluacion/ranking_pasajes.py <manifiesto.json del banco real> \
      --perfil light --perfil medium --idioma es --particion todas \
      --volcar-publicados /ruta/fuera/del/repo/publicados.jsonl --salida /ruta/fuera/del/repo/ranking
  uv run python herramientas/evaluacion/forma_resultados.py \
      /ruta/fuera/del/repo/publicados-light.jsonl /ruta/fuera/del/repo/publicados-medium.jsonl \
      --salida /ruta/fuera/del/repo/forma --precision-objetivo 0.98
  ```

  Los volcados no llevan ni el texto de los pasajes ni el de las preguntas. Con 56 preguntas repartidas en `dev` y `test` la
  muestra es chica: mirar el límite de Wilson y los errores de `dev` (el informe avisa si son menos de 10). Si el resultado es
  «ningún τ cumple», la forma `clara` queda desactivada y el producto usa solo `variantes`, `documentos` y `neutral`.
- Pruebas: `tests/evaluacion/test_forma_resultados.py` (13, con escenarios cuya respuesta se calcula a mano).
