# Avance del plan de presentación

Plan: [presentacion.md](presentacion.md). Tareas: [presentacion-tareas.md](presentacion-tareas.md).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado · ⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| P0.1 | ✅ | 2026-10-16 | (ver git log) | `--volcar-publicados` en `ranking_pasajes.py` (un JSONL por perfil, sin texto de pasajes ni de la pregunta); 5 pruebas nuevas. Ver «P0.1» abajo. |
| P0.2 | ✅ | 2026-10-16 | (ver git log) | Análisis hecho sobre documentos reales (banco regenerado de 56 preguntas). **`light`: `clara` desactivada** (ningún margen llega a 0,98). **`medium`: τ ≈ 3,6 da 21/21 aciertos pero no demuestra 0,98** (Wilson inf. 0,845): decisión de producto abierta. Ver «P0.2: resultado con documentos reales». ⚠ P1.1 y P4 esperan esa decisión. |
| P1.1 | ✅ | 2026-10-16 | (ver git log) | `ipsis/consulta/v2/forma.py` (`forma_de_pagina`, `margen`, `relacion`) y bloque `v2.presentation` (apagado, sin `engine.yaml` ni `config_version` nuevos). 22 pruebas. Ver «P1.1» abajo. |
| P1.2 | ✅ | 2026-10-16 | (ver git log) | El motor publica `forma_resultados` (solo primera página, solo encendido) y la API `result_shape`. 19 pruebas. `clara` nunca se emite sin `clear_margin` (opción 1). |
| P2.1 | ✅ | 2026-10-16 | (ver git log) | Mensajes `results_variants` y `results_documents` (en/es/pt); el widget los elige por `result_shape`. |
| P2.2 | ✅ | 2026-10-16 | (ver git log) | `variants`: fila «Elige tu caso»; `documents`: marca de grupo por documento. Sin `clear`. |
| P3.1 | ✅ | 2026-10-16 | (ver git log) | Aprobado por el usuario. Fuente abierta → `opened_source`, una vez por tarjeta. |
| P3.2 | ✅ | 2026-10-16 | (ver git log) | Botón «No es esto» → `results_retry` y tarjetas anteriores compactas. |
| P4 | ✅ | 2026-10-16 | (ver git log) | Aprobado por el usuario (recomendación: `clara` apagada). `ipsis init` escribe `v2.presentation.enabled: true`; ADR 0010; sin migración ni `config_version` nueva. |
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

## P0.2: resultado con documentos reales

**El banco.** Los documentos que usó la sesión anterior se perdieron con su contenedor. El usuario volvió a subir los tres originales
(el reglamento de prácticas y las dos versiones de la rúbrica del supervisor, que son casi gemelas) y se **regeneró** un banco
adversarial de 56 preguntas: 28 objetivos × (formal + informal), con cada evidencia como texto literal con offsets calculados por el
programa sobre el texto estructural (el cargador oficial lo valida). Grupos: pares P1/P2 (26), reglas sueltas (22) y rúbricas gemelas
(8). Partición fijada por objetivo: dev 34, test 22. **No es el banco anterior**: las preguntas son otras y más difíciles, por lo que
sus cifras **no son comparables** con el 0,893 de hit@1 de antes. Vive fuera del repositorio (privado); el usuario recibió el paquete
(banco, constructor y LEEME) para reusarlo. Aquí solo hay cifras agregadas e IDs.

**Calidad del primer resultado en este banco** (todas las particiones; el banco sintético daba 1,000 y 0,991):

| Perfil | hit@1 | hit@3 | hit@5 | formal hit@1 / hit@3 | informal hit@1 / hit@3 | p50 / p95 ms |
|---|---|---|---|---|---|---|
| light | 0,661 | 0,875 | 0,893 | 0,75 / 0,96 | 0,57 / 0,79 | 77 / 166 |
| medium (bge) | 0,643 | 0,875 | 0,946 | 0,86 / 1,00 | 0,43 / 0,75 | 819 / 969 |

Por grupo (`medium`): pares P1/P2 0,58 / 0,92; reglas 0,77 / 0,86; rúbricas gemelas 0,50 / 0,75. **Lo informal es el problema grande**:
en `medium` solo el 43 % de las preguntas informales tiene la fuente correcta primera y el 25 % ni siquiera la tiene entre las tres.
Eso es de recuperación y no lo arregla ninguna presentación.

**¿Separa el margen aciertos de errores?** Depende del perfil.

- **`light`: no.** La precisión del primer resultado sube con el margen, pero con la cobertura mínima pedida (0,30) el máximo en `dev` es
  ~0,92; solo llega a 1,0 con coberturas de ~0,12 o menos (4 preguntas). **`clara` queda desactivada en `light`.**
