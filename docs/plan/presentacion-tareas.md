# Tareas: presentación de fuentes por forma de resultados

Análisis y fases: [presentacion.md](presentacion.md). Estado de cada tarea:
[presentacion-avance.md](presentacion-avance.md).

Este archivo está escrito para que cada tarea la ejecute un agente (Sonnet
5.5) en una sesión propia, sin depender del contexto de otra conversación.
Todo lo que el agente no podría deducir leyendo el código está escrito
abajo, en «Reglas fijas» y en los puntos ⚠ de cada tarea.

## Cómo trabajar una tarea

1. Leer este archivo completo, [presentacion.md](presentacion.md) y la fila
   de la tarea en el avance.
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
  Durante el desarrollo, solo las carpetas afectadas (`tests/consulta`,
  `tests/lenguaje`, `tests/integracion`); antes del commit,
  `PYTEST -m "not slow and not modelos and not browser"` y, si se tocó el
  widget, `PYTEST -m browser` (Chromium en `/opt/pw-browsers` o
  `playwright install chromium` fuera de la nube).
- Modelos: `IPSIS_MODELS_DIR=.cache/modelos`; descargar con
  `ipsis models download --profile medium`.
- `MEDIR` = `uv run python herramientas/evaluacion/ranking_pasajes.py`
  (ver `--help`; `--salida` siempre fuera del repositorio).

## Reglas fijas (no se deducen del código)

1. **Nunca inventar cifras.** Si los modelos no se descargan, la tarea queda
   ⛔ con el error exacto. No estimar ni rellenar tablas.
2. **Sin generación** ([ADR 0001](../decisions/0001-non-generative-answers.md)).
   Todo texto nuevo es una plantilla en `ipsis/recursos/voz/{es,en,pt}.yaml`
   o en los textos de interfaz de `ipsis/recursos/idiomas/{es,en,pt}.yaml`.
   Los marcadores solo se llenan con campos literales que la API ya publica
   (`doc_title`, `scope`, conteos). Las plantillas pasan el linter de tonos
   (`ipsis/lenguaje/tonos.py::errores_plantilla`, ver
   `docs/guide/personality.md`).
3. **No cambiar el ranking ni lo publicado.** Ni el orden, ni la cantidad, ni
   las ventanas de contexto, ni los puntajes. La forma se calcula **después**
   de elegir las fuentes, en `MotorV2._publicar`
   (`ipsis/consulta/v2/motor.py`).
4. **Apagado por defecto hasta P4.** Toda opción nueva entra con un valor
   que reproduce la conducta actual (`neutral`). Los valores por defecto de
   `ipsis/recursos/plantillas/engine.yaml` y de los perfiles solo cambian en
   P4, con aprobación del usuario.
5. **Tres idiomas.** Cada plantilla o texto nuevo existe en es, en y pt, en el
   mismo commit; las pruebas cubren los tres.
6. **Determinismo.** La misma página de resultados produce siempre la misma
   forma. Desempates explícitos.
7. **Medir en `dev`, informar en `test`.** Los umbrales se eligen mirando solo
   la partición `dev`; `test` se mide una vez por configuración.
8. **Los documentos reales del usuario no están en el repositorio.** El banco
   adversarial (56 preguntas, ver `docs/plan/precision-ingesta-avance.md`,
   «Banco adversarial con documentos reales») es la medición que más
   importa. Pedir la ruta al usuario (⚠) y no copiar su contenido al repo ni
   a los commits; solo cifras agregadas e IDs de caso.
9. **Latencia.** El cálculo de la forma no carga modelos ni hace consultas
   nuevas; debe costar menos de 1 ms por página.
10. **Nombres.** Código en español, como el resto del paquete; lo que ve la
    persona y la API pública, en inglés, con la traducción en
    `ipsis/configuracion/glosario.py` y en `respuesta_publica`
    (`ipsis/servicio/api.py`).

---

