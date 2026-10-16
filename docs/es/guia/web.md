# Widget en tu sitio web

La integración tiene dos partes:

- el **servicio**, que corre en tu servidor (ver
  [despliegue.md](despliegue.md));
- el **widget**, un solo archivo `widget.js` sin dependencias que el
  servicio publica en `/widget.js`.

Para configurarlo en HTML, Astro, Svelte, React, Angular o Python, consulta
[integraciones web](integraciones.md): ejemplos ejecutables, CORS,
configuración y cómo conservar el widget al navegar entre rutas.

![Widget v2 con fuentes numeradas y contexto literal](../../assets/widget-sources-es.png)

## Probar el widget y configurar el proyecto

Desde la carpeta de un proyecto, ejecuta `ipsis serve`. Abre
`/widget/demo.html` con el tema que ya tiene el proyecto y habilita
`/admin/panel`; la página de prueba enlaza al panel y `/` redirige a la página
de prueba. Pega en el panel el token de administración que se muestra en la
terminal. Si ya existe `IPSIS_ADMIN_TOKEN`, se reutiliza; si no, se crea un
token temporal para esta ejecución, sin guardarlo. Se conserva el modo de
producción, incluido HTTPS para el acceso remoto de administración.

Usa `ipsis serve --no-open` para no abrir el navegador. `--no-demo` desactiva
la página de prueba y evita que se abra; `--no-admin` desactiva el panel aunque
haya un token configurado. La API y los archivos del widget siguen
disponibles. Ejecuta `ipsis help serve` para ver todas las opciones.

## Orientación separada de los resultados

Con el motor v2, una sección de orientación se ubica sobre las fuentes
ordenadas. Usa un catálogo fijo de 142 mensajes para cada uno de español,
inglés y portugués, elegido según el idioma de los documentos del proyecto. Los
demás idiomas usan la orientación en inglés como respaldo. Las diecisiete categorías
son `welcome`, `greeting`, `thanks`, `farewell`, `capability`, `tips`,
`searching`, `results`, `results_variants`, `results_documents`, `results_retry`, `opened_source`, `continuation`,
`no_results`, `about`, `limits` y `examples`. Los catálogos YAML están en `ipsis/recursos/voz/` y son
independientes de los tonos y de las plantillas de fuentes existentes. Es texto
de interfaz: nunca evidencia documental ni respuestas generadas.

Las plantillas `results` y `continuation` pueden usar `{count}` (el número con
su sustantivo, ya en singular o plural del idioma: «3 resultados», «1
resultado»), `{n}` (el número solo) y `{query}` (lo que se buscó). Una
plantilla que no usa ninguno recibe el conteo al inicio («3 resultados. …»), de
modo que el conteo siempre llega a quien lee sin ocupar una línea propia (el
encabezado «N resultados para …» se conserva solo para lectores de pantalla). `results_variants` («depende de tu caso») y `results_documents` («lo encontré en varios documentos») reemplazan a `results` en la primera página cuando la API informa `result_shape: variants` o `documents` (tabla de `/ask`, más abajo, y `v2.presentation.enabled`); describen la página y nunca dicen cuál fuente responde. `results_documents` puede usar además `{n_docs}`, la cantidad de documentos distintos entre las fuentes que se ven. Con la forma `neutral`, o con un banco de mensajes sin estas dos categorías, se usa `results` como siempre. Los dos caminos de corrección de más abajo usan `opened_source` (`{doc}` y `{scope_suffix}`, este último ya con su coma inicial o vacío) y `results_retry` (con `{count}`). El
menú de ayuda es un icono «?» en el encabezado del asistente. Mientras el
asistente no está hablando, o aún no empezó, un punto aparece y se desvanece
después de su mensaje para indicar que espera.

