// Movimiento de la hoja completa. Las poses y el parpadeo siguen en avatar-core.
// La duración sale del .avatar.json para que el widget y el movimiento terminen
// juntos, incluso al configurar estos gestos para otros eventos.
const SUAVE = p => p * p * p * (p * (p * 6 - 15) + 10);
import { avionFolio } from "./avion-folio.js";
// Reposo y atención flotan sin cambiar la forma de sus ojos.
export const FLOTACION = new Set(["idle", "attentive", "listening", "float"]);
export const MOVIMIENTOS = new Set([...FLOTACION, "spin", "flip", "bounce", "sway", "dance", "paper-plane-out", "paper-plane-in"]);

export function movimientoFolio(clave, progreso, variante) {
  const p = Math.max(0, Math.min(1, progreso));
  const onda = Math.sin(2 * Math.PI * p);
  const envolvente = Math.sin(Math.PI * p);
  const movimiento = { x: 0, y: 0, giro: 0, escalaX: 1, escalaY: 1, frente: true };
  switch (clave) {
    case "paper-plane-out":
    case "paper-plane-in":
      movimiento.avion = avionFolio(clave, p, variante);
      break;
    case "spin":
      movimiento.giro = 360 * SUAVE(p);
      break;
    case "flip": {
      const coseno = Math.cos(2 * Math.PI * SUAVE(p));
      // Un mínimo de grosor deja ver el canto cuando la hoja está de perfil.
      movimiento.escalaX = (coseno < 0 ? -1 : 1) * Math.max(0.035, Math.abs(coseno));
      movimiento.y = -4 * envolvente;
      movimiento.frente = coseno >= 0;
      break;
    }
    case "bounce": {
      const salto = Math.abs(onda);
      movimiento.y = -12 * salto;
      movimiento.escalaX = 1 + 0.06 * Math.cos(4 * Math.PI * p) * envolvente;
      movimiento.escalaY = 1 - 0.07 * Math.cos(4 * Math.PI * p) * envolvente;
      break;
    }
    case "sway":
      movimiento.x = 4 * onda;
      movimiento.giro = 18 * onda;
      break;
    case "dance":
      movimiento.x = 7 * onda;
      movimiento.y = -6 * Math.abs(onda);
      movimiento.giro = 14 * Math.sin(4 * Math.PI * p);
      break;
    case "idle":
    case "attentive":
    case "listening":
    case "float":
      movimiento.y = -7 * (1 - Math.cos(2 * Math.PI * p)) / 2;
      movimiento.giro = 5 * onda;
      break;
  }
  return movimiento;
}