## P0. Medición

### P0.1 Volcar las fuentes publicadas por pregunta

- **Objetivo:** tener, por pregunta, los resultados publicados con lo
  necesario para calcular formas y separación.
- **Archivo:** `herramientas/evaluacion/ranking_pasajes.py`.
- **Pasos:**
  - Opción nueva `--volcar-publicados RUTA` (jsonl). En `observar_caso`,
    después de `motor.consultar`, escribir una fila por caso con `id`,
    `split`, `pregunta`, `rango_final` y, por cada fuente publicada (las
    primeras `--resultados`), `rango`, `score`, `tipo_puntaje`
    (`logit_reranker`/`recuperacion`), `doc_id`, `seccion_path`, `alcance`,
    `rasgos` y `correcto` (usa `solapa` contra `caso.evidencias`, como ya
    hace `GrabadorCandidatos`). Los datos están en
    `resultado.diagnostico["contrato_http"]["fragmentos"]` (ver
    `MotorV2._publicar`).
  - No escribir el texto de los pasajes (el banco real es privado).
  - Prueba en `tests/evaluacion/` con un motor falso: formato de la fila,
    ausencia de texto y `correcto` bien calculado.
- **Aceptación:** prueba en verde; una corrida con `banco_pasajes` en `light`
  (sin modelos pesados) produce el archivo.

### P0.2 Análisis de forma y separación

- **Depende de:** P0.1.
- **Objetivo:** saber si existe un umbral de separación con el que la primera
  fuente casi nunca falla, y cuántos de los fallos son variantes.
- **Archivo nuevo:** `herramientas/evaluacion/forma_resultados.py` (lee el
  jsonl de P0.1; no carga modelos).
- **Definiciones (escribirlas en el docstring):**
  - `margen` = `score[1] - score[2]` (solo entre fuentes con el mismo
    `tipo_puntaje`; si difieren o hay menos de dos, `None`).
  - `variantes`: las fuentes 1 y 2 tienen el mismo `doc_id` y la misma
    sección padre (`seccion_path[:-1]`), o ambas tienen `alcance` y es
    distinto.
  - `documentos`: las fuentes 1 y 2 tienen distinto `doc_id`.
- **Salida (Markdown + JSON):**
  1. Tabla por relación (`variantes` / `documentos` / otra): n, hit@1, hit@3.
  2. Curva por umbral τ (de 0 a máx., en pasos de la distribución observada):
     cobertura (fracción de preguntas con `margen ≥ τ`) y precisión del
     primer resultado en ese subconjunto.
  3. El menor τ con precisión ≥ objetivo en `dev`, y su precisión y
     cobertura en `test`.
- **⚠ Antes de correr:** preguntar al usuario (a) la ruta del banco con
  documentos reales y (b) la precisión objetivo para `clear`.
  Recomendación: 0,98, y exigir cobertura ≥ 30 % para que valga la pena.
- **Corridas:** `medium` y `light`, en `banco_pasajes` (es) y en el banco
  real. Si el banco real no está disponible, solo `banco_pasajes`, dejándolo
  dicho (sus documentos son sintéticos).
- **Aceptación:** tablas en el avance; recomendación explícita: τ por perfil,
  o «`clear` desactivada» si ningún τ cumple precisión y cobertura.

## P1. Señal `result_shape`

### P1.1 Función de forma

- **Depende de:** P0.2 (para los valores por defecto; la función puede
  escribirse antes).
- **Archivo nuevo:** `ipsis/consulta/v2/forma.py`, con una función pura
  `forma_de_pagina(fuentes, opciones) -> str` que devuelve `"clara"`,
  `"variantes"`, `"documentos"` o `"neutral"`. Entrada: la lista publicada con
  `score`, `tipo_puntaje`, `doc_id`, `seccion_path` y `alcance`. Mismas
  definiciones de P0.2. Orden de decisión: `clara` (si está activa y
  `margen ≥ τ`) → `variantes` → `documentos` → `neutral`.
