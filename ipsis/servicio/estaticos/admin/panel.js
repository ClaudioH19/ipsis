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

  // --- estado del proyecto y umbrales ----------------------------------
  function fila(dl, termino, valor) {
    dl.appendChild(elemento("dt", termino));
    dl.appendChild(elemento("dd", valor == null ? "-" : String(valor)));
  }
  function textoTarea(t) {
    if (!t || t.state === "idle") return "";
    if (t.state === "running") return textos.tareaCorriendo;
    if (t.state === "done") return textos.tareaLista;
    return textos.tareaError + " " + (t.message || "");
  }
  function pintarProyecto(d) {
    var dl = $("resumen-proyecto");
    vaciar(dl);
    fila(dl, textos.perfil, d.profile + " -- " + d.description);
    fila(dl, textos.indice, d.index.state + (d.index.chunks != null ? " (" + d.index.chunks + " " + textos.fragmentos + ")" : ""));
    fila(dl, textos.calibracion, d.calibration.state + (d.calibration.reason ? " -- " + d.calibration.reason : ""));
    fila(dl, d.ready ? textos.listo : textos.noListo, textoTarea(d.task));
    var cuerpo = $("tabla-umbrales");
    vaciar(cuerpo);
    d.thresholds.forEach(function (u) {
      var tr = elemento("tr");
      tr.appendChild(elemento("td", u.key));
      tr.appendChild(elemento("td", u.value == null ? "-" : String(u.value)));
      tr.appendChild(elemento("td", u.profile == null ? "-" : String(u.profile)));
      var td = elemento("td");
      var entrada = elemento("input", null, { type: "number", min: "0", max: "1", step: "0.01",
                                             "data-umbral": u.key, "aria-label": u.key });
      if (u.source !== "profile" && u.project != null) entrada.value = String(u.project);
      entrada.dataset.inicial = entrada.value;
      td.appendChild(entrada);
      tr.appendChild(td);
      tr.appendChild(elemento("td", textos["origen" + u.source.charAt(0).toUpperCase() + u.source.slice(1)] || u.source));
      cuerpo.appendChild(tr);
    });
    var lista = $("lista-doctor");
    vaciar(lista);
    d.doctor.forEach(function (c) {
      var li = elemento("li", "[" + c.level + "] " + c.name + ": " + c.message, { "class": "nivel-" + c.level });
      lista.appendChild(li);
    });
  }
  function cargarProyecto() {
    return api("GET", "/status").then(pintarProyecto, fallo);
  }
  // Mientras el motor se recarga (umbrales o reindexado), se consulta /task cada 2 s.
  function seguirTarea(alTerminar) {
    api("GET", "/task").then(function (r) {
      $("doc-tarea").textContent = textoTarea(r.task);
      if (r.task && r.task.state === "running") { setTimeout(function () { seguirTarea(alTerminar); }, 2000); return; }
      if (alTerminar) alTerminar();
    }, fallo);
  }
  $("actualizar-proyecto").addEventListener("click", cargarProyecto);
  $("pestana-proyecto").addEventListener("click", cargarProyecto);
  $("guardar-umbrales").addEventListener("click", function () {
    var cambios = {};
    Array.prototype.forEach.call(document.querySelectorAll("[data-umbral]"), function (e) {
      if (e.value === e.dataset.inicial) return;
      cambios[e.dataset.umbral] = e.value === "" ? null : Number(e.value);
    });
    if (!Object.keys(cambios).length) { avisar(textos.sinCambios); return; }
    mostrarErrores([]);
    api("PUT", "/thresholds", { thresholds: cambios }).then(function () {
      avisar(textos.guardado);
      seguirTarea(cargarProyecto);
    }, fallo);
  });

  // --- documentos -------------------------------------------------------
  function pintarDocumentos(lista) {
    var cuerpo = $("tabla-documentos");
    vaciar(cuerpo);
    lista.forEach(function (d) {
      var tr = elemento("tr");
      tr.appendChild(elemento("td", d.title || d.doc_id));
      tr.appendChild(elemento("td", d.file || "-"));
      tr.appendChild(elemento("td", d.active ? textos.si : textos.no));
      cuerpo.appendChild(tr);
    });
  }
  function cargarDocumentos() { return api("GET", "/documents").then(pintarDocumentos, fallo); }
  $("pestana-documentos").addEventListener("click", cargarDocumentos);
  function subirArchivo(archivo) {
    return fetch("/admin/documents?name=" + encodeURIComponent(archivo.name), {
      method: "POST", body: archivo,
      headers: { Authorization: "Bearer " + tokenEnMemoria, "Content-Type": "application/octet-stream" }
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (json) {
        if (r.ok) return json;
        var error = new Error("http " + r.status);
        error.errores = erroresDe(json);
        throw error;
      });
    });
  }
  $("doc-subir").addEventListener("click", function () {
    var archivos = Array.prototype.slice.call($("doc-archivo").files || []);
    if (!archivos.length) { avisar(textos.sinArchivo); return; }
    var lista = $("doc-resultados");
    vaciar(lista);
    mostrarErrores([]);
    archivos.reduce(function (p, archivo) {
      return p.then(function () {
        return subirArchivo(archivo).then(function (r) {
          var texto = r.rejected ? textos.rechazado + " " + r.rejected : (r.duplicate ? textos.duplicado : textos.subido);
          lista.appendChild(elemento("li", archivo.name + ": " + texto));
        }, function (e) { lista.appendChild(elemento("li", archivo.name + ": " + (e.errores || [String(e)]).join(" "))); });
      });
    }, Promise.resolve()).then(function () {
      avisar(textos.reindexarAviso);
      cargarDocumentos();
    });
  });
  $("doc-reindexar").addEventListener("click", function () {
    mostrarErrores([]);
    api("POST", "/reindex").then(function (r) {
      $("doc-tarea").textContent = textoTarea(r.task);
      seguirTarea(function () { cargarDocumentos(); recargarVista(); });
    }, fallo);
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
