// Vida de Folio: el cuerpo sigue al puntero, se inclina al escribir y reacciona al borrar.
//
// Un resorte amortiguado por canal (x, y, giro, escala) mueve el lienzo con las propiedades CSS individuales
// `translate`, `rotate` y `scale`, que se componen con el movimiento interno de Folio (flotación, giros, avioncito)
// sin tocar su `transform`. Las pulsaciones y los borrados no cambian la meta: dan un impulso de velocidad y el
// resorte hace el resto, con un rebote suave como el de iOS. El bucle de animación duerme cuando todo está en reposo.
const RIGIDEZ = 170;
const AMORTIGUACION = 17; // ζ ≈ 0,65: un rebote y se asienta
const PASO_MAX = 1 / 120;
const CANALES = ["x", "y", "giro", "escala"];
const REPOSO = { x: 0, y: 0, giro: 0, escala: 1 };
// Un resorte con estos parámetros alcanza un desplazamiento ≈ v0 / K con K ≈ 22 (por unidad): se usa para convertir
// «cuánto quiero que se mueva» en el impulso inicial.
const K = 22;

const RADIO_SIGUE_PX = 200; // distancia a la que el desvío hacia el puntero ya es casi el máximo
const CERCANIA_PX = 220; // cerca del puntero, Folio crece un poco
const QUIETO_MS = 1500; // sin mover el puntero, vuelve al centro
const ESCRIBIENDO_MS = 1000; // tras la última tecla, deja de inclinarse hacia el campo
const VENTANA_BORRADO_MS = 900;
const RAFAGA_BORRADO = 5; // borrados dentro de la ventana que cuentan como «borrar con prisa»
const MIN_CARACTERES_LIMPIAR = 4; // vaciar un campo con al menos esto se vive como «olvídalo»

const limitar = (v, a, b) => Math.min(b, Math.max(a, v));