- **Configuración:** bloque opcional `v2.presentation` en
  `PipelineV2Config` (`ipsis/configuracion/esquemas.py`) con
  `enabled: false`, `clear_margin: null` (null = `clara` desactivada) y
  `clear_margin_by_profile` si P0.2 dio umbrales distintos. Nombres públicos
  en `glosario.py`.
  ⚠ Si añadir el bloque a `ipsis/recursos/plantillas/engine.yaml` exige subir
  `config_version` y escribir una migración, preguntar; recomendación: no
  añadirlo a la plantilla hasta P4 (el esquema ya da el valor por defecto).
- **Pruebas:** `tests/consulta/test_forma.py`: cada forma con casos mínimos;
  `tipo_puntaje` mezclado → sin margen; una sola fuente → `neutral`;
  desactivado → siempre `neutral`; determinismo.
- **Aceptación:** pruebas en verde; nada lo llama todavía.

### P1.2 Publicar la forma

- **Depende de:** P1.1.
- **Pasos:**
  - En `MotorV2._publicar`, solo en la primera página (no en `continuar`),
    calcular la forma y guardarla en el contrato HTTP como
    `forma_resultados`. En la continuación, no publicarla.
  - `respuesta_publica` y `RespuestaConsulta` (`ipsis/servicio/api.py`):
    campo opcional `result_shape` con los valores públicos `clear`,
    `variants`, `documents` y `neutral`.
  - Traza/diagnóstico: registrar forma, margen y τ aplicado (para auditar).
  - Documentar el campo en la tabla de la API de `docs/guide/web.md` y
    `docs/es/guia/web.md`.
- **Pruebas:** motor v2 con retriever falso (ver `tests/consulta/test_motor_v2.py`):
  con la opción apagada no hay cambio en la respuesta pública salvo
  `result_shape: neutral`; con ella encendida, cada forma aparece; la
  continuación no la trae. Los fragmentos y su orden son idénticos con la
  opción encendida y apagada (regla 3).
- **Aceptación:** suite rápida en verde; la caracterización
  (`tests/integracion/test_caracterizacion.py`) no cambia.

## P2. Widget por forma

### P2.1 Plantillas por forma

- **Depende de:** P1.2.
- **Pasos:**
  - En `ipsis/recursos/voz/{es,en,pt}.yaml`, categorías nuevas
    `results_clear`, `results_variants`, `results_documents`, con 4–6
    variantes cada una y el mismo registro que `results`. Marcadores
    permitidos: `{count}`, `{n}`, `{query}` (ya existen) y nuevos
    `{top_doc}` (doc_title de la fuente 1), `{scopes}` (alcances distintos de
    la página, unidos con «, » y «o» según idioma) y `{n_docs}`.
  - Ejemplos de tono (adaptar, no copiar sin revisar):
    `results_clear`: «Esto dice *{top_doc}*. Abajo hay otras fuentes por si
    tu caso es distinto.» `results_variants`: «Depende de tu caso: {scopes}.
    Elige el que corresponde.» `results_documents`: «Lo encontré en {n_docs}
    documentos. Revisa cuál aplica.»
  - Pasar cada texto por el linter de tonos; agregar las categorías a lo que
    el linter recorre si hoy no las incluye.
  - En `widget.js`, donde se elige `categoriaVoz` (cerca de la línea 1762):
    si la respuesta trae `result_shape` distinto de `neutral` y no es
    continuación, usar `results_<forma>`; si la categoría no existe en el
    banco, caer a `results`. Rellenar los marcadores nuevos solo con campos
    de la respuesta.
  - Textos de lectores de pantalla (`anunciador`) coherentes con el mensaje.
- **Pruebas:** `tests/lenguaje/test_voz.py` (bancos completos en tres idiomas,
  marcadores válidos); prueba de navegador con respuestas simuladas para las
  cuatro formas (ver `tests/integracion/test_widget_browser.py`).
