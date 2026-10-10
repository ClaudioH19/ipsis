// Folio conserva el dibujo del logo y usa el mismo motor de gestos que los
// avatares procedurales. Todas las piezas se mueven juntas sobre la hoja.
import {
  advanceAvatarPlayback, applyAmbientMotion, createAvatarPlaybackState,
  pauseAvatarPlayback, playAvatarAnimation, quaternionFromEuler, radians,
  resolveAnimation, resolveExpression, resumeAvatarPlayback,
  rotateWithQuaternion, sampleAvatarFrame, validateAvatarDefinition,
} from "@bible-strong/avatar-core";
import { FLOTACION, MOVIMIENTOS, movimientoFolio } from "./movimiento-folio.js";
import { contornoRedondo, elegirVuelo } from "./avion-folio.js";
import { crearAutonomia } from "./autonomia-folio.js";

const NS = "http://www.w3.org/2000/svg";
const PAPEL = "M-27 -46h48l18 18v62a12 12 0 0 1-12 12h-54a12 12 0 0 1-12-12v-68a12 12 0 0 1 12-12z";
const PLIEGUE = "M21 -46v12a6 6 0 0 0 6 6h12z";
const ESCALA_OJOS = 196 / 78;
let siguienteId = 0;

function elemento(tipo, atributos = {}) {
  const nodo = document.createElementNS(NS, tipo);
  for (const [clave, valor] of Object.entries(atributos)) nodo.setAttribute(clave, String(valor));
  return nodo;
}

function color(nodo, propiedad, nombre, respaldo) {
  nodo.style[propiedad] = `var(--rw-folio-${nombre},${respaldo})`;
}

