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
 * El componente acepta `api`, `widget-key`, `color`, `titulo`, `saludo` y
 * `posicion`; emite rag:abierto, rag:cerrado, rag:pregunta, rag:respuesta y
 * rag:error.
 *
 * Atributos `data-` soportados en la etiqueta <script>:
 *   data-api        base del servicio (si se omite, usa el mismo origen
 *                   desde el que se sirvió este archivo -- normalmente
 *                   correcto, porque el servicio sirve su propio widget).
 *   data-widget-key clave pública de widget (opcional, ver
 *                   ipsis/servicio/seguridad.py -- NO es un secreto).
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
  if (window.customElements && !window.customElements.get("ipsis-chat")) {
    window.customElements.define("ipsis-chat", class extends HTMLElement {});
  }
  var host = document.querySelector("ipsis-chat:not([data-rag-inicializado])");
  if (!host) {
    host = document.createElement(window.customElements ? "ipsis-chat" : "div");
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
  var CABECERA_CLAVE_WIDGET = "X-Ipsis-Widget-Key";
  // Carpeta alternativa para el motor y la definición del avatar (widget
  // exportado con `ipsis widget exportar`): ahí están avatar.js y avatares/.
  var AVATAR_BASE = opcion("avatar-base", "avatarBase", null);

  // Ubicación: lo que declare el sitio (atributos del elemento o data-* del
  // <script>) manda; lo que no, llega de estilos.yaml vía /config.
  var VALIDOS = {
    posicion: ["abajo-derecha", "abajo-izquierda", "arriba-derecha", "arriba-izquierda", "incrustado"],
    tamano: ["compacto", "normal", "amplio"],
    lanzador: ["burbuja", "pestana", "oculto"]
  };
  function enLista(valor, clave) {
    return VALIDOS[clave].indexOf(valor) >= 0 ? valor : null;
  }
  function entero(valor, minimo, maximo) {
    var n = parseInt(valor, 10);
    return isNaN(n) ? null : Math.min(Math.max(n, minimo), maximo);
  }
  var DEL_SITIO = {
    posicion: enLista(host.getAttribute("modo") === "incrustado" ? "incrustado" : opcion("posicion", "posicion", null), "posicion"),
    tamano: enLista(opcion("tamano", "tamano", null), "tamano"),
    lanzador: enLista(opcion("lanzador", "lanzador", null), "lanzador"),
    desplazamiento_x: entero(opcion("desplazamiento-x", "desplazamientoX", null), 0, 400),
    desplazamiento_y: entero(opcion("desplazamiento-y", "desplazamientoY", null), 0, 400),
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
  // Textos de la interfaz. Estos valores en español son el respaldo si
  // /config no responde; normalmente llegan del paquete de idioma del
  // servicio (campo `interfaz` de /config).
  var TEXTOS = {
    abrir: "Abrir chat de {titulo}",
    subtitulo: "Responde citando el documento",
    cerrar: "Cerrar chat",
    etiqueta_pregunta: "Escribe tu pregunta",
    placeholder: "Escribe tu pregunta...",
    enviar: "Enviar pregunta",
    no_directa: "No es una respuesta directa",
    esperando: "Buscando en el documento",
    error_limite: "Demasiadas preguntas seguidas. Espera unos segundos e intenta de nuevo.",
    error_origen: "Este sitio no está autorizado para usar el asistente.",
    error_http: "El servicio no pudo responder (HTTP {estado}).",
    error_red: "No se pudo contactar al asistente. Revisa tu conexión e intenta de nuevo.",
    error_servicio: "El asistente no está disponible en este momento. Intenta de nuevo más tarde.",
    invitacion_citas: "Puedes comprobarlo en la cita de abajo.",
    fuentes_una: "1 fuente del documento",
    fuentes_varias: "{n} fuentes del documento",
    posicion_cita: "caracteres {inicio}–{fin}",
    codigo_fuente: "Código fuente",
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
    ".rw-raiz[data-lanzador='oculto'] .rw-panel{top:auto;bottom:var(--rw-margen-y);}",
    ".rw-raiz[data-lanzador='oculto'][data-posicion^='arriba'] .rw-panel{bottom:auto;top:var(--rw-margen-y);}",
    ".rw-panel[hidden]{display:none;}",
    // Incrustado: el widget vive dentro de un contenedor del sitio, siempre abierto.
    ".rw-raiz[data-posicion='incrustado']{position:relative;inset:auto;z-index:auto;width:100%;height:100%;}",
    ".rw-raiz[data-posicion='incrustado'] .rw-boton{display:none;}",
    ".rw-raiz[data-posicion='incrustado'] .rw-panel{position:relative;inset:auto;width:100%;max-width:100%;",
    "  height:100%;min-height:420px;max-height:none;animation:none;box-shadow:none;}",
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
    "  to{opacity:1;transform:translateY(0) scale(1);}}",
    "@media (prefers-reduced-motion:reduce){",
    "  .rw-panel,.rw-msg,.rw-punto{animation:none;} .rw-boton,.rw-enviar{transition:none;}}",

    ".rw-cabecera{background:var(--rw-superficie);color:var(--rw-texto);",
    "  padding:14px var(--rw-relleno);display:flex;align-items:center;gap:11px;flex:none;",
    "  border-bottom:1px solid var(--rw-borde);}",
    ".rw-avatar{width:34px;height:34px;border-radius:50%;background:var(--rw-acento);",
    "  color:var(--rw-acento-texto);display:flex;align-items:center;justify-content:center;flex:none;}",
    ".rw-avatar svg{width:18px;height:18px;}",
    // Avatar animado (opcional): reemplaza al ícono solo cuando ya está montado.
    ".rw-avatar.rw-avatar-vivo{width:var(--rw-avatar-tamano,56px);height:var(--rw-avatar-tamano,56px);",
    "  background:transparent;border-radius:0;}",
    ".rw-avatar-lienzo{width:100%;height:100%;display:block;pointer-events:none;}",
    ".rw-avatar-lienzo svg{width:100%;height:100%;}",
    ".rw-boton.rw-con-avatar[aria-expanded='false'] .rw-icono-chat{display:none;}",
    ".rw-boton .rw-avatar-lienzo{width:84%;height:84%;}",
    ".rw-boton[aria-expanded='true'] .rw-avatar-lienzo{display:none;}",
    ".rw-avatar-esquina{position:absolute;right:18px;z-index:1;width:var(--rw-avatar-tamano,56px);",
    "  height:var(--rw-avatar-tamano,56px);pointer-events:none;}",
    ".rw-avatar-esquina[data-esquina='esquina-superior']{top:calc(var(--rw-avatar-tamano,56px) / -2);}",
    ".rw-avatar-esquina[data-esquina='esquina-inferior']{bottom:72px;}",
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
    ".rw-enviar:focus-visible{outline:3px solid var(--rw-acento);outline-offset:2px;}",
    ".rw-sr-solo{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);}",

    // Teléfono (o apaisado bajo): hoja a pantalla completa. La altura sigue al
    // viewport visible, así el teclado virtual no tapa el campo de texto.
    "@media (max-width:480px), (max-height:480px) and (orientation:landscape){",
    "  .rw-raiz:not([data-posicion='incrustado']){--rw-margen-x:16px;--rw-margen-y:16px;}",
    "  .rw-raiz:not([data-posicion='incrustado']) .rw-panel{position:fixed;left:0;right:0;",
    "    top:var(--rw-vv-arriba,0px);bottom:auto;width:100%;max-width:100%;",
    "    height:var(--rw-vv-alto,100dvh);max-height:none;border-radius:0;border:none;",
    "    padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom)",
    "      env(safe-area-inset-left);animation:rw-aparecer var(--rw-dur-panel) ease-out;}",
    "  .rw-msg{max-width:92%;}",
    "  .rw-raiz{--rw-avatar-tamano:40px !important;}",
    "  .rw-avatar-esquina[data-esquina='esquina-superior']{top:8px;right:56px;}",
    "  .rw-raiz.rw-teclado .rw-avatar.rw-avatar-vivo,.rw-raiz.rw-teclado .rw-avatar-esquina{display:none;}}",
    // Contraste alto del sistema (Windows): bordes visibles y el tramo marcado.
    "@media (forced-colors:active){",
    "  .rw-boton,.rw-enviar,.rw-cerrar{border:2px solid ButtonText;}",
    "  .rw-panel,.rw-msg,.rw-citas details,.rw-cita{border:1px solid CanvasText;}",
    "  .rw-tramo{forced-color-adjust:none;background:Mark;color:MarkText;}}",
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
  boton.setAttribute("aria-label", texto("abrir", { titulo: TITULO_INICIAL }));
  // Dos iconos fijos: el CSS muestra uno u otro segun aria-expanded, asi
  // el mismo boton abre y cierra sin que nada dependa de la API.
  boton.appendChild(icono("chat", "rw-icono-chat"));
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
  subtituloTexto.textContent = texto("subtitulo");
  subtitulo.appendChild(puntoVivo);
  subtitulo.appendChild(subtituloTexto);
  cabeceraTextos.appendChild(tituloEl);
  cabeceraTextos.appendChild(subtitulo);

  var botonCerrar = document.createElement("button");
  botonCerrar.type = "button";
  botonCerrar.className = "rw-cerrar";
  botonCerrar.setAttribute("aria-label", texto("cerrar"));
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
  etiquetaInput.textContent = texto("etiqueta_pregunta");
  var input = document.createElement("input");
  input.id = "rw-input";
  input.type = "text";
  input.autocomplete = "off";
  input.placeholder = texto("placeholder");
  var botonEnviar = document.createElement("button");
  botonEnviar.type = "submit";
  botonEnviar.className = "rw-enviar";
  botonEnviar.setAttribute("aria-label", texto("enviar"));
  botonEnviar.appendChild(icono("enviar"));
  input.addEventListener("input", function () { avatarAlTeclear(); });
  form.appendChild(etiquetaInput);
  form.appendChild(input);
  form.appendChild(botonEnviar);
  panel.appendChild(form);
  // AGPL §13: quien usa el servicio por red puede obtener su código fuente.
  var enlaceFuente = document.createElement("a");
  enlaceFuente.className = "rw-fuente";
  enlaceFuente.href = API_BASE + "/fuente";
  enlaceFuente.target = "_blank";
  enlaceFuente.rel = "noopener noreferrer";
  enlaceFuente.textContent = texto("codigo_fuente");
  panel.appendChild(enlaceFuente);

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
    relacionado: texto("no_directa"),
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
    invitacion.textContent = micro("invitacion_citas");
    caja.appendChild(invitacion);
    // Encabezado con el número de fuentes: deja ver de un vistazo que la
    // respuesta está respaldada, sin tener que desplegar nada.
    var titulo = document.createElement("p");
    titulo.className = "rw-citas-titulo";
    titulo.textContent = fragmentos.length === 1
      ? texto("fuentes_una") : texto("fuentes_varias", { n: fragmentos.length });
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
        posicion.textContent = " · " + texto("posicion_cita", { inicio: frag.offset_inicio, fin: frag.offset_fin });
        origen.appendChild(posicion);
      }
      cabeceraCita.appendChild(origen);
      var cuerpo = document.createElement("p");
      cuerpo.className = "rw-cita-texto";
      var rango = rangoExacto(frag, exacta);
      textoConTramo(cuerpo, frag.texto || "", rango);
      if (rango && !enLista) item.open = true;  // la cita con el tramo se ve sin desplegar
      item.appendChild(cabeceraCita);
      item.appendChild(cuerpo);
      caja.appendChild(item);
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
      agregarCitas(burbuja, respuesta.fragmentos, respuesta.respuesta_exacta);
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
    var esperando = micro("esperando");
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
    subtituloTexto.textContent = texto("subtitulo");
    botonCerrar.setAttribute("aria-label", texto("cerrar"));
    etiquetaInput.textContent = texto("etiqueta_pregunta");
    input.placeholder = texto("placeholder");
    botonEnviar.setAttribute("aria-label", texto("enviar"));
    ETIQUETAS_ESTADO.relacionado = texto("no_directa");
    enlaceFuente.textContent = texto("codigo_fuente");
  }

  function cargarConfigServidor() {
    fetch(API_BASE + "/config", { headers: cabecerasComunes() })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (cfg) {
        PRESENTACION.densidad = cfg.densidad === "compacta" ? "compacta" : "comoda";
        // Las citas nunca se ocultan: «abiertas» es el nombre anterior de «lista».
        PRESENTACION.citas = (cfg.citas === "lista" || cfg.citas === "abiertas") ? "lista" : "acordeon";
        PRESENTACION.mostrarEtiquetaEstado = cfg.mostrar_etiqueta_estado !== false;
        panel.setAttribute("data-densidad", PRESENTACION.densidad);
        if (cfg.preset) panel.setAttribute("data-preset", cfg.preset);
        aplicarInterfaz(cfg.interfaz);
        if (cfg.microcopia && typeof cfg.microcopia === "object") MICROCOPIA = cfg.microcopia;
        var u = cfg.ubicacion || {};
        Object.keys(DEL_SITIO).forEach(function (clave) {
          if (DEL_SITIO[clave] !== null || u[clave] === undefined || clave === "posicion") return;
          var valor = VALIDOS[clave] ? enLista(u[clave], clave) : entero(u[clave], 0, 2147483647);
          if (valor !== null) UBICACION[clave] = valor;
        });
        // La posición incrustada la decide el sitio (el elemento vive en su página).
        if (DEL_SITIO.posicion === null && !INCRUSTADO && enLista(u.posicion, "posicion") &&
            u.posicion !== "incrustado") {
          UBICACION.posicion = u.posicion;
        }
        aplicarUbicacion();
        configurarAvatar(cfg.avatar);
        if (cfg.nombre_asistente) {
          tituloEl.textContent = cfg.nombre_asistente;
          botonTexto.textContent = cfg.nombre_asistente;
          panel.setAttribute("aria-label", cfg.nombre_asistente);
          boton.setAttribute("aria-label", texto("abrir", { titulo: cfg.nombre_asistente }));
        }
        var bienvenida = (MICROCOPIA.bienvenida && MICROCOPIA.bienvenida.length) ? micro("bienvenida") : cfg.saludo;
        if (bienvenida && mensajes.children.length === 0) {
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
          throw new Error(micro("error_limite"));
        }
        if (r.status === 401 || r.status === 403) {
          throw new Error(texto("error_origen"));
        }
        if (r.status === 503) {
          throw new Error(micro("error_servicio"));
        }
        if (!r.ok) {
          throw new Error(texto("error_http", { estado: r.status }));
        }
        return r.json();
      })
      .then(function (respuesta) {
        agregarMensajeAsistente(respuesta);
        emitir("rag:respuesta", { estado: respuesta.estado, respuesta: respuesta });
        avatarAlResponder(respuesta.estado);
      })
      .catch(function (err) {
        // Los navegadores describen los fallos de transporte con textos
        // distintos ("Failed to fetch", "Load failed", etc.). Los errores
        // HTTP creados arriba sí son deliberados y se conservan; un TypeError
        // de fetch recibe un mensaje estable para quien usa el widget.
        var mensajeError = err instanceof TypeError
          ? micro("error_red")
          : (err && err.message ? err.message : micro("error_red"));
        agregarMensajeError(mensajeError);
        emitir("rag:error", { mensaje: mensajeError });
        avatarAlFallar();
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
    avatarAlEnviar();
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
    panel.hidden = false;
    boton.setAttribute("aria-expanded", "true");
    input.focus();
    document.addEventListener("keydown", manejarTeclado, true);
    cargarAvatar();
    ubicarAvatar();
    if (AVATAR.controlador) avatarAlAbrir();
    emitir("rag:abierto");
  }

  function cerrarPanel() {
    if (INCRUSTADO) return;
    panel.hidden = true;
    boton.setAttribute("aria-expanded", "false");
    document.removeEventListener("keydown", manejarTeclado, true);
    ubicarAvatar();
    if (AVATAR.controlador) avatarAlCerrar();
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
  if (INCRUSTADO) botonCerrar.hidden = true;

  // La configuración se pide al cargar: la ubicación de estilos.yaml aplica al
  // lanzador desde el principio, y el saludo ya está listo al abrir.
  // -------------------------------------------------------------------
  // 6. Avatar (opcional). El motor (/avatar.js, @bible-strong/avatar-web)
  //    se carga bajo demanda: al abrir el panel por primera vez o, si va en
  //    el lanzador, cuando el navegador está ocioso. Si algo falla (red,
  //    CSP sin 'unsafe-eval', definición inválida) queda el ícono y se emite
  //    rag:avatar con el error: el chat nunca se rompe.
  // -------------------------------------------------------------------
  var AVATAR = { config: null, promesa: null, controlador: null, definicion: null, lienzo: null };

  function urlDelServicio(ruta) {
    if (/^https?:\/\//.test(ruta)) return ruta;
    if (AVATAR_BASE) return new URL(AVATAR_BASE.replace(/\/?$/, "/") + ruta.replace(/^\//, ""), window.location.href).href;
    return API_BASE + ruta;
  }

  function configurarAvatar(cfg) {
    if (!cfg || typeof cfg !== "object" || !cfg.activo || !cfg.url_motor || !cfg.url_definicion) return;
    AVATAR.config = cfg;
    var tamano = entero(cfg.tamano, 32, 160);
    if (tamano !== null) contenedor.style.setProperty("--rw-avatar-tamano", tamano + "px");
    if (INCRUSTADO || !panel.hidden) {
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
      emitir("rag:avatar", { estado: "error", mensaje: String((error && error.message) || error) });
    });
    return AVATAR.promesa;
  }

  function montarAvatar(motor, definicion) {
    var lienzo = document.createElement("span");
    lienzo.className = "rw-avatar-lienzo";
    // Decorativo: los estados ya tienen texto y etiqueta propios.
    lienzo.setAttribute("aria-hidden", "true");
    var ajustes = AVATAR.config.mirada || {};
    if (ajustes.activa) {
      definicion = conMirada(definicion, Number(ajustes.amplitud_ojos) || 0, Number(ajustes.amplitud_cabeza) || 0);
    }
    AVATAR.definicion = definicion;
    var opciones = {
      definition: definicion,
      size: "100%",
      ariaLabel: "",
      onError: function (e) { emitir("rag:avatar", { estado: "error", mensaje: e.message }); }
    };
    var inicial = claveDe("inactivo");
    if (definicion.animations && definicion.animations[inicial]) opciones.defaultAnimation = inicial;
    // createAvatar valida la definición (y lanza si no es válida): recién
    // con el avatar montado se reemplaza el ícono.
    AVATAR.controlador = motor.createAvatar(lienzo, opciones);
    AVATAR.lienzo = lienzo;
    maquina.ultimoPersistente = inicial;
    ubicarAvatar();
    emitir("rag:avatar", { estado: "listo", nombre: AVATAR.config.nombre });
    reiniciarInactividad(false);
    if (INCRUSTADO || !panel.hidden) avatarAlAbrir();
  }

  // Lleva el lienzo a donde corresponde: el lanzador con el panel cerrado
  // (si en_lanzador), y la cabecera o una esquina del panel con él abierto.
  var esquinaAvatar = null;
  function ubicarAvatar() {
    var lienzo = AVATAR.lienzo, cfg = AVATAR.config;
    if (!lienzo || !cfg) return;
    var abierto = INCRUSTADO || !panel.hidden;
    var destino;
    if (!abierto) {
      if (!cfg.en_lanzador) return;
      destino = boton;
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
    var enCabecera = destino === avatar;
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
    error: 6, respuesta_ok: 5, respuesta_relacionada: 5, sin_respuesta: 5, conversacional: 5,
    enviado: 4, despertar: 3, saludo: 2, despedida: 2, lanzador: 1
  };
  var PERSISTENTES = {
    inactivo: 1, atento: 1, escribiendo: 1, pensando: 1, pensando_largo: 1, somnoliento: 1
  };
  var DURACION_MINIMA_MS = 600;
  var RETRASO_TECLEO_MS = 1200;
  var PENSANDO_LARGO_MS = 3000;
  var maquina = {
    persistente: "inactivo", transitorio: null, prioridad: 0, temporizador: null,
    tecleo: null, largo: null, inactividad: null, ultimoPersistente: null, saludado: false
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
    if (clave === maquina.ultimoPersistente) return;
    maquina.ultimoPersistente = clave;
    reproducir(clave);
    emitir("rag:avatar", { estado: "evento", evento: maquina.persistente, clave: clave });
  }

  function persistir(estado) {
    maquina.persistente = estado;
    if (estado !== "pensando" && estado !== "pensando_largo") {
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
    reproducir(clave);
    emitir("rag:avatar", { estado: "evento", evento: evento, clave: clave });
    maquina.temporizador = setTimeout(function () {
      maquina.transitorio = null;
      maquina.prioridad = 0;
      aplicarPersistente();
    }, duracionDe(clave));
  }

  // Punto único de entrada: lo usan el widget, el panel /admin y los sitios.
  function disparar(evento) {
    if (!AVATAR.controlador) return false;
    reiniciarInactividad(evento !== "somnoliento");
    if (PERSISTENTES[evento]) persistir(evento);
    else transitar(evento);
    return true;
  }

  // --- 6.2 Inactividad y visibilidad ------------------------------------
  function reiniciarInactividad(despertar) {
    clearTimeout(maquina.inactividad);
    if (despertar && maquina.persistente === "somnoliento") {
      maquina.persistente = (INCRUSTADO || !panel.hidden) ? "atento" : "inactivo";
      transitar("despertar");
    }
    var minutos = Number((AVATAR.config || {}).inactividad_min) || 2;
    maquina.inactividad = setTimeout(function () { persistir("somnoliento"); }, minutos * 60000);
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
    if (!maquina.saludado) {
      maquina.saludado = true;
      maquina.persistente = "atento";
      transitar("saludo");
    } else {
      persistir("atento");
    }
  }
  function avatarAlCerrar() {
    maquina.persistente = "inactivo";
    transitar("despedida");
  }
  function avatarAlTeclear() {
    if (!AVATAR.controlador) return;
    reiniciarInactividad(true);
    if (maquina.persistente !== "pensando" && maquina.persistente !== "pensando_largo") persistir("escribiendo");
    clearTimeout(maquina.tecleo);
    maquina.tecleo = setTimeout(function () {
      if (maquina.persistente === "escribiendo") persistir("atento");
    }, RETRASO_TECLEO_MS);
  }
  function avatarAlEnviar() {
    if (!AVATAR.controlador) return;
    clearTimeout(maquina.tecleo);
    maquina.persistente = "pensando";
    transitar("enviado");
    clearTimeout(maquina.largo);
    maquina.largo = setTimeout(function () {
      if (maquina.persistente === "pensando") persistir("pensando_largo");
    }, PENSANDO_LARGO_MS);
  }
  var EVENTO_DE_ESTADO = {
    ok: "respuesta_ok", relacionado: "respuesta_relacionada", sin_respuesta: "sin_respuesta",
    conversacional: "conversacional"
  };
  function avatarAlResponder(estado) {
    if (!AVATAR.controlador) return;
    maquina.persistente = "atento";
    clearTimeout(maquina.largo);
    transitar(EVENTO_DE_ESTADO[estado] || "respuesta_relacionada");
  }
  function avatarAlFallar() {
    if (!AVATAR.controlador) return;
    maquina.persistente = "atento";
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
    return maquina.persistente === "inactivo" || maquina.persistente === "atento";
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
    if (celda.col === mirada.col && celda.fila === mirada.fila) return;
    mirada.col = celda.col;
    mirada.fila = celda.fila;
    maquina.ultimoPersistente = null;
    AVATAR.controlador.setExpression(claveMirada(celda.col, celda.fila));
  }

  function volverAlCentro() {
    if (mirada.col === 2 && mirada.fila === 1) return;
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
    });
  }, { passive: true });

  cargarConfigServidor();

  // API del sitio (se supone un widget por página): abrir y cerrar desde un
  // botón propio (lanzador «oculto») o consultar el estado.
  window.RagChat = {
    abrir: abrirPanel,
    cerrar: cerrarPanel,
    // Avatar: disparar(evento) devuelve false si todavía no hay avatar montado.
    avatar: {
      disparar: disparar,
      estado: function () {
        return { listo: !!AVATAR.controlador, persistente: maquina.persistente, transitorio: maquina.transitorio,
                 mirada: AVATAR.controlador ? claveMirada(mirada.col, mirada.fila) : null };
      }
    },
    estado: function () {
      return {
        abierto: !panel.hidden,
        posicion: UBICACION.posicion,
        tamano: UBICACION.tamano,
        lanzador: UBICACION.lanzador,
        sesion: ID_SESION
      };
    }
  };
})();