- **Aceptación:** con `neutral` el widget se comporta exactamente como antes.

### P2.2 Disposición por forma

- **Depende de:** P2.1.
- **Pasos:**
  - `variants`: el alcance (`scope`) pasa a ser el encabezado visible de cada
    tarjeta, y sobre la lista aparece una fila de atajos (uno por alcance)
    que lleva a la tarjeta correspondiente y abre su contexto. Sin alcance,
    usar la última parte de la sección.
  - `clear`: la primera tarjeta con el contexto abierto; las demás debajo de
    un separador «También aparece en» (texto de interfaz nuevo,
    tres idiomas), con su contexto cerrado.
  - `documents`: separador con el título del documento antes de cada grupo.
  - Respetar `prefers-reduced-motion`, `animations.enabled: false`, el modo
    oscuro, los nueve temas y el teclado. No cambiar el orden de las
    tarjetas ni sus números.
  - Capturas nuevas con `herramientas/capturas_widget.py` si el entorno
    tiene Chromium; si no, dejarlo anotado.
- **Pruebas:** navegador: orden y numeración intactos en las cuatro formas;
  los atajos son botones accesibles; tema oscuro y móvil (ver
  `tests/integracion/test_widget_responsive.py`).
- **Aceptación:** pruebas de navegador en verde; capturas o nota en el avance.

## P3. Caminos de corrección

- **Depende de:** P2.2.
- **⚠ Antes de empezar:** confirmar con el usuario que quiere estos dos
  caminos; cambian la conducta visible cuando la señal está encendida.

### P3.1 Abrir una fuente que no es la primera

- Al abrir el contexto de la fuente 2 o 3 (primera vez por búsqueda), el
  asistente dice una plantilla nueva `opened_source` («Esto es de
  *{doc}*{scope_suffix}.»), sin afirmar que sea la respuesta. Tres idiomas,
  linter de tonos.
- No se envía nada al servidor (P5 decide si se registra).
- **Pruebas:** navegador: abrir la fuente 1 no cambia el mensaje; abrir la 2
  sí, una sola vez.

### P3.2 «No es esto»

- Botón bajo la lista de la primera página, con texto de interfaz nuevo
  (tres idiomas), que hace lo mismo que «Mostrar más resultados» (pide la
  continuación existente) y usa la categoría nueva `results_retry`
  («Entonces quizás buscabas…»). Las tarjetas anteriores se compactan, no se
  borran.
- Si no hay continuación (`has_more: false`), el botón no aparece.
- **Pruebas:** navegador con continuación simulada.

## P4. Activación, ADR y documentación

- **Depende de:** P0.2, P2.2 y, si se aprobó, P3.
- **⚠ Pedir aprobación** con las cifras de P0.2: activar
  `v2.presentation.enabled: true` en proyectos nuevos (y migrados, si el
  usuario lo pide), con `clear_margin` medido por perfil o desactivado.
- Si se cambia la plantilla de `engine.yaml`: subir `config_version` con su
  migración (`ipsis/configuracion/migraciones.py`) y pruebas en
  `tests/configuracion/test_migraciones.py`.
- ADR nuevo (siguiente número libre en `docs/decisions/`): «Presentación
  según la forma de los resultados», con la medición y los límites.
- Guías del widget EN/ES, `docs/methodology/fuentes-v2.md`, `CHANGELOG.md`.

## P5. Opcional: registro del rango abierto

- **⚠ Solo si el usuario lo pide.** Endpoint o campo opt-in que registre en
  `.ipsis/logs/` (ya existe `queries.jsonl` y `RegistroConsultas`) qué rango
  abrió la persona, sin texto de la pregunta si el registro está en modo
  mínimo. Apagado por defecto; documentado en la guía de despliegue como
  dato personal posible. Sirve para medir hit@k con personas reales y
  recalibrar τ.