export function createFolioAvatar(target, {
  definition: input, defaultAnimation, defaultExpression, autoplay = true,
  size = 240, ariaLabel = "Folio", className, onError, onAnimationEnd, onExpressionChange,
  autonomy = false,
}) {
  if (defaultAnimation !== undefined && defaultExpression !== undefined) {
    throw new Error("Choose either defaultAnimation or defaultExpression, not both.");
  }
  const validacion = validateAvatarDefinition(input);
  if (!validacion.ok) {
    const error = validacion.errors[0];
    throw new Error(`Invalid avatar definition at ${error.path}: ${error.message}`);
  }
  const definicion = validacion.value;
  const destino = typeof target === "string" ? document.querySelector(target) : target;
  if (!destino) throw new Error(`Avatar target '${target}' was not found.`);

  const contenedor = document.createElement("span");
  contenedor.className = ["bs-avatar", "bs-avatar-folio", className].filter(Boolean).join(" ");
  const tamano = typeof size === "number" ? `${size}px` : size;
  Object.assign(contenedor.style, { display: "inline-block", width: tamano, height: tamano });
  contenedor.setAttribute("role", "img");
  contenedor.setAttribute("aria-label", ariaLabel);
  const svg = elemento("svg", { viewBox: "-64 -64 128 128", "aria-hidden": "true" });
  Object.assign(svg.style, { display: "block", width: "100%", height: "100%" });
  const id = `ipsis-folio-${++siguienteId}`;
  const defs = elemento("defs");
  const clip = elemento("clipPath", { id });
  clip.append(elemento("path", { d: PAPEL }));
  defs.append(clip);
  const hoja = elemento("g", { "data-folio": "hoja" });
  const movimiento = elemento("g", { "data-folio": "movimiento" });
  const cara = elemento("g", { "data-folio": "cara" });
  const avion = elemento("g", { "data-folio": "avion", opacity: 0 });
  const alas = Array.from({ length: 4 }, (_, i) => elemento("path", {
    "data-folio": `ala-${i}`, "stroke-width": 1.25, "stroke-linejoin": "round",
  }));
  for (const ala of alas) color(ala, "stroke", "borde", "#d6cdb8");
  color(alas[2], "fill", "pliegue", "#e4dac4");
  color(alas[3], "fill", "resalte", "#93c5fd");
  avion.append(...alas);
  const estela = elemento("g", { "data-folio": "estela", opacity: 0 });
  const rafagas = Array.from({ length: 3 }, (_, i) => elemento("path", {
    "data-folio": `rafaga-${i}`, fill: "none", "stroke-width": 1.4, "stroke-linecap": "round",
  }));
  for (const rafaga of rafagas) color(rafaga, "stroke", "resalte", "#93c5fd");
  estela.append(...rafagas);
  const papel = elemento("path", {
    d: PAPEL, "data-folio": "papel", "stroke-width": 2.5, "stroke-linejoin": "round",
  });
  const pliegue = elemento("path", {
    d: PLIEGUE, "data-folio": "pliegue", "stroke-width": 2.5, "stroke-linejoin": "round",
  });
  color(papel, "stroke", "borde", "#d6cdb8");
  color(pliegue, "stroke", "borde", "#d6cdb8");
  color(pliegue, "fill", "pliegue", "#e4dac4");
  const ojos = elemento("g", { "clip-path": `url(#${id})` });
  const rostro = elemento("g", { "data-folio": "rostro" });
  const izquierdo = elemento("rect", { "data-folio": "ojo-izquierdo" });
  const derecho = elemento("rect", { "data-folio": "ojo-derecho" });
  ojos.append(izquierdo, derecho);
  rostro.append(ojos);
  const renglon = elemento("rect", { x: -25, y: 14, width: 52, height: 5, rx: 2.5 });
  const resalte = elemento("rect", { x: -25, y: 25, width: 34, height: 9, rx: 4.5, "data-folio": "resalte" });
  const final = elemento("rect", { x: 13, y: 27, width: 14, height: 5, rx: 2.5 });
  color(renglon, "fill", "renglon", "#cbd5e1");
  color(resalte, "fill", "resalte", "#93c5fd");
  color(final, "fill", "renglon", "#cbd5e1");
  cara.append(pliegue, renglon, resalte, final);
  hoja.append(papel, cara);
  movimiento.append(estela, hoja, avion, rostro);
  svg.append(defs, movimiento);
  contenedor.append(svg);
  destino.append(contenedor);

  let estado = createAvatarPlaybackState();
  let frame;
  let raf = null;
  let destruido = false;
  let ultimaExpresion;
  let desplazamiento = null;
  let autonomiaActiva = autonomy;
  let pausaAutonomia = null;
  let reaccionActual = null;
  let expresionVisible = null;
  const poses = Object.fromEntries(Object.keys(definicion.expressions).map(clave => [clave,
    sampleAvatarFrame(definicion, { ...createAvatarPlaybackState(), activeExpression: clave }, 0,
      { reduceMotion: true }).expression]));
  const autonomia = crearAutonomia(definicion, poses);
  const entorno = () => ({
    random: Math.random,
    reduceMotion: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  });

  function dibujarOjo(nodo, expr, lado, parpadeo) {
    const ancho = expr[`width${lado}`] / ESCALA_OJOS;
    const alto = expr[`height${lado}`] * parpadeo / ESCALA_OJOS;
    const signo = lado === "Left" ? -1 : 1;
    const x = (signo * expr.spacing / 2 + expr[`positionX${lado}`]) / ESCALA_OJOS;
    const y = expr[`positionY${lado}`] / ESCALA_OJOS;
    nodo.setAttribute("x", String(-ancho / 2));
    nodo.setAttribute("y", String(-alto / 2));
    nodo.setAttribute("width", String(ancho));
    nodo.setAttribute("height", String(alto));
    nodo.setAttribute("rx", String(Math.min(ancho, alto) / 2));
    nodo.setAttribute("transform", `translate(${x} ${y}) rotate(${expr[lado === "Left" ? "leftAngle" : "rightAngle"]})`);
  }

  function dibujar(now) {
    const ambiente = entorno();
    frame = sampleAvatarFrame(definicion, estado, now, ambiente);
    const reaccion = (autonomiaActiva || autonomia.tieneInteraccion()) && !ambiente.reduceMotion && !document.hidden
      ? autonomia.muestrear(pausaAutonomia ?? now, frame, autonomiaActiva) : null;
    reaccionActual = reaccion?.clave ?? null;
    contenedor.dataset.reaccion = reaccionActual ?? "";
    const expresion = reaccion?.expression ?? frame.expression;
    expresionVisible = expresion;
    const expr = ambiente.reduceMotion ? expresion : applyAmbientMotion(expresion, frame.sampledAt);
    const orientacion = quaternionFromEuler(radians(expr.headX), radians(expr.headY), radians(expr.headZ));
    const ejeX = rotateWithQuaternion(orientacion, [1, 0, 0]);
    const ejeY = rotateWithQuaternion(orientacion, [0, 1, 0]);
    hoja.setAttribute("transform", `matrix(${ejeX[0]} ${ejeX[1]} ${ejeY[0]} ${ejeY[1]} 0 0)`);
    let progreso = 0;
    if (desplazamiento && !ambiente.reduceMotion) {
      const reloj = desplazamiento.pausado ?? now;
      const transcurrido = Math.max(0, reloj - desplazamiento.inicio);
      progreso = desplazamiento.bucle
        ? (transcurrido % desplazamiento.duracion) / desplazamiento.duracion
        : Math.min(1, transcurrido / desplazamiento.duracion);
    }
    const mov = movimientoFolio(ambiente.reduceMotion ? null : desplazamiento?.clave, progreso, desplazamiento?.vuelo);
    mov.x += reaccion?.x ?? 0;
    mov.y += reaccion?.y ?? 0;
    mov.giro += reaccion?.giro ?? 0;
    mov.escalaX *= reaccion?.escalaX ?? 1;
    mov.escalaY *= reaccion?.escalaY ?? 1;
    mov.frente = mov.frente && (reaccion?.frente ?? true);
    mov.avion = reaccion?.avion ?? mov.avion;
    movimiento.setAttribute("transform", `translate(${mov.x} ${mov.y}) rotate(${mov.giro}) scale(${mov.escalaX} ${mov.escalaY})`);
    hoja.setAttribute("opacity", String(mov.avion?.hoja ?? 1));
    avion.setAttribute("opacity", String(mov.avion?.origami ?? 0));
    const vuelo = mov.avion;
    const transformacionAvion = vuelo
      ? `translate(${vuelo.x} ${vuelo.y}) rotate(${vuelo.giro}) scale(${vuelo.escala}) ${hoja.getAttribute("transform")}`
      : hoja.getAttribute("transform");
    avion.setAttribute("transform", transformacionAvion);
    // Una sola pareja de ojos: no se funde ni desaparece con la hoja. Al
    // volver del vuelo se interpola su posición hacia la cara de Folio.
    const pesoAvion = vuelo ? vuelo.origami / Math.max(0.0001, vuelo.origami + vuelo.hoja) : 0;
    const gesto = vuelo?.rostro;
    const escalaVuelo = 1 + ((vuelo?.escala ?? 1) - 1) * pesoAvion;
    const escalaOjos = 1 + ((gesto?.escala ?? 1) - 1) * pesoAvion;
    rostro.setAttribute("transform", `translate(${(vuelo?.x ?? 0) * pesoAvion} ${(vuelo?.y ?? 0) * pesoAvion}) rotate(${(vuelo?.giro ?? 0) * pesoAvion}) scale(${escalaVuelo}) ${hoja.getAttribute("transform")} translate(${(gesto?.x ?? 0) * pesoAvion} ${(gesto?.y ?? 0) * pesoAvion}) rotate(${(gesto?.giro ?? 0) * pesoAvion}) scale(${escalaOjos})`);
    rostro.setAttribute("opacity", String(mov.frente ? Math.min(1, vuelo ? vuelo.hoja + vuelo.origami : 1) : 0));
    estela.setAttribute("transform", vuelo ? `translate(${vuelo.x} ${vuelo.y}) rotate(${vuelo.giro}) scale(${vuelo.escala})` : "");
    estela.setAttribute("opacity", String((mov.avion?.estela ?? 0) * 0.5));
    if (mov.avion) {
      avion.dataset.sentido = String(vuelo.sentido);
      vuelo.paneles.forEach((puntos, i) => alas[i].setAttribute("d", contornoRedondo(puntos)));
      vuelo.rafagas.forEach((r, i) => {
        rafagas[i].setAttribute("d", r.d);
        rafagas[i].setAttribute("opacity", String(r.opacidad));
        rafagas[i].setAttribute("stroke-dasharray", `${r.longitud} 20`);
        rafagas[i].setAttribute("stroke-dashoffset", String(r.avance));
      });
    }
    color(alas[0], "fill", "papel", frame.colors.body);
    color(alas[1], "fill", "papel", frame.colors.body);
    cara.setAttribute("opacity", mov.frente ? "1" : "0");
    color(papel, "fill", "papel", frame.colors.body);
    color(izquierdo, "fill", "tinta", frame.colors.eyes);
    color(derecho, "fill", "tinta", frame.colors.eyes);
    const parpadeo = ambiente.reduceMotion ? 1 : reaccion?.blink ?? frame.blink;
    dibujarOjo(izquierdo, expr, "Left", parpadeo);
    dibujarOjo(derecho, expr, "Right", parpadeo);
    if (ultimaExpresion !== estado.activeExpression) {
      ultimaExpresion = estado.activeExpression;
      onExpressionChange?.(ultimaExpresion);
    }
  }

  function siguiente(now) {
    raf = null;
    if (destruido) return;
    const animacion = estado.activeAnimation;
    const estabaReproduciendo = estado.status === "playing";
    estado = advanceAvatarPlayback(definicion, estado, now, entorno());
    dibujar(now);
    if (estabaReproduciendo && estado.status === "stopped" && animacion) onAnimationEnd?.(animacion);
    if (debeAnimar()) programar();
  }

  function debeAnimar() {
    return !document.hidden && pausaAutonomia === null && (estado.status === "playing"
      || autonomiaActiva || autonomia.tieneInteraccion() || (desplazamiento?.bucle && !entorno().reduceMotion));
  }

  function programar() {
    if (raf === null && !destruido) raf = requestAnimationFrame(siguiente);
  }

  function cancelar() {
    if (raf !== null) cancelAnimationFrame(raf);
    raf = null;
  }

  const controlador = {
    play(clave) {
      const now = performance.now();
      if (estado.status === "paused" && estado.activeAnimation === clave) {
        if (pausaAutonomia !== null) autonomia.reanudar(now - pausaAutonomia);
        estado = resumeAvatarPlayback(estado, now);
        if (desplazamiento?.pausado !== undefined) {
          desplazamiento.inicio += now - desplazamiento.pausado;
          delete desplazamiento.pausado;
        }
      } else {
        const resultado = playAvatarAnimation(definicion, clave, now, frame);
        if (!resultado.ok) return { ok: false, error: resultado.error };
        estado = resultado.value;
        autonomia.reiniciar();
        const animacion = definicion.animations[clave];
        const flotando = FLOTACION.has(clave) && animacion.playbackMode === "loop";
        const anterior = flotando && FLOTACION.has(desplazamiento?.clave) && desplazamiento.bucle
          ? desplazamiento : null;
        // La flotación mantiene su fase al mirar y volver a estar atento.
        const duracion = flotando ? 4000
          : animacion.steps.reduce((total, paso) => total + paso.holdMs + paso.transitionMs, 0);
        desplazamiento = MOVIMIENTOS.has(clave) && duracion > 0
          ? { clave, inicio: anterior ? anterior.inicio + now - (anterior.pausado ?? now) : now,
              duracion, bucle: animacion.playbackMode === "loop",
              ...(clave.startsWith("paper-plane-") ? { vuelo: elegirVuelo() } : {}) }
          : null;
      }
      pausaAutonomia = null;
      dibujar(now);
      programar();
      return { ok: true };
    },
    setExpression(clave) {
      const resultado = resolveExpression(definicion, clave);
      if (!resultado.ok) return { ok: false, error: resultado.error };
      const now = performance.now();
      pausaAutonomia = null;
      autonomia.reiniciar();
      if (!(clave.startsWith("mirada-") && FLOTACION.has(desplazamiento?.clave) && desplazamiento.bucle)) {
        desplazamiento = null;
      } else if (desplazamiento.pausado !== undefined) {
        desplazamiento.inicio += now - desplazamiento.pausado;
        delete desplazamiento.pausado;
      }
      estado = {
        ...createAvatarPlaybackState(), activeExpression: clave,
        ...(estado.activeExpression === clave ? {} : {
          status: "playing",
          directTransition: { from: frame, startedAt: now, durationMs: 420, transition: "smooth" },
        }),
      };
      cancelar();
      dibujar(now);
      if (debeAnimar()) programar();
      return { ok: true };
    },
    react(clave) {
      const resultado = resolveExpression(definicion, clave);
      if (!resultado.ok) return { ok: false, error: resultado.error };
      if (destruido || pausaAutonomia !== null || document.hidden || entorno().reduceMotion) return { ok: false };
      const now = performance.now();
      autonomia.reaccionar(clave, now, { ...frame, expression: expresionVisible ?? frame.expression });
      dibujar(now);
      programar();
      return { ok: true };
    },
    setAutonomy(activa) {
      const valor = Boolean(activa);
      if (autonomiaActiva === valor) return;
      autonomiaActiva = valor;
      autonomia.reiniciar();
      dibujar(performance.now());
      if (debeAnimar()) programar();
      else cancelar();
    },
    pause() {
      pausaAutonomia ??= performance.now();
      if (desplazamiento) desplazamiento.pausado ??= pausaAutonomia;
      if (estado.status === "playing") {
        const now = performance.now();
        estado = pauseAvatarPlayback(estado, now);
        dibujar(now);
      }
      cancelar();
    },
    stop() {
      estado = createAvatarPlaybackState();
      desplazamiento = null;
      pausaAutonomia = performance.now();
      autonomia.reiniciar();
      cancelar();
      dibujar(performance.now());
    },
    getState() {
      return {
        ...(estado.activeAnimation ? { activeAnimation: estado.activeAnimation } : {}),
        activeExpression: estado.activeExpression, status: estado.status,
        reaction: reaccionActual,
      };
    },
    destroy() {
      destruido = true;
      cancelar();
      document.removeEventListener("visibilitychange", visibilidad);
      preferencia?.removeEventListener("change", cambiarPreferencia);
      contenedor.remove();
    },
  };

  function visibilidad() {
    autonomia.reiniciar();
    if (document.hidden) cancelar();
    else {
      dibujar(performance.now());
      if (debeAnimar()) programar();
    }
  }
  function cambiarPreferencia() {
    autonomia.reiniciar();
    dibujar(performance.now());
    if (debeAnimar()) programar();
  }
  const preferencia = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  document.addEventListener("visibilitychange", visibilidad);
  preferencia?.addEventListener("change", cambiarPreferencia);

  // Inicializa primero el fotograma: también sirve de origen de las transiciones.
  dibujar(performance.now());
  if (defaultAnimation !== undefined || defaultExpression !== undefined) {
    const resultado = defaultAnimation !== undefined
      ? resolveAnimation(definicion, defaultAnimation)
      : resolveExpression(definicion, defaultExpression);
    if (!resultado.ok) {
      if (onError) onError(resultado.error);
      else console.error(`[Avatar] ${resultado.error.message}`);
    } else if (defaultAnimation !== undefined && autoplay) controlador.play(defaultAnimation);
    else {
      estado.activeExpression = defaultExpression ?? resultado.value.steps[0]?.expression ?? "neutral";
      dibujar(performance.now());
    }
  }
  if (autonomiaActiva) programar();
  return controlador;
}
