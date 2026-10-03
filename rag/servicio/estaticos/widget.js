/*
 * Widget de chat embebible -- rag-extractivo.
 *
 * Un único archivo, sin frameworks ni dependencias externas. Se integra con
 * una línea:
 *
 *   <script src="https://tu-servidor/widget.js" data-api="https://tu-servidor"></script>
 *
 * O como Web Component declarativo:
 *   <rag-extractivo-chat api="https://tu-servidor"></rag-extractivo-chat>
 *   <script src="https://tu-servidor/widget.js"></script>
 *
 * El componente acepta `api`, `widget-key`, `color`, `titulo`, `saludo` y
 * `posicion`; emite rag:abierto, rag:cerrado, rag:pregunta, rag:respuesta y
 * rag:error.
 *
 * Atributos `data-` soportados en la etiqueta <script>:
 *   data-api        base del servicio (si se omite, usa el mismo origen
 *                   desde el que se sirvió este archivo -- normalmente
 *                   correcto, porque el servicio sirve su propio widget).
 *   data-widget-key clave pública de widget (opcional, ver
 *                   rag/servicio/seguridad.py -- NO es un secreto).
 *   data-color      color de acento (hex), por defecto "#2563eb".
 *   data-titulo     título del panel (se sobrescribe con lo que traiga
 *                   /config en cuanto responda, salvo que /config falle).
 *   data-saludo     saludo inicial de repuesto, por si /config no responde.
 *   data-posicion   "abajo-derecha" (por defecto) | "abajo-izquierda".
 *
 * Reglas de diseño del widget:
 *  - Shadow DOM: el CSS del sitio anfitrión no debe deformar el widget, ni
 *    al revés.
 *  - Los CUATRO estados de una respuesta (ok / relacionado / sin_respuesta /
 *    conversacional) se pintan DISTINTO -- es la mitad de la honestidad del
 *    sistema.
 *  - Ningún texto que venga de la API se inserta como HTML: SIEMPRE
 *    `textContent`, nunca `innerHTML` con datos de la API interpolados.
 *  - Accesible: roles ARIA, cierre con Escape, foco atrapado en el panel
 *    abierto, pantalla completa en móvil.
 *  - Identificador de sesión en `localStorage` (la API exige `id_sesion`).
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
  if (window.customElements && !window.customElements.get("rag-extractivo-chat")) {
    window.customElements.define("rag-extractivo-chat", class extends HTMLElement {});
  }
  var host = document.querySelector("rag-extractivo-chat:not([data-rag-inicializado])");
  if (!host) {
    host = document.createElement(window.customElements ? "rag-extractivo-chat" : "div");
    document.body.appendChild(host);
  }
  host.id = host.id || "rag-widget-host";
  host.setAttribute("data-rag-inicializado", "true");

  function opcion(atributo, dato, repuesto) {
    return host.getAttribute(atributo) || datos[dato] || repuesto;
  }
  var API_BASE = opcion("api", "api", window.location.origin).replace(/\/$/, "");
  var CLAVE_WIDGET = opcion("widget-key", "widgetKey", "") || null;
  var COLOR_ACENTO = opcion("color", "color", "#2563eb");
  var TITULO_INICIAL = opcion("titulo", "titulo", "Asistente");
  var SALUDO_INICIAL = opcion("saludo", "saludo", "Hola, ¿en qué puedo ayudarte?");
  var POSICION = opcion("posicion", "posicion", "abajo-derecha") === "abajo-izquierda" ? "izquierda" : "derecha";
  var CABECERA_CLAVE_WIDGET = "X-Rag-Widget-Key";
  var PRESENTACION = {
    densidad: "comoda",
    citas: "acordeon",
    mostrarEtiquetaEstado: true,
  };
  function emitir(nombre, detalle) {
    host.dispatchEvent(new CustomEvent(nombre, { detail: detalle || {}, bubbles: true }));
  }

  // -------------------------------------------------------------------
  // 1. Identificador de sesión: se genera una vez por navegador y se
  //    reusa entre recargas (localStorage) -- la API exige `id_sesion`
  //    en cada POST /consultar.
  // -------------------------------------------------------------------
  function generarIdSesion() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    // Repuesto sin crypto.randomUUID (navegadores más viejos): suficiente
    // para distinguir sesiones, no necesita ser criptográficamente fuerte.
    return "sesion-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  function idSesion() {
    var CLAVE_STORAGE = "rag_widget_id_sesion";
    try {
      var existente = window.localStorage.getItem(CLAVE_STORAGE);
      if (existente) return existente;
      var nuevo = generarIdSesion();
      window.localStorage.setItem(CLAVE_STORAGE, nuevo);
      return nuevo;
    } catch (e) {
      // localStorage puede fallar (modo privado estricto, cuotas): la
      // sesión sigue funcionando, solo no sobrevive a una recarga.
      return generarIdSesion();
    }
  }
  var ID_SESION = idSesion();

  // -------------------------------------------------------------------
  // 2. Contenedor con Shadow DOM: aísla el CSS del widget del sitio
  //    anfitrión (y viceversa), sea cual sea el sitio donde se embeba.
  // -------------------------------------------------------------------
  var raiz = host.attachShadow({ mode: "open" });

  var estilos = document.createElement("style");
  // TODO el diseno sale de estas variables. Son los valores de repuesto,
  // los que se usan si el servicio no responde: `configuracion/estilos.yaml`
  // las redefine y el servicio las sirve en /estilos.css, que se enlaza
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
    "  --rw-radio-panel:18px;",
    "  --rw-radio-burbuja:16px;",
    "  --rw-radio-control:12px;",
    "  --rw-ancho-panel:390px;",
    "  --rw-alto-panel:600px;",
    "  --rw-tamano-boton:58px;",
    "  --rw-tamano-icono:26px;",
    "  --rw-margen:24px;",
    "  --rw-separacion:12px;",
    "  --rw-relleno:16px;",
    "  --rw-dur-panel:.22s;",
    "  --rw-dur-burbuja:.2s;",
    "  --rw-dur-control:.18s;",
    "  --rw-dur-latido:1.2s;",
    "  --rw-curva:cubic-bezier(.16,1,.3,1);",
    "  --rw-desplazamiento-entrada:12px;",
    "  --rw-escala-entrada:.96;",
    "  --rw-escala-hover:1.04;",
    "  position:fixed;bottom:var(--rw-margen);" + POSICION + ":var(--rw-margen);",
    "  z-index:2147483000;font-family:var(--rw-fuente);font-size:var(--rw-tamano-base);",
    "  line-height:1.5;-webkit-font-smoothing:antialiased;}",
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
    ".rw-boton[aria-expanded='true'] .rw-icono-chat{display:none;}",
    ".rw-boton[aria-expanded='true'] .rw-icono-cerrar{display:block;}",

    ".rw-panel{position:fixed;bottom:calc(var(--rw-margen) + var(--rw-tamano-boton) + 16px);",
    "  " + POSICION + ":var(--rw-margen);width:var(--rw-ancho-panel);",
    "  max-width:calc(100vw - var(--rw-margen) * 2);height:var(--rw-alto-panel);",
    "  max-height:calc(100vh - 140px);background:var(--rw-superficie);",
    "  border-radius:var(--rw-radio-panel);box-shadow:var(--rw-sombra-panel);display:flex;",
    "  flex-direction:column;overflow:hidden;border:1px solid var(--rw-borde);",
    "  transform-origin:bottom " + POSICION + ";",
    "  animation:rw-entrar var(--rw-dur-panel) var(--rw-curva);}",
    ".rw-panel[hidden]{display:none;}",
    "@keyframes rw-entrar{",
    "  from{opacity:0;transform:translateY(var(--rw-desplazamiento-entrada)) scale(var(--rw-escala-entrada));}",
    "  to{opacity:1;transform:translateY(0) scale(1);}}",
    "@media (prefers-reduced-motion:reduce){",
    "  .rw-panel,.rw-msg,.rw-punto{animation:none;} .rw-boton,.rw-enviar{transition:none;}}",

    ".rw-cabecera{background:var(--rw-superficie);color:var(--rw-texto);",
    "  padding:14px var(--rw-relleno);display:flex;align-items:center;gap:11px;flex:none;",
    "  border-bottom:1px solid var(--rw-borde);}",
    ".rw-avatar{width:34px;height:34px;border-radius:50%;background:var(--rw-acento);",
    "  color:var(--rw-acento-texto);display:flex;align-items:center;justify-content:center;flex:none;}",
    ".rw-avatar svg{width:18px;height:18px;}",
    ".rw-cabecera-textos{flex:1;min-width:0;}",
    ".rw-cabecera h2{margin:0;font-size:calc(var(--rw-tamano-base) + .5px);font-weight:650;",
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
    "  scrollbar-width:thin;}",
    ".rw-mensajes::-webkit-scrollbar{width:8px;}",
    ".rw-mensajes::-webkit-scrollbar-thumb{background:var(--rw-borde);border-radius:99px;}",
    ".rw-panel[data-densidad='compacta'] .rw-mensajes{padding:10px;gap:8px;}",
    ".rw-panel[data-densidad='compacta'] .rw-msg{padding:7px 10px;max-width:92%;}",
    ".rw-msg{max-width:86%;padding:10px 13px;border-radius:var(--rw-radio-burbuja);",
    "  font-size:var(--rw-tamano-mensaje);line-height:var(--rw-interlineado);",
    "  white-space:pre-wrap;overflow-wrap:anywhere;",
    "  animation:rw-burbuja var(--rw-dur-burbuja) ease-out;}",
    "@keyframes rw-burbuja{from{opacity:0;transform:translateY(5px);}to{opacity:1;transform:none;}}",
    ".rw-msg-usuario{align-self:flex-end;background:var(--rw-acento);color:var(--rw-acento-texto);",
    "  border-bottom-right-radius:5px;}",
    ".rw-msg-ok{align-self:flex-start;background:var(--rw-superficie);color:var(--rw-texto);",
    "  border:1px solid var(--rw-borde);border-bottom-left-radius:5px;}",
    ".rw-msg-relacionado{align-self:flex-start;background:var(--rw-superficie);",
    "  color:var(--rw-texto);border:1px solid var(--rw-borde);",
    "  border-left:3px solid var(--rw-aviso-borde);border-bottom-left-radius:5px;}",
    ".rw-msg-sin_respuesta{align-self:center;background:transparent;color:var(--rw-texto-suave);",
    "  border:none;font-size:var(--rw-tamano-cita);text-align:center;padding:4px 8px;max-width:100%;}",
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

    ".rw-escribiendo{align-self:flex-start;display:flex;gap:4px;padding:12px 14px;",
    "  background:var(--rw-superficie);border:1px solid var(--rw-borde);",
    "  border-radius:var(--rw-radio-burbuja);border-bottom-left-radius:5px;}",
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
    "  transition:border-color .15s ease;}",
    ".rw-form input::placeholder{color:var(--rw-texto-suave);}",
    ".rw-form input:focus{outline:none;border-color:var(--rw-acento);}",
    ".rw-form input:disabled{opacity:.6;}",
    ".rw-enviar{background:var(--rw-acento);color:var(--rw-acento-texto);border:none;",
    "  border-radius:var(--rw-radio-control);width:42px;height:42px;flex:none;cursor:pointer;",
    "  display:flex;align-items:center;justify-content:center;",
    "  transition:opacity .15s ease, transform var(--rw-dur-control) ease;}",
    ".rw-enviar svg{width:18px;height:18px;}",
    ".rw-enviar:hover:not(:disabled){transform:scale(var(--rw-escala-hover));}",
    ".rw-enviar:disabled{opacity:.45;cursor:default;}",
    ".rw-enviar:focus-visible{outline:3px solid var(--rw-acento);outline-offset:2px;}",
    ".rw-sr-solo{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);}",

    "@media (max-width:480px){",
    "  .rw-panel{position:fixed;top:0;left:0;right:0;bottom:0;width:100%;max-width:100%;",
    "    height:100%;max-height:100%;border-radius:0;border:none;}",
    "  .rw-raiz{--rw-margen:16px;}",
    "  .rw-msg{max-width:92%;}}",
  ].join("\n");
  raiz.appendChild(estilos);

  // Tema del despliegue: `configuracion/estilos.yaml`, servido en
  // /estilos.css. Se enlaza DESPUES del bloque de arriba, asi que
  // redefine las variables que declare y deja el resto con su valor de
  // repuesto. Si el servicio no responde, el widget se ve igual que aqui
  // -- nunca queda sin estilos.
  var temaServidor = document.createElement("link");
  temaServidor.rel = "stylesheet";
  temaServidor.href = API_BASE + "/estilos.css";
  raiz.appendChild(temaServidor);

  // Iconos en SVG en vez de emoji: un emoji se dibuja distinto en cada
  // sistema (y en Windows sale con su propio color), mientras que el SVG
  // hereda `currentColor` y se ve igual en todas partes. Se construyen con
  // createElementNS porque este archivo no usa innerHTML en ningun punto.
  var NS_SVG = "http://www.w3.org/2000/svg";
  var TRAZOS = {
    chat: "M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z",
    cerrar: "M18 6 6 18M6 6l12 12",
    enviar: "M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"
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

  var contenedor = document.createElement("div");
  contenedor.className = "rw-raiz";
  raiz.appendChild(contenedor);

  var boton = document.createElement("button");
  boton.className = "rw-boton";
  boton.type = "button";
  boton.setAttribute("aria-haspopup", "dialog");
  boton.setAttribute("aria-expanded", "false");
  boton.setAttribute("aria-label", "Abrir chat de " + TITULO_INICIAL);
  // Dos iconos fijos: el CSS muestra uno u otro segun aria-expanded, asi
  // el mismo boton abre y cierra sin que nada dependa de la API.
  boton.appendChild(icono("chat", "rw-icono-chat"));
  boton.appendChild(icono("cerrar", "rw-icono-cerrar"));
  contenedor.appendChild(boton);

  var panel = document.createElement("div");
  panel.className = "rw-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "true");
  panel.setAttribute("aria-label", TITULO_INICIAL);
  panel.hidden = true;
  contenedor.appendChild(panel);

  var cabecera = document.createElement("div");
  cabecera.className = "rw-cabecera";

  var avatar = document.createElement("div");
  avatar.className = "rw-avatar";
  avatar.appendChild(icono("chat"));

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
  subtituloTexto.textContent = "Responde citando el documento";
  subtitulo.appendChild(puntoVivo);
  subtitulo.appendChild(subtituloTexto);
  cabeceraTextos.appendChild(tituloEl);
  cabeceraTextos.appendChild(subtitulo);

  var botonCerrar = document.createElement("button");
  botonCerrar.type = "button";
  botonCerrar.className = "rw-cerrar";
  botonCerrar.setAttribute("aria-label", "Cerrar chat");
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
  etiquetaInput.textContent = "Escribe tu pregunta";
  var input = document.createElement("input");
  input.id = "rw-input";
  input.type = "text";
  input.autocomplete = "off";
  input.placeholder = "Escribe tu pregunta...";
  var botonEnviar = document.createElement("button");
  botonEnviar.type = "submit";
  botonEnviar.className = "rw-enviar";
  botonEnviar.setAttribute("aria-label", "Enviar pregunta");
  botonEnviar.appendChild(icono("enviar"));
  form.appendChild(etiquetaInput);
  form.appendChild(input);
  form.appendChild(botonEnviar);
  panel.appendChild(form);

  // -------------------------------------------------------------------
  // 3. Render de mensajes -- TODO texto que venga de la API se asigna con
  //    `textContent`, nunca `innerHTML`: un documento con una comilla
  //    angular no debe poder inyectar marcado en el sitio anfitrión.
  // -------------------------------------------------------------------
  function desplazarAlFinal() {
    mensajes.scrollTop = mensajes.scrollHeight;
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
    relacionado: "No es una respuesta directa",
    sin_respuesta: null,
    conversacional: null,
  };

  function agregarCitas(contenedorMsg, fragmentos) {
    if (!fragmentos || !fragmentos.length || PRESENTACION.citas === "ocultas") return;
    var caja = document.createElement("div");
    caja.className = "rw-citas";
    // Encabezado con el numero de fuentes: deja ver de un vistazo que la
    // respuesta esta respaldada, sin tener que desplegar nada.
    var titulo = document.createElement("p");
    titulo.className = "rw-citas-titulo";
    titulo.textContent = fragmentos.length === 1
      ? "1 fuente del documento"
      : fragmentos.length + " fuentes del documento";
    caja.appendChild(titulo);
    fragmentos.forEach(function (frag) {
      var det = document.createElement("details");
      det.open = PRESENTACION.citas === "abiertas";
      var resumen = document.createElement("summary");
      // documento + sección: texto de la API, SIEMPRE por textContent.
      resumen.textContent = (frag.doc_titulo || "") + " › " + (frag.seccion || "");
      var cuerpo = document.createElement("p");
      cuerpo.className = "rw-cita-texto";
      cuerpo.textContent = frag.texto || "";
      det.appendChild(resumen);
      det.appendChild(cuerpo);
      caja.appendChild(det);
    });
    contenedorMsg.appendChild(caja);
  }

  function agregarMensajeAsistente(respuesta) {
    var estadoResp = respuesta.estado || "sin_respuesta";
    var burbuja = document.createElement("div");
    burbuja.className = "rw-msg rw-msg-" + (ETIQUETAS_ESTADO.hasOwnProperty(estadoResp) ? estadoResp : "sin_respuesta");

    var aviso = ETIQUETAS_ESTADO[estadoResp];
    if (aviso && PRESENTACION.mostrarEtiquetaEstado) {
      var spanAviso = document.createElement("span");
      spanAviso.className = "rw-aviso";
      spanAviso.textContent = aviso; // texto FIJO del widget, no de la API
      burbuja.appendChild(spanAviso);
    }

    var parrafo = document.createElement("p");
    parrafo.style.margin = "0";
    parrafo.textContent = respuesta.respuesta || ""; // texto de la API -> textContent
    burbuja.appendChild(parrafo);

    if (estadoResp === "ok" || estadoResp === "relacionado") {
      agregarCitas(burbuja, respuesta.fragmentos);
    }

    mensajes.appendChild(burbuja);
    desplazarAlFinal();
  }

  // Indicador de "escribiendo": sin el, el widget se queda mudo entre que
  // se envia la pregunta y llega la respuesta. Son tres puntos animados,
  // no un mensaje -- no se agrega nada al historial.
  var burbujaEspera = null;

  function mostrarEscribiendo() {
    if (burbujaEspera) return;
    burbujaEspera = document.createElement("div");
    burbujaEspera.className = "rw-escribiendo";
    burbujaEspera.setAttribute("aria-label", "Buscando en el documento");
    for (var i = 0; i < 3; i++) {
      var punto = document.createElement("span");
      punto.className = "rw-punto";
      burbujaEspera.appendChild(punto);
    }
    mensajes.appendChild(burbujaEspera);
    desplazarAlFinal();
  }

  function ocultarEscribiendo() {
    if (burbujaEspera && burbujaEspera.parentNode) {
      burbujaEspera.parentNode.removeChild(burbujaEspera);
    }
    burbujaEspera = null;
  }

  function agregarMensajeError(texto) {
    var burbuja = document.createElement("div");
    burbuja.className = "rw-msg rw-msg-sin_respuesta";
    burbuja.textContent = texto;
    mensajes.appendChild(burbuja);
    desplazarAlFinal();
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

  function cargarConfigServidor() {
    fetch(API_BASE + "/config", { headers: cabecerasComunes() })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (cfg) {
        PRESENTACION.densidad = cfg.densidad === "compacta" ? "compacta" : "comoda";
        PRESENTACION.citas = ["acordeon", "abiertas", "ocultas"].indexOf(cfg.citas) >= 0
          ? cfg.citas : "acordeon";
        PRESENTACION.mostrarEtiquetaEstado = cfg.mostrar_etiqueta_estado !== false;
        panel.setAttribute("data-densidad", PRESENTACION.densidad);
        if (cfg.preset) panel.setAttribute("data-preset", cfg.preset);
        if (cfg.nombre_asistente) {
          tituloEl.textContent = cfg.nombre_asistente;
          panel.setAttribute("aria-label", cfg.nombre_asistente);
          boton.setAttribute("aria-label", "Abrir chat de " + cfg.nombre_asistente);
        }
        if (cfg.saludo && mensajes.children.length === 0) {
          agregarMensajeAsistente({ estado: "conversacional", respuesta: cfg.saludo });
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

  function enviarPregunta(pregunta) {
    agregarMensajeUsuario(pregunta);
    input.value = "";
    input.disabled = true;
    botonEnviar.disabled = true;
    mostrarEscribiendo();

    fetch(API_BASE + "/consultar", {
      method: "POST",
      headers: cabecerasComunes(),
      body: JSON.stringify({ pregunta: pregunta, id_sesion: ID_SESION }),
    })
      .then(function (r) {
        if (r.status === 429) {
          throw new Error("Demasiadas preguntas seguidas. Espera unos segundos e intenta de nuevo.");
        }
        if (r.status === 401) {
          throw new Error("Este sitio no está autorizado para usar el asistente.");
        }
        if (!r.ok) {
          throw new Error("El servicio no pudo responder (HTTP " + r.status + ").");
        }
        return r.json();
      })
      .then(function (respuesta) {
        agregarMensajeAsistente(respuesta);
        emitir("rag:respuesta", { estado: respuesta.estado, respuesta: respuesta });
      })
      .catch(function (err) {
        // Los navegadores describen los fallos de transporte con textos
        // distintos ("Failed to fetch", "Load failed", etc.). Los errores
        // HTTP creados arriba sí son deliberados y se conservan; un TypeError
        // de fetch recibe un mensaje estable para quien usa el widget.
        var mensajeError = err instanceof TypeError
          ? "No se pudo contactar al asistente. Revisa tu conexión e intenta de nuevo."
          : (err && err.message ? err.message : "No se pudo contactar al asistente.");
        agregarMensajeError(mensajeError);
        emitir("rag:error", { mensaje: mensajeError });
      })
      .finally(function () {
        ocultarEscribiendo();
        input.disabled = false;
        botonEnviar.disabled = false;
        input.focus();
      });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var texto = input.value.trim();
    if (!texto) return;
    emitir("rag:pregunta", { pregunta: texto });
    enviarPregunta(texto);
  });

  // -------------------------------------------------------------------
  // 5. Abrir/cerrar, foco atrapado y Escape -- accesibilidad del panel.
  // -------------------------------------------------------------------
  var elementoFocoPrevio = null;

  function elementosFocables() {
    var lista = panel.querySelectorAll("button, input, [href], [tabindex]:not([tabindex='-1'])");
    return Array.prototype.filter.call(lista, function (el) {
      return !el.disabled && el.offsetParent !== null;
    });
  }

  function abrirPanel() {
    // Dentro de Shadow DOM, document.activeElement es el host; conservar el
    // elemento interno permite devolver el foco al botón que abrió el diálogo.
    elementoFocoPrevio = raiz.activeElement || document.activeElement;
    panel.hidden = false;
    boton.setAttribute("aria-expanded", "true");
    if (mensajes.children.length === 0) cargarConfigServidor();
    input.focus();
    document.addEventListener("keydown", manejarTeclado, true);
    emitir("rag:abierto");
  }

  function cerrarPanel() {
    panel.hidden = true;
    boton.setAttribute("aria-expanded", "false");
    document.removeEventListener("keydown", manejarTeclado, true);
    if (elementoFocoPrevio && typeof elementoFocoPrevio.focus === "function") {
      elementoFocoPrevio.focus();
    } else {
      boton.focus();
    }
    emitir("rag:cerrado");
  }

  function manejarTeclado(ev) {
    if (ev.key === "Escape") {
      ev.preventDefault();
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
    if (panel.hidden) abrirPanel();
    else cerrarPanel();
  });
  botonCerrar.addEventListener("click", cerrarPanel);
})();