**Cómo buscar**, **Qué puedo hacer**, **Sobre el asistente**, **Alcance** y
**Ejemplos** rotan entre sus mensajes de forma local, sin enviar una consulta
de búsqueda. Los saludos, agradecimientos y despedidas escritos también van a
esta sección, y conservan las fuentes desplegadas y el botón de continuación.
Solo las expresiones de cortesía completas evitan la recuperación documental;
una consulta mixta como «hola, ¿cuál es el stock del producto A?» sigue
consultando el corpus.

La orientación se revela carácter por carácter, sin retrasar las peticiones de
red ni mostrar las fuentes carácter por carácter. **Mostrar completo** termina
la animación de inmediato. Un mensaje nuevo cancela la animación anterior. Las
preferencias de movimiento reducido, incluso si cambian mientras se escribe,
muestran el texto completo; `ipsis widget style set animations.enabled=false`
también desactiva la escritura. Los lectores de pantalla reciben el mensaje
completo una sola vez, en lugar de actualizaciones por carácter. Los errores de
búsqueda aparecen en la orientación y dejan disponibles los resultados
existentes.

`GET /config` agrega `assistant_messages` (categoría → lista de textos fijos),
`suggested_questions`, `animations_enabled` y las etiquetas de orientación
localizadas en `interface`. El motor v1 conserva su flujo de chat actual.

## Insertarlo

La forma más simple: pide el código ya armado y pégalo antes de `</body>`.

```bash
ipsis widget snippet --api https://asistente.tu-dominio.cl
ipsis widget snippet --api https://asistente.tu-dominio.cl --component   # como Web Component
```

Con la etiqueta `<script>`:

```html
<script src="https://asistente.tu-dominio.cl/widget.js"
        data-api="https://asistente.tu-dominio.cl"
        data-position="bottom-right" data-size="normal" data-launcher="bubble"
        defer></script>
```

O como Web Component:

```html
<ipsis-chat api="https://asistente.tu-dominio.cl" position="bottom-left"></ipsis-chat>
<script src="https://asistente.tu-dominio.cl/widget.js" defer></script>
```

Agrega el origen exacto de tu sitio a CORS
(`ipsis configure cors_origins=https://www.tu-sitio.cl`). Si usas claves de
widget (`data-widget-key`), recuerda que son públicas: identifican y limitan
el tráfico, no son un secreto.

Los atributos y valores están en inglés en todos los idiomas; los textos que
ve el visitante salen del idioma del proyecto.

## Ubicación, tamaño y lanzador

Se configuran en `config/styles.yaml` (sección `placement`) o con atributos
en la etiqueta. **Si el sitio declara un atributo, ese manda.**

| Opción | Atributo (`data-` en el `<script>`) | Valores |
|---|---|---|
| Posición | `position` | `bottom-right` (por defecto), `bottom-left`, `top-right`, `top-left`, `embedded` |
| Distancia al borde | `offset-x`, `offset-y` | píxeles (24 por defecto) |
| Capa | `z-index` | entero (2147483000 por defecto) |
| Tamaño del panel | `size` | `compact` (340×520), `normal` (390×600), `wide` (440×680) |
| Lanzador | `launcher` | `bubble` (botón redondo), `tab` (botón con el nombre), `hidden` |

Otros atributos: `title` y `greeting` (solo se usan si `/config` no
responde), `color` (acento) y `widget-key`.

**Incrustado.** El chat vive dentro de un contenedor de tu página, siempre
abierto, sin botón ni ventana flotante. El contenedor decide el alto:

```html
<div style="height:560px">
  <ipsis-chat api="https://asistente.tu-dominio.cl" mode="embedded"></ipsis-chat>
</div>
<script src="https://asistente.tu-dominio.cl/widget.js" defer></script>
```

**Lanzador oculto.** Tu sitio abre el chat con su propio botón:

```html
<button onclick="window.Ipsis.open()">¿Dudas? Pregunta al manual</button>
```

## API JavaScript del sitio

Se supone un widget por página.

