// Gestos de compañía: se superponen al reposo sin cambiar el evento del chat.
// El reloj lo presta el renderer, así que no quedan temporizadores al destruirlo.
import {
  advanceAvatarPlayback, playAvatarAnimation, sampleAvatarFrame,
} from "@bible-strong/avatar-core";
import { movimientoFolio } from "./movimiento-folio.js";
import { elegirVuelo } from "./avion-folio.js";

const SUAVE = p => p * p * (3 - 2 * p);
const GESTOS = ["look-left", "look-right", "curious", "reading", "kind", "wink"];
const ANIMACIONES = ["nod", "wave", "listening", "sway", "bounce", "float"];
const OCASIONALES = ["dance", "spin", "flip", "plane-trip"];

export function crearAutonomia(definicion, poses, random = () => Math.random()) {
  const disponibles = [
    ...GESTOS.filter(clave => poses[clave]).map(clave => ({ clave, peso: 4, pose: true })),
    ...ANIMACIONES.filter(clave => definicion.animations[clave]).map(clave => ({ clave, peso: 3 })),
    ...OCASIONALES.filter(clave => clave === "plane-trip"
      ? definicion.animations["paper-plane-out"] && definicion.animations["paper-plane-in"]
      : definicion.animations[clave]).map(clave => ({ clave, peso: 1, ocasional: true })),
  ];
  let proxima = null, reaccion = null, ultima = null;
  let ocasionalDesde = -Infinity;
  const ambiente = () => ({ random, reduceMotion: false });
  const duracion = clave => definicion.animations[clave].steps
    .reduce((total, paso) => total + paso.holdMs + paso.transitionMs, 0);

  function reiniciar() { proxima = null; reaccion = null; }
  function reanudar(delta) {
    if (proxima !== null) proxima += delta;
    ocasionalDesde += delta;
    if (reaccion) {
      reaccion.inicio += delta;
      if (reaccion.estado) {
        // La reproducción secundaria usa tiempo local, sin avanzar en pausa.
        reaccion.origen += delta;
      }
    }
  }
  function esperar(now) { proxima = now + 1800 + random() * 1800; }

  function comenzar(elegido, now, baseFrame, solicitada = false) {
    reaccion = { ...elegido, inicio: now, sostener: solicitada ? 350 : 650 + random() * 700,
      sentido: random() < 0.5 ? -1 : 1, origen: now, solicitada,
      desde: solicitada ? baseFrame.expression : null };
    if (!elegido.pose) {
      reaccion.animacion = elegido.clave === "plane-trip" ? "paper-plane-out" : elegido.clave;
      reaccion.duracion = duracion(reaccion.animacion);
      reaccion.total = reaccion.duracion + (elegido.clave === "plane-trip" ? duracion("paper-plane-in") : 0);
      reaccion.estado = playAvatarAnimation(definicion, reaccion.animacion, 0, baseFrame).value;
      if (elegido.clave === "plane-trip") reaccion.vuelo = elegirVuelo(random);
    }
    if (elegido.ocasional) ocasionalDesde = now + 45000 + random() * 15000;
  }

  function reaccionar(clave, now, baseFrame) {
    if (!poses[clave]) return false;
    comenzar({ clave, pose: true }, now, baseFrame, true);
    return true;
  }

  function elegir(now) {
    const opciones = disponibles.filter(gesto => gesto.clave !== ultima
      && (!gesto.ocasional || now >= ocasionalDesde));
    // Una definición parcial puede tener un solo gesto: sigue funcionando.
    const candidatos = opciones.length ? opciones : disponibles.filter(g => !g.ocasional || now >= ocasionalDesde);
    let dado = random() * candidatos.reduce((total, gesto) => total + gesto.peso, 0);
    for (const gesto of candidatos) {
      dado -= gesto.peso;
      if (dado < 0) return gesto;
    }
    return candidatos.at(-1);
  }

  function muestrear(now, baseFrame, automatica = true) {
    const base = baseFrame.expression;
    const quieto = { expression: base, clave: null, x: 0, y: 0, giro: 0 };
    if (!automatica && !reaccion?.solicitada) return quieto;
    if (!disponibles.length && !reaccion) return quieto;
    if (proxima === null) esperar(now);
    if (automatica && !reaccion && now >= proxima) {
      const elegido = elegir(now);
      if (!elegido) { esperar(now); return quieto; }
      ultima = elegido.clave;
      comenzar(elegido, now, baseFrame);
    }
    const activo = reaccion?.total ?? (650 + (reaccion?.sostener ?? 0));
    if (reaccion && now >= reaccion.inicio + activo + 800) {
      reaccion = null;
      esperar(now);
    }
    if (!reaccion) return quieto;
    const t = now - reaccion.inicio;
    const peso = t < 650 ? SUAVE(t / 650)
      : t < activo ? 1 : 1 - SUAVE((t - activo) / 800);
    let destino = poses[reaccion.clave], movimiento, blink;
    if (reaccion.estado) {
      let reloj = now - reaccion.origen;
      if (reaccion.clave === "plane-trip" && reaccion.animacion === "paper-plane-out" && reloj >= reaccion.duracion) {
        reaccion.origen += reaccion.duracion;
        reloj = now - reaccion.origen;
        reaccion.animacion = "paper-plane-in";
        reaccion.duracion = duracion(reaccion.animacion);
        reaccion.estado = playAvatarAnimation(definicion, reaccion.animacion, 0, baseFrame).value;
      }
      // Los bucles del catálogo se interpretan durante un solo ciclo.
      const tiempo = Math.min(reloj, Math.max(0, reaccion.duracion - 0.001));
      reaccion.estado = advanceAvatarPlayback(definicion, reaccion.estado, tiempo, ambiente());
      const frame = sampleAvatarFrame(definicion, reaccion.estado, tiempo, ambiente());
      destino = frame.expression;
      blink = reaccion.clave === "plane-trip" ? 1 : Math.min(baseFrame.blink, frame.blink);
      movimiento = movimientoFolio(reaccion.animacion, Math.min(1, reloj / reaccion.duracion), reaccion.vuelo);
    }
    const desde = t < 650 && reaccion.desde ? reaccion.desde : base;
    const expression = { ...desde };
    for (const [campo, valor] of Object.entries(destino)) {
      if (typeof valor === "number" && typeof desde[campo] === "number") {
        expression[campo] = desde[campo] + (valor - desde[campo]) * peso;
      }
    }
    return { expression, clave: reaccion.clave, blink,
      ...(movimiento ?? {}),
      x: (movimiento?.x ?? reaccion.sentido * 1.5) * peso,
      y: (movimiento?.y ?? -2) * peso,
      // Un giro completo termina en 360°: no se deshace durante el retorno.
      giro: movimiento?.giro ?? reaccion.sentido * 3 * Math.sin(t / 450) * peso };
  }
  return { reiniciar, reanudar, muestrear, reaccionar,
    tieneInteraccion: () => Boolean(reaccion?.solicitada) };
}