- **`medium`: sí, y con una curva monótona** (dev + test juntos, n = 56): margen ≥ 2,0 → 31/35 (0,886); ≥ 3,07 → 23/24 (0,958);
  **≥ 3,59 → 21/21 (1,000; Wilson inf. 0,845; cobertura 0,38)**; ≥ 4,45 → 18/18; ≥ 5,18 → 15/15. El único error con margen ≥ 3,07 es una
  pregunta formal cuya fuente correcta salió tercera (margen 3,44).
- **Con el procedimiento del plan** (menor τ que cumple 0,98 en `dev`, informado en `test`): **τ = 3,59** para `medium`: dev 12/12
  (cobertura 0,35) y test 9/9 (cobertura 0,41).

**Por qué NO se puede afirmar que se cumple el 0,98.** 21 aciertos de 21 son compatibles con una tasa de error real de hasta ~15 % (límite
inferior de Wilson al 95 % = 0,845); para sostener 0,98 con ese intervalo harían falta del orden de 190 preguntas sin error. Además, τ
se eligió como el menor valor que no falla en `dev`, lo que es optimista (en `test` aguanta, pero son 9 preguntas), y las preguntas las
escribió el mismo asistente que construye el sistema. La conclusión honesta es «señal real y prometedora, no demostrada».

**Decisión de producto abierta (⚠ del usuario).**

1. `clara` **desactivada** (recomendado para empezar): el widget usa solo `variantes`, `documentos` y `neutral`, que no afirman cuál es la
   correcta. No necesita umbral.
2. `clara` **solo en `medium`, con τ conservador (≈ 4,5)**: 18/18 observados, cobertura ~32 %. Riesgo: algún «Esto dice…» equivocado
   (hasta ~15 % de esas páginas con el 95 % de confianza). Mitigable con una redacción que afirme la procedencia y no la corrección
   («Esto dice *X*, abajo hay otras fuentes por si tu caso es distinto»).
3. Esperar a medir con más preguntas (idealmente de personas reales, P5) antes de decidir.

**Formas resultantes en `medium` con τ = 3,59** (dev / test): `clara` 12 / 9, `variantes` 5 / 5, `documentos` 3 / 1, `neutral` 14 / 7: aun
con `clara`, ~40 % de las páginas serían `neutral` (mismo documento, otra sección). Entre las páginas `variantes` el primer resultado acierta
83 % (dev) y 62,5 % (test): el mensaje «Depende de tu caso» es donde más falta hace.

### Decisión del usuario: opción 1

`clara` queda **desactivada**: no se configura ningún `clear_margin` y el widget usa solo «Depende de tu caso» (`variantes`) y «Lo encontré
en varios documentos» (`documentos`), más el mensaje actual para `neutral`. No hay disposición `clear` en P2. La función y la
configuración siguen existiendo, así que activarla más adelante (opción 2 o 3) no pide código nuevo, solo medir con más preguntas (P5).

## P1.2: el motor publica la forma

- `MotorV2._anadir_forma` (`ipsis/consulta/v2/motor.py`) calcula la forma de la primera página sobre lo ya publicado y la deja en
  `contrato_http["forma_resultados"]` y en `diagnostico["forma_resultados"]` (`forma`, `margen`, `relacion`). Solo con
  `v2.presentation.enabled`; apagada **no deja ninguna clave** (desviación del plan, que decía «`neutral` siempre»: así la salida pública y los
  contratos de caracterización quedan idénticos). `continuar` no la llama: las páginas siguientes no la traen.
- La API pública agrega `result_shape` (`clear`, `variants`, `documents`, `neutral`) a `RespuestaConsulta`, documentado en las dos guías web.
- Pruebas: `tests/consulta/test_forma_motor.py` (19): formas con dobles de motor, apagada sin claves, encender no cambia contenido ni orden de
  las fuentes, margen por perfil sobre el general, sin forma en páginas siguientes ni sin resultados, traducción a la API.

## P2.1: mensajes del widget por forma

- Dos categorías nuevas en el banco de voz (`ipsis/recursos/voz/{es,en,pt}.yaml`), seis mensajes cada una por idioma: `results_variants`
  («depende de tu caso») y `results_documents` («lo encontré en {n_docs} documentos»). El banco pasa de 118 a 130 mensajes y de 13 a 15
  categorías (READMEs y guías web actualizados).
- `widget.js`: `respuestaInterna` lee `result_shape`; en la primera página, `variants`/`documents` usan su categoría, y si el banco no la
  tiene (o la forma es `neutral`, o no hay forma) se usa `results` como antes. `{n_docs}` cuenta los documentos distintos de las fuentes
  mostradas. La categoría visible (`data-category`) sigue siendo `results`.
