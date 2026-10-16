/*
 * Widget de chat embebible -- ipsis.
 *
 * Un único archivo, sin frameworks ni dependencias externas. Se integra con
 * una línea:
 *
 *   <script src="https://tu-servidor/widget.js" data-api="https://tu-servidor"></script>
 *
 * O como Web Component declarativo:
 *   <ipsis-chat api="https://tu-servidor"></ipsis-chat>
 *   <script src="https://tu-servidor/widget.js"></script>
 *
 * El componente acepta `api`, `widget-key`, `color`, `title`, `greeting`,
 * `position`, `size`, `launcher`, `offset-x`, `offset-y`, `z-index` y
 * `mode="embedded"`; emite ipsis:open, ipsis:close, ipsis:question,
 * ipsis:answer, ipsis:error e ipsis:avatar.
 *
 * Atributos `data-` soportados en la etiqueta <script>:
 *   data-api        base del servicio (si se omite, usa el mismo origen
 *                   desde el que se sirvió este archivo -- normalmente
 *                   correcto, porque el servicio sirve su propio widget).
 *   data-widget-key clave pública de widget (opcional, ver
 *                   ipsis/servicio/seguridad.py -- NO es un secreto).
 *   data-color      color de acento (hex), por defecto "#2563eb".
 *   data-title      título del panel (se sobrescribe con lo que traiga
 *                   /config en cuanto responda, salvo que /config falle).
 *   data-greeting   saludo inicial de repuesto, por si /config no responde.
 *   data-position   "bottom-right" (por defecto) | "bottom-left" | "top-right"
 *                   | "top-left" | "embedded"; también data-size, data-launcher,
 *                   data-offset-x, data-offset-y y data-z-index.
 *
 * La API pública (atributos, /config, /ask, eventos y window.Ipsis) usa
 * nombres en inglés; por dentro el widget conserva los suyos.
 *
 * Reglas de diseño del widget:
 *  - Shadow DOM: el CSS del sitio anfitrión no debe deformar el widget, ni
 *    al revés.
 *  - Los CUATRO estados de una respuesta (ok / related / no_answer /
 *    conversational) se pintan DISTINTO -- es la mitad de la honestidad del
 *    sistema.
 *  - Ningún texto que venga de la API se inserta como HTML: SIEMPRE
 *    `textContent`, nunca `innerHTML` con datos de la API interpolados.
 *  - Accesible: roles ARIA, cierre con Escape, foco atrapado en el panel
 *    abierto, pantalla completa en móvil.
 *  - Identificador de sesión nuevo en cada carga de página (la API exige `session_id`).
 */
