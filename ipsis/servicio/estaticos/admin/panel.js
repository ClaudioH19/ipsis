/*
 * Panel /admin/panel. Sin innerHTML y sin textos propios: los mensajes vienen
 * del HTML (#textos, data-*) o del servicio. El token vive solo en
 * sessionStorage y viaja en Authorization: Bearer.
 */
(function () {
  "use strict";

  var CLAVE_TOKEN = "ipsis-admin-token";
  var $ = function (id) { return document.getElementById(id); };
  var textos = $("textos").dataset;
  var estado = { datos: null, estilos: null, situacion: null };

  // --- utilidades -------------------------------------------------------
  function leerToken() {
    try { return sessionStorage.getItem(CLAVE_TOKEN); } catch (e) { return null; }
  }
  function guardarToken(valor) {
    try {
      if (valor) sessionStorage.setItem(CLAVE_TOKEN, valor);
      else sessionStorage.removeItem(CLAVE_TOKEN);
    } catch (e) { /* sin almacenamiento: el token dura lo que la página */ }
  }
  var tokenEnMemoria = leerToken();

  function vaciar(nodo) { while (nodo.firstChild) nodo.removeChild(nodo.firstChild); }
  function elemento(etiqueta, texto, atributos) {
    var n = document.createElement(etiqueta);
    if (texto != null) n.textContent = texto;
    Object.keys(atributos || {}).forEach(function (k) { n.setAttribute(k, atributos[k]); });
    return n;
  }
  function opciones(select, valores, actual) {
    vaciar(select);
    valores.forEach(function (v) {
      var o = elemento("option", v.texto != null ? v.texto : v, { value: v.valor != null ? v.valor : v });
      select.appendChild(o);
    });
    if (actual != null) select.value = actual;
  }
  function avisar(texto) { $("estado").textContent = texto || ""; }
  function mostrarErrores(lista) {
    var caja = $("errores");
    vaciar(caja);
    if (!lista || !lista.length) return;
    var ul = elemento("ul");
    lista.forEach(function (e) { ul.appendChild(elemento("li", e)); });
    caja.appendChild(ul);
  }

  function erroresDe(cuerpo) {
    var d = cuerpo && cuerpo.detail;
    if (d && d.errors) return d.errors;
    if (typeof d === "string") return [d];
    if (Array.isArray(d)) return d.map(function (x) { return x.msg || JSON.stringify(x); });
    return [JSON.stringify(cuerpo)];
  }

  // Petición a /admin; rechaza con la lista de errores del servicio.
  function api(metodo, ruta, cuerpo) {
    var opciones = { method: metodo, headers: { Authorization: "Bearer " + tokenEnMemoria } };
    if (cuerpo !== undefined) {
      opciones.headers["Content-Type"] = "application/json";
      opciones.body = JSON.stringify(cuerpo);
    }
    return fetch("/admin" + ruta, opciones).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (json) {
        if (r.ok) return json;
        // Con la sesión abierta, un 401 significa que el token cambió. Al entrar,
        // el error del servicio ya lo muestra entrar().
        if (r.status === 401 && !$("contenido").hidden) salir(textos.sinSesion);
        var error = new Error("http " + r.status);
        error.errores = erroresDe(json);
        error.status = r.status;
        throw error;
      });
    }, function () {
      var error = new Error("red");
      error.errores = [textos.errorRed];
      throw error;
    });
  }
  function fallo(error) { mostrarErrores(error.errores || [String(error)]); avisar(""); }

  // --- acceso -----------------------------------------------------------
  function salir(motivo) {
    tokenEnMemoria = null;
    guardarToken(null);
    $("contenido").hidden = true;
    $("acceso").hidden = false;
    $("vista-previa").src = "about:blank";
    $("error-acceso").textContent = motivo || "";
  }

  function entrar(token) {
    tokenEnMemoria = token;
    $("error-acceso").textContent = "";
    avisar(textos.cargando);
    return cargarTodo().then(function () {
      guardarToken(token);
      $("acceso").hidden = true;
      $("contenido").hidden = false;
      recargarVista();
      avisar("");
    }, function (error) {
      tokenEnMemoria = null;
      guardarToken(null);
      $("error-acceso").textContent = (error.errores || [String(error)]).join(" ");
    });
  }

  $("form-acceso").addEventListener("submit", function (ev) {
    ev.preventDefault();
    entrar($("token").value.trim());
    $("token").value = "";
  });
  $("salir").addEventListener("click", function () { salir(""); });

  // --- pestañas -------------------------------------------------------
  var pestanas = Array.prototype.slice.call(document.querySelectorAll("[role=tab]"));
  pestanas.forEach(function (p) {
    p.addEventListener("click", function () {
      pestanas.forEach(function (otra) {
        var activa = otra === p;
        otra.setAttribute("aria-selected", String(activa));
        $(otra.getAttribute("aria-controls")).hidden = !activa;
      });
    });
  });

  // --- carga ------------------------------------------------------------
  function cargarTodo() {
    return Promise.all([api("GET", "/personality"), api("GET", "/styles"), api("GET", "/styles/presets"),
                        api("GET", "/styles/flat")])
      .then(function (r) {
        estado.datos = r[0];
        estado.estilos = r[1];
        pintarAvatar();
        pintarWidget(r[2]);
        pintarEstilo(r[3]);
        mostrarErrores([]);
        return pintarTono();
      });
  }
  function recargarDatos() {
    return Promise.all([api("GET", "/personality"), api("GET", "/styles"), api("GET", "/styles/flat")])
      .then(function (r) {
        estado.datos = r[0];
        estado.estilos = r[1];
        pintarAvatar();
        pintarWidget(null);
        pintarEstilo(r[2]);
        return pintarTono();
      });
  }

  function guardado(texto) {
    mostrarErrores([]);
    return recargarDatos().then(function () {
      recargarVista();
      avisar(texto || textos.guardado);
    });
  }

  // --- vista previa -----------------------------------------------------
  var vista = $("vista-previa");
  function recargarVista() {
    vista.setAttribute("data-lista", "false");
    vista.src = "/admin/panel/vista-previa.html?v=" + Date.now();
  }
  vista.addEventListener("load", function () {
    if (vista.src === "about:blank") return;
    var chat = vista.contentWindow && vista.contentWindow.Ipsis;
    if (chat && chat.open) chat.open();
    vista.setAttribute("data-lista", "true");
  });

  // --- tono -------------------------------------------------------------
  function pintarTono() {
    var d = estado.datos, tono = d.config.tone;
    opciones($("tono-activo"), d.tones.map(function (t) { return t.tone; }), tono.active);
    var actual = d.tones.filter(function (t) { return t.tone === tono.active; })[0];
    $("tono-descripcion").textContent = actual ? actual.description : "";
    // Textos propios no neutros: aviso, no error (se guardan igual).
    var avisos = $("tono-avisos");
    vaciar(avisos);
    (d.tone_warnings || []).forEach(function (texto) { avisos.appendChild(elemento("li", texto)); });
    Array.prototype.forEach.call(document.getElementsByName("variedad"), function (r) {
      r.checked = r.value === tono.variety;
    });
    var situaciones = Object.keys(d.situations);
    if (!estado.situacion || situaciones.indexOf(estado.situacion) < 0) estado.situacion = situaciones[0];
    opciones($("situacion"), situaciones, estado.situacion);
    pintarPropias();
    return pintarVariantes($("tono-activo").value);
  }

  function pintarPropias() {
    var propias = (estado.datos.config.tone.templates || {})[estado.situacion];
    if (typeof propias === "string") propias = [propias];
    $("propias").value = (propias || []).join("\n");
  }

  function pintarVariantes(tono) {
    return api("POST", "/personality/preview", { tone: tono, situation: estado.situacion })
      .then(function (r) {
        var lista = $("variantes");
        vaciar(lista);
        (r[estado.situacion] || []).forEach(function (v) { lista.appendChild(elemento("li", v)); });
      }, fallo);
  }

  $("tono-activo").addEventListener("change", function () {
    var tono = $("tono-activo").value;
    api("PUT", "/personality", { tone: { active: tono } }).then(function () { return guardado(); }, fallo);
  });
  Array.prototype.forEach.call(document.getElementsByName("variedad"), function (r) {
    r.addEventListener("change", function () {
      api("PUT", "/personality", { tone: { variety: r.value } }).then(function () { return guardado(); }, fallo);
    });
  });
  $("situacion").addEventListener("change", function () {
    estado.situacion = $("situacion").value;
    pintarPropias();
    pintarVariantes($("tono-activo").value);
  });

  function guardarPlantillas(nuevas) {
    // templates se reemplaza completo: se envía el mapa entero.
    api("PUT", "/personality", { tone: { templates: nuevas } }).then(function () { return guardado(); }, fallo);
  }
  $("guardar-propias").addEventListener("click", function () {
    var lineas = $("propias").value.split("\n").map(function (l) { return l.trim(); })
      .filter(function (l) { return l; });
    var nuevas = Object.assign({}, estado.datos.config.tone.templates);
    if (lineas.length) nuevas[estado.situacion] = lineas; else delete nuevas[estado.situacion];
    guardarPlantillas(nuevas);
  });
  $("quitar-propias").addEventListener("click", function () {
    var nuevas = Object.assign({}, estado.datos.config.tone.templates);
    delete nuevas[estado.situacion];
    guardarPlantillas(nuevas);
  });

  // --- avatar -----------------------------------------------------------
  function clavesDe(nombre) {
    var a = estado.datos.avatars.filter(function (x) { return x.name === nombre; })[0];
    if (!a || a.error) return [];
    return a.animations.concat(a.expressions.filter(function (e) { return a.animations.indexOf(e) < 0; }));
  }

  function pintarAvatar() {
    var d = estado.datos, a = d.config.avatar, colores = a.colors || {};
    $("avatar-estado").textContent = d.avatar.message || d.avatar.state || "";
    var nombres = d.avatars.map(function (x) { return x.name; });
    if (nombres.indexOf(a.definition) < 0) nombres.unshift(a.definition);
    opciones($("avatar-activo-sel"), nombres, a.definition);
    $("color-cuerpo").value = colores.body || "#f5f1e8";
    $("color-ojos").value = colores.eyes || "#1e293b";
    $("avatar-ubicacion").value = a.placement;
    $("avatar-tamano").value = a.size;
    $("avatar-lanzador").checked = !!a.in_launcher;
    $("avatar-mirada").checked = !!(a.gaze && a.gaze.enabled);
    pintarEventos();
  }

  function pintarEventos() {
    var d = estado.datos, a = d.config.avatar, cuerpo = $("tabla-eventos");
    var claves = clavesDe(a.definition);
    vaciar(cuerpo);
    Object.keys(d.events).forEach(function (evento) {
      var fila = elemento("tr", null, { "data-evento": evento });
      fila.appendChild(elemento("th", evento, { scope: "row" }));
      var celda = elemento("td");
      var sel = elemento("select", null, { "aria-label": evento });
      var sugerida = d.events[evento].suggested;
      var lista = [{ valor: "", texto: sugerida + " " + textos.sugerida }].concat(
        claves.map(function (k) { return { valor: k, texto: k }; }));
      var propia = (a.events || {})[evento];
      if (propia && claves.indexOf(propia) < 0) lista.push({ valor: propia, texto: propia });
      opciones(sel, lista, propia || "");
      sel.addEventListener("change", function () { asignarEvento(evento, sel.value); });
      celda.appendChild(sel);
      fila.appendChild(celda);
      var probar = elemento("td");
      var boton = elemento("button", "▶", { type: "button", "aria-label": evento, "data-probar": evento });
      boton.addEventListener("click", function () { disparar(evento); });
      probar.appendChild(boton);
      fila.appendChild(probar);
      cuerpo.appendChild(fila);
    });
  }

  function asignarEvento(evento, clave) {
    var eventos = Object.assign({}, estado.datos.config.avatar.events);
    if (clave) eventos[evento] = clave; else delete eventos[evento];
    api("PUT", "/personality", { avatar: { events: eventos } }).then(function () { return guardado(); }, fallo);
  }

  function disparar(evento) {
    var chat = vista.contentWindow && vista.contentWindow.Ipsis;
    if (chat && chat.avatar && typeof chat.avatar.trigger === "function") {
      chat.avatar.trigger(evento);
      avisar(textos.disparado + " " + evento);
    } else {
      avisar(textos.sinAvatar);
    }
  }

  $("avatar-activo-sel").addEventListener("change", function () {
    api("PUT", "/personality", { avatar: { definition: $("avatar-activo-sel").value } })
      .then(function () { return guardado(); }, fallo);
  });
  $("guardar-colores").addEventListener("click", function () {
    api("PUT", "/personality", { avatar: { colors: { body: $("color-cuerpo").value, eyes: $("color-ojos").value } } })
      .then(function () { return guardado(); }, fallo);
  });
  $("guardar-avatar").addEventListener("click", function () {
    api("PUT", "/personality", { avatar: {
      placement: $("avatar-ubicacion").value,
      size: parseInt($("avatar-tamano").value, 10),
      in_launcher: $("avatar-lanzador").checked,
      gaze: { enabled: $("avatar-mirada").checked }
    } }).then(function () { return guardado(); }, fallo);
  });

  $("avatar-archivo").addEventListener("change", function () {
    var archivo = $("avatar-archivo").files[0];
    if (archivo && !$("avatar-nombre").value) {
      $("avatar-nombre").value = archivo.name.replace(/\.avatar\.json$|\.json$/i, "").toLowerCase()
        .replace(/[^a-z0-9]+/g, "-").replace(/^[^a-z]+|-+$/g, "");
    }
  });
  $("avatar-importar").addEventListener("click", function () {
    var archivo = $("avatar-archivo").files[0], nombre = $("avatar-nombre").value.trim();
    if (!archivo || !nombre) { mostrarErrores([textos.sinArchivo]); return; }
    var lector = new FileReader();
    lector.onload = function () {
      var definicion;
      try {
        definicion = JSON.parse(String(lector.result));
      } catch (e) {
        mostrarErrores([textos.jsonInvalido + " " + e.message]);
        return;
      }
      api("POST", "/avatars", { name: nombre, definition: definicion })
        .then(function (r) { return guardado(textos.importado + " " + r.name); }, fallo);
    };
    lector.readAsText(archivo);
  });

  // --- widget -----------------------------------------------------------
  function pintarWidget(presets) {
    var e = estado.estilos, u = e.placement || {}, p = e.presentation || {};
    if (presets) {
      opciones($("preset"), Object.keys(presets).map(function (k) {
        return { valor: k, texto: k + " — " + presets[k] };
      }), e.preset);
    } else if (e.preset) {
      $("preset").value = e.preset;
    }
    $("color-acento").value = (e.colors && e.colors.accent) || "#2563eb";
    if (u.position) $("posicion").value = u.position;
    if (u.size) $("tamano").value = u.size;
    if (u.launcher) $("lanzador").value = u.launcher;
    if (p.citations) $("citas").value = p.citations;
  }

  $("aplicar-preset").addEventListener("click", function () {
    api("POST", "/styles/preset", { name: $("preset").value })
      .then(function () { return guardado(textos.preset); }, fallo);
  });
  $("guardar-widget").addEventListener("click", function () {
    api("PUT", "/styles", {
      colors: { accent: $("color-acento").value },
      placement: { position: $("posicion").value, size: $("tamano").value, launcher: $("lanzador").value },
      presentation: { citations: $("citas").value }
    }).then(function () { return guardado(); }, fallo);
  });

  // --- estilo completo: un campo por cada «seccion.clave» de styles.yaml ----
  var HEX = /^#[0-9a-fA-F]{6}$/;
  var originales = {};

  function pintarEstilo(campos) {
    var caja = $("campos-estilo");
    vaciar(caja);
    originales = {};
    var seccionActual = null;
    campos.forEach(function (campo) {
      var seccion = campo.key.split(".")[0];
      if (seccion !== seccionActual) {
        caja.appendChild(elemento("h4", seccion));
        seccionActual = seccion;
      }
      var valor = campo.value;
      var etiqueta = elemento("label", campo.key.split(".")[1] + " ");
      var entrada = elemento("input", null, { "data-clave": campo.key });
      if (typeof valor === "boolean") {
        entrada.type = "checkbox";
        entrada.checked = valor;
        originales[campo.key] = String(valor);
      } else if (typeof valor === "string" && HEX.test(valor)) {
        entrada.type = "color";
        entrada.value = valor.toLowerCase();
        originales[campo.key] = entrada.value;
      } else {
        entrada.type = "text";
        entrada.value = String(valor);
        originales[campo.key] = entrada.value;
      }
      etiqueta.appendChild(entrada);
      caja.appendChild(etiqueta);
    });
  }

  $("guardar-estilo").addEventListener("click", function () {
    var asignaciones = [];
    Array.prototype.forEach.call($("campos-estilo").querySelectorAll("input[data-clave]"), function (entrada) {
      var clave = entrada.getAttribute("data-clave");
      var valor = entrada.type === "checkbox" ? String(entrada.checked) : entrada.value;
      if (valor !== originales[clave]) asignaciones.push(clave + "=" + valor);
    });
    if (!asignaciones.length) { avisar(textos.sinCambios); return; }
    api("POST", "/styles/set", { assignments: asignaciones }).then(function () { return guardado(); }, fallo);
  });

  // --- arranque ---------------------------------------------------------
  if (tokenEnMemoria) entrar(tokenEnMemoria);
})();