- Desviación del plan: no se agregó el marcador `{scopes}` (un alcance vacío dejaría la frase rota) y no pasan por `errores_plantilla`,
  porque ese linter es de los tonos del asistente y el banco de voz es otro catálogo, con su propia prueba (`tests/lenguaje/test_voz.py`).
- Pruebas: 5 de navegador (`test_widget_browser.py`: cada forma, sin forma, banco sin la categoría) y 3 del banco.
- Entorno: los tests de navegador necesitan el enlace `/opt/pw-browsers/chromium_headless_shell-1243/…/chrome-headless-shell` → el Chromium
  instalado (creado fuera del repo). `test_demo_browser.py` tiene 6 fallos que ya existían (la página de demostración ya no tiene el
  encabezado «Explora tus documentos»).

## P2.2: disposición del widget por forma

- `variants`: fila «Elige tu caso» (`search_variants_label`, en/es/pt) con un atajo por etiqueta de alcance distinta entre las tres primeras tarjetas;
  el atajo desplaza y enfoca el título de la tarjeta. Solo aparece con al menos dos etiquetas distintas.
- `documents`: la primera tarjeta de cada documento recibe `data-grupo="nuevo"` (borde superior más grueso). Se resolvió así, y no con separadores
  `<li>`, para no cambiar la estructura de la lista (el conteo, los ids `rw-documento-N` y la numeración dependen de ella).
- `neutral` o sin forma: igual que antes. `clear` no se implementa (opción 1). El orden y el contenido no cambian en ningún caso.
- Pruebas de navegador (`test_widget_browser.py`): atajos y foco, sin atajos si hay una sola etiqueta o la forma es `neutral`/ausente, marcas de grupo y
  orden; `test_widget_browser.py` + `test_widget_responsive.py`: 92 pasan. Capturas revisadas a mano a 420 px (variantes y documentos).
- Guías web EN/ES: viñeta «Page shape / Forma de la página» en «Search layout».

## P3: caminos de corrección (aprobados por el usuario)

Ambos caminos viven solo cuando la API informa `result_shape` (es decir, con `v2.presentation.enabled`); sin la señal el widget se comporta como siempre.

- **P3.1:** al abrir el contexto de una fuente que no es la primera, el asistente dice la plantilla `opened_source` («Esto es de {doc}{scope_suffix}…»),
  sin afirmar que sea la respuesta. Una vez **por tarjeta** (no una sola vez por búsqueda: abrir la 2 y luego la 3 dice algo de cada una), por
  clic en el título o en «Leer el contexto completo». No envía nada al servidor. El alcance (o el título de la sección padre) va tras el
  documento con su coma (`{scope_suffix}`, vacío si no hay).
- **P3.2:** botón «No es esto» (`search_not_this`) junto a «Mostrar más resultados» en la primera página, solo si hay continuación. Pide la misma
  página siguiente; el mensaje sale de `results_retry` («Entonces quizás buscabas…», siempre con `{count}`) y las tarjetas anteriores quedan
  compactas (`data-compacta`: su extracto se oculta hasta abrir su contexto; con CSS `:has`, así que un navegador sin él las muestra completas).
  Si el banco no trae `results_retry` se usa `continuation`.
- Banco de voz: 142 mensajes en 17 categorías (+`results_retry`, `opened_source`, 6 por idioma). Textos de interfaz: `search_not_this` en en/es/pt.
- Pruebas: 7 de navegador (mensaje por fuente y una vez por tarjeta, por resumen, sin forma no hay caminos, «No es esto» pide la continuación y
  compacta, «Mostrar más» no compacta, sin más páginas no hay botón, banco sin las plantillas); 3 del banco. Verifiqué por mutación que las pruebas
  detectan quitar la compactación y quitar la condición de la forma.
- Guías web EN/ES: viñeta «Correction paths / Caminos de corrección».

## P4: activación por defecto (aprobada por el usuario)

- La plantilla `engine.yaml` de los proyectos nuevos trae `v2.presentation.enabled: true`; `clear_margin` no se configura (opción 1).
- **Sin migración y sin subir `config_version`** (desviación del plan, que la pedía «si cambia la plantilla»): el valor por defecto **del esquema** es `true` (pedido
  del usuario: «déjalas por defecto para no estar activando en el repositorio»), así que los proyectos existentes lo reciben al cargar, sin bloque ni migración, y se apaga con
  `enabled: false`. Prueba: `tests/configuracion/test_defectos_de_proyectos_nuevos.py`.
- ADR 0010 `presentation-by-result-shape`, guías web (EN/ES), `docs/methodology/fuentes-v2.md` (sección «Forma de la página») y CHANGELOG `[Unreleased]`.