(function () {
  "use strict";

  // -------------------------------------------------------------------
  // 0. Punto de entrada: el propio <script> que cargó este archivo trae
  //    los atributos data-* de configuración.
  // -------------------------------------------------------------------
  var scriptActual = document.currentScript;
  if (!scriptActual) {
    // Navegadores muy antiguos sin document.currentScript: se busca el
    // último <script> que apunte a este archivo.
    var candidatos = document.getElementsByTagName("script");
    for (var i = candidatos.length - 1; i >= 0; i--) {
      if (/widget\.js(\?|$)/.test(candidatos[i].src)) {
        scriptActual = candidatos[i];
        break;
      }
    }
  }
  var datos = (scriptActual && scriptActual.dataset) || {};
  if (window.customElements && !window.customElements.get("ipsis-chat")) {
    window.customElements.define("ipsis-chat", class extends HTMLElement {});
  }
  var host = document.querySelector("ipsis-chat:not([data-ipsis-ready])");
  if (!host) {
    host = document.createElement(window.customElements ? "ipsis-chat" : "div");
    document.body.appendChild(host);
  }
  host.id = host.id || "ipsis-widget-host";
  host.setAttribute("data-ipsis-ready", "true");

  function opcion(atributo, dato, repuesto) {
    return host.getAttribute(atributo) || datos[dato] || repuesto;
  }
  var API_BASE = opcion("api", "api", window.location.origin).replace(/\/$/, "");
  var CLAVE_WIDGET = opcion("widget-key", "widgetKey", "") || null;
  var COLOR_ACENTO = opcion("color", "color", "#2563eb");
  var TITULO_INICIAL = opcion("title", "title", "Assistant");
  var SALUDO_INICIAL = opcion("greeting", "greeting", "Hi, how can I help you?");
  var CABECERA_CLAVE_WIDGET = "X-Ipsis-Widget-Key";
  // Carpeta alternativa para el motor y la definición del avatar (widget
  // exportado con `ipsis widget export`): ahí están avatar.js y avatars/.
  var AVATAR_BASE = opcion("avatar-base", "avatarBase", null);

  // Ubicación: lo que declare el sitio (atributos del elemento o data-* del
  // <script>) manda; lo que no, llega de styles.yaml vía /config.
  var VALIDOS = {
    posicion: ["abajo-derecha", "abajo-izquierda", "arriba-derecha", "arriba-izquierda", "incrustado"],
    tamano: ["compacto", "normal", "amplio"],
    lanzador: ["burbuja", "pestana", "oculto"]
  };
  // Valores públicos (atributos y /config) → internos.
  var INTERNOS = {
    posicion: { "bottom-right": "abajo-derecha", "bottom-left": "abajo-izquierda", "top-right": "arriba-derecha",
                "top-left": "arriba-izquierda", "embedded": "incrustado" },
    tamano: { "compact": "compacto", "normal": "normal", "wide": "amplio" },
    lanzador: { "bubble": "burbuja", "tab": "pestana", "hidden": "oculto" }
  };
  function publico(clave, valor) {
    var mapa = INTERNOS[clave];
    for (var externo in mapa) if (mapa[externo] === valor) return externo;
    return valor;
  }
  function enLista(valor, clave) {
    var interno = INTERNOS[clave][valor];
    return interno && VALIDOS[clave].indexOf(interno) >= 0 ? interno : null;
  }
  function entero(valor, minimo, maximo) {
    var n = parseInt(valor, 10);
    return isNaN(n) ? null : Math.min(Math.max(n, minimo), maximo);
  }
  var DEL_SITIO = {
    posicion: enLista(host.getAttribute("mode") === "embedded" ? "embedded" : opcion("position", "position", null), "posicion"),
    tamano: enLista(opcion("size", "size", null), "tamano"),
    lanzador: enLista(opcion("launcher", "launcher", null), "lanzador"),
    desplazamiento_x: entero(opcion("offset-x", "offsetX", null), 0, 400),
    desplazamiento_y: entero(opcion("offset-y", "offsetY", null), 0, 400),
    z_index: entero(opcion("z-index", "zIndex", null), 0, 2147483647)
  };
  var UBICACION = {
    posicion: "abajo-derecha", tamano: "normal", lanzador: "burbuja",
    desplazamiento_x: 24, desplazamiento_y: 24, z_index: 2147483000
  };
  Object.keys(DEL_SITIO).forEach(function (clave) {
    if (DEL_SITIO[clave] !== null) UBICACION[clave] = DEL_SITIO[clave];
  });
  var INCRUSTADO = UBICACION.posicion === "incrustado";
  // Textos de la interfaz. Estos valores en inglés son el respaldo si
  // /config no responde; normalmente llegan del paquete de idioma del
  // servicio (campo `interface` de /config).
  var TEXTOS = {
    open: "Open chat with {title}",
    subtitle: "Answers by citing the document",
    close: "Close chat",
    question_label: "Type your question",
    placeholder: "Type your question...",
    send: "Send question",
    not_direct: "Not a direct answer",
    check_citation: "Check the citation",
    waiting: "Searching the document",
    rate_limit_error: "Too many questions in a row. Wait a few seconds and try again.",
    origin_error: "This site is not allowed to use the assistant.",
    http_error: "The service could not answer (HTTP {status}).",
    network_error: "Could not reach the assistant. Check your connection and try again.",
    service_error: "The assistant is not available right now. Try again later.",
    citations_hint: "You can check it in the citation below.",
    sources_one: "1 source from the document",
    sources_many: "{n} sources from the document",
    citation_position: "characters {start}–{end}",
    source_code: "Source code",
    ranked_hint: "Sources ranked by relevance",
    read_context: "Read the source and full context",
    context_truncated: "The displayed context is truncated.",
    keep_searching: "Keep searching",
    rephrase_search: "You can also write a more specific question.",
    search_exhausted: "No more results in this search. Try rephrasing your question.",
    search_expired: "This search has expired. Submit your question again.",
    search_send: "Search",
    search_subtitle: "Search and review sources",
    search_open: "Open search of {title}",
    search_close: "Close search",
    search_question_label: "Search your documents",
    search_results_label: "Search results",
    search_results_count: "{n} results for “{query}”",
    search_results_count_one: "1 result for “{query}”",
    search_read_document: "Read full context",
    search_close_document: "Close context",
    result_distinguished: "Distinguished by",
    voice_count_phrase: "{n} results",
    voice_count_phrase_one: "1 result",
    search_stage_read: "Reading the documents…",
    search_stage_compare: "Comparing sources…",
    search_stage_rank: "Sorting by relevance…",
    clear_input: "Clear search",
    source_original: "View original text",
    source_table: "Source table",
    source_table_hint: "Open full context to read the table with its columns.",
    search_more: "Show more results",
    search_added: "Added {n} results.",
    search_start: "Search your documents",
    search_instruction: "Enter a question or keywords to find information.",
    voice_label: "Guidance from ipsis",
    voice_help: "Search tips",
    voice_options: "What I can do",
    voice_show_all: "Show full message",
    voice_results: "Open a source to check its context.",
    voice_continuation: "Review the newly added sources.",
    voice_no_results: "Try different keywords or check the loaded documents.",
    voice_about: "About the assistant",
    voice_limits: "Scope",
    voice_examples: "Examples",
    suggestions_label: "Try a question",
    result_number: "Source {n}",
    faq_title: "Frequently asked questions",
    faq_topic: "Topic",
    faq_all: "All topics",
    faq_count: "{n} questions available",
    voice_menu: "Help",
    voice_show_less: "Show less",
  };
  // Variantes del tono activo (/config::microcopia). El widget rota entre ellas;
  // si /config no responde, usa el texto de TEXTOS.
  var MICROCOPIA = {};
  var giro = 0;
  function micro(situacion, variables) {
    var opciones = MICROCOPIA[situacion];
    if (!opciones || !opciones.length) return texto(situacion, variables);
    giro += 1;
    var valor = String(opciones[giro % opciones.length]);
    Object.keys(variables || {}).forEach(function (nombre) {
      valor = valor.split("{" + nombre + "}").join(String(variables[nombre]));
    });
    return valor;
  }
  function texto(clave, variables) {
    var valor = String(TEXTOS[clave] || "");
    Object.keys(variables || {}).forEach(function (nombre) {
      valor = valor.split("{" + nombre + "}").join(String(variables[nombre]));
    });
    return valor;
  }
  var PRESENTACION = {
    densidad: "comoda",
    citas: "acordeon",
    mostrarEtiquetaEstado: true,
    alineacion: "justificada",
    diseno: "cards",
    mostrarNumeros: true,
    mostrarRuta: true,
    expandirContexto: false,
    mostrarSugerencias: true,
  };
  var CONTENIDO = {}, SUGERENCIAS = [], PREGUNTAS_FIJAS = [];
  function emitir(nombre, detalle) {
    host.dispatchEvent(new CustomEvent(nombre, { detail: detalle || {}, bubbles: true }));
  }

  // -------------------------------------------------------------------
  // 1. Identificador de sesión: uno nuevo en cada carga de página -- la
  //    API exige `session_id` en cada POST /ask. El servidor recuerda la
  //    conversación por sesión (preguntas de seguimiento); salir de la
  //    página o recargarla empieza otra, como lo que ve la persona (el
  //    widget no guarda el historial). La anterior se olvida en el
  //    servidor por inactividad.
  // -------------------------------------------------------------------
  function generarIdSesion() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    // Repuesto sin crypto.randomUUID (navegadores más viejos): suficiente
    // para distinguir sesiones, no necesita ser criptográficamente fuerte.
    return "session-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  var ID_SESION = generarIdSesion();

  // -------------------------------------------------------------------
  // 2. Contenedor con Shadow DOM: aísla el CSS del widget del sitio
  //    anfitrión (y viceversa), sea cual sea el sitio donde se embeba.
  // -------------------------------------------------------------------
  var raiz = host.attachShadow({ mode: "open" });

  var estilos = document.createElement("style");
  // TODO el diseno sale de estas variables. Son los valores de repuesto,
  // los que se usan si el servicio no responde: `config/styles.yaml`
  // las redefine y el servicio las sirve en /styles.css, que se enlaza
  // DESPUES de este bloque (ver mas abajo) y por tanto gana.
  estilos.textContent = [
    ".rw-raiz{",
    "  --rw-acento:" + COLOR_ACENTO + ";",
    "  --rw-acento-texto:#ffffff;",
    "  --rw-superficie:#ffffff;",
    "  --rw-fondo:#f4f5f7;",
    "  --rw-texto:#15181d;",
    "  --rw-texto-suave:#5b6472;",
    "  --rw-borde:#e3e6ea;",
    "  --rw-aviso:#b4801f;",
    "  --rw-aviso-borde:#d9a441;",
    "  --rw-vivo:#22c55e;",
    "  --rw-sombra-panel:0 12px 40px rgba(16,24,40,.18), 0 2px 8px rgba(16,24,40,.08);",
    "  --rw-sombra-boton:0 8px 24px rgba(16,24,40,.28);",
    "  --rw-fuente:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;",
    "  --rw-tamano-base:14px;",
    "  --rw-tamano-mensaje:13.5px;",
    "  --rw-tamano-cita:12px;",
    "  --rw-tamano-etiqueta:10.5px;",
    "  --rw-interlineado:1.55;",
    "  --rw-titulo:var(--rw-texto);--rw-seccion:var(--rw-texto-suave);",
    "  --rw-superficie-resultado:var(--rw-superficie);--rw-borde-resultado:var(--rw-borde);",
    "  --rw-fuente-titulo:var(--rw-fuente);--rw-tamano-titulo:17px;--rw-peso-titulo:650;--rw-tamano-seccion:12px;",
    "  --rw-radio-resultado:12px;--rw-separacion-resultado:16px;--rw-relleno-resultado:14px;",
    "  --rw-radio-panel:18px;",
    "  --rw-radio-burbuja:16px;",
    "  --rw-radio-control:12px;",
    "  --rw-ancho-panel:390px;",
    "  --rw-alto-panel:600px;",
    "  --rw-tamano-boton:58px;",
    "  --rw-tamano-icono:26px;",
    "  --rw-separacion:12px;",
    "  --rw-relleno:16px;",
    "  --rw-dur-panel:.34s;",
    "  --rw-dur-salida:.2s;",
    "  --rw-dur-burbuja:.36s;",
    "  --rw-dur-control:.22s;",
    "  --rw-dur-latido:1.2s;",
    "  --rw-curva:cubic-bezier(.16,1,.3,1);",
    "  --rw-desplazamiento-entrada:16px;",
    "  --rw-escala-entrada:.92;",
    "  --rw-escala-hover:1.04;",
    "  --rw-margen-x:24px;--rw-margen-y:24px;",
    "  position:fixed;z-index:var(--rw-z,2147483000);font-family:var(--rw-fuente);",
    "  font-size:var(--rw-tamano-base);line-height:1.5;-webkit-font-smoothing:antialiased;}",
    // Ubicación: esquina por atributo; el panel sale hacia dentro de la pantalla.
    ".rw-raiz[data-posicion$='derecha']{right:var(--rw-margen-x);}",
    ".rw-raiz[data-posicion$='izquierda']{left:var(--rw-margen-x);}",
    ".rw-raiz[data-posicion^='abajo']{bottom:var(--rw-margen-y);}",
    ".rw-raiz[data-posicion^='arriba']{top:var(--rw-margen-y);}",
    ".rw-raiz[data-tamano='compacto']{--rw-ancho-panel:340px;--rw-alto-panel:520px;}",
    ".rw-raiz[data-tamano='amplio']{--rw-ancho-panel:440px;--rw-alto-panel:680px;}",
    "@media (prefers-color-scheme:dark){.rw-raiz{",
    "  --rw-superficie:#1b1f27;--rw-fondo:#12151b;--rw-texto:#eceff4;",
    "  --rw-texto-suave:#9aa4b2;--rw-borde:#2b323d;--rw-aviso:#e0b055;",
    "  --rw-sombra-panel:0 12px 40px rgba(0,0,0,.55), 0 2px 8px rgba(0,0,0,.35);",
    "  --rw-sombra-boton:0 8px 24px rgba(0,0,0,.5);}}",
    ":host, *{box-sizing:border-box;}",

    ".rw-boton{width:var(--rw-tamano-boton);height:var(--rw-tamano-boton);border-radius:50%;",
    "  border:none;cursor:pointer;background:var(--rw-acento);color:var(--rw-acento-texto);",
    "  padding:0;box-shadow:var(--rw-sombra-boton);display:flex;align-items:center;",
    "  justify-content:center;",
    "  transition:transform var(--rw-dur-control) ease, box-shadow var(--rw-dur-control) ease;}",
    ".rw-boton:hover{transform:translateY(-2px) scale(var(--rw-escala-hover));}",
    ".rw-boton:active{transform:translateY(0) scale(.97);}",
    ".rw-boton:focus-visible{outline:3px solid var(--rw-acento);outline-offset:3px;}",
    ".rw-boton svg{width:var(--rw-tamano-icono);height:var(--rw-tamano-icono);display:block;}",
    ".rw-boton .rw-icono-cerrar{display:none;}",
    // El papel del logo llena menos que un trazo: algo más grande que los otros íconos.
    ".rw-boton .rw-icono-chat{width:calc(var(--rw-tamano-icono) * 1.45);height:calc(var(--rw-tamano-icono) * 1.45);}",
    ".rw-boton[aria-expanded='true'] .rw-icono-chat{display:none;}",
    ".rw-boton[aria-expanded='true'] .rw-icono-cerrar{display:block;}",

    ".rw-panel{position:fixed;width:var(--rw-ancho-panel);",
    "  max-width:calc(100vw - var(--rw-margen-x) * 2);height:var(--rw-alto-panel);",
    "  max-height:calc(100dvh - var(--rw-tamano-boton) - var(--rw-margen-y) * 2 - 32px);",
    "  background:var(--rw-superficie);",
    "  border-radius:var(--rw-radio-panel);box-shadow:var(--rw-sombra-panel);display:flex;",
    "  flex-direction:column;overflow:hidden;border:1px solid var(--rw-borde);",
    "  animation:rw-entrar var(--rw-dur-panel) var(--rw-curva);}",
    ".rw-raiz[data-posicion$='derecha'] .rw-panel{right:var(--rw-margen-x);}",
    ".rw-raiz[data-posicion$='izquierda'] .rw-panel{left:var(--rw-margen-x);}",
    ".rw-raiz[data-posicion^='abajo'] .rw-panel{bottom:calc(var(--rw-margen-y) + var(--rw-tamano-boton) + 16px);",
    "  transform-origin:bottom center;}",
    ".rw-raiz[data-posicion^='arriba'] .rw-panel{top:calc(var(--rw-margen-y) + var(--rw-tamano-boton) + 16px);",
    "  transform-origin:top center;}",
    // Crece desde la esquina del lanzador, no desde el centro.
    ".rw-raiz[data-posicion='abajo-derecha'] .rw-panel{transform-origin:bottom right;}",
    ".rw-raiz[data-posicion='abajo-izquierda'] .rw-panel{transform-origin:bottom left;}",
    ".rw-raiz[data-posicion='arriba-derecha'] .rw-panel{transform-origin:top right;}",
    ".rw-raiz[data-posicion='arriba-izquierda'] .rw-panel{transform-origin:top left;}",
    // Al cerrar se encoge hacia el lanzador; recién al terminar queda hidden.
    ".rw-panel.rw-saliendo{animation:rw-salir var(--rw-dur-salida) cubic-bezier(.4,0,1,1) forwards;",
    "  pointer-events:none;}",
    ".rw-raiz[data-lanzador='oculto'] .rw-panel{top:auto;bottom:var(--rw-margen-y);}",
    ".rw-raiz[data-lanzador='oculto'][data-posicion^='arriba'] .rw-panel{bottom:auto;top:var(--rw-margen-y);}",
    ".rw-panel[hidden]{display:none;}",
    // Incrustado: el widget vive dentro de un contenedor del sitio, siempre abierto.
    ".rw-raiz[data-posicion='incrustado']{position:relative;inset:auto;z-index:auto;width:100%;height:100%;}",
    ".rw-raiz[data-posicion='incrustado'] .rw-boton{display:none;}",
    ".rw-raiz[data-posicion='incrustado'] .rw-panel{position:relative;inset:auto;width:100%;max-width:100%;",
    "  height:100%;min-height:420px;max-height:none;animation:none;box-shadow:none;}",
    // Incrustado en un teléfono: de borde a borde, sin esquinas ni marco.
    "@media (max-width:480px){.rw-raiz[data-posicion='incrustado'] .rw-panel{border-radius:0;border-inline:0;}}",
    // Lanzador: burbuja (por defecto), pestaña con el nombre, u oculto.
    ".rw-raiz[data-lanzador='oculto'] .rw-boton{display:none;}",
    ".rw-raiz[data-lanzador='pestana'] .rw-boton{width:auto;height:44px;border-radius:var(--rw-radio-control);",
    "  padding:0 16px;gap:8px;font:600 var(--rw-tamano-base)/1 var(--rw-fuente);}",
    ".rw-raiz[data-lanzador='pestana'] .rw-boton svg{width:20px;height:20px;}",
    ".rw-boton-texto{display:none;white-space:nowrap;max-width:220px;overflow:hidden;text-overflow:ellipsis;}",
    ".rw-raiz[data-lanzador='pestana'] .rw-boton-texto{display:inline;}",
    "@keyframes rw-aparecer{from{opacity:0;}to{opacity:1;}}",
    "@keyframes rw-entrar{",
    "  from{opacity:0;transform:translateY(var(--rw-desplazamiento-entrada)) scale(var(--rw-escala-entrada));}",
    "  60%{opacity:1;}",
    "  to{opacity:1;transform:translateY(0) scale(1);}}",
    "@keyframes rw-salir{",
    "  to{opacity:0;transform:translateY(calc(var(--rw-desplazamiento-entrada) / 2)) scale(var(--rw-escala-entrada));}}",
    "@keyframes rw-subir{from{opacity:0;transform:translateY(24px);}to{opacity:1;transform:none;}}",

    // Lanzador (burbuja): el papel y la X se cruzan con un giro en vez de saltar.
    ".rw-raiz:not([data-lanzador='pestana']) .rw-boton{position:relative;}",
    ".rw-raiz:not([data-lanzador='pestana']) .rw-boton > svg{position:absolute;left:50%;top:50%;",
    "  transition:opacity var(--rw-dur-control) ease, transform var(--rw-dur-panel) var(--rw-curva);}",
    ".rw-raiz:not([data-lanzador='pestana']) .rw-boton .rw-icono-chat{transform:translate(-50%,-50%);}",
    ".rw-raiz:not([data-lanzador='pestana']) .rw-boton .rw-icono-cerrar{display:block;opacity:0;",
    "  transform:translate(-50%,-50%) rotate(-90deg) scale(.5);}",
    ".rw-raiz:not([data-lanzador='pestana']) .rw-boton[aria-expanded='true'] .rw-icono-chat{display:block;",
    "  opacity:0;transform:translate(-50%,-50%) rotate(90deg) scale(.5);}",
    ".rw-raiz:not([data-lanzador='pestana']) .rw-boton[aria-expanded='true'] .rw-icono-cerrar{opacity:1;",
    "  transform:translate(-50%,-50%);}",

    "@media (prefers-reduced-motion:reduce){",
    "  .rw-panel,.rw-msg,.rw-punto,.rw-parrafo,.rw-citas,.rw-escribiendo,.rw-enviando svg{animation:none;}",
    "  .rw-boton,.rw-enviar,.rw-boton > svg,.rw-form input{transition:none;}}",

    ".rw-cabecera{background:var(--rw-superficie);color:var(--rw-texto);",
    "  padding:14px var(--rw-relleno);display:flex;align-items:center;gap:11px;flex:none;",
    "  border-bottom:1px solid var(--rw-borde);}",
    ".rw-avatar{width:34px;height:34px;border-radius:50%;background:var(--rw-acento);",
    "  color:var(--rw-acento-texto);display:flex;align-items:center;justify-content:center;flex:none;}",
    ".rw-avatar svg{width:26px;height:26px;}",
    // Avatar animado (opcional): reemplaza al ícono solo cuando ya está montado.
    ".rw-avatar.rw-avatar-vivo{width:var(--rw-avatar-tamano,56px);height:var(--rw-avatar-tamano,56px);",
    "  background:transparent;border-radius:0;}",
    ".rw-avatar-lienzo{width:100%;height:100%;display:block;pointer-events:none;}",
    ".rw-avatar-lienzo svg{width:100%;height:100%;}",
    // El motor de Folio dibuja el logo completo y acepta --rw-folio-* del tema.
    ".rw-boton.rw-con-avatar[aria-expanded='false'] .rw-icono-chat{display:none;}",
    ".rw-boton .rw-avatar-lienzo{width:84%;height:84%;}",
    ".rw-boton[aria-expanded='true'] .rw-avatar-lienzo{display:none;}",
    ".rw-avatar-esquina{position:absolute;right:18px;z-index:1;width:var(--rw-avatar-tamano,56px);",
    "  height:var(--rw-avatar-tamano,56px);pointer-events:none;}",
    ".rw-avatar-esquina[data-esquina='esquina-superior']{top:calc(var(--rw-avatar-tamano,56px) / -2);}",
    ".rw-avatar-esquina[data-esquina='esquina-inferior']{bottom:72px;}",
    ".rw-cabecera-textos{flex:1;min-width:0;}",
    ".rw-cabecera h2{margin:0;font-family:var(--rw-fuente-titulo);color:var(--rw-titulo);font-size:calc(var(--rw-tamano-base) + .5px);font-weight:var(--rw-peso-titulo);",
    "  letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}",
    ".rw-subtitulo{margin:1px 0 0;font-size:11.5px;color:var(--rw-texto-suave);",
    "  display:flex;align-items:center;gap:5px;}",
    ".rw-punto-vivo{width:6px;height:6px;border-radius:50%;background:var(--rw-vivo);flex:none;}",
    ".rw-cerrar{background:transparent;border:none;color:var(--rw-texto-suave);cursor:pointer;",
    "  line-height:0;padding:7px;border-radius:9px;flex:none;",
    "  transition:background var(--rw-dur-control) ease;}",
    ".rw-cerrar svg{width:17px;height:17px;}",
    ".rw-cerrar:hover,.rw-cerrar:focus-visible{background:var(--rw-fondo);color:var(--rw-texto);}",

    ".rw-mensajes{flex:1 1 auto;overflow-y:auto;padding:var(--rw-relleno);display:flex;",
    "  flex-direction:column;gap:var(--rw-separacion);background:var(--rw-fondo);",
    "  min-height:0;scrollbar-gutter:stable;}",
    ".rw-mensajes,.rw-tabla-scroll,.rw-faq-lista,.rw-voz-texto{scrollbar-width:thin;",
    "  scrollbar-color:color-mix(in srgb,var(--rw-texto-suave) 40%,transparent) transparent;}",
    ".rw-raiz ::-webkit-scrollbar{width:6px;height:6px;}",
    ".rw-raiz ::-webkit-scrollbar-track{background:transparent;}",
    ".rw-raiz ::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--rw-texto-suave) 40%,transparent);border-radius:99px;}",
    ".rw-raiz ::-webkit-scrollbar-thumb:hover{background:var(--rw-acento);}",
    ".rw-panel[data-densidad='compacta'] .rw-mensajes{padding:10px;gap:8px;}",
    ".rw-panel[data-densidad='compacta'] .rw-msg{padding:7px 10px;max-width:92%;}",
    ".rw-msg{max-width:86%;padding:10px 13px;border-radius:var(--rw-radio-burbuja);",
    "  font-size:var(--rw-tamano-mensaje);line-height:var(--rw-interlineado);",
    "  white-space:pre-wrap;overflow-wrap:anywhere;",
    "  animation:rw-burbuja var(--rw-dur-burbuja) var(--rw-curva) both;transform-origin:bottom left;}",
    "@keyframes rw-burbuja{from{opacity:0;transform:translateY(10px) scale(.96);}to{opacity:1;transform:none;}}",
    // Lo que escribe la persona sale desde el campo (abajo a la derecha).
    ".rw-msg.rw-msg-usuario{transform-origin:bottom right;}",
    // La respuesta se revela párrafo a párrafo (el retraso lo pone el JS) y las citas al final.
    ".rw-msg .rw-parrafo{animation:rw-parrafo var(--rw-dur-burbuja) var(--rw-curva) both;}",
    "@keyframes rw-parrafo{from{opacity:0;transform:translateY(4px);}to{opacity:1;transform:none;}}",
    ".rw-msg .rw-citas{animation:rw-aparecer var(--rw-dur-burbuja) ease-out both;}",
    // Párrafos de la respuesta (answer_blocks): el pasaje es texto del documento;
    // el conector y la cita, frases del asistente, van más suaves.
    ".rw-parrafo{margin:0;}",
    ".rw-parrafo + .rw-parrafo{margin-top:.6em;}",
    ".rw-conector,.rw-cita-breve{color:var(--rw-texto-suave);}",
    ".rw-cita-breve{font-size:var(--rw-tamano-cita);}",
    ".rw-resultados{margin:.8em 0 0;padding-left:1.5em;white-space:normal;}",
    ".rw-resultado{margin:.8em 0;padding:.7em;border:1px solid var(--rw-borde);border-radius:8px;}",
    ".rw-resultado-titulo{margin:0;font-weight:600;overflow-wrap:anywhere;}",
    ".rw-resultado-origen{margin:.35em 0;color:var(--rw-texto-suave);font-size:var(--rw-tamano-cita);}",
    ".rw-resultado-vista,.rw-resultado-contexto{white-space:pre-wrap;overflow-wrap:anywhere;}",
    ".rw-resultado details{margin-top:.6em;}",
    ".rw-resultado summary{cursor:pointer;color:var(--rw-acento);}",
    ".rw-panel[data-modo='busqueda'] .rw-form{border-top:1px solid var(--rw-borde);border-bottom:0;",
    "  background:var(--rw-superficie);padding:12px var(--rw-relleno);}",
    ".rw-panel[data-modo='busqueda'] .rw-form input{border-radius:24px;min-width:0;}",
    ".rw-panel[data-modo='busqueda'] .rw-enviar{border-radius:50%;}",
    ".rw-panel[data-modo='busqueda'] .rw-mensajes{gap:0;background:var(--rw-fondo);}",
    ".rw-busqueda{width:100%;min-width:0;color:var(--rw-texto);line-height:var(--rw-interlineado);}",
    ".rw-busqueda-contador{font-size:var(--rw-tamano-cita);font-weight:400;color:var(--rw-texto-suave);",
    "  margin:0 0 18px;overflow-wrap:anywhere;}",
    ".rw-busqueda .rw-resultados{list-style:none;margin:0;padding:0;}",
    ".rw-busqueda .rw-resultado{border:1px solid var(--rw-borde-resultado);border-radius:var(--rw-radio-resultado);",
    "  margin:0 0 var(--rw-separacion-resultado);padding:var(--rw-relleno-resultado);background:var(--rw-superficie-resultado);",
    "  animation:rw-resultados-entrar var(--rw-dur-burbuja) var(--rw-curva) both;}",
    "@keyframes rw-resultados-entrar{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}",
    ".rw-mensajes.rw-buscando .rw-busqueda{opacity:.5;transition:opacity var(--rw-dur-control) ease;}",
    ".rw-carga{height:3px;flex:none;overflow:hidden;background:var(--rw-fondo);}",
    ".rw-carga[hidden]{display:none;}",
    ".rw-carga::after{content:'';display:block;width:40%;height:100%;background:var(--rw-acento);",
    "  border-radius:99px;animation:rw-carga 1s ease-in-out infinite;}",
    "@keyframes rw-carga{from{transform:translateX(-100%);}to{transform:translateX(350%);}}",
    ".rw-panel[data-animaciones='false'] .rw-resultado,.rw-panel[data-animaciones='false'] .rw-carga::after{animation:none;}",
    ".rw-panel[data-animaciones='false'] .rw-busqueda{transition:none;}",
    "@media(prefers-reduced-motion:reduce){.rw-busqueda .rw-resultado,.rw-carga::after{animation:none;}",
    "  .rw-mensajes.rw-buscando .rw-busqueda{transition:none;}}",
    ".rw-busqueda .rw-resultado-origen{margin:0 0 8px;line-height:1.4;overflow-wrap:anywhere;}",
    ".rw-resultado-numero{display:inline-block;border:1px solid var(--rw-borde-resultado);border-radius:4px;",
    "  padding:1px 6px;margin-inline-end:8px;color:var(--rw-seccion);font-weight:650;font-size:var(--rw-tamano-seccion);}",
    ".rw-busqueda .rw-resultado-titulo{display:block;font-family:var(--rw-fuente-titulo);font-size:var(--rw-tamano-titulo);",
    "  font-weight:var(--rw-peso-titulo);line-height:1.4;text-align:start;background:none;border:0;padding:0;color:var(--rw-titulo);cursor:pointer;}",
    ".rw-busqueda .rw-resultado-titulo:hover{text-decoration:underline;}",
    ".rw-panel[data-diseno='lines'] .rw-busqueda .rw-resultado{border:0;border-bottom:1px solid var(--rw-borde-resultado);",
    "  border-radius:0;background:transparent;padding:0 0 var(--rw-relleno-resultado);}",
    ".rw-panel[data-diseno='editorial'] .rw-busqueda .rw-resultado{border:0;border-inline-start:3px solid var(--rw-borde-resultado);",
    "  border-radius:0;padding:var(--rw-relleno-resultado);}",
    ".rw-busqueda .rw-resultado-titulo:focus-visible,.rw-busqueda summary:focus-visible{",
    "  outline:2px solid var(--rw-acento);outline-offset:3px;}",
    ".rw-panel[data-preset='contrast'] .rw-resultado-titulo,",
    ".rw-panel[data-preset='contrast'] .rw-busqueda summary{text-decoration:underline;}",
    ".rw-panel[data-preset='contrast'] .rw-seguir{color:var(--rw-texto);border-color:var(--rw-texto);}",
    ".rw-panel[data-preset='contrast'] .rw-busqueda :focus-visible,",
    ".rw-panel[data-preset='contrast'] .rw-form input:focus{outline:2px solid var(--rw-texto);outline-offset:3px;}",
    ".rw-panel[data-modo='busqueda'] .rw-enviando svg{animation:none;}",
    ".rw-resultado-ruta{margin:6px 0;color:var(--rw-seccion);font-size:var(--rw-tamano-seccion);overflow-wrap:anywhere;}",
    ".rw-busqueda .rw-resultado-vista{white-space:normal;margin:6px 0;font-size:var(--rw-tamano-mensaje);}",
    ".rw-busqueda .rw-resultado-vista strong{font-weight:700;}",
    ".rw-busqueda .rw-resultado-contexto{font-size:var(--rw-tamano-mensaje);margin:10px 0;}",
    ".rw-resultado-encabezado{margin:0;font-size:inherit;font-weight:600;}",
    ".rw-documento{white-space:normal;min-width:0;line-height:max(1.6,var(--rw-interlineado));}",
    ".rw-documento p{margin:0;white-space:pre-line;overflow-wrap:anywhere;}",
    ".rw-documento p + p{margin-top:.85em;}",
    ".rw-documento h5{margin:1.1em 0 .5em;padding-bottom:.4em;border-bottom:1px solid var(--rw-borde-resultado);",
    "  font-family:var(--rw-fuente-titulo);font-weight:var(--rw-peso-titulo);color:var(--rw-seccion);font-size:1.05em;line-height:1.4;text-align:start;}",
    ".rw-documento h5:first-child{margin-top:0;}",
    ".rw-tabla-scroll{max-width:100%;overflow-x:auto;overscroll-behavior-x:contain;margin:.9em 0;",
    "  border:1px solid var(--rw-borde);border-radius:8px;scrollbar-width:thin;}",
    ".rw-tabla-scroll:focus-visible{outline:2px solid var(--rw-acento);outline-offset:2px;}",
    ".rw-tabla{border-collapse:collapse;table-layout:auto;min-width:100%;font-size:.95em;}",
    ".rw-tabla td,.rw-tabla th{padding:10px 12px;min-width:140px;max-width:320px;",
    "  vertical-align:top;border-bottom:1px solid var(--rw-borde);border-right:1px solid var(--rw-borde);",
    "  text-align:start;white-space:pre-wrap;overflow-wrap:anywhere;}",
    ".rw-tabla tr:last-child>*{border-bottom:0;}.rw-tabla tr>*:last-child{border-right:0;}",
    ".rw-tabla th{font-weight:650;background:var(--rw-fondo);overflow-wrap:normal;hyphens:none;}",
    ".rw-tabla tbody tr:nth-child(even){background:color-mix(in srgb,var(--rw-fondo) 60%,transparent);}",
    ".rw-fuente-literal pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere;}",
    ".rw-parrafo-frase .rw-documento{color:var(--rw-texto-suave);}",
    ".rw-busqueda details{margin:8px 0 0;padding:0;font-size:var(--rw-tamano-cita);}",
    ".rw-busqueda details[open]{border-left:2px solid var(--rw-borde);padding-left:12px;}",
    ".rw-busqueda-acciones{border-top:1px solid var(--rw-borde);padding-top:12px;}",
    ".rw-busqueda-ayuda{font-size:var(--rw-tamano-cita);color:var(--rw-texto-suave);margin:0 0 12px;}",
    ".rw-busqueda-vacia{text-align:center;padding:36px 0;color:var(--rw-texto-suave);}",
    ".rw-busqueda-vacia h3{color:var(--rw-texto);font-size:18px;margin:0 0 10px;}",
    ".rw-sugerencias{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin-top:16px;}",
    ".rw-sugerencias button{font:inherit;font-size:var(--rw-tamano-cita);text-align:start;max-width:100%;overflow-wrap:anywhere;",
    "  border:1px solid var(--rw-borde);border-radius:var(--rw-radio-control);background:var(--rw-superficie);color:var(--rw-texto);",
    "  padding:8px 10px;cursor:pointer;}.rw-sugerencias button:hover{border-color:var(--rw-acento);}",
    ".rw-sugerencias button:focus-visible{outline:2px solid var(--rw-acento);outline-offset:2px;}",
    ".rw-faq{margin:20px 0 0;text-align:start;border:1px solid var(--rw-borde);border-radius:var(--rw-radio-control);",
    "  background:var(--rw-superficie);padding:12px;color:var(--rw-texto);}",
    ".rw-faq summary{cursor:pointer;font-weight:600;color:var(--rw-titulo);}",
    ".rw-faq label{display:block;margin:12px 0 6px;font-size:var(--rw-tamano-cita);}",
    ".rw-faq select{width:100%;font:inherit;border:1px solid var(--rw-borde);border-radius:6px;padding:6px;",
    "  background:var(--rw-fondo);color:var(--rw-texto);}",
    ".rw-faq-lista{max-height:240px;overflow:auto;display:flex;flex-direction:column;gap:4px;}",
    ".rw-faq-lista button{font:inherit;font-size:var(--rw-tamano-cita);text-align:start;border:0;border-radius:4px;",
    "  padding:8px;background:var(--rw-fondo);color:var(--rw-texto);cursor:pointer;overflow-wrap:anywhere;}",
    ".rw-faq :focus-visible{outline:2px solid var(--rw-acento);outline-offset:2px;}",
    ".rw-panel[data-densidad='compacta'] .rw-busqueda .rw-resultado{margin-bottom:calc(var(--rw-separacion-resultado) * .75);}",
    // Justificado opcional (presentation.text_align): solo el texto del
    // documento, con guiones para que no queden huecos en una burbuja angosta.
    ".rw-panel[data-alineacion='justificada'] .rw-parrafo-pasaje,",
    ".rw-panel[data-alineacion='justificada'] .rw-cita-texto{text-align:justify;",
    "  -webkit-hyphens:auto;hyphens:auto;}",
    ".rw-panel[data-alineacion='justificada'] .rw-documento p{text-align:justify;",
    "  text-align-last:start;-webkit-hyphens:auto;hyphens:auto;}",
    ".rw-msg-usuario{align-self:flex-end;background:var(--rw-acento);color:var(--rw-acento-texto);",
    "  border-bottom-right-radius:5px;}",
    ".rw-msg-ok{align-self:flex-start;background:var(--rw-superficie);color:var(--rw-texto);",
    "  border:1px solid var(--rw-borde);border-bottom-left-radius:5px;}",
    ".rw-msg-relacionado{align-self:flex-start;background:var(--rw-superficie);",
    "  color:var(--rw-texto);border:1px solid var(--rw-borde);",
    "  border-left:3px solid var(--rw-aviso-borde);border-bottom-left-radius:5px;}",
    ".rw-msg-sin_respuesta{align-self:center;background:transparent;color:var(--rw-texto-suave);",
    "  border:none;font-size:var(--rw-tamano-cita);text-align:center;padding:4px 8px;max-width:100%;}",
    // Sin respuesta, pero con alternativas parecidas (postura proactiva): burbuja con citas.
    ".rw-msg-alternativas{align-self:flex-start;background:var(--rw-superficie);",
    "  color:var(--rw-texto);border:1px solid var(--rw-borde);border-bottom-left-radius:5px;}",
    ".rw-msg-conversacional{align-self:flex-start;background:var(--rw-superficie);",
    "  color:var(--rw-texto);border:1px dashed var(--rw-borde);border-bottom-left-radius:5px;}",
    ".rw-aviso{display:flex;align-items:center;gap:5px;font-size:var(--rw-tamano-etiqueta);",
    "  font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--rw-aviso);",
    "  margin-bottom:6px;}",

    ".rw-citas{margin-top:10px;border-top:1px solid var(--rw-borde);padding-top:8px;}",
    ".rw-citas-titulo{font-size:var(--rw-tamano-etiqueta);font-weight:700;text-transform:uppercase;",
    "  letter-spacing:.05em;color:var(--rw-texto-suave);margin:0 0 6px;}",
    ".rw-citas details{margin-top:5px;border-radius:9px;background:var(--rw-fondo);",
    "  border:1px solid var(--rw-borde);overflow:hidden;}",
    ".rw-citas summary{cursor:pointer;font-size:11.5px;color:var(--rw-texto-suave);",
    "  font-weight:600;padding:7px 9px;list-style:none;display:flex;gap:6px;align-items:baseline;}",
    ".rw-citas summary::-webkit-details-marker{display:none;}",
    ".rw-citas summary::before{content:'▸';font-size:10px;flex:none;",
    "  transition:transform .15s ease;display:inline-block;}",
    ".rw-citas details[open] summary::before{transform:rotate(90deg);}",
    ".rw-citas summary:hover{color:var(--rw-texto);}",
    ".rw-citas .rw-cita-texto{margin:0;padding:0 10px 10px 24px;font-size:var(--rw-tamano-cita);",
    "  color:var(--rw-texto);line-height:var(--rw-interlineado);white-space:pre-wrap;",
    "  overflow-wrap:anywhere;}",
    ".rw-citas-invitacion{margin:0 0 6px;font-size:var(--rw-tamano-cita);color:var(--rw-texto-suave);}",
    ".rw-cita-origen{min-width:0;}",
    ".rw-cita-posicion{font-weight:400;opacity:.85;white-space:nowrap;}",
    ".rw-cita{margin-top:5px;border-radius:9px;background:var(--rw-fondo);border:1px solid var(--rw-borde);}",
    ".rw-cita-cabecera{margin:0;padding:7px 9px 4px;font-size:11.5px;font-weight:600;color:var(--rw-texto-suave);}",
    ".rw-cita .rw-cita-texto{padding:0 10px 10px;}",
    ".rw-tramo{background:color-mix(in srgb, var(--rw-acento) 22%, transparent);color:inherit;",
    "  border-radius:3px;padding:0 1px;font-weight:600;}",

    ".rw-escribiendo{align-self:flex-start;display:flex;gap:4px;padding:12px 14px;",
    "  background:var(--rw-superficie);border:1px solid var(--rw-borde);",
    "  border-radius:var(--rw-radio-burbuja);border-bottom-left-radius:5px;",
    "  animation:rw-burbuja var(--rw-dur-burbuja) var(--rw-curva) both;transform-origin:bottom left;}",
    ".rw-punto{width:6px;height:6px;border-radius:50%;background:var(--rw-texto-suave);",
    "  animation:rw-latir var(--rw-dur-latido) infinite ease-in-out;}",
    ".rw-punto:nth-child(2){animation-delay:.15s;} .rw-punto:nth-child(3){animation-delay:.3s;}",
    "@keyframes rw-latir{0%,60%,100%{opacity:.25;transform:translateY(0);}",
    "  30%{opacity:1;transform:translateY(-3px);}}",

    ".rw-form{flex:none;display:flex;gap:8px;padding:var(--rw-separacion);align-items:center;",
    "  border-top:1px solid var(--rw-borde);background:var(--rw-superficie);}",
    ".rw-form input{flex:1;padding:11px 14px;border:1px solid var(--rw-borde);",
    "  border-radius:var(--rw-radio-control);font-size:var(--rw-tamano-mensaje);",
    "  font-family:inherit;background:var(--rw-fondo);color:var(--rw-texto);",
    "  transition:border-color var(--rw-dur-control) ease, box-shadow var(--rw-dur-control) ease;}",
    ".rw-form input::placeholder{color:var(--rw-texto-suave);}",
    ".rw-form input:focus{outline:none;border-color:var(--rw-acento);",
    "  box-shadow:0 0 0 3px color-mix(in srgb, var(--rw-acento) 18%, transparent);}",
    ".rw-form input:disabled{opacity:.6;}",
    ".rw-fuente{flex:none;display:block;text-align:center;font-size:var(--rw-tamano-etiqueta);",
    "  color:var(--rw-texto-suave);padding:0 0 6px;background:var(--rw-superficie);text-decoration:none;}",
    ".rw-fuente:hover,.rw-fuente:focus-visible{text-decoration:underline;color:var(--rw-texto);}",
    ".rw-enviar{background:var(--rw-acento);color:var(--rw-acento-texto);border:none;",
    "  border-radius:var(--rw-radio-control);width:42px;height:42px;flex:none;cursor:pointer;",
    "  display:flex;align-items:center;justify-content:center;",
    "  transition:opacity .15s ease, transform var(--rw-dur-control) ease;}",
    ".rw-enviar svg{width:18px;height:18px;}",
    ".rw-enviar:hover:not(:disabled){transform:scale(var(--rw-escala-hover));}",
    ".rw-enviar:disabled{opacity:.45;cursor:default;}",
    ".rw-enviar:active:not(:disabled){transform:scale(.92);}",
    // Al enviar, el avión sale por la esquina y vuelve a entrar.
    ".rw-enviando svg{animation:rw-despegar .5s var(--rw-curva);}",
    "@keyframes rw-despegar{0%{transform:none;opacity:1;}",
    "  40%{transform:translate(9px,-9px) scale(.7);opacity:0;}",
    "  41%{transform:translate(-9px,9px) scale(.7);opacity:0;}",
    "  100%{transform:none;opacity:1;}}",
    ".rw-enviar:focus-visible,.rw-seguir:focus-visible{outline:3px solid var(--rw-acento);outline-offset:2px;}",
    ".rw-seguir{font:inherit;color:var(--rw-acento);background:var(--rw-superficie);",
    "  border:1px solid var(--rw-acento);border-radius:var(--rw-radio-control);padding:.5em .8em;cursor:pointer;}",
    ".rw-seguir:disabled{opacity:.45;cursor:default;}",
    ".rw-sr-solo{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);}",
    ".rw-voz{flex:none;display:flex;align-items:flex-end;gap:10px;padding:8px var(--rw-separacion) 10px;",
    "  border-top:1px solid var(--rw-borde);background:var(--rw-fondo);color:var(--rw-texto);text-align:start;}",
    ".rw-voz-burbuja{position:relative;flex:1;min-width:0;padding:9px 13px;background:var(--rw-superficie);",
    "  border:1px solid var(--rw-borde);border-radius:var(--rw-radio-control);box-shadow:0 1px 2px rgba(16,24,40,.05);}",
    // Con el avatar al lado, la burbuja le apunta con una colita.
    ".rw-voz[data-avatar='si'] .rw-voz-burbuja::after{content:'';position:absolute;inset-inline-end:-6px;bottom:16px;",
    "  width:10px;height:10px;background:var(--rw-superficie);border-top:1px solid var(--rw-borde);",
    "  border-inline-end:1px solid var(--rw-borde);transform:rotate(45deg);}",
    ".rw-voz[dir='rtl'] .rw-voz-burbuja::after,[dir='rtl'] .rw-voz[data-avatar='si'] .rw-voz-burbuja::after{transform:rotate(-135deg);}",
    ".rw-voz-avatar{flex:none;width:var(--rw-avatar-tamano,56px);height:var(--rw-avatar-tamano,56px);display:none;}",
    ".rw-voz-avatar:not(:empty){display:block;}",
    ".rw-voz-avatar .rw-avatar-lienzo{width:100%;height:100%;display:block;pointer-events:none;}",
    ".rw-voz[hidden]{display:none;}",
    // El título es solo para lectores de pantalla; el menú de ayuda vive en el encabezado como un «?».
    ".rw-voz h3{position:absolute;width:1px;height:1px;margin:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}",
    ".rw-voz-texto{margin:0;min-height:0;font-size:var(--rw-tamano-cita);line-height:1.45;overflow-wrap:anywhere;",
    "  display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;}",
    ".rw-voz[data-expandido='true'] .rw-voz-texto{display:block;max-height:min(120px,25dvh);overflow:auto;}",
    ".rw-voz-menu{position:relative;flex:none;}",
    ".rw-voz-menu summary{list-style:none;cursor:pointer;display:flex;align-items:center;justify-content:center;width:32px;height:32px;",
    "  border-radius:50%;color:var(--rw-texto-suave);transition:background var(--rw-dur-control) ease,color var(--rw-dur-control) ease;}",
    ".rw-voz-menu summary::-webkit-details-marker{display:none;}",
    ".rw-voz-menu summary svg{width:19px;height:19px;}",
    ".rw-voz-menu summary:hover,.rw-voz-menu[open] summary{background:var(--rw-fondo);color:var(--rw-texto);}",
    ".rw-voz-menu summary:focus-visible{outline:2px solid var(--rw-acento);outline-offset:1px;}",
    ".rw-voz-menu .rw-voz-acciones{position:absolute;inset-inline-end:0;top:calc(100% + 8px);z-index:6;",
    "  width:220px;max-width:calc(100vw - 32px);padding:6px;display:flex;flex-direction:column;gap:2px;",
    "  background:var(--rw-superficie);border:1px solid var(--rw-borde);border-radius:var(--rw-radio-control);box-shadow:var(--rw-sombra-panel);}",
    ".rw-voz-menu:not([open]) .rw-voz-acciones{display:none;}",
    ".rw-voz-menu .rw-voz-acciones button{display:block;width:100%;text-align:start;font:inherit;font-size:var(--rw-tamano-cita);",
    "  color:var(--rw-texto);background:transparent;border:0;border-radius:8px;padding:9px 10px;cursor:pointer;}",
    ".rw-voz-menu .rw-voz-acciones button:hover{background:var(--rw-fondo);}",
    ".rw-voz-menu .rw-voz-acciones button:focus-visible{outline:2px solid var(--rw-acento);outline-offset:-2px;}",
    ".rw-voz-acciones{display:flex;flex-wrap:wrap;gap:8px;}",
    ".rw-voz button{font:inherit;font-size:var(--rw-tamano-etiqueta);color:var(--rw-texto);",
    "  background:var(--rw-superficie);border:1px solid var(--rw-borde);border-radius:var(--rw-radio-control);",
    "  padding:5px 10px;cursor:pointer;}",
    ".rw-voz button:focus-visible{outline:2px solid var(--rw-acento);outline-offset:2px;}",
    // «Mostrar completo» / «Contraer»: un enlace discreto bajo el texto, no un botón.
    ".rw-voz .rw-voz-mas{display:block;margin:3px 0 0;padding:0;border:0;background:none;color:var(--rw-acento);font-weight:600;",
    "  font-size:calc(var(--rw-tamano-etiqueta) + .5px);}",
    ".rw-voz .rw-voz-mas[hidden]{display:none;}",
    // Espera: un punto que aparece y desaparece mientras el asistente no habla (o aún no empieza).
    ".rw-voz-texto::after{content:'';display:inline-block;width:9px;height:9px;margin-inline-start:7px;border-radius:50%;",
    "  background:var(--rw-acento);vertical-align:middle;opacity:0;animation:rw-espera 1.7s ease-in-out infinite;}",
    ".rw-voz[data-typing='true'] .rw-voz-texto::after{display:none;}",
    "@keyframes rw-espera{0%,100%{opacity:0;transform:scale(.45);}50%{opacity:1;transform:scale(1);}}",
    ".rw-panel[data-animaciones='false'] .rw-voz-texto::after{animation:none;opacity:.55;}",
    "@media(prefers-reduced-motion:reduce){.rw-voz-texto::after{animation:none;opacity:.55;}}",

    // Pulido visual: buscador, botones, orientación, resultados y esqueleto de búsqueda.
    ".rw-campo{position:relative;flex:1;min-width:0;display:flex;align-items:center;}",
    ".rw-campo input{width:100%;box-sizing:border-box;min-height:46px;padding:11px 44px 11px 16px;}",
    ".rw-limpiar{position:absolute;inset-inline-end:7px;top:50%;transform:translateY(-50%);width:32px;height:32px;padding:0;",
    "  display:flex;align-items:center;justify-content:center;border:0;border-radius:50%;background:transparent;",
    "  color:var(--rw-texto-suave);cursor:pointer;transition:background var(--rw-dur-control) ease,color var(--rw-dur-control) ease;}",
    ".rw-limpiar[hidden]{display:none;}",
    ".rw-limpiar svg{width:15px;height:15px;}",
    ".rw-limpiar:hover,.rw-limpiar:focus-visible{background:color-mix(in srgb,var(--rw-texto) 10%,transparent);color:var(--rw-texto);}",
    ".rw-limpiar:focus-visible{outline:2px solid var(--rw-acento);outline-offset:1px;}",
    ".rw-form .rw-enviar{width:46px;height:46px;box-shadow:0 4px 12px color-mix(in srgb,var(--rw-acento) 32%,transparent);}",
    ".rw-form .rw-enviar:hover:not(:disabled){box-shadow:0 6px 16px color-mix(in srgb,var(--rw-acento) 42%,transparent);}",
    ".rw-form .rw-enviar:disabled{box-shadow:none;}",
    ".rw-panel[data-modo='busqueda'] .rw-form{padding-block:12px;}",
    ".rw-panel[data-modo='busqueda'] .rw-form input{background:var(--rw-fondo);}",
    // Botones y chips.
    ".rw-sugerencias button{min-height:40px;padding:9px 14px;border-radius:99px;box-shadow:0 1px 2px rgba(16,24,40,.05);",
    "  transition:border-color var(--rw-dur-control) ease,transform var(--rw-dur-control) ease,box-shadow var(--rw-dur-control) ease;}",
    ".rw-sugerencias button:hover{transform:translateY(-1px);box-shadow:0 4px 10px -4px rgba(16,24,40,.18);}",
    ".rw-sugerencias button:active{transform:none;}",
    ".rw-seguir{display:block;width:100%;min-height:44px;margin:0 0 12px;font-weight:650;border-radius:var(--rw-radio-control);",
    "  transition:background var(--rw-dur-control) ease,transform var(--rw-dur-control) ease;}",
    ".rw-seguir:hover:not(:disabled){background:color-mix(in srgb,var(--rw-acento) 8%,var(--rw-superficie));}",
    ".rw-seguir:active:not(:disabled){transform:scale(.985);}",
    ".rw-busqueda-acciones{text-align:center;}",
    ".rw-busqueda-ayuda{margin-bottom:12px;}",
    // Resultados.
    // El conteo («3 resultados para …») lo dice el asistente en su mensaje; la línea queda solo para lectores de pantalla.
    ".rw-busqueda-contador{position:absolute;width:1px;height:1px;margin:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}",
    ".rw-panel:not([data-diseno='lines']):not([data-diseno='editorial']) .rw-busqueda .rw-resultado{",
    "  box-shadow:0 1px 2px rgba(16,24,40,.05),0 6px 16px -8px rgba(16,24,40,.14);",
    "  transition:box-shadow var(--rw-dur-control) ease,border-color var(--rw-dur-control) ease;}",
    ".rw-panel:not([data-diseno='lines']):not([data-diseno='editorial']) .rw-busqueda .rw-resultado:hover{",
    "  border-color:color-mix(in srgb,var(--rw-acento) 38%,var(--rw-borde-resultado));}",
    ".rw-busqueda .rw-resultado-origen{display:flex;flex-wrap:wrap;align-items:center;column-gap:8px;row-gap:3px;margin:0 0 10px;}",
    ".rw-busqueda .rw-resultado-numero{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;padding:0 6px;",
    "  margin:0;border:0;border-radius:99px;background:var(--rw-acento);color:var(--rw-acento-texto);font-size:11px;font-weight:700;}",
    ".rw-resultado-doc{min-width:0;font-weight:650;color:var(--rw-texto);overflow-wrap:anywhere;}",
    ".rw-resultado-alcance{display:inline-flex;align-items:center;max-width:100%;padding:1px 9px;border-radius:99px;font-size:calc(var(--rw-tamano-cita) - .5px);font-weight:650;",
    "  color:var(--rw-acento);background:color-mix(in srgb,var(--rw-acento) 10%,var(--rw-superficie));",
    "  border:1px solid color-mix(in srgb,var(--rw-acento) 30%,var(--rw-borde));overflow-wrap:anywhere;}",
    ".rw-resultado-padre{color:var(--rw-seccion);background:var(--rw-fondo);border-color:var(--rw-borde-resultado);font-weight:600;}",
    ".rw-resultado-rasgos{flex-basis:100%;min-width:0;font-size:calc(var(--rw-tamano-cita) - 1px);color:var(--rw-texto-suave);overflow-wrap:anywhere;}",
    ".rw-resultado-archivo{flex-basis:100%;min-width:0;font-size:calc(var(--rw-tamano-cita) - 1px);color:var(--rw-texto-suave);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;opacity:.85;}",
    ".rw-busqueda .rw-resultado-vista{margin:8px 0 4px;}",
    ".rw-busqueda details{margin-top:10px;}",
    ".rw-busqueda details > summary{display:inline-flex;align-items:center;gap:8px;min-height:36px;padding:6px 14px;list-style:none;cursor:pointer;",
    "  border:1px solid color-mix(in srgb,var(--rw-acento) 35%,var(--rw-borde));border-radius:99px;",
    "  background:color-mix(in srgb,var(--rw-acento) 6%,var(--rw-superficie));color:var(--rw-acento);font-weight:650;",
    "  transition:background var(--rw-dur-control) ease,border-color var(--rw-dur-control) ease;}",
    ".rw-busqueda details > summary::-webkit-details-marker{display:none;}",
    ".rw-busqueda details > summary::before{content:'';width:6px;height:6px;border:solid currentColor;border-width:0 2px 2px 0;",
    "  transform:translateY(-1px) rotate(-45deg);transition:transform var(--rw-dur-control) ease;}",
    ".rw-busqueda details[open] > summary::before{transform:translateY(-2px) rotate(45deg);}",
    ".rw-busqueda details > summary:hover{background:color-mix(in srgb,var(--rw-acento) 12%,var(--rw-superficie));border-color:var(--rw-acento);}",
    ".rw-busqueda details[open]{border-left:0;padding-left:0;}",
    ".rw-busqueda details[open] > .rw-resultado-contexto{margin-top:12px;padding-inline-start:12px;border-inline-start:2px solid var(--rw-borde-resultado);}",
    // Carga secuencial: cada resultado entra a su turno, como una hoja que cae.
    ".rw-busqueda .rw-resultado{animation-delay:calc(var(--rw-i,0) * 320ms);}",
    "@keyframes rw-resultados-entrar{0%{opacity:0;transform:translateY(-22px) rotate(-1.8deg) scale(.98);}",
    "  60%{opacity:1;transform:translateY(2px) rotate(.3deg);}100%{opacity:1;transform:none;}}",
    // Esqueleto de búsqueda: hojas grises que llegan una tras otra.
    ".rw-esqueleto{padding:2px 0 0;}",
    ".rw-esqueleto-estado{display:flex;align-items:center;gap:8px;min-height:20px;margin:0 2px 14px;font-size:calc(var(--rw-tamano-cita) + .5px);color:var(--rw-texto-suave);}",
    ".rw-esqueleto-estado i{flex:none;width:7px;height:7px;border-radius:50%;background:var(--rw-acento);animation:rw-pulso-esq 1s ease-in-out infinite;}",
    "@keyframes rw-pulso-esq{0%,100%{transform:scale(.7);opacity:.5;}50%{transform:scale(1.25);opacity:1;}}",
    ".rw-esq-tarjeta{position:relative;border:1px solid var(--rw-borde-resultado);border-radius:var(--rw-radio-resultado);background:var(--rw-superficie-resultado);",
    "  padding:var(--rw-relleno-resultado);margin:0 0 var(--rw-separacion-resultado);transform-origin:50% 0;",
    "  animation:rw-hoja 2.4s cubic-bezier(.16,1,.3,1) infinite both;}",
    ".rw-esq-tarjeta:nth-of-type(2){animation-delay:.35s;}",
    ".rw-esq-tarjeta:nth-of-type(3){animation-delay:.7s;}",
    ".rw-esq-tarjeta::before{content:'';position:absolute;top:-1px;inset-inline-end:-1px;width:22px;height:22px;",
    "  border-start-end-radius:var(--rw-radio-resultado);border-end-start-radius:8px;",
    "  background:linear-gradient(225deg,var(--rw-fondo) 50%,var(--rw-borde-resultado) 50%);box-shadow:-2px 2px 4px rgba(0,0,0,.08);}",
    "@keyframes rw-hoja{0%{opacity:0;transform:translateY(-34px) rotate(-4deg) scale(.95);}",
    "  22%{opacity:1;transform:translateY(2px) rotate(.6deg);}34%,82%{opacity:1;transform:none;}100%{opacity:0;transform:translateY(8px);}}",
    ".rw-esq-l{display:block;height:9px;margin:0 0 8px;border-radius:5px;background:var(--rw-borde);}",
    ".rw-esq-n{width:20px;height:20px;border-radius:5px;margin-bottom:10px;background:transparent;border:1px solid var(--rw-borde);}",
    ".rw-esq-t{height:14px;width:70%;margin-bottom:12px;}",
    ".rw-esq-s{width:34%;height:8px;}",
    ".rw-esq-w1{width:100%;}.rw-esq-w2{width:92%;}.rw-esq-w3{width:58%;}",
    ".rw-mensajes.rw-buscando .rw-busqueda{opacity:1;}",
    ".rw-mensajes.rw-buscando .rw-busqueda .rw-resultados{opacity:.55;transition:opacity var(--rw-dur-control) ease;}",
    ".rw-panel[data-animaciones='false'] .rw-esq-tarjeta,.rw-panel[data-animaciones='false'] .rw-esqueleto-estado i{animation:none;}",
    "@media(prefers-reduced-motion:reduce){.rw-esq-tarjeta,.rw-esqueleto-estado i,.rw-busqueda .rw-resultado,",
    "  .rw-sugerencias button{animation:none;transition:none;}}",

    // Teléfono (o apaisado bajo): hoja a pantalla completa. La altura sigue al
    // viewport visible, así el teclado virtual no tapa el campo de texto.
    "@media (max-width:480px), (max-height:480px) and (orientation:landscape){",
    "  .rw-raiz:not([data-posicion='incrustado']){--rw-margen-x:16px;--rw-margen-y:16px;}",
    "  .rw-raiz:not([data-posicion='incrustado']) .rw-panel{position:fixed;left:0;right:0;",
    "    top:var(--rw-vv-arriba,0px);bottom:auto;width:100%;max-width:100%;",
    "    height:var(--rw-vv-alto,100dvh);max-height:none;border-radius:0;border:none;",
    "    padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom)",
    "      env(safe-area-inset-left);animation:rw-subir var(--rw-dur-panel) var(--rw-curva);}",
    "  .rw-msg{max-width:92%;}",
    "  .rw-raiz{--rw-avatar-tamano:40px !important;}",
    "  .rw-avatar-esquina[data-esquina='esquina-superior']{top:8px;right:56px;}",
    "  .rw-raiz.rw-teclado .rw-avatar.rw-avatar-vivo,.rw-raiz.rw-teclado .rw-avatar-esquina,.rw-raiz.rw-teclado .rw-voz-avatar{display:none;}}",
    // Contraste alto del sistema (Windows): bordes visibles y el tramo marcado.
    "@media (forced-colors:active){",
    "  .rw-boton,.rw-enviar,.rw-cerrar{border:2px solid ButtonText;}",
    "  .rw-panel,.rw-msg,.rw-citas details,.rw-cita{border:1px solid CanvasText;}",
    "  .rw-tramo{forced-color-adjust:none;background:Mark;color:MarkText;}}",
  ].join("\n");
  raiz.appendChild(estilos);

  // Tema del despliegue: `config/styles.yaml`, servido en
  // /styles.css. Se enlaza DESPUES del bloque de arriba, asi que
  // redefine las variables que declare y deja el resto con su valor de
  // repuesto. Si el servicio no responde, el widget se ve igual que aqui
  // -- nunca queda sin estilos.
  var temaServidor = document.createElement("link");
  temaServidor.rel = "stylesheet";
  temaServidor.href = API_BASE + "/styles.css";
  raiz.appendChild(temaServidor);

  // Iconos en SVG en vez de emoji: un emoji se dibuja distinto en cada
  // sistema (y en Windows sale con su propio color), mientras que el SVG
  // hereda `currentColor` y se ve igual en todas partes. Se construyen con
  // createElementNS porque este archivo no usa innerHTML en ningun punto.
  var NS_SVG = "http://www.w3.org/2000/svg";
  var TRAZOS = {
    cerrar: "M18 6 6 18M6 6l12 12",
    enviar: "M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z",
    buscar: "M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
    ayuda: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"
  };

  function icono(nombre, clase) {
    var svg = document.createElementNS(NS_SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    if (clase) svg.setAttribute("class", clase);
    var path = document.createElementNS(NS_SVG, "path");
    path.setAttribute("d", TRAZOS[nombre]);
    svg.appendChild(path);
    return svg;
  }

  // El ícono del asistente: el logo de ipsis en miniatura (docs/assets/logo.svg,
  // mismas coordenadas, recortado al papel). Los colores son variables para
  // que un tema los cambie; por defecto, los del logo.
  var FOLIO_ICONO = [
    ["path", { d: "M32 18h48l18 18v62a12 12 0 0 1-12 12H32a12 12 0 0 1-12-12V30a12 12 0 0 1 12-12z",
               "stroke-width": "2.5", "stroke-linejoin": "round" }, "papel", "borde"],
    ["path", { d: "M80 18v12a6 6 0 0 0 6 6h12z", "stroke-width": "2.5", "stroke-linejoin": "round" }, "pliegue", "borde"],
    ["rect", { x: "44", y: "44", width: "9", height: "20", rx: "4.5" }, "tinta"],
    ["rect", { x: "65", y: "44", width: "9", height: "20", rx: "4.5" }, "tinta"],
    ["rect", { x: "34", y: "78", width: "52", height: "5", rx: "2.5" }, "renglon"],
    ["rect", { x: "34", y: "89", width: "34", height: "9", rx: "4.5" }, "resalte"],
    ["rect", { x: "72", y: "91", width: "14", height: "5", rx: "2.5" }, "renglon"]
  ];
  var FOLIO_COLORES = { papel: "#f5f1e8", borde: "#d6cdb8", pliegue: "#e4dac4", tinta: "#1e293b",
                        renglon: "#cbd5e1", resalte: "#93c5fd" };

  function iconoFolio(clase) {
    var svg = document.createElementNS(NS_SVG, "svg");
    svg.setAttribute("viewBox", "14 12 100 104");
    svg.setAttribute("aria-hidden", "true");
    if (clase) svg.setAttribute("class", clase);
    var grupo = document.createElementNS(NS_SVG, "g");
    grupo.setAttribute("transform", "rotate(-5 64 64)");
    FOLIO_ICONO.forEach(function (pieza) {
      var el = document.createElementNS(NS_SVG, pieza[0]);
      Object.keys(pieza[1]).forEach(function (k) { el.setAttribute(k, pieza[1][k]); });
      el.style.fill = "var(--rw-folio-" + pieza[2] + "," + FOLIO_COLORES[pieza[2]] + ")";
      if (pieza[3]) el.style.stroke = "var(--rw-folio-" + pieza[3] + "," + FOLIO_COLORES[pieza[3]] + ")";
      grupo.appendChild(el);
    });
    svg.appendChild(grupo);
    return svg;
  }

  var contenedor = document.createElement("div");
  contenedor.className = "rw-raiz";
  raiz.appendChild(contenedor);

  function aplicarUbicacion() {
    contenedor.setAttribute("data-posicion", UBICACION.posicion);
    contenedor.setAttribute("data-tamano", UBICACION.tamano);
    contenedor.setAttribute("data-lanzador", UBICACION.lanzador);
    contenedor.style.setProperty("--rw-margen-x", UBICACION.desplazamiento_x + "px");
    contenedor.style.setProperty("--rw-margen-y", UBICACION.desplazamiento_y + "px");
    contenedor.style.setProperty("--rw-z", String(UBICACION.z_index));
  }
  aplicarUbicacion();

  // Región viva para lectores de pantalla: anuncia "buscando…" y los errores.
  var anunciador = document.createElement("div");
  anunciador.className = "rw-sr-solo";
  anunciador.setAttribute("role", "status");
  anunciador.setAttribute("aria-live", "polite");
  function anunciar(mensaje) {
    anunciador.textContent = "";
    window.setTimeout(function () { anunciador.textContent = mensaje; }, 30);
  }

  var boton = document.createElement("button");
  boton.className = "rw-boton";
  boton.type = "button";
  boton.setAttribute("aria-haspopup", "dialog");
  boton.setAttribute("aria-expanded", "false");
  boton.setAttribute("aria-label", texto("open", { title: TITULO_INICIAL }));
  // Dos iconos fijos: el CSS muestra uno u otro segun aria-expanded, asi
  // el mismo boton abre y cierra sin que nada dependa de la API.
  boton.appendChild(iconoFolio("rw-icono-chat"));
  boton.appendChild(icono("cerrar", "rw-icono-cerrar"));
  // Texto visible solo con el lanzador «pestana».
  var botonTexto = document.createElement("span");
  botonTexto.className = "rw-boton-texto";
  botonTexto.setAttribute("aria-hidden", "true");
  botonTexto.textContent = TITULO_INICIAL;
  boton.appendChild(botonTexto);
  contenedor.appendChild(boton);
  contenedor.appendChild(anunciador);

  var panel = document.createElement("div");
  panel.className = "rw-panel";
  panel.setAttribute("data-alineacion", PRESENTACION.alineacion);
  // Incrustado: parte de la página, no un diálogo modal.
  panel.setAttribute("role", INCRUSTADO ? "region" : "dialog");
  if (!INCRUSTADO) panel.setAttribute("aria-modal", "true");
  panel.setAttribute("aria-label", TITULO_INICIAL);
  panel.hidden = !INCRUSTADO;
  contenedor.appendChild(panel);

  var cabecera = document.createElement("div");
  cabecera.className = "rw-cabecera";

  var avatar = document.createElement("div");
  avatar.className = "rw-avatar";
  avatar.appendChild(iconoFolio());

  var cabeceraTextos = document.createElement("div");
  cabeceraTextos.className = "rw-cabecera-textos";
  var tituloEl = document.createElement("h2");
  tituloEl.id = "rw-titulo";
  tituloEl.textContent = TITULO_INICIAL;
  // Subtitulo fijo del widget: dice de entrada de donde salen las
  // respuestas, que es la promesa del sistema.
  var subtitulo = document.createElement("p");
  subtitulo.className = "rw-subtitulo";
  var puntoVivo = document.createElement("span");
  puntoVivo.className = "rw-punto-vivo";
  var subtituloTexto = document.createElement("span");
  subtituloTexto.textContent = texto("subtitle");
  subtitulo.appendChild(puntoVivo);
  subtitulo.appendChild(subtituloTexto);
  cabeceraTextos.appendChild(tituloEl);
  cabeceraTextos.appendChild(subtitulo);

  var botonCerrar = document.createElement("button");
  botonCerrar.type = "button";
  botonCerrar.className = "rw-cerrar";
  botonCerrar.setAttribute("aria-label", texto("close"));
  botonCerrar.appendChild(icono("cerrar"));

  cabecera.appendChild(avatar);
  cabecera.appendChild(cabeceraTextos);
  cabecera.appendChild(botonCerrar);
  panel.appendChild(cabecera);
  panel.setAttribute("aria-labelledby", "rw-titulo");

  var mensajes = document.createElement("div");
  mensajes.className = "rw-mensajes";
  mensajes.setAttribute("role", "log");
  mensajes.setAttribute("aria-live", "polite");
  panel.appendChild(mensajes);

  var form = document.createElement("form");
  form.className = "rw-form";
  var etiquetaInput = document.createElement("label");
  etiquetaInput.className = "rw-sr-solo";
  etiquetaInput.setAttribute("for", "rw-input");
  etiquetaInput.textContent = texto("question_label");
  var input = document.createElement("input");
  input.id = "rw-input";
  input.type = "text";
  input.autocomplete = "off";
  input.placeholder = texto("placeholder");
  var botonEnviar = document.createElement("button");
  botonEnviar.type = "submit";
  botonEnviar.className = "rw-enviar";
  botonEnviar.setAttribute("aria-label", texto("send"));
  botonEnviar.appendChild(icono("enviar"));
  var campo = document.createElement("span");
  campo.className = "rw-campo";
  var botonLimpiar = document.createElement("button");
  botonLimpiar.type = "button";
  botonLimpiar.className = "rw-limpiar";
  botonLimpiar.hidden = true;
  botonLimpiar.setAttribute("aria-label", texto("clear_input"));
  botonLimpiar.appendChild(icono("cerrar"));
  function actualizarLimpiar() { botonLimpiar.hidden = !input.value || input.disabled; }
  botonLimpiar.addEventListener("click", function () {
    input.value = "";
    actualizarLimpiar();
    input.focus();
  });
  input.addEventListener("input", function () { avatarAlTeclear(); actualizarLimpiar(); });
  campo.appendChild(input);
  campo.appendChild(botonLimpiar);
  form.appendChild(etiquetaInput);
  form.appendChild(campo);
  form.appendChild(botonEnviar);
  panel.appendChild(form);
  // AGPL §13: quien usa el servicio por red puede obtener su código fuente.
  var enlaceFuente = document.createElement("a");
  enlaceFuente.className = "rw-fuente";
  enlaceFuente.href = API_BASE + "/source";
  enlaceFuente.target = "_blank";
  enlaceFuente.rel = "noopener noreferrer";
  enlaceFuente.textContent = texto("source_code");
  panel.appendChild(enlaceFuente);

  // -------------------------------------------------------------------
  // 3. Render de mensajes -- TODO texto que venga de la API se asigna con
  //    `textContent`, nunca `innerHTML`: un documento con una comilla
  //    angular no debe poder inyectar marcado en el sitio anfitrión.
  // -------------------------------------------------------------------
  function sinMovimiento() {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  function desplazarAlFinal() {
    if (sinMovimiento() || typeof mensajes.scrollTo !== "function") {
      mensajes.scrollTop = mensajes.scrollHeight;
      return;
    }
    mensajes.scrollTo({ top: mensajes.scrollHeight, behavior: "smooth" });
  }

  function agregarMensajeUsuario(texto) {
    var burbuja = document.createElement("div");
    burbuja.className = "rw-msg rw-msg-usuario";
    burbuja.textContent = texto; // texto tecleado por el propio usuario
    mensajes.appendChild(burbuja);
    desplazarAlFinal();
  }

  var ETIQUETAS_ESTADO = {
    ok: null,
    relacionado: texto("not_direct"),
    sin_respuesta: null,
    conversacional: null,
  };

  // Rango del tramo exacto dentro del texto de una cita, o null. Solo se marca
  // si el texto en esos offsets es idéntico al tramo: nunca se adivina.
  function rangoExacto(frag, exacta) {
    if (!exacta || !frag || exacta.chunk_id !== frag.chunk_id || typeof frag.texto !== "string") return null;
    var ini = exacta.offset_inicio - frag.offset_inicio;
    var fin = exacta.offset_fin - frag.offset_inicio;
    if (isFinite(ini) && isFinite(fin) && ini >= 0 && fin > ini && fin <= frag.texto.length &&
        frag.texto.slice(ini, fin) === exacta.texto) {
      return [ini, fin];
    }
    return null;
  }

  // Texto literal de la cita con el tramo dentro de un <mark> creado por DOM.
  function textoConTramo(elemento, textoCita, rango) {
    if (!rango) {
      elemento.textContent = textoCita;
      return;
    }
    elemento.appendChild(document.createTextNode(textoCita.slice(0, rango[0])));
    var marca = document.createElement("mark");
    marca.className = "rw-tramo";
    marca.textContent = textoCita.slice(rango[0], rango[1]);
    elemento.appendChild(marca);
    elemento.appendChild(document.createTextNode(textoCita.slice(rango[1])));
  }

  // Las citas van SIEMPRE debajo de la respuesta, para comprobarla: la
  // presentación solo elige acordeón (desplegable) o lista (a la vista).
  function agregarCitas(contenedorMsg, fragmentos, exacta) {
    if (!fragmentos || !fragmentos.length) return;
    var caja = document.createElement("div");
    caja.className = "rw-citas";
    var invitacion = document.createElement("p");
    invitacion.className = "rw-citas-invitacion";
    invitacion.textContent = micro("citations_hint");
    caja.appendChild(invitacion);
    // Encabezado con el número de fuentes: deja ver de un vistazo que la
    // respuesta está respaldada, sin tener que desplegar nada.
    var titulo = document.createElement("p");
    titulo.className = "rw-citas-titulo";
    titulo.textContent = fragmentos.length === 1
      ? texto("sources_one") : texto("sources_many", { n: fragmentos.length });
    caja.appendChild(titulo);
    var enLista = PRESENTACION.citas === "lista";
    fragmentos.forEach(function (frag) {
      var item = document.createElement(enLista ? "div" : "details");
      item.className = enLista ? "rw-cita" : "";
      var cabeceraCita = document.createElement(enLista ? "p" : "summary");
      if (enLista) cabeceraCita.className = "rw-cita-cabecera";
      // documento + sección: texto de la API, SIEMPRE por textContent. Un solo
      // elemento en línea: así la posición fluye con el título y no se aprieta.
      var origen = document.createElement("span");
      origen.className = "rw-cita-origen";
      var seccion = frag.seccion && frag.seccion !== frag.doc_titulo ? " › " + frag.seccion : "";
      origen.textContent = (frag.doc_titulo || "") + seccion;
      if (typeof frag.offset_inicio === "number" && typeof frag.offset_fin === "number") {
        var posicion = document.createElement("span");
        posicion.className = "rw-cita-posicion";
        posicion.textContent = " · " + texto("citation_position", { start: frag.offset_inicio, end: frag.offset_fin });
        origen.appendChild(posicion);
      }
      cabeceraCita.appendChild(origen);
      var cuerpo = document.createElement("div");
      cuerpo.className = "rw-cita-texto";
      var rango = rangoExacto(frag, exacta);
      documentoVisual(cuerpo, frag.texto || "", frag.bloques_fuente, frag.offset_inicio, rango);
      if (rango && !enLista) item.open = true;  // la cita con el tramo se ve sin desplegar
      item.appendChild(cabeceraCita);
      item.appendChild(cuerpo);
      caja.appendChild(item);
    });
    contenedorMsg.appendChild(caja);
  }

  // Respuesta pública de /ask → la forma interna que pinta el widget.
  var ESTADOS_INTERNOS = { ok: "ok", related: "relacionado", no_answer: "sin_respuesta",
                           conversational: "conversacional", degraded: "degradado", saturated: "saturado" };
  function fragmentoInterno(f) {
    return { chunk_id: f.chunk_id, doc_id: f.doc_id, doc_titulo: f.doc_title, seccion: f.section, texto: f.text,
             offset_inicio: f.offset_start, offset_fin: f.offset_end, version: f.version,
             rango: f.rank, coincidencia_inicio: f.match_start, coincidencia_fin: f.match_end,
             truncado: f.truncated, archivo: f.source_name, alcance: f.scope, rasgos: f.distinctive_terms, bloques_fuente: f.source_blocks };
  }
  function respuestaInterna(r) {
    r = r || {};
    var exacta = r.exact_answer;
    return {
      estado: ESTADOS_INTERNOS[r.status] || "sin_respuesta",
      modo: r.response_mode,
      categoria: r.conversational_category,
      continuation: r.continuation,
      has_more: r.has_more,
      forma: r.result_shape,
      respuesta: r.answer,
      bloques: (r.answer_blocks || []).map(function (b) {
        return { tipo: b.type, texto: b.text, conector: b.connector, cita: b.citation };
      }),
      nivel: r.confidence_level || null,
      fragmentos: (r.fragments || []).map(fragmentoInterno),
      alternativas: (r.alternatives || []).map(fragmentoInterno),
      respuesta_exacta: exacta ? { chunk_id: exacta.chunk_id, texto: exacta.text, offset_inicio: exacta.offset_start,
                                   offset_fin: exacta.offset_end } : null
    };
  }

  // Texto de la API, siempre por textContent: conector, pasaje literal y cita
  // en elementos separados para darles estilo distinto.
  function parrafoDeBloque(bloque) {
    var parrafo = document.createElement("div");
    parrafo.className = "rw-parrafo rw-parrafo-" + (bloque.tipo === "passage" ? "pasaje" : "frase");
    if (bloque.conector) {
      var conector = document.createElement("span");
      conector.className = "rw-conector";
      conector.textContent = bloque.conector + " ";
      parrafo.appendChild(conector);
    }
    var contenido = document.createElement("div");
    documentoVisual(contenido, bloque.texto || "");
    parrafo.appendChild(contenido);
    if (bloque.cita) {
      var cita = document.createElement("span");
      cita.className = "rw-cita-breve";
      cita.textContent = " " + bloque.cita + ".";
      parrafo.appendChild(cita);
    }
    return parrafo;
  }

  function agregarMensajeAsistente(respuesta) {
    if (modoBusqueda && respuesta.estado === "conversacional") {
      hablar(respuesta.categoria ? voz(respuesta.categoria, respuesta.respuesta) : respuesta.respuesta,
             respuesta.categoria || "greeting");
      return;
    }
    if (respuesta.modo === "ranked_sources") {
      renderizarBusqueda(respuesta);
      return;
    }
    if (modoBusqueda) { hablar(respuesta.respuesta, "message"); return; }
    var estadoResp = respuesta.estado || "sin_respuesta";
    var alternativas = estadoResp === "sin_respuesta" ? (respuesta.alternativas || []) : [];
    var burbuja = document.createElement("div");
    burbuja.className = "rw-msg rw-msg-" + (alternativas.length ? "alternativas"
      : ETIQUETAS_ESTADO.hasOwnProperty(estadoResp) ? estadoResp : "sin_respuesta");

    var aviso = ETIQUETAS_ESTADO[estadoResp];
    // Respuesta directa sin lector (confidence_level medium): pide revisar la cita.
    if (estadoResp === "ok" && respuesta.nivel === "medium") aviso = texto("check_citation");
    if (aviso && PRESENTACION.mostrarEtiquetaEstado) {
      var spanAviso = document.createElement("span");
      spanAviso.className = "rw-aviso";
      spanAviso.textContent = aviso; // texto FIJO del widget, no de la API
      burbuja.appendChild(spanAviso);
    }

    // Un párrafo por bloque; sin bloques (API anterior), el texto completo.
    var bloques = respuesta.bloques && respuesta.bloques.length
      ? respuesta.bloques : [{ tipo: "message", texto: respuesta.respuesta || "" }];
    bloques.forEach(function (bloque, i) {
      var parrafo = parrafoDeBloque(bloque);
      // Se revela párrafo a párrafo, con un tope para que una respuesta larga no tarde.
      parrafo.style.animationDelay = Math.min(i, 5) * 70 + "ms";
      burbuja.appendChild(parrafo);
    });

    if (estadoResp === "ok" || estadoResp === "relacionado" || alternativas.length) {
      agregarCitas(burbuja, alternativas.length ? alternativas : respuesta.fragmentos,
                   alternativas.length ? null : respuesta.respuesta_exacta);
      var citas = burbuja.querySelector(".rw-citas");
      if (citas) citas.style.animationDelay = (Math.min(bloques.length, 6) * 70 + 80) + "ms";
    }

    mensajes.appendChild(burbuja);
    desplazarAlFinal();
  }

  var modoBusqueda = false;
  var paginaBusqueda = null;
  var indicadorBusqueda = document.createElement("div");
  indicadorBusqueda.className = "rw-carga";
  indicadorBusqueda.hidden = true;
  indicadorBusqueda.setAttribute("aria-hidden", "true");
  var BANCO_VOZ = {}, girosVoz = {}, animacionesVoz = true, cuadroVoz = null, textoVozCompleto = "";
  var espacioVoz = document.createElement("section");
  espacioVoz.className = "rw-voz";
  espacioVoz.hidden = true;
  var tituloVoz = document.createElement("h3");
  tituloVoz.id = "rw-voz-titulo";
  espacioVoz.setAttribute("aria-labelledby", tituloVoz.id);
  var completarVoz = document.createElement("button");
  completarVoz.type = "button";
  completarVoz.className = "rw-voz-mas";
  completarVoz.hidden = true;
  completarVoz.addEventListener("click", function () {
    espacioVoz.dataset.expandido = espacioVoz.dataset.expandido === "true" ? "false" : "true";
    finalizarVoz();
  });
  var textoVoz = document.createElement("p");
  textoVoz.className = "rw-voz-texto";
  textoVoz.setAttribute("aria-hidden", "true");
  // Se anuncia una vez el texto completo, nunca carácter por carácter.
  var anuncioVoz = document.createElement("span");
  anuncioVoz.className = "rw-sr-solo";
  anuncioVoz.setAttribute("role", "status");
  anuncioVoz.setAttribute("aria-live", "polite");
  anuncioVoz.setAttribute("aria-atomic", "true");
  var accionesVoz = document.createElement("div");
  accionesVoz.className = "rw-voz-acciones";
  var menuVoz = document.createElement("details"), resumenMenuVoz = document.createElement("summary");
  menuVoz.className = "rw-voz-menu";
  menuVoz.append(resumenMenuVoz, accionesVoz);
  accionesVoz.addEventListener("click", function (e) {
    if (e.target.closest("button")) { menuVoz.open = false; resumenMenuVoz.focus(); }
  });
  raiz.addEventListener("click", function (e) { if (!menuVoz.contains(e.target)) menuVoz.open = false; });
  var ayudaVoz = document.createElement("button"), opcionesVoz = document.createElement("button");
  ayudaVoz.type = opcionesVoz.type = "button";
  ayudaVoz.addEventListener("click", function () { hablar(voz("tips", texto("search_instruction")), "tips"); });
  opcionesVoz.addEventListener("click", function () { hablar(voz("capability", texto("search_instruction")), "capability"); });
  accionesVoz.append(ayudaVoz, opcionesVoz);
  var botonesVoz = {};
  ["about", "limits", "examples"].forEach(function (categoria) {
    var accion = document.createElement("button");
    accion.type = "button";
    accion.addEventListener("click", function () { hablar(voz(categoria), categoria); });
    botonesVoz[categoria] = accion;
    accionesVoz.appendChild(accion);
  });
  textoVoz.id = "rw-voz-texto";
  completarVoz.setAttribute("aria-controls", textoVoz.id);
  var burbujaVoz = document.createElement("div");
  burbujaVoz.className = "rw-voz-burbuja";
  burbujaVoz.append(textoVoz, completarVoz);
  var lugarAvatarVoz = document.createElement("div");   // aquí vive el avatar con ubicación «mensaje»
  lugarAvatarVoz.className = "rw-voz-avatar";
  espacioVoz.append(tituloVoz, burbujaVoz, lugarAvatarVoz, anuncioVoz);

  function voz(categoria, repuesto) {
    var opciones = BANCO_VOZ[categoria];
    if (!opciones || !opciones.length) return repuesto || texto("search_instruction");
    if (girosVoz[categoria] === undefined) girosVoz[categoria] = Math.floor(Math.random() * opciones.length);
    var indice = girosVoz[categoria]++ % opciones.length;
    return String(opciones[indice]);
  }

  function finalizarVoz() {
    if (cuadroVoz !== null) window.cancelAnimationFrame(cuadroVoz);
    cuadroVoz = null;
    textoVoz.textContent = textoVozCompleto;
    espacioVoz.dataset.typing = "false";
    var expandido = espacioVoz.dataset.expandido === "true";
    completarVoz.setAttribute("aria-expanded", String(expandido));
    completarVoz.textContent = texto(expandido ? "voice_show_less" : "voice_show_all");
    completarVoz.hidden = !expandido && textoVozCompleto.length <= 90 && textoVoz.scrollHeight <= textoVoz.clientHeight + 1;
    if (completarVoz.hidden && raiz.activeElement === completarVoz) resumenMenuVoz.focus();
  }

  function hablar(mensaje, categoria) {
    finalizarVoz();
    espacioVoz.dataset.expandido = "false";
    completarVoz.textContent = texto("voice_show_all");
    completarVoz.setAttribute("aria-expanded", "false");
    textoVozCompleto = String(mensaje || "");
    espacioVoz.dataset.category = categoria || "message";
    anuncioVoz.textContent = textoVozCompleto;
    if (!animacionesVoz || sinMovimiento() || !textoVozCompleto) { finalizarVoz(); return; }
    var caracteres = window.Intl && Intl.Segmenter
      ? Array.from(new Intl.Segmenter(panel.lang || undefined, { granularity: "grapheme" }).segment(textoVozCompleto),
                   function (s) { return s.segment; }) : Array.from(textoVozCompleto);
    var inicio = performance.now();
    textoVoz.textContent = "";
    espacioVoz.dataset.typing = "true";
    completarVoz.hidden = false;
    function escribir(ahora) {
      if (!animacionesVoz || sinMovimiento()) { finalizarVoz(); return; }
      var n = Math.min(caracteres.length, Math.floor((ahora - inicio) / 18) + 1);
      textoVoz.textContent = caracteres.slice(0, n).join("");
      if (n >= caracteres.length) finalizarVoz();
      else cuadroVoz = window.requestAnimationFrame(escribir);
    }
    cuadroVoz = window.requestAnimationFrame(escribir);
  }
  if (window.matchMedia) {
    var movimientoVoz = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (movimientoVoz.addEventListener) movimientoVoz.addEventListener("change", function (e) {
      if (e.matches) finalizarVoz();
    });
  }

  function activarBusqueda() {
    modoBusqueda = true;
    panel.setAttribute("data-modo", "busqueda");
    boton.setAttribute("aria-label", texto("search_open", { title: tituloEl.textContent }));
    botonCerrar.setAttribute("aria-label", texto("search_close"));
    subtituloTexto.textContent = CONTENIDO.subtitle || texto("search_subtitle");
    // El mensaje del asistente va abajo, junto al campo de búsqueda (donde está la atención) y con el avatar a su derecha.
    panel.insertBefore(espacioVoz, form);
    panel.insertBefore(indicadorBusqueda, mensajes);
    espacioVoz.hidden = false;
    if (AVATAR && AVATAR.lienzo) ubicarAvatar();
    tituloVoz.textContent = texto("voice_label");
    completarVoz.textContent = texto("voice_show_all");
    ayudaVoz.textContent = texto("voice_help");
    opcionesVoz.textContent = texto("voice_options");
    // Ayuda: un «?» en el encabezado (junto al nombre del asistente) que abre el menú de ayuda.
    resumenMenuVoz.replaceChildren(icono("ayuda"));
    resumenMenuVoz.setAttribute("aria-label", texto("voice_menu"));
    resumenMenuVoz.title = texto("voice_menu");
    cabecera.insertBefore(menuVoz, botonCerrar);
    Object.keys(botonesVoz).forEach(function (categoria) {
      botonesVoz[categoria].textContent = texto("voice_" + categoria);
      botonesVoz[categoria].hidden = !(BANCO_VOZ[categoria] && BANCO_VOZ[categoria].length);
    });
    mensajes.setAttribute("role", "region");
    mensajes.setAttribute("aria-label", texto("search_results_label"));
    mensajes.removeAttribute("aria-live");
    etiquetaInput.textContent = texto("search_question_label");
    input.placeholder = texto("search_start");
    botonEnviar.setAttribute("aria-label", texto("search_send"));
    botonEnviar.replaceChildren(icono("buscar"));
  }

  function mostrarInicioBusqueda() {
    var inicio = document.createElement("div");
    inicio.className = "rw-busqueda-vacia";
    var titulo = document.createElement("h3");
    titulo.textContent = CONTENIDO.welcome_title || texto("search_start");
    var ayuda = document.createElement("p");
    ayuda.textContent = CONTENIDO.welcome_text || texto("search_instruction");
    inicio.appendChild(titulo);
    inicio.appendChild(ayuda);
    if (PRESENTACION.mostrarSugerencias && SUGERENCIAS.length) {
      var sugerencias = document.createElement("div");
      sugerencias.className = "rw-sugerencias";
      sugerencias.setAttribute("role", "group");
      sugerencias.setAttribute("aria-label", texto("suggestions_label"));
      SUGERENCIAS.forEach(function (pregunta) {
        var sugerencia = document.createElement("button");
        sugerencia.type = "button";
        sugerencia.textContent = pregunta;
        sugerencia.addEventListener("click", function () {
          input.value = pregunta;
          actualizarLimpiar();
          input.focus();
        });
        sugerencias.appendChild(sugerencia);
      });
      inicio.appendChild(sugerencias);
    }
    if (PREGUNTAS_FIJAS.length) {
      var frecuentes = document.createElement("details");
      frecuentes.className = "rw-faq";
      var resumenFaq = document.createElement("summary");
      resumenFaq.textContent = texto("faq_title");
      var filtroLabel = document.createElement("label");
      filtroLabel.textContent = texto("faq_topic");
      var filtro = document.createElement("select");
      var todos = document.createElement("option");
      todos.value = "";
      todos.textContent = texto("faq_all");
      filtro.appendChild(todos);
      Array.from(new Set(PREGUNTAS_FIJAS.map(function (p) { return p.topic; }))).forEach(function (tema) {
        var opcion = document.createElement("option");
        opcion.value = opcion.textContent = tema;
        filtro.appendChild(opcion);
      });
      filtroLabel.appendChild(filtro);
      var cuentaFaq = document.createElement("p");
      cuentaFaq.setAttribute("role", "status");
      var listaFaq = document.createElement("div");
      listaFaq.className = "rw-faq-lista";
      function filtrarPreguntas() {
        listaFaq.replaceChildren();
        PREGUNTAS_FIJAS.filter(function (p) { return !filtro.value || p.topic === filtro.value; }).forEach(function (p) {
          var consulta = document.createElement("button");
          consulta.type = "button";
          consulta.textContent = p.question;
          consulta.addEventListener("click", function () { input.value = p.question; actualizarLimpiar(); input.focus(); });
          listaFaq.appendChild(consulta);
        });
        cuentaFaq.textContent = texto("faq_count", { n: listaFaq.children.length });
      }
      filtro.addEventListener("change", filtrarPreguntas);
      filtrarPreguntas();
      frecuentes.append(resumenFaq, filtroLabel, cuentaFaq, listaFaq);
      inicio.appendChild(frecuentes);
    }
    mensajes.replaceChildren(inicio);
  }

  function textoDestacado(elemento, contenido, pregunta) {
    // Destacar palabras literales de la consulta; no modifica el texto fuente.
    var palabras = (pregunta || "").split(/[^A-Za-z0-9_\u00c0-\u024f]+/).filter(function (p) {
      return p.length > 2;
    }).slice(0, 20);
    var minusculas = contenido.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    var tramos = [];
    if (minusculas.length === contenido.length) palabras.forEach(function (palabra) {
      var termino = palabra.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(), posicion = 0, encontrado;
      while ((encontrado = minusculas.indexOf(termino, posicion)) !== -1) {
        tramos.push([encontrado, encontrado + termino.length]);
        posicion = encontrado + termino.length;
      }
    });
    tramos.sort(function (a, b) { return a[0] - b[0]; });
    var unidos = [];
    tramos.forEach(function (t) {
      var ultimo = unidos[unidos.length - 1];
      if (ultimo && t[0] <= ultimo[1]) ultimo[1] = Math.max(ultimo[1], t[1]);
      else unidos.push(t.slice());
    });
    var posicion = 0;
    unidos.forEach(function (t) {
      elemento.appendChild(document.createTextNode(contenido.slice(posicion, t[0])));
      var destacado = document.createElement("strong");
      destacado.textContent = contenido.slice(t[0], t[1]);
      elemento.appendChild(destacado);
      posicion = t[1];
    });
    elemento.appendChild(document.createTextNode(contenido.slice(posicion)));
  }

  // La estructura procede del parser. Nunca se adivinan columnas separando «|».
  function bloquesVerificados(bloques, fuente, base) {
    if (!Array.isArray(bloques) || !bloques.length || bloques.length > 500 || !Number.isInteger(base)) return [];
    var caracteres = Array.from(fuente), anterior = base, totalCeldas = 0;
    function literal(c) {
      return c && typeof c.text === "string" && Number.isInteger(c.offset_start) && Number.isInteger(c.offset_end) && c.offset_start >= base &&
        c.offset_end >= c.offset_start && c.offset_end <= base + caracteres.length &&
        caracteres.slice(c.offset_start - base, c.offset_end - base).join("") === c.text;
    }
    for (var b of bloques) {
      if (!literal(b) || b.offset_start < anterior || !["paragraph", "heading", "table"].includes(b.kind)) return [];
      anterior = b.offset_end;
      if (b.kind !== "table") continue;
      if (!Number.isInteger(b.columns) || b.columns < 1 || b.columns > 100 ||
          !Array.isArray(b.rows) || !b.rows.length || b.rows.length > 200) return [];
      var ocupadas = [];
      for (var i = 0; i < b.rows.length; i++) {
        var fila = b.rows[i];
        if (!Array.isArray(fila.cells)) return [];
        for (var c of fila.cells) {
          if (++totalCeldas > 2000 || !literal(c) || c.offset_start < b.offset_start || c.offset_end > b.offset_end ||
              !Number.isInteger(c.column) || c.column < 0 || !Number.isInteger(c.column_span) || c.column_span < 1 ||
              !Number.isInteger(c.row_span) || c.row_span < 1 || c.column + c.column_span > b.columns ||
              i + c.row_span > b.rows.length) return [];
          for (var y = i; y < i + c.row_span; y++) for (var x = c.column; x < c.column + c.column_span; x++) {
            ocupadas[y] = ocupadas[y] || [];
            if (ocupadas[y][x]) return [];
            ocupadas[y][x] = true;
          }
        }
      }
    }
    return bloques;
  }

  function documentoVisual(contenedor, fuente, bloques, base, rango, pregunta) {
    contenedor.classList.add("rw-documento");
    var caracteres = Array.from(fuente);
    function indice(offset) { return caracteres.slice(0, offset - base).join("").length; }
    function escribir(e, contenido, inicio) {
      if (rango) {
        var desde = Math.max(0, rango[0] - inicio), hasta = Math.min(contenido.length, rango[1] - inicio);
        textoConTramo(e, contenido, hasta > desde ? [desde, hasta] : null);
      } else textoDestacado(e, contenido, pregunta);
    }
    function parrafos(textoFuente, inicio) {
      var partes = textoFuente.split(/(\n\s*\n)/), posicion = inicio;
      partes.forEach(function (parte) {
        if (!parte.trim()) contenedor.appendChild(document.createTextNode(parte));
        else {
          var p = document.createElement("p");
          escribir(p, parte, posicion);
          contenedor.appendChild(p);
        }
        posicion += parte.length;
      });
    }
    var validos = bloquesVerificados(bloques, fuente, base), posicion = 0;
    if (!validos.length) { parrafos(fuente, 0); return false; }
    validos.forEach(function (b) {
      var inicio = indice(b.offset_start), fin = indice(b.offset_end);
      parrafos(fuente.slice(posicion, inicio), posicion);
      if (b.kind === "table") {
        var scroll = document.createElement("div");
        scroll.className = "rw-tabla-scroll";
        scroll.tabIndex = 0;
        scroll.setAttribute("role", "region");
        scroll.setAttribute("aria-label", texto("source_table"));
        var tabla = document.createElement("table"), cuerpo = document.createElement("tbody"), ocupadas = [];
        tabla.className = "rw-tabla";
        tabla.setAttribute("aria-label", texto("source_table"));
        b.rows.forEach(function (fila, y) {
          var tr = document.createElement("tr"), porColumna = {};
          fila.cells.forEach(function (c) { porColumna[c.column] = c; });
          for (var x = 0; x < b.columns; x++) {
            if (ocupadas[y] && ocupadas[y][x]) continue;
            var c = porColumna[x], td = document.createElement(fila.header ? "th" : "td");
            if (c) {
              td.colSpan = c.column_span; td.rowSpan = c.row_span;
              if (c.locator) td.title = c.locator;
              if (fila.header) td.setAttribute("scope", c.column_span > 1 ? "colgroup" : "col");
              escribir(td, c.text, indice(c.offset_start));
              for (var j = y; j < y + c.row_span; j++) for (var k = x; k < x + c.column_span; k++) {
                ocupadas[j] = ocupadas[j] || []; ocupadas[j][k] = true;
              }
            }
            tr.appendChild(td);
          }
          cuerpo.appendChild(tr);
        });
        tabla.appendChild(cuerpo); scroll.appendChild(tabla); contenedor.appendChild(scroll);
      } else {
        var p = document.createElement(b.kind === "heading" ? "h5" : "p");
        escribir(p, b.text, inicio); contenedor.appendChild(p);
      }
      posicion = fin;
    });
    parrafos(fuente.slice(posicion), posicion);
    return validos.some(function (b) { return b.kind === "table"; });
  }

  function agregarResultados(lista, fragmentos, pregunta) {
    var primero = null, nuevos = 0;
    fragmentos.forEach(function (frag, indice) {
      var clave = JSON.stringify([frag.doc_id, frag.chunk_id, frag.version, frag.offset_inicio, frag.offset_fin]);
      if (paginaBusqueda && paginaBusqueda.vistos.has(clave)) return;
      if (paginaBusqueda) paginaBusqueda.vistos.add(clave);
      var item = document.createElement("li");
      item.className = "rw-resultado";
      item.style.setProperty("--rw-i", String(Math.min(nuevos++, 6)));
      item.value = frag.rango || indice + 1;
      var origen = document.createElement("p");
      origen.className = "rw-resultado-origen";
      var nombreDoc = frag.doc_titulo || frag.archivo || "";
      var docTitulo = document.createElement("span");
      docTitulo.className = "rw-resultado-doc";
      docTitulo.textContent = nombreDoc + (frag.version ? " \u00b7 v" + frag.version : "");
      origen.appendChild(docTitulo);
      // Contexto de un vistazo: el alcance de la unidad («Práctica Profesional II») y, si el documento no declara
      // uno, el título de la sección que la contiene. Sin ninguno de los dos (documento sin estructura) no hay etiqueta.
      var rutaSecciones = (frag.seccion || "").split(/\s*>\s*/).filter(Boolean);
      var tituloPadre = rutaSecciones.length > 1 ? rutaSecciones[rutaSecciones.length - 2] : "";
      var contexto = frag.alcance || tituloPadre;
      if (contexto) {
        var alcance = document.createElement("span");
        alcance.className = "rw-resultado-alcance" + (frag.alcance ? "" : " rw-resultado-padre");
        alcance.textContent = contexto;
        origen.appendChild(alcance);
      }
      if (frag.rasgos && frag.rasgos.length) {
        // Lo que distingue a esta fuente de otras casi iguales (p. ej. la tabla de otra práctica).
        var rasgos = document.createElement("span");
        rasgos.className = "rw-resultado-rasgos";
        rasgos.textContent = texto("result_distinguished") + ": " + frag.rasgos.join(" \u00b7 ");
        origen.appendChild(rasgos);
      }
      if (frag.archivo && frag.archivo !== nombreDoc) {
        var archivo = document.createElement("span");
        archivo.className = "rw-resultado-archivo";
        archivo.textContent = frag.archivo;
        archivo.title = frag.archivo;
        origen.appendChild(archivo);
      }
      if (PRESENTACION.mostrarNumeros) {
        var numero = document.createElement("span");
        numero.className = "rw-resultado-numero";
        numero.textContent = String(frag.rango || lista.children.length + 1);
        numero.setAttribute("aria-label", texto("result_number", { n: numero.textContent }));
        origen.prepend(numero);
      }
      item.appendChild(origen);
      var secciones = (frag.seccion || "").split(/\s*>\s*/).filter(Boolean);
      if (bloquesVerificados(frag.bloques_fuente, frag.texto || "", frag.offset_inicio).some(function (b) {
        return b && b.kind === "table" && b.rows && b.rows[0] &&
          b.rows[0].cells.filter(function (c) { return c.text; }).map(function (c) { return c.text; })
            .join(" | ") === secciones[secciones.length - 1];
      })) {
        secciones.pop();  // ruta sintética del parser legacy, ya visible en la tabla
      }
      var encabezado = document.createElement("h4");
      encabezado.className = "rw-resultado-encabezado";
      var titulo = document.createElement("button");
      titulo.type = "button";
      titulo.className = "rw-resultado-titulo";
      titulo.textContent = secciones.length ? secciones[secciones.length - 1] : frag.doc_titulo || frag.archivo;
      encabezado.appendChild(titulo);
      item.appendChild(encabezado);
      // La ruta no repite el título de la sección que ya muestra la etiqueta de contexto.
      var rutaPartes = secciones.slice(0, -1);
      if (!frag.alcance && tituloPadre) rutaPartes = rutaPartes.slice(0, -1);
      if (PRESENTACION.mostrarRuta && rutaPartes.length) {
        var ruta = document.createElement("p");
        ruta.className = "rw-resultado-ruta";
        ruta.textContent = rutaPartes.join(" \u203a ");
        item.appendChild(ruta);
      }
      var completo = frag.texto || "";
      // La API cuenta caracteres Unicode; slice de JavaScript cuenta unidades UTF-16.
      var caracteres = Array.from(completo);
      var inicioFuente = Math.max(0, (frag.coincidencia_inicio == null ? frag.offset_inicio : frag.coincidencia_inicio) - frag.offset_inicio);
      var finFuente = Math.min(caracteres.length, (frag.coincidencia_fin == null ? frag.offset_fin : frag.coincidencia_fin) - frag.offset_inicio);
      var inicio = caracteres.slice(0, inicioFuente).join("").length;
      var fin = caracteres.slice(0, finFuente).join("").length;
      var coincidencia = completo.slice(inicio, fin) || completo;
      var vista = document.createElement("div");
      vista.className = "rw-resultado-vista";
      var caracteresVista = Array.from(coincidencia);
      var tablaCoincidente = bloquesVerificados(frag.bloques_fuente, completo, frag.offset_inicio).find(function (b) {
        return b.kind === "table" && b.offset_start < frag.offset_inicio + finFuente &&
          frag.offset_inicio + inicioFuente < b.offset_end;
      });
      // Una tabla corta se muestra con sus columnas; el contexto completo conserva las grandes.
      if (tablaCoincidente && Array.from(tablaCoincidente.text).length <= 1600) {
        documentoVisual(vista, tablaCoincidente.text, [tablaCoincidente], tablaCoincidente.offset_start, null, pregunta);
      } else if (tablaCoincidente) vista.textContent = texto("source_table_hint");
      else documentoVisual(vista, caracteresVista.length > 400 ? caracteresVista.slice(0, 400).join("") + "\u2026"
        : coincidencia, [], frag.offset_inicio + inicioFuente, null, pregunta);
      item.appendChild(vista);
      var detalles = document.createElement("details");
      detalles.id = "rw-documento-" + (lista.children.length + 1);
      var resumen = document.createElement("summary");
      resumen.textContent = texto("search_read_document");
      detalles.appendChild(resumen);
      titulo.setAttribute("aria-controls", detalles.id);
      detalles.open = PRESENTACION.expandirContexto;
      titulo.setAttribute("aria-expanded", String(detalles.open));
      resumen.textContent = texto(detalles.open ? "search_close_document" : "search_read_document");
      titulo.addEventListener("click", function () { detalles.open = !detalles.open; });
      detalles.addEventListener("toggle", function () {
        titulo.setAttribute("aria-expanded", String(detalles.open));
        resumen.textContent = texto(detalles.open ? "search_close_document" : "search_read_document");
      });
      var posicion = document.createElement("p");
      posicion.className = "rw-resultado-origen";
      posicion.textContent = texto("citation_position", { start: frag.offset_inicio, end: frag.offset_fin });
      detalles.appendChild(posicion);
      var contexto = document.createElement("div");
      contexto.className = "rw-resultado-contexto";
      var conTabla = documentoVisual(contexto, completo, frag.bloques_fuente, frag.offset_inicio,
        fin > inicio && fin - inicio < completo.length ? [inicio, fin] : null);
      detalles.appendChild(contexto);
      if (conTabla) {
        var original = document.createElement("details"), etiquetaOriginal = document.createElement("summary");
        original.className = "rw-fuente-literal";
        etiquetaOriginal.textContent = texto("source_original");
        var literal = document.createElement("pre");
        literal.textContent = completo;
        original.appendChild(etiquetaOriginal); original.appendChild(literal); detalles.appendChild(original);
      }
      if (frag.truncado) {
        var recorte = document.createElement("p");
        recorte.textContent = texto("context_truncated");
        detalles.appendChild(recorte);
      }
      item.appendChild(detalles);
      lista.appendChild(item);
      if (!primero) primero = titulo;
    });
    return primero;
  }

  function renderizarBusqueda(respuesta) {
    activarBusqueda();
    if (!respuesta.continuando || !paginaBusqueda) {
      var seccion = document.createElement("section");
      seccion.className = "rw-busqueda";
      var contador = document.createElement("h3");
      contador.className = "rw-busqueda-contador";
      var lista = document.createElement("ol");
      lista.className = "rw-resultados";
      var acciones = document.createElement("div");
      acciones.className = "rw-busqueda-acciones";
      seccion.appendChild(contador);
      seccion.appendChild(lista);
      seccion.appendChild(acciones);
      paginaBusqueda = { seccion: seccion, contador: contador, lista: lista, acciones: acciones, vistos: new Set() };
      mensajes.replaceChildren(seccion);
      mensajes.scrollTop = 0;
    }
    var cantidadAnterior = paginaBusqueda.lista.children.length;
    var primero = agregarResultados(paginaBusqueda.lista, respuesta.fragmentos, respuesta.pregunta);
    var cantidad = paginaBusqueda.lista.children.length;
    paginaBusqueda.contador.textContent = texto(cantidad === 1 ? "search_results_count_one" : "search_results_count",
      { n: cantidad, query: respuesta.pregunta });
    paginaBusqueda.acciones.replaceChildren();
    var ayuda = document.createElement("p");
    ayuda.className = "rw-busqueda-ayuda";
    ayuda.textContent = cantidad === 0 ? respuesta.respuesta || texto("search_instruction")
      : texto(respuesta.has_more === false ? "search_exhausted" : "rephrase_search");
    paginaBusqueda.acciones.appendChild(ayuda);
    if (respuesta.has_more && respuesta.continuation) {
      var mas = document.createElement("button");
      mas.type = "button";
      mas.className = "rw-seguir";
      mas.dataset.activo = "si";
      mas.textContent = texto("search_more");
      mas.addEventListener("click", function () { enviarPregunta(respuesta.pregunta, respuesta.continuation, mas); });
      paginaBusqueda.acciones.appendChild(mas);
    }
    anunciador.textContent = respuesta.continuando
      ? texto("search_added", { n: cantidad - cantidadAnterior }) : paginaBusqueda.contador.textContent;
    if (respuesta.continuando && primero) primero.focus({ preventScroll: true });
    var categoriaVoz = cantidad === 0 ? "no_results" : respuesta.continuando ? "continuation" : "results";
    // El conteo va en el mensaje del asistente (no en una línea aparte). Las plantillas pueden ubicarlo con
    // {count} («3 resultados», ya en singular o plural del idioma), {n} y {query}; si no usan ninguno, el conteo
    // se antepone («3 resultados.»). Sin resultados no hay conteo.
    // Con la forma de la página (result_shape) hay un mensaje propio: «depende de tu caso» si las primeras fuentes son
    // variantes de lo mismo, «en varios documentos» si vienen de documentos distintos. Describen la página y no dicen
    // cuál responde. Si el banco no lo tiene, o la forma es neutral, vale el mensaje de siempre. {n_docs} cuenta los
    // documentos distintos de las fuentes que se ven.
    var bancoVoz = categoriaVoz;
    if (categoriaVoz === "results" && !respuesta.continuando) {
      var propio = respuesta.forma === "variants" ? "results_variants" : respuesta.forma === "documents" ? "results_documents" : null;
      if (propio && BANCO_VOZ[propio] && BANCO_VOZ[propio].length) bancoVoz = propio;
    }
    var documentosVistos = {};
    (respuesta.fragmentos || []).forEach(function (f) { documentosVistos[f.doc_id || f.doc_titulo || ""] = true; });
    var mensajeVoz = voz(bancoVoz, texto("voice_" + categoriaVoz));
    if (cantidad > 0) {
      var frase = texto(cantidad === 1 ? "voice_count_phrase_one" : "voice_count_phrase", { n: cantidad });
      if (/\{(count|n|query|n_docs)\}/.test(mensajeVoz)) {
        mensajeVoz = mensajeVoz.replace(/\{count\}/g, frase).replace(/\{n\}/g, String(cantidad))
          .replace(/\{n_docs\}/g, String(Object.keys(documentosVistos).length))
          .replace(/\{query\}/g, respuesta.pregunta || "");
      } else {
        mensajeVoz = frase + ". " + mensajeVoz;
      }
    }
    hablar(mensajeVoz, categoriaVoz);
  }

  // Indicador de "escribiendo": sin el, el widget se queda mudo entre que
  // se envia la pregunta y llega la respuesta. Son tres puntos animados,
  // no un mensaje -- no se agrega nada al historial.
  var burbujaEspera = null;

  // Búsqueda: tarjetas de esqueleto en el lugar de los resultados. Un marcador
  // recorre sus renglones como si Folio leyera, y el estado avanza por etapas.
  // Es decorativo (aria-hidden): los lectores de pantalla oyen "buscando".
  var esqueleto = null, cicloEsqueleto = null, ocultosPorEsqueleto = [];

  function crearEsqueleto(tarjetas) {
    var e = document.createElement("div");
    e.className = "rw-esqueleto";
    e.setAttribute("aria-hidden", "true");
    var estado = document.createElement("p");
    estado.className = "rw-esqueleto-estado";
    var punto = document.createElement("i"), etiqueta = document.createElement("span");
    estado.append(punto, etiqueta);
    e.appendChild(estado);
    for (var i = 0; i < tarjetas; i++) {
      var t = document.createElement("div");
      t.className = "rw-esq-tarjeta";
      ["n", "t", "s", "w1", "w2", "w3"].forEach(function (clase) {
        var l = document.createElement("span");
        l.className = "rw-esq-l rw-esq-" + clase;
        t.appendChild(l);
      });
      e.appendChild(t);
    }
    var etapas = ["search_stage_read", "search_stage_compare", "search_stage_rank"], k = 0;
    etiqueta.textContent = texto(etapas[0]);
    clearInterval(cicloEsqueleto);
    if (!sinMovimiento()) {
      cicloEsqueleto = setInterval(function () {
        if (k < etapas.length - 1) etiqueta.textContent = texto(etapas[++k]);
      }, 1100);
    }
    return e;
  }

  function mostrarEsqueleto(continuando) {
    quitarEsqueleto();
    if (continuando && paginaBusqueda) {
      esqueleto = crearEsqueleto(1);
      paginaBusqueda.seccion.insertBefore(esqueleto, paginaBusqueda.acciones);
      return;
    }
    esqueleto = crearEsqueleto(3);
    ocultosPorEsqueleto = Array.prototype.slice.call(mensajes.children);
    ocultosPorEsqueleto.forEach(function (n) { n.hidden = true; });
    mensajes.insertBefore(esqueleto, mensajes.firstChild);
    mensajes.scrollTop = 0;
  }

  function quitarEsqueleto() {
    clearInterval(cicloEsqueleto);
    if (esqueleto && esqueleto.parentNode) esqueleto.parentNode.removeChild(esqueleto);
    esqueleto = null;
    ocultosPorEsqueleto.forEach(function (n) { if (n.parentNode === mensajes) n.hidden = false; });
    ocultosPorEsqueleto = [];
  }

  function mostrarEscribiendo(continuando) {
    if (modoBusqueda) {
      mensajes.setAttribute("aria-busy", "true");
      mensajes.classList.add("rw-buscando");
      indicadorBusqueda.hidden = false;
      mostrarEsqueleto(continuando);
      hablar(voz("searching", micro("waiting")), "searching");
      return;
    }
    if (burbujaEspera) return;
    burbujaEspera = document.createElement("div");
    burbujaEspera.className = "rw-escribiendo";
    var esperando = micro("waiting");
    burbujaEspera.setAttribute("aria-label", esperando);
    anunciar(esperando);
    for (var i = 0; i < 3; i++) {
      var punto = document.createElement("span");
      punto.className = "rw-punto";
      burbujaEspera.appendChild(punto);
    }
    mensajes.appendChild(burbujaEspera);
    desplazarAlFinal();
  }

  function ocultarEscribiendo() {
    mensajes.setAttribute("aria-busy", "false");
    mensajes.classList.remove("rw-buscando");
    indicadorBusqueda.hidden = true;
    quitarEsqueleto();
    if (burbujaEspera && burbujaEspera.parentNode) {
      burbujaEspera.parentNode.removeChild(burbujaEspera);
    }
    burbujaEspera = null;
  }

  function agregarMensajeError(texto) {
    if (modoBusqueda) { hablar(texto, "error"); return; }
    var burbuja = document.createElement("div");
    burbuja.className = "rw-msg rw-msg-sin_respuesta";
    burbuja.textContent = texto;
    mensajes.appendChild(burbuja);
    desplazarAlFinal();
    anunciar(texto);
  }

  // -------------------------------------------------------------------
  // 4. Llamadas a la API. Nunca se llama a ningún LLM externo desde aquí
  //    -- solo al propio servicio (`API_BASE`).
  // -------------------------------------------------------------------
  function cabecerasComunes() {
    var cab = { "Content-Type": "application/json" };
    if (CLAVE_WIDGET) cab[CABECERA_CLAVE_WIDGET] = CLAVE_WIDGET;
    return cab;
  }

  function aplicarInterfaz(interfaz) {
    if (!interfaz || typeof interfaz !== "object") return;
    Object.keys(TEXTOS).forEach(function (clave) {
      if (typeof interfaz[clave] === "string" && interfaz[clave]) TEXTOS[clave] = interfaz[clave];
    });
    subtituloTexto.textContent = texto("subtitle");
    botonCerrar.setAttribute("aria-label", texto("close"));
    etiquetaInput.textContent = texto("question_label");
    input.placeholder = texto("placeholder");
    botonEnviar.setAttribute("aria-label", texto("send"));
    ETIQUETAS_ESTADO.relacionado = texto("not_direct");
    enlaceFuente.textContent = texto("source_code");
  }

  function cargarConfigServidor() {
    fetch(API_BASE + "/config", { headers: cabecerasComunes() })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (cfg) {
        PRESENTACION.densidad = cfg.density === "compact" ? "compacta" : "comoda";
        // Las citas nunca se ocultan: acordeón (desplegable) o lista (a la vista).
        PRESENTACION.citas = cfg.citations === "list" ? "lista" : "acordeon";
        PRESENTACION.mostrarEtiquetaEstado = cfg.show_status_label !== false;
        PRESENTACION.alineacion = cfg.text_align === "start" ? "inicio" : "justificada";
        PRESENTACION.diseno = ["cards", "lines", "editorial"].indexOf(cfg.result_layout) >= 0 ? cfg.result_layout
          : cfg.preset === "editorial" ? "editorial"
          : ["minimal", "search", "search_compact"].indexOf(cfg.preset) >= 0 ? "lines" : "cards";
        PRESENTACION.mostrarNumeros = cfg.show_result_numbers !== false;
        PRESENTACION.mostrarRuta = cfg.show_section_path !== false;
        PRESENTACION.expandirContexto = cfg.expand_context === true;
        PRESENTACION.mostrarSugerencias = cfg.show_suggestions !== false;
        CONTENIDO = cfg.widget_content || {};
        SUGERENCIAS = (Array.isArray(cfg.suggested_questions) ? cfg.suggested_questions : []).filter(function (s) {
          return typeof s === "string" && s.trim();
        }).slice(0, 6);
        PREGUNTAS_FIJAS = (Array.isArray(cfg.default_questions) ? cfg.default_questions : []).filter(function (p) {
          return p && typeof p.question === "string" && p.question.trim() && typeof p.topic === "string" && p.topic.trim();
        }).slice(0, 500);
        panel.setAttribute("data-diseno", PRESENTACION.diseno);
        panel.setAttribute("data-densidad", PRESENTACION.densidad);
        panel.setAttribute("data-alineacion", PRESENTACION.alineacion);
        // hyphens:auto parte las palabras con las reglas del idioma de lang.
        if (typeof cfg.language === "string" && /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/.test(cfg.language)) {
          panel.setAttribute("lang", cfg.language);
        }
        if (cfg.preset) panel.setAttribute("data-preset", cfg.preset);
        aplicarInterfaz(cfg.interface);
        if (cfg.microcopy && typeof cfg.microcopy === "object") MICROCOPIA = cfg.microcopy;
        if (cfg.assistant_messages && typeof cfg.assistant_messages === "object") BANCO_VOZ = cfg.assistant_messages;
        animacionesVoz = cfg.animations_enabled !== false;
        panel.setAttribute("data-animaciones", String(animacionesVoz));
        var p = cfg.placement || {};
        // styles.yaml::placement con los nombres públicos → los del widget.
        var u = { posicion: p.position, tamano: p.size, lanzador: p.launcher, desplazamiento_x: p.offset_x,
                  desplazamiento_y: p.offset_y, z_index: p.z_index };
        Object.keys(DEL_SITIO).forEach(function (clave) {
          if (DEL_SITIO[clave] !== null || u[clave] === undefined || clave === "posicion") return;
          var valor = VALIDOS[clave] ? enLista(u[clave], clave) : entero(u[clave], 0, 2147483647);
          if (valor !== null) UBICACION[clave] = valor;
        });
        // La posición incrustada la decide el sitio (el elemento vive en su página).
        if (DEL_SITIO.posicion === null && !INCRUSTADO && enLista(u.posicion, "posicion") &&
            u.posicion !== "embedded") {
          UBICACION.posicion = enLista(u.posicion, "posicion");
        }
        aplicarUbicacion();
        configurarAvatar(cfg.avatar);
        if (cfg.assistant_name) {
          var nombreVisible = CONTENIDO.title || cfg.assistant_name;
          tituloEl.textContent = nombreVisible;
          botonTexto.textContent = nombreVisible;
          panel.setAttribute("aria-label", nombreVisible);
          boton.setAttribute("aria-label", texto("open", { title: nombreVisible }));
        }
        if (CONTENIDO.subtitle) subtituloTexto.textContent = CONTENIDO.subtitle;
        var bienvenida = (MICROCOPIA.welcome && MICROCOPIA.welcome.length) ? micro("welcome") : cfg.greeting;
        if (cfg.response_mode === "ranked_sources" || modoBusqueda) {
          activarBusqueda();
          if (!paginaBusqueda && !peticionPendiente && !textoVozCompleto) {
            mostrarInicioBusqueda();
            hablar(voz("welcome", cfg.greeting), "welcome");
          }
        } else if (bienvenida && mensajes.children.length === 0) {
          agregarMensajeAsistente({ estado: "conversacional", respuesta: bienvenida });
        }
      })
      .catch(function () {
        // /config puede fallar (servicio recién arrancando, red, etc.) --
        // el widget sigue funcionando con los atributos data-* de repuesto,
        // nunca se rompe por esto. Se muestra el saludo de repuesto una
        // sola vez si no se mostró ya el del servidor.
        if (mensajes.children.length === 0) {
          agregarMensajeAsistente({ estado: "conversacional", respuesta: SALUDO_INICIAL });
        }
      });
  }

  var peticionPendiente = false;
  function enviarPregunta(pregunta, cursor, botonMas) {
    if (peticionPendiente) return;
    peticionPendiente = true;
    var exito = false;
    if (!cursor) {
      if (!modoBusqueda) {
        agregarMensajeUsuario(pregunta);
        input.value = "";
      } else input.value = pregunta;
    }
    mensajes.querySelectorAll(".rw-seguir").forEach(function (b) { b.disabled = true; });
    input.disabled = true;
    actualizarLimpiar();
    botonEnviar.disabled = true;
    mostrarEscribiendo(!!cursor);

    fetch(API_BASE + "/ask", {
      method: "POST",
      headers: cabecerasComunes(),
      body: JSON.stringify({ question: pregunta, session_id: ID_SESION, continuation: cursor || undefined }),
    })
      .then(function (r) {
        if (r.status === 429) {
          throw new Error(micro("rate_limit_error"));
        }
        if (r.status === 401 || r.status === 403) {
          throw new Error(texto("origin_error"));
        }
        if (r.status === 503) {
          throw new Error(micro("service_error"));
        }
        if (r.status === 409 && cursor) {
          if (botonMas) botonMas.dataset.activo = "no";
          throw new Error(texto("search_expired"));
        }
        if (!r.ok) {
          throw new Error(texto("http_error", { status: r.status }));
        }
        return r.json();
      })
      .then(function (publica) {
        var respuesta = respuestaInterna(publica);
        respuesta.pregunta = pregunta;
        respuesta.continuando = !!cursor;
        if (botonMas) botonMas.dataset.activo = "no";
        agregarMensajeAsistente(respuesta);
        exito = true;
        emitir("ipsis:answer", { status: publica.status, answer: publica });
        avatarAlResponder(respuesta.estado);
      })
      .catch(function (err) {
        // Los navegadores describen los fallos de transporte con textos
        // distintos ("Failed to fetch", "Load failed", etc.). Los errores
        // HTTP creados arriba sí son deliberados y se conservan; un TypeError
        // de fetch recibe un mensaje estable para quien usa el widget.
        var mensajeError = err instanceof TypeError
          ? micro("network_error")
          : (err && err.message ? err.message : micro("network_error"));
        agregarMensajeError(mensajeError);
        emitir("ipsis:error", { message: mensajeError });
        avatarAlFallar();
      })
      .finally(function () {
        ocultarEscribiendo();
        peticionPendiente = false;
        mensajes.querySelectorAll(".rw-seguir").forEach(function (b) {
          b.disabled = b.dataset.activo !== "si";
        });
        input.disabled = false;
        actualizarLimpiar();
        botonEnviar.disabled = false;
        if (!cursor || !modoBusqueda || !paginaBusqueda || !exito) input.focus();
      });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var texto = input.value.trim();
    if (!texto || peticionPendiente) return;
    emitir("ipsis:question", { question: texto });
    botonEnviar.classList.remove("rw-enviando");
    void botonEnviar.offsetWidth; // reinicia la animación si se envía otra vez enseguida
    botonEnviar.classList.add("rw-enviando");
    avatarAlEnviar();
    enviarPregunta(texto);
  });

  // -------------------------------------------------------------------
  // 5. Abrir/cerrar, foco atrapado y Escape -- accesibilidad del panel.
  // -------------------------------------------------------------------
  var elementoFocoPrevio = null;

  function elementosFocables() {
    var lista = panel.querySelectorAll("button, input, select, textarea, summary, [href], [tabindex]:not([tabindex='-1'])");
    return Array.prototype.filter.call(lista, function (el) {
      return !el.disabled && el.offsetParent !== null;
    });
  }

  // Viewport visible (descuenta el teclado virtual en móviles): la hoja a
  // pantalla completa usa su alto y su desplazamiento.
  function ajustarViewport() {
    var vv = window.visualViewport;
    if (!vv) return;
    contenedor.style.setProperty("--rw-vv-alto", vv.height + "px");
    contenedor.style.setProperty("--rw-vv-arriba", vv.offsetTop + "px");
    // Teléfono con el teclado abierto: el avatar cede su espacio al campo.
    contenedor.classList.toggle("rw-teclado", window.innerWidth <= 480 && vv.height < window.innerHeight * 0.75);
  }
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", ajustarViewport);
    window.visualViewport.addEventListener("scroll", ajustarViewport);
  }

  function abrirPanel() {
    if (INCRUSTADO) {
      input.focus();
      return;
    }
    // Dentro de Shadow DOM, document.activeElement es el host; conservar el
    // elemento interno permite devolver el foco al botón que abrió el diálogo.
    elementoFocoPrevio = raiz.activeElement || document.activeElement;
    ajustarViewport();
    terminarSalida(false);
    panel.hidden = false;
    if (cuadroVoz === null) finalizarVoz();
    boton.setAttribute("aria-expanded", "true");
    input.focus();
    document.addEventListener("keydown", manejarTeclado, true);
    cargarAvatar();
    ubicarAvatar();
    if (AVATAR.controlador) avatarAlAbrir();
    emitir("ipsis:open");
  }

  // La salida se anima y recién al terminar el panel queda hidden. Sin
  // animación (prefers-reduced-motion o `animations.enabled: false`) se oculta al tiro.
  var temporizadorSalida = null;
  function terminarSalida(ocultar) {
    if (temporizadorSalida) clearTimeout(temporizadorSalida);
    temporizadorSalida = null;
    panel.classList.remove("rw-saliendo");
    panel.removeEventListener("animationend", alTerminarSalida);
    if (ocultar) panel.hidden = true;
  }
  function alTerminarSalida(ev) {
    if (ev.target === panel) terminarSalida(true);
  }
  function panelAbierto() {
    return !panel.hidden && !panel.classList.contains("rw-saliendo");
  }

  function cerrarPanel() {
    if (INCRUSTADO) return;
    panel.classList.add("rw-saliendo");
    var estilo = window.getComputedStyle(panel);
    if (sinMovimiento() || estilo.animationName === "none" || parseFloat(estilo.animationDuration) === 0) {
      terminarSalida(true);
    } else {
      panel.addEventListener("animationend", alTerminarSalida);
      temporizadorSalida = setTimeout(function () { terminarSalida(true); }, 600);  // por si no llega el evento
    }
    boton.setAttribute("aria-expanded", "false");
    document.removeEventListener("keydown", manejarTeclado, true);
    ubicarAvatar();
    if (AVATAR.controlador) avatarAlCerrar();
    if (elementoFocoPrevio && typeof elementoFocoPrevio.focus === "function") {
      elementoFocoPrevio.focus();
    } else {
      boton.focus();
    }
    emitir("ipsis:close");
  }

  function manejarTeclado(ev) {
    if (ev.key === "Escape") {
      ev.preventDefault();
      if (menuVoz.open) { menuVoz.open = false; resumenMenuVoz.focus(); return; }
      cerrarPanel();
      return;
    }
    if (ev.key !== "Tab") return;
    var focables = elementosFocables();
    if (!focables.length) return;
    var primero = focables[0];
    var ultimo = focables[focables.length - 1];
    // Foco atrapado dentro del panel: si Tab/Shift+Tab saldría del panel,
    // se lo rebota al otro extremo -- comparación contra shadowRoot.activeElement
    // (no document.activeElement, que dentro de un Shadow DOM abierto
    // apunta al host, no al elemento real con foco).
    var activo = raiz.activeElement;
    if (ev.shiftKey && activo === primero) {
      ev.preventDefault();
      ultimo.focus();
    } else if (!ev.shiftKey && activo === ultimo) {
      ev.preventDefault();
      primero.focus();
    }
  }

  boton.addEventListener("click", function () {
    if (!panelAbierto()) abrirPanel();
    else cerrarPanel();
  });
  botonCerrar.addEventListener("click", cerrarPanel);
  if (INCRUSTADO) botonCerrar.hidden = true;

  // La configuración se pide al cargar: la ubicación de styles.yaml aplica al
  // lanzador desde el principio, y el saludo ya está listo al abrir.
  // -------------------------------------------------------------------
  // 6. Avatar (opcional). El motor (/avatar.js, @bible-strong/avatar-web)
  //    se carga bajo demanda: al abrir el panel por primera vez o, si va en
  //    el lanzador, cuando el navegador está ocioso. Si algo falla (red,
  //    CSP sin 'unsafe-eval', definición inválida) queda el ícono y se emite
  //    ipsis:avatar con el error: el chat nunca se rompe.
  // -------------------------------------------------------------------
  var AVATAR = { config: null, promesa: null, controlador: null, definicion: null, lienzo: null,
                 analizarTexto: null, expresionTexto: null, sobre: false, ultimoContacto: -Infinity };

  function urlDelServicio(ruta) {
    if (/^https?:\/\//.test(ruta)) return ruta;
    if (AVATAR_BASE) return new URL(AVATAR_BASE.replace(/\/?$/, "/") + ruta.replace(/^\//, ""), window.location.href).href;
    return API_BASE + ruta;
  }

  // /config::avatar (nombres públicos) → los del widget.
  var UBICACIONES_AVATAR = { "header": "cabecera", "message": "mensaje", "top-corner": "esquina-superior", "bottom-corner": "esquina-inferior" };
  function avatarInterno(c) {
    if (!c || typeof c !== "object") return null;
    var g = c.gaze || {};
    return {
      activo: !!c.enabled, nombre: c.name, url_definicion: c.definition_url, url_motor: c.engine_url,
      ubicacion: UBICACIONES_AVATAR[c.placement] || "cabecera", tamano: c.size, en_lanzador: !!c.in_launcher,
      mirada: { activa: !!g.enabled, amplitud_ojos: g.eye_range, amplitud_cabeza: g.head_range, zona_muerta: g.dead_zone },
      inactividad_min: c.idle_minutes, eventos: c.events || {}, respaldos: c.fallbacks || {}
    };
  }

  function configurarAvatar(publico) {
    var cfg = avatarInterno(publico);
    if (!cfg || !cfg.activo || !cfg.url_motor || !cfg.url_definicion) return;
    AVATAR.config = cfg;
    var tamano = entero(cfg.tamano, 32, 160);
    if (tamano !== null) contenedor.style.setProperty("--rw-avatar-tamano", tamano + "px");
    if (INCRUSTADO || panelAbierto()) {
      cargarAvatar();
    } else if (cfg.en_lanzador) {
      var ocioso = window.requestIdleCallback || function (fn) { return setTimeout(fn, 1500); };
      ocioso(function () { cargarAvatar(); });
    }
  }

  function cargarAvatar() {
    var cfg = AVATAR.config;
    if (!cfg || AVATAR.promesa) return AVATAR.promesa;
    AVATAR.promesa = Promise.all([
      import(urlDelServicio(cfg.url_motor)),
      fetch(urlDelServicio(cfg.url_definicion), { headers: cabecerasComunes() }).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
    ]).then(function (r) {
      montarAvatar(r[0], r[1]);
    }).catch(function (error) {
      AVATAR.controlador = null;
      emitir("ipsis:avatar", { state: "error", message: String((error && error.message) || error) });
    });
    return AVATAR.promesa;
  }

  function montarAvatar(motor, definicion) {
    var lienzo = document.createElement("span");
    lienzo.className = "rw-avatar-lienzo";
    if (/^[a-z0-9-]+$/.test(String(AVATAR.config.nombre || ""))) lienzo.setAttribute("data-avatar", AVATAR.config.nombre);
    // Decorativo: los estados ya tienen texto y etiqueta propios.
    lienzo.setAttribute("aria-hidden", "true");
    var ajustes = AVATAR.config.mirada || {};
    if (ajustes.activa) {
      var agregarMirada = typeof motor.withPointerGaze === "function" ? motor.withPointerGaze : conMirada;
      definicion = agregarMirada(definicion, Number(ajustes.amplitud_ojos) || 0, Number(ajustes.amplitud_cabeza) || 0);
    }
    AVATAR.definicion = definicion;
    var opciones = {
      definition: definicion,
      size: "100%",
      ariaLabel: "",
      onError: function (e) { emitir("ipsis:avatar", { state: "error", message: e.message }); }
    };
    var inicial = claveDe("idle");
    if (definicion.animations && definicion.animations[inicial]) opciones.defaultAnimation = inicial;
    // createAvatar valida la definición (y lanza si no es válida): recién
    // con el avatar montado se reemplaza el ícono.
    AVATAR.controlador = motor.createAvatar(lienzo, opciones);
    AVATAR.analizarTexto = typeof motor.reactionForText === "function" ? motor.reactionForText : null;
    autonomiaAvatar(true);
    AVATAR.lienzo = lienzo;
    maquina.ultimoPersistente = inicial;
    ubicarAvatar();
    emitir("ipsis:avatar", { state: "ready", name: AVATAR.config.nombre });
    reiniciarInactividad(false);
    if (INCRUSTADO || panelAbierto()) avatarAlAbrir();
  }

  // Lleva el lienzo a donde corresponde: el lanzador con el panel cerrado
  // (si en_lanzador), y la cabecera o una esquina del panel con él abierto.
  var esquinaAvatar = null;
  function ubicarAvatar() {
    var lienzo = AVATAR.lienzo, cfg = AVATAR.config;
    if (!lienzo || !cfg) return;
    var abierto = INCRUSTADO || panelAbierto();
    var destino;
    if (!abierto) {
      if (!cfg.en_lanzador) return;
      destino = boton;
    } else if (cfg.ubicacion === "mensaje" && modoBusqueda) {
      destino = lugarAvatarVoz;           // junto al mensaje del asistente, abajo a la derecha
    } else if (cfg.ubicacion === "esquina-superior" || cfg.ubicacion === "esquina-inferior") {
      if (!esquinaAvatar) {
        esquinaAvatar = document.createElement("div");
        esquinaAvatar.className = "rw-avatar-esquina";
        panel.appendChild(esquinaAvatar);
      }
      esquinaAvatar.setAttribute("data-esquina", cfg.ubicacion);
      destino = esquinaAvatar;
    } else {
      destino = avatar;
    }
    if (lienzo.parentNode === destino) return;
    destino.appendChild(lienzo);
    espacioVoz.dataset.avatar = destino === lugarAvatarVoz ? "si" : "no";
    var enCabecera = destino === avatar;
    // Con el avatar junto al mensaje, el ícono fijo de la cabecera sobra:
    // el mismo personaje no debe verse dos veces en pantalla.
    avatar.style.display = destino === lugarAvatarVoz ? "none" : "";
    avatar.classList.toggle("rw-avatar-vivo", enCabecera);
    Array.prototype.forEach.call(avatar.children, function (hijo) {
      if (hijo !== lienzo) hijo.style.display = enCabecera ? "none" : "";
    });
    if (cfg.en_lanzador) boton.classList.add("rw-con-avatar");
  }

  // --- 6.1 Máquina de estados ------------------------------------------
  // Persistentes: inactivo, atento, escribiendo, pensando, pensando_largo y
  // somnoliento; se repiten (loop) mientras dure la situación. Transitorios:
  // el resto; suenan una vez (≥ 600 ms) y vuelven al persistente vigente.
  // Un transitorio de mayor prioridad interrumpe a otro; uno de menor
  // prioridad espera a que termine el actual o se descarta.
  var PRIORIDAD = {
    error: 6, answer_ok: 5, answer_related: 5, no_answer: 5, conversational: 5,
    sent: 4, wake_up: 3, greeting: 2, farewell: 2, launcher: 1
  };
  var PERSISTENTES = {
    idle: 1, attentive: 1, typing: 1, thinking: 1, thinking_long: 1, sleepy: 1
  };
  var DURACION_MINIMA_MS = 600;
  var RETRASO_TECLEO_MS = 1200;
  var PENSANDO_LARGO_MS = 3000;
  var maquina = {
    persistente: "idle", transitorio: null, prioridad: 0, temporizador: null,
    tecleo: null, largo: null, inactividad: null, ultimoPersistente: null
  };

  function existe(clave) {
    var d = AVATAR.definicion;
    return !!(d && clave && ((d.animations && d.animations[clave]) || (d.expressions && d.expressions[clave])));
  }

  // Clave efectiva de un evento: la de /config; si el avatar no la tiene,
  // la del evento de respaldo en cadena, y al final la expresión neutral.
  function claveDe(evento) {
    var cfg = AVATAR.config || {}, eventos = cfg.eventos || {}, respaldos = cfg.respaldos || {};
    var vistos = {};
    while (evento && !vistos[evento]) {
      vistos[evento] = true;
      if (existe(eventos[evento])) return eventos[evento];
      evento = respaldos[evento];
    }
    return "neutral";
  }

  // Reproduce una clave: animación si existe como tal, si no expresión.
  function reproducir(clave) {
    var c = AVATAR.controlador, d = AVATAR.definicion;
    if (!c) return;
    if (d.animations && d.animations[clave]) c.play(clave);
    else c.setExpression(clave);
  }

  function duracionDe(clave) {
    var anim = AVATAR.definicion && AVATAR.definicion.animations && AVATAR.definicion.animations[clave];
    if (!anim || anim.playbackMode !== "once") return 1200;
    var total = 0;
    anim.steps.forEach(function (paso) { total += (paso.transitionMs || 0) + (paso.holdMs || 0); });
    return Math.max(DURACION_MINIMA_MS, total);
  }

  function aplicarPersistente() {
    if (maquina.transitorio) return;
    var clave = claveDe(maquina.persistente);
    if (clave === maquina.ultimoPersistente) {
      autonomiaAvatar(maquina.persistente === "idle" || maquina.persistente === "attentive");
      return;
    }
    maquina.ultimoPersistente = clave;
    reproducir(clave);
    autonomiaAvatar(maquina.persistente === "idle" || maquina.persistente === "attentive");
    emitir("ipsis:avatar", { state: "event", event: maquina.persistente, key: clave });
  }

  function persistir(estado) {
    maquina.persistente = estado;
    if (estado !== "idle" && estado !== "attentive") autonomiaAvatar(false);
    if (estado !== "thinking" && estado !== "thinking_long") {
      clearTimeout(maquina.largo);
      maquina.largo = null;
    }
    aplicarPersistente();
  }

  function transitar(evento) {
    var prioridad = PRIORIDAD[evento] || 1;
    if (maquina.transitorio && prioridad < maquina.prioridad) return;
    clearTimeout(maquina.temporizador);
    var clave = claveDe(evento);
    maquina.transitorio = evento;
    maquina.prioridad = prioridad;
    maquina.ultimoPersistente = null;
    autonomiaAvatar(false);
    reproducir(clave);
    emitir("ipsis:avatar", { state: "event", event: evento, key: clave });
    maquina.temporizador = setTimeout(function () {
      maquina.transitorio = null;
      maquina.prioridad = 0;
      aplicarPersistente();
    }, duracionDe(clave));
  }

  // Punto único de entrada: lo usan el widget, el panel /admin y los sitios.
  function autonomiaAvatar(activa) {
    var c = AVATAR.controlador;
    if (c && typeof c.setAutonomy === "function") c.setAutonomy(activa);
  }

  function reaccionAvatar(clave) {
    var c = AVATAR.controlador;
    if (c && typeof c.react === "function" && existe(clave) && !maquina.transitorio) c.react(clave);
  }

  function disparar(evento) {
    if (!AVATAR.controlador) return false;
    reiniciarInactividad(evento !== "sleepy");
    if (PERSISTENTES[evento]) persistir(evento);
    else transitar(evento);
    return true;
  }

  // --- 6.2 Inactividad y visibilidad ------------------------------------
  function reiniciarInactividad(despertar) {
    clearTimeout(maquina.inactividad);
    if (despertar && maquina.persistente === "sleepy") {
      maquina.persistente = (INCRUSTADO || panelAbierto()) ? "attentive" : "idle";
      transitar("wake_up");
    }
    var minutos = Number((AVATAR.config || {}).inactividad_min) || 2;
    maquina.inactividad = setTimeout(function () { persistir("sleepy"); }, minutos * 60000);
  }

  document.addEventListener("visibilitychange", function () {
    var c = AVATAR.controlador;
    if (!c) return;
    if (document.hidden) {
      c.pause();
    } else {
      maquina.ultimoPersistente = null;
      aplicarPersistente();
    }
  });

  // --- 6.3 Enlace con el chat -------------------------------------------
  function avatarAlAbrir() {
    // Cada apertura reproduce el gesto configurado (Folio despierta), también
    // al reabrir antes de que termine la despedida.
    maquina.persistente = "attentive";
    reiniciarInactividad(false);
    transitar("greeting");
  }
  function avatarAlCerrar() {
    maquina.persistente = "idle";
    transitar("farewell");
  }
  function avatarAlTeclear() {
    if (!AVATAR.controlador) return;
    reiniciarInactividad(true);
    var empieza = maquina.persistente !== "typing";
    if (maquina.persistente !== "thinking" && maquina.persistente !== "thinking_long") persistir("typing");
    if (maquina.persistente === "typing" && AVATAR.analizarTexto) {
      var expresion = AVATAR.analizarTexto(input.value);
      if (empieza || expresion !== AVATAR.expresionTexto) reaccionAvatar(expresion);
      AVATAR.expresionTexto = expresion;
    }
    clearTimeout(maquina.tecleo);
    maquina.tecleo = setTimeout(function () {
      if (maquina.persistente === "typing") {
        persistir("attentive");
        if (input.value.trim() && AVATAR.analizarTexto) reaccionAvatar(AVATAR.analizarTexto(input.value));
      }
    }, RETRASO_TECLEO_MS);
  }
  function avatarAlEnviar() {
    if (!AVATAR.controlador) return;
    clearTimeout(maquina.tecleo);
    AVATAR.expresionTexto = null;
    maquina.persistente = "thinking";
    transitar("sent");
    clearTimeout(maquina.largo);
    maquina.largo = setTimeout(function () {
      if (maquina.persistente === "thinking") persistir("thinking_long");
    }, PENSANDO_LARGO_MS);
  }
  var EVENTO_DE_ESTADO = {
    ok: "answer_ok", relacionado: "answer_related", sin_respuesta: "no_answer",
    conversacional: "conversational"
  };
  function avatarAlResponder(estado) {
    if (!AVATAR.controlador) return;
    maquina.persistente = "attentive";
    clearTimeout(maquina.largo);
    transitar(EVENTO_DE_ESTADO[estado] || "answer_related");
  }
  function avatarAlFallar() {
    if (!AVATAR.controlador) return;
    maquina.persistente = "attentive";
    clearTimeout(maquina.largo);
    transitar("error");
  }

  // --- 6.4 Mirada: grilla de 5 × 3 expresiones derivadas de neutral -------
  // El widget sigue al puntero cambiando de expresión (la librería no trae
  // seguimiento). Zona muerta al centro, histéresis contra el temblor y
  // vuelta al centro tras 1,5 s quieto. Solo en reposo (inactivo o atento) y
  // nunca con prefers-reduced-motion.
  var COLUMNAS = 5, FILAS = 3, HISTERESIS_PX = 6, QUIETO_MS = 1500;
  function claveMirada(col, fila) { return "mirada-c" + col + "-f" + fila; }

  function conMirada(definicion, amplitudOjos, amplitudCabeza) {
    var neutral = definicion.expressions && definicion.expressions.neutral;
    var total = Object.keys(definicion.expressions || {}).length;
    if (!neutral || total + COLUMNAS * FILAS > 128) return definicion;
    var expresiones = {}, orden = (definicion.expressionOrder || []).slice();
    Object.keys(definicion.expressions).forEach(function (k) { expresiones[k] = definicion.expressions[k]; });
    for (var col = 0; col < COLUMNAS; col++) {
      for (var fila = 0; fila < FILAS; fila++) {
        var dx = (col - 2) / 2, dy = fila - 1, e = JSON.parse(JSON.stringify(neutral));
        ["left", "right"].forEach(function (lado) {
          e.eyes[lado].x = e.eyes[lado].x + dx * amplitudOjos * 2;
          e.eyes[lado].y = e.eyes[lado].y + dy * amplitudOjos * 1.5;
        });
        e.head.y = e.head.y + dx * amplitudCabeza * 2;
        e.head.x = e.head.x - dy * amplitudCabeza;
        expresiones[claveMirada(col, fila)] = e;
        orden.push(claveMirada(col, fila));
      }
    }
    var salida = {};
    Object.keys(definicion).forEach(function (k) { salida[k] = definicion[k]; });
    salida.expressions = expresiones;
    salida.expressionOrder = orden;
    return salida;
  }

  // Nivel (0, 1 o 2) de |d| con histéresis respecto del nivel actual.
  function nivel(d, actual, zona) {
    var limites = [zona, zona * 6], n = 0;
    for (var i = 0; i < limites.length; i++) {
      var limite = limites[i] + (actual > i ? -HISTERESIS_PX : HISTERESIS_PX);
      if (Math.abs(d) >= limite) n = i + 1;
    }
    return n;
  }

  var mirada = { col: 2, fila: 1, quieto: null, pendiente: null };
  function celdaPara(dx, dy, zona) {
    var nx = nivel(dx, Math.abs(mirada.col - 2), zona), ny = Math.min(1, nivel(dy, Math.abs(mirada.fila - 1), zona));
    return { col: 2 + (dx < 0 ? -nx : nx), fila: 1 + (dy < 0 ? -ny : ny) };
  }

  function puedeMirar() {
    var cfg = AVATAR.config;
    if (!AVATAR.controlador || !cfg || !cfg.mirada || !cfg.mirada.activa) return false;
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
    if (maquina.transitorio) return false;
    return maquina.persistente === "idle" || maquina.persistente === "attentive";
  }

  function mirarHacia(x, y) {
    if (!puedeMirar() || !AVATAR.lienzo || !AVATAR.lienzo.isConnected) return;
    var caja = AVATAR.lienzo.getBoundingClientRect();
    if (!caja.width) return;
    var zona = Number(AVATAR.config.mirada.zona_muerta);
    if (!(zona >= 0)) zona = 24;
    var celda = celdaPara(x - (caja.left + caja.width / 2), y - (caja.top + caja.height / 2), zona);
    clearTimeout(mirada.quieto);
    mirada.quieto = setTimeout(volverAlCentro, QUIETO_MS);
    autonomiaAvatar(false);
    if (celda.col === mirada.col && celda.fila === mirada.fila) return;
    mirada.col = celda.col;
    mirada.fila = celda.fila;
    maquina.ultimoPersistente = null;
    AVATAR.controlador.setExpression(claveMirada(celda.col, celda.fila));
  }

  function volverAlCentro() {
    if (mirada.col === 2 && mirada.fila === 1) {
      if (puedeMirar()) autonomiaAvatar(true);
      return;
    }
    mirada.col = 2;
    mirada.fila = 1;
    if (puedeMirar()) {
      maquina.ultimoPersistente = null;
      aplicarPersistente();
    }
  }

  document.addEventListener("pointermove", function (ev) {
    if (mirada.pendiente) return;
    var x = ev.clientX, y = ev.clientY;
    mirada.pendiente = window.requestAnimationFrame(function () {
      mirada.pendiente = null;
      mirarHacia(x, y);
      // El lienzo es decorativo (pointer-events:none): se detecta el contacto
      // por su caja, sin interceptar los clics del lanzador o del chat.
      if (!AVATAR.lienzo) return;
      var caja = AVATAR.lienzo.getBoundingClientRect();
      var dentro = caja.width > 0 && x >= caja.left && x <= caja.right && y >= caja.top && y <= caja.bottom;
      if (dentro && !AVATAR.sobre && puedeMirar() && performance.now() - AVATAR.ultimoContacto >= 2000) {
        AVATAR.ultimoContacto = performance.now();
        reiniciarInactividad(true);
        reaccionAvatar("kind");
      }
      AVATAR.sobre = dentro;
    });
  }, { passive: true });
  document.addEventListener("pointerleave", function () { AVATAR.sobre = false; volverAlCentro(); });

  cargarConfigServidor();

  // API del sitio (se supone un widget por página): abrir y cerrar desde un
  // botón propio (launcher «hidden») o consultar el estado.
  window.Ipsis = {
    open: abrirPanel,
    close: cerrarPanel,
    // Avatar: trigger(event) devuelve false si todavía no hay avatar montado.
    avatar: {
      trigger: disparar,
      state: function () {
        return { ready: !!AVATAR.controlador, persistent: maquina.persistente, transient: maquina.transitorio,
                 gaze: AVATAR.controlador ? claveMirada(mirada.col, mirada.fila) : null };
      }
    },
    state: function () {
      return {
        open: panelAbierto(),
        position: publico("posicion", UBICACION.posicion),
        size: publico("tamano", UBICACION.tamano),
        launcher: publico("lanzador", UBICACION.lanzador),
        session: ID_SESION
      };
    }
  };
})();