export function crearVida(lienzo, opciones = {}) {
  const puede = opciones.puede ?? (() => true);
  const reaccionar = opciones.reaccionar ?? (() => {});
  const reducido = opciones.reducido ?? (() =>
    typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches);
  const pedirCuadro = opciones.pedirCuadro ?? (f => requestAnimationFrame(f));
  const cancelarCuadro = opciones.cancelarCuadro ?? (id => cancelAnimationFrame(id));
  const ahora = opciones.ahora ?? (() => performance.now());
  const esperar = opciones.esperar ?? ((f, ms) => setTimeout(f, ms));
  const cancelarEspera = opciones.cancelarEspera ?? (id => clearTimeout(id));

  const s = { ...REPOSO }, v = { x: 0, y: 0, giro: 0, escala: 0 }, meta = { ...REPOSO };
  let cuadro = null, anterior = 0, quieto = null, escribiendo = null, previo = 0, alternar = 1;
  let borrados = [];
  const pendientes = new Set();

  const enReposo = () => CANALES.every(c => Math.abs(s[c] - meta[c]) < (c === "escala" ? 5e-4 : 0.01) && Math.abs(v[c]) < 0.05);
  const metaEnReposo = () => CANALES.every(c => meta[c] === REPOSO[c]);

  function escribirEstilo() {
    if (CANALES.every(c => s[c] === REPOSO[c])) {
      lienzo.style.translate = lienzo.style.rotate = lienzo.style.scale = "";
      return;
    }
    lienzo.style.translate = `${s.x.toFixed(2)}px ${s.y.toFixed(2)}px`;
    lienzo.style.rotate = `${s.giro.toFixed(2)}deg`;
    lienzo.style.scale = s.escala.toFixed(4);
  }

  function paso(dt) {
    for (const c of CANALES) {
      v[c] += (-RIGIDEZ * (s[c] - meta[c]) - AMORTIGUACION * v[c]) * dt;
      s[c] += v[c] * dt;
    }
  }

  function cuadroNuevo(t) {
    cuadro = null;
    let dt = Math.min((t - anterior) / 1000, 1 / 20);
    anterior = t;
    if (!puede() || reducido()) Object.assign(meta, REPOSO);
    while (dt > 0) {
      const d = Math.min(dt, PASO_MAX);
      paso(d);
      dt -= d;
    }
    if (enReposo() && metaEnReposo()) {
      Object.assign(s, REPOSO);
      CANALES.forEach(c => { v[c] = 0; });
      escribirEstilo();
      return;
    }
    escribirEstilo();
    cuadro = pedirCuadro(cuadroNuevo);
  }

  function despertar() {
    if (cuadro !== null || reducido()) return;
    anterior = ahora();
    cuadro = pedirCuadro(cuadroNuevo);
  }

  const programar = (f, ms) => {
    const id = esperar(() => { pendientes.delete(id); f(); }, ms);
    pendientes.add(id);
    return id;
  };

  function reposar() {
    Object.assign(meta, REPOSO);
    despertar();
  }

  // Impulso de «desplazamiento deseado» en un canal.
  const empujar = (canal, cantidad) => { v[canal] += cantidad * K; };

  // Sacudida lateral con giro, como negar con la cabeza.
  function sacudir(px, grados, veces) {
    for (let i = 0; i < veces; i++) {
      const signo = i % 2 === 0 ? 1 : -1, atenuacion = 1 - i * 0.18;
      programar(() => {
        if (!puede() || reducido()) return;
        empujar("x", signo * px * atenuacion);
        empujar("giro", signo * grados * atenuacion);
        despertar();
      }, i * 110);
    }
  }

  return {
    // Cuerpo hacia el puntero: se inclina, se desvía un poco y crece al acercarse.
    apuntar(px, py) {
      if (reducido() || !puede()) return;
      const caja = lienzo.getBoundingClientRect();
      if (!caja.width) return;
      const dx = px - (caja.left + caja.width / 2), dy = py - (caja.top + caja.height / 2);
      const cercania = limitar(1 - Math.hypot(dx, dy) / CERCANIA_PX, 0, 1);
      const nx = Math.tanh(dx / RADIO_SIGUE_PX), ny = Math.tanh(dy / RADIO_SIGUE_PX);
      meta.x = nx * 4.5;
      meta.y = ny * 3.5 + (escribiendo !== null ? 2 : 0);
      meta.giro = nx * 6;
      meta.escala = 1 + 0.06 * cercania + (escribiendo !== null ? 0.025 : 0);
      despertar();
      if (quieto !== null) cancelarEspera(quieto);
      quieto = esperar(() => { quieto = null; if (escribiendo === null) reposar(); }, QUIETO_MS);
    },

    soltar() { reposar(); },

    // Un cambio del campo de texto: `tipo` es `InputEvent.inputType`, `valor` el texto resultante.
    escribir(tipo, valor) {
      const largo = [...String(valor ?? "")].length, antes = previo;
      previo = largo;
      if (reducido() || !puede()) return;
      const t = ahora();
      // Solo un borrado de verdad (`deleteContentBackward`, `deleteByCut`…): reemplazar la selección por una letra acorta el
      // texto pero se escribe, no se borra.
      if (String(tipo).startsWith("delete")) {
        borrados = borrados.filter(m => t - m < VENTANA_BORRADO_MS).concat(t);
        if (largo === 0 && antes >= MIN_CARACTERES_LIMPIAR) {
          reaccionar("wink");
          empujar("y", -5);
          empujar("escala", 0.07);
          sacudir(3, 5, 2);
        } else if (borrados.length >= RAFAGA_BORRADO) {
          reaccionar("surprised");
          empujar("escala", -0.05);
          sacudir(6, 9, 4);
          borrados = [];
        } else {
          sacudir(3.5, 5.5, 2);
        }
      } else {
        // Cada letra es un cabeceo breve; el vaivén cambia de lado para no verse mecánico.
        alternar = -alternar;
        empujar("y", 1.6);
        empujar("escala", 0.018);
        empujar("giro", alternar * 1.1);
        if (largo - antes > 3) empujar("escala", 0.03); // pegar texto: un sobresalto más grande
        meta.y = 2;
        meta.escala = 1.025;
      }
      if (escribiendo !== null) cancelarEspera(escribiendo);
      escribiendo = esperar(() => { escribiendo = null; reposar(); }, ESCRIBIENDO_MS);
      despertar();
    },

    destruir() {
      if (cuadro !== null) cancelarCuadro(cuadro);
      cuadro = null;
      pendientes.forEach(cancelarEspera);
      pendientes.clear();
      for (const id of [quieto, escribiendo]) if (id !== null) cancelarEspera(id);
      quieto = escribiendo = null;
      Object.assign(s, REPOSO);
      escribirEstilo();
    },

    // Para las pruebas.
    estado: () => ({ ...s, meta: { ...meta } }),
  };
}