| Llamada | Qué hace |
|---|---|
| `window.Ipsis.open()` | Abre el panel |
| `window.Ipsis.close()` | Lo cierra |
| `window.Ipsis.state()` | `{open, position, size, launcher, session}` |
| `window.Ipsis.avatar.trigger(evento)` | Hace reaccionar al avatar con un evento de la tabla de [personalidad.md](personalidad.md#cómo-reacciona-el-avatar). Devuelve `false` si aún no hay avatar |
| `window.Ipsis.avatar.state()` | `{ready, persistent, transient, gaze}` |

Eventos que emite el elemento: `ipsis:open`, `ipsis:close`,
`ipsis:question` (`{question}`), `ipsis:answer` (`{status, answer}`, donde
`answer` es la respuesta completa de `POST /ask`), `ipsis:error`
(`{message}`) e `ipsis:avatar`. Este último trae `{state: "ready", name}`
cuando el avatar se montó, `{state: "error", message}` cuando no se pudo y
quedó el ícono, y `{state: "event", event, key}` en cada reacción.

## API HTTP

El `session_id` se crea en cada carga de página, sin `localStorage`.
Recargar o navegar empieza una conversación nueva; cerrar y reabrir el panel
la conserva. El servidor olvida la conversación tras el periodo configurado
de inactividad (30 minutos por defecto). La memoria pertenece a cada worker.

El widget usa tres endpoints públicos; también puedes llamarlos tú:

| Endpoint | Qué devuelve |
|---|---|
| `POST /ask` con `{"question": "...", "session_id": "..."}` | `status` (`ok`, `related`, `no_answer`, `conversational`, `degraded`, `saturated`), `answer`, `answer_blocks` (`answer` por párrafo: `type` es `lead`, `passage` o `message`, con `text`, `connector`, `citation` y `chunk_id`; el texto de `passage` es literal del documento), `fragments` (`doc_title`, `section`, `offset_start`, `offset_end`, `text`, `score`…), `plan` (`clarification` cuando la pregunta no tiene tema: el asistente lo pide), `confidence_level` (`high`: respuesta directa leída por el lector QA, 96,6 % correcta en los bancos medidos; `medium`: respuesta directa sin lector, 85 %; `low`: pasaje relacionado; ausente si no hay respuesta), `confidence`, `latency_ms`, `exact_answer` cuando el lector marcó un tramo, `alternatives` (solo en `no_answer` con la postura proactiva: pasajes literales parecidos, con los campos de `fragments`; no responden la pregunta) y `conversational_category` Con el motor v2 y `v2.presentation.enabled`, la primera página trae además `result_shape`: `variants` (las dos primeras fuentes son variantes de lo mismo), `documents` (vienen de documentos distintos) o `neutral`. Describe la página, no si la primera fuente responde; `clear` solo aparece con un `clear_margin` explícito, que no se recomienda. Las páginas siguientes (`continuation`) nunca la traen. También en la primera página, con el carril multimedia encendido (`media.enabled` y un `media.min_score`), `media`: fichas de audio y video escritas por una persona (`media_id`, `title`, `kind`, `url`, `start_seconds`, `chapter_title`, `chapter_description`, `description`, `duration`, `version`). Nunca cambia `fragments`; por ahora solo se publican las fichas con enlace web. |
| `GET /config` | Lo que necesita el widget: `assistant_name`, `greeting`, `response_mode`, `preset`, `density`, `citations`, los textos de `interface`, la `microcopy` del tono, `assistant_messages`, `animations_enabled`, `placement` y `avatar` |
| `GET /health`, `GET /ready` | Vida y preparación (con el mismo diagnóstico que `ipsis doctor` en `project`) |

Con claves de widget configuradas, `POST /ask` exige el encabezado
`X-Ipsis-Widget-Key`.

## Avatar

Si `personality.yaml` tiene un avatar activo y válido, el widget lo muestra
en lugar del ícono:

- **Carga bajo demanda:** el motor (`/avatar.js`, 52 KB comprimido) se pide
  al abrir el panel por primera vez. Con `avatar.in_launcher: true` se pide
  antes, cuando el navegador está ocioso, para mostrarlo en el botón.
- **Nunca rompe el chat:** si falla la red, la definición o la CSP, queda el
  ícono y se emite `ipsis:avatar` con el error.
- **Decorativo:** lleva `aria-hidden`; los estados ya tienen texto.

## Pantallas

- **Teléfono** (≤ 480 px de ancho, o apaisado bajo): hoja a pantalla
  completa.
  - Respeta los bordes seguros (`safe-area-inset`, con
    `viewport-fit=cover` en tu página).
  - Sigue el alto visible, así el teclado virtual no tapa el campo de
    texto.
- **Tablet** (481–1024 px): panel ajustado al espacio disponible.
- **Escritorio:** panel flotante en la esquina elegida.
- **Preferencias del sistema:** modo oscuro, `prefers-reduced-motion` (sin
  animaciones) y contraste alto (`forced-colors`).

## Diseño de búsqueda

Con el motor v2 (`response_mode: ranked_sources` en `GET /config`) el widget usa un diseño de búsqueda:

- **Buscador abajo**, como un chat: los resultados se desplazan encima, en escritorio y en teléfono. El
  campo tiene un botón para borrar.
- **Mensaje del asistente sobre el buscador**, donde está la atención: dice cuántos resultados hay (ver las
  plantillas con `{count}` más arriba). Con `avatar.placement: message` (el valor por defecto de los
  proyectos nuevos) el avatar queda a su derecha; `header`, `top-corner` y `bottom-corner` siguen
  disponibles ([personalidad.md](personalidad.md)). Mientras el teclado del teléfono está abierto, el
  avatar se oculta para ahorrar espacio.
- **Carga:** mientras se busca, tarjetas grises de esqueleto van cayendo una tras otra, con una línea de
  estado que pasa por «Leyendo los documentos…», «Comparando fuentes…» y «Ordenando por relevancia…»;
  luego los resultados entran de a uno. «Mostrar más resultados» agrega una sola tarjeta de esqueleto bajo
  la lista. Respeta `prefers-reduced-motion` y `animations.enabled: false`.
- **Etiqueta de alcance:** cada resultado muestra, junto al título del documento, una etiqueta pequeña con
  lo que lo distingue de sus unidades hermanas (por ejemplo «Práctica Profesional II»). La API la devuelve
  como `scope` y los términos que distinguen unidades parecidas como `distinctive_terms`.
- **Forma de la página** (con `v2.presentation.enabled`, que hace que la API devuelva `result_shape`): cuando las
  primeras fuentes son `variants` de lo mismo (por ejemplo la tabla de cada práctica), una fila «Elige tu caso» con
  atajos lleva a la tarjeta de cada variante; cuando vienen de varios `documents`, la primera tarjeta de cada
  documento lleva un borde superior más grueso. También cambia el mensaje del asistente (`results_variants`,
  `results_documents`). Ni las fuentes que se muestran ni su orden cambian, y una página `neutral` se ve igual que
  sin la opción.
- **Carril multimedia** (solo con `media.enabled`): tras las fuentes, un bloque aparte «También hay un video sobre esto» muestra el
  texto de la propia ficha (tipo, duración, capítulo y minuto, descripción, «Según la descripción del video») y un botón que abre el
  enlace en otra pestaña. En YouTube y Vimeo el enlace incluye el minuto del capítulo. No hay reproductor incrustado (ni iframe) y los
  enlaces que no son `http`/`https` nunca se muestran.
- **Caminos de corrección** (solo cuando la API informa `result_shape`): al abrir el contexto de una fuente que no es la
  primera, el asistente dice de dónde es («Esto es de *Reglamento*, Práctica Profesional II»), una vez por tarjeta, sin afirmar
  que sea la respuesta y sin enviar nada al servidor. Bajo la lista, junto a «Mostrar más resultados», un botón «No es esto»
  pide la misma página siguiente, el asistente responde «Entonces quizás buscabas…» y las tarjetas anteriores se compactan
  (su extracto se oculta hasta que abres su contexto; no se borra nada). No aparece si no hay más resultados.
- **Página de prueba:** `/widget/demo.html` ocupa toda la pantalla en teléfonos (sin encabezado de página;
  el formulario de la clave de acceso está en `#clave-acceso`) y se ajusta a la ventana en escritorio.

## Citas

Toda respuesta con evidencia muestra, **debajo**, un bloque de citas para
comprobarla:

- una invitación a revisar la fuente (del tono activo);
- por cada cita: documento, sección y posición en caracteres, con el texto
  literal;
- el tramo exacto que respondió, resaltado.

`styles.yaml::presentation.citations` elige cómo se ven, nunca si se ven:

- `accordion`: desplegables; la que tiene el tramo exacto viene abierta;
- `list`: todas a la vista.

## Textos

- **Del tono activo** (ver [personalidad.md](personalidad.md)): la
  bienvenida, «buscando…», la invitación a las citas y los mensajes de error
  vienen de `/config` en 7 variantes, y el widget rota entre ellas.
- **Orientación de v2:** su catálogo fijo y separado tiene 142 mensajes por
  idioma admitido, con ejemplos e información sobre el asistente y su alcance.
- **Textos de la interfaz** (etiquetas de botones, placeholder…): vienen del
  paquete de idioma del proyecto.
- **Accesibilidad:** «buscando…» y los errores se anuncian a los lectores
  de pantalla con una región `aria-live`.
- **Seguridad:** ningún texto de la API se inserta como HTML; todo usa
  `textContent`.

## Estilo

Los resultados se distinguen con tarjetas (`cards`), separadores (`lines`) o
un margen editorial (`editorial`). Los presets `classic`, `minimal`,
`editorial`, `contrast`, `search`, `search_compact`, `ocean`, `forest` y
`midnight` combinan estos diseños con sus colores y tipografías.

Los títulos tienen color, fuente, tamaño y peso propios. Puedes ajustar las
secciones, los bordes y el fondo de los resultados sin cambiar el color de los
botones. Por ejemplo:

```bash
ipsis widget theme apply forest
ipsis widget style set presentation.result_layout=cards colors.heading="#14532d" typography.heading_family="Georgia, serif" typography.heading_size=20px
ipsis widget style set shape.result_radius=12px shape.result_gap=18px
ipsis widget style set content.title="Centro de ayuda" content.welcome_title="¿Qué necesitas revisar?"
ipsis widget theme preview --output preview.html
```

| Clave de `styles.yaml` | Qué cambia |
|---|---|
| `colors.heading`, `colors.section` | Colores de títulos y secciones |
| `colors.result_surface`, `colors.result_border` | Fondo y demarcadores de los resultados |
| `typography.heading_family`, `heading_size`, `heading_weight`, `section_size` | Tipografía de títulos y secciones |
| `shape.result_radius`, `result_gap`, `result_padding` | Radios, separación y relleno |
| `presentation.show_result_numbers`, `show_section_path` | Numeración y ruta de secciones |
| `presentation.expand_context` | Abre los contextos desde el inicio |
| `presentation.show_suggestions` | Muestra las preguntas de ejemplo |
| `content.title`, `subtitle`, `welcome_title`, `welcome_text` | Cabecera y presentación inicial; vacío usa el idioma del proyecto |

El panel `/admin/panel` incluye estas opciones en **Widget → Estilo completo**.
Cambiar de preset conserva los textos de `content` y el CSS personalizado.
La vista previa usa el widget real con datos de ejemplo y funciona sin servicio
ni índice.

En español, inglés y portugués, la bienvenida ofrece seis preguntas que
rellenan el campo sin enviarlo. Los botones **Sobre el asistente**, **Alcance**
y **Ejemplos** amplían los mensajes fijos. Estos textos de interfaz se muestran
separados de las fuentes documentales y no ejecutan consultas.

**Preguntas frecuentes** permite explorar al menos 100 preguntas completas
por idioma, repartidas en diez temas. `/config::default_questions` publica
pregunta y tema; la respuesta fija se resuelve en el servicio. Las consultas
con información documental añadida siguen consultando el índice. Las 142
variantes de mensajes son un catálogo distinto de las preguntas reconocidas.

La orientación ocupa dos líneas por defecto. **Mostrar completo** permite
leerla en un área desplazable; **Contraer** devuelve el espacio a las fuentes.
El menú **Ayuda** (el icono «?» del encabezado) muestra las acciones sobre la
lista, sin cambiar su altura.
La barra de carga y las transiciones de las tarjetas hacen visibles las
consultas nuevas; respetan `animations.enabled` y el movimiento reducido.

Todo el aspecto vive en `config/styles.yaml` y se aplica sin reiniciar el
servicio:

- **Presets:** `ipsis widget theme list` y `ipsis widget theme apply editorial`
  (`classic`, `minimal`, `editorial`, `contrast`).
- **Cada valor:** `ipsis widget style show` y, por ejemplo,
  `ipsis widget style set colors.accent=#0ea5e9 shape.panel_radius=10px
  typography.family="Inter, sans-serif"`. Secciones: `colors`,
  `dark_colors`, `typography`, `shape`, `shadows`, `animations`,
  `placement` y `presentation`.
- **Sin terminal:** el panel `/admin/panel`, pestaña Widget, «Estilo
  completo» (ver [personalidad.md](personalidad.md#panel-gráfico-adminpanel)).
- **Vista previa sin servicio:** `ipsis widget theme preview`.

## CSP de tu sitio

Si tu sitio usa Content Security Policy, permite el dominio del asistente:

```text
script-src  'self' https://asistente.tu-dominio.cl;
connect-src 'self' https://asistente.tu-dominio.cl;
style-src   'self' https://asistente.tu-dominio.cl 'unsafe-inline';
```

- `style-src` permite la hoja `/styles.css` y el estilo propio del widget,
  que vive aislado en su Shadow DOM.
- El avatar animado necesita además `'unsafe-eval'` en `script-src`,
  porque su librería valida la definición con ajv, que compila el esquema en
  el navegador. Sin eso, el widget muestra el ícono y el chat funciona igual.
- Si el widget se sirve desde otro dominio, el servicio debe permitir tu
  sitio en `cors_origins`: el motor del avatar es un módulo ES y el
  navegador lo pide con CORS.

## Exportar archivos estáticos

```bash
ipsis widget export ./public/ipsis --api https://asistente.tu-dominio.cl --position bottom-left
```

Genera, para servirlos desde otro servidor:

- `widget.js` y `snippet.html`;
- `avatar.js` y `avatar.js.LICENSE.txt` (el motor y sus licencias);
- `avatars/<nombre>.avatar.json`: el avatar activo, con los colores del
  proyecto. Si hay avatar, el snippet lleva `avatar-base="."`: el widget
  carga el motor y la definición desde esa carpeta, no desde el servicio.

## Ejemplos ejecutables

- `examples/html`: página estática configurable desde `config.js`;
- `examples/react`: proyecto Vite y adaptador de eventos para React;
- `examples/astro`, `examples/svelte`, `examples/angular`: adaptadores de frameworks;
- `examples/python`: página FastAPI que incrusta el widget;
- `examples/wordpress`: plugin instalable con el shortcode `[ipsis]`.

Los comandos y las URLs locales están en
[examples/README.md](../../../examples/README.md).

Las pruebas de navegador (`pytest -m browser`) usan Chromium real y
verifican:

- teclado, foco y diálogo;
- cada posición en teléfono, tablet y escritorio, sin desbordes y con el
  campo visible con el teclado abierto;
- las citas con el tramo exacto marcado;
- la API `window.Ipsis`.
