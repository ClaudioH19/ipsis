import assert from "node:assert/strict";
import test from "node:test";
import { crearVida } from "./vida-folio.js";

// Reloj falso: cuadros de 16 ms y temporizadores que vencen al avanzar el tiempo.
function entorno({ reducido = false, puede = true } = {}) {
  let t = 0, siguiente = 1;
  const cuadros = new Map(), esperas = new Map(), reacciones = [];
  const estilo = { translate: "", rotate: "", scale: "" };
  const lienzo = { style: estilo, getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }) };
  const ctx = { reacciones, estilo, puede, reducido };
  const vida = crearVida(lienzo, {
    puede: () => ctx.puede, reducido: () => ctx.reducido, reaccionar: c => reacciones.push(c),
    ahora: () => t,
    pedirCuadro: f => { const id = siguiente++; cuadros.set(id, f); return id; },
    cancelarCuadro: id => cuadros.delete(id),
    esperar: (f, ms) => { const id = siguiente++; esperas.set(id, { f, vence: t + ms }); return id; },
    cancelarEspera: id => esperas.delete(id),
  });
  function avanzar(ms) {
    for (const fin = t + ms; t < fin;) {
      t += 16;
      for (const [id, e] of [...esperas]) if (e.vence <= t) { esperas.delete(id); e.f(); }
      for (const [id, f] of [...cuadros]) { cuadros.delete(id); f(t); }
    }
  }
  return { vida, avanzar, ...ctx, cuadros: () => cuadros.size, esperas: () => esperas.size,
    escala: () => Number(estilo.scale || 1), x: () => parseFloat(estilo.translate || "0") };
}
const maximo = (e, ms, medir) => {
  let m = -Infinity;
  for (let i = 0; i < ms / 16; i++) { e.avanzar(16); m = Math.max(m, medir()); }
  return m;
};

test("una tecla da un cabeceo breve y todo vuelve al reposo", () => {
  const e = entorno();
  e.vida.escribir("insertText", "h");
  assert.ok(maximo(e, 400, () => e.escala()) > 1.02, "la escala debe crecer");
  e.avanzar(3000);
  assert.deepEqual(e.estilo, { translate: "", rotate: "", scale: "" });
  assert.equal(e.cuadros(), 0, "el bucle duerme en reposo");
  assert.equal(e.reacciones.length, 0);
});

test("mientras se escribe se mantiene inclinado hacia el campo y lo suelta al parar", () => {
  const e = entorno();
  for (let i = 1; i <= 8; i++) { e.vida.escribir("insertText", "x".repeat(i)); e.avanzar(120); }
  assert.ok(e.escala() > 1.015, "inclinado mientras escribe");
  e.avanzar(3000);
  assert.equal(e.estilo.scale, "");
});

test("un borrado suelto sacude la cabeza sin cambiar de expresión", () => {
  const e = entorno();
  e.vida.escribir("insertText", "hola");
  e.avanzar(3000);
  e.vida.escribir("deleteContentBackward", "hol");
  const desvio = maximo(e, 500, () => Math.abs(e.x()));
  assert.ok(desvio > 0.8, `debe moverse de lado (${desvio})`);
  assert.deepEqual(e.reacciones, []);
});

test("borrar con prisa sobresalta; vaciar el campo guiña", () => {
  const e = entorno();
  e.vida.escribir("insertText", "una frase larga");
  for (let i = 1; i <= 5; i++) { e.vida.escribir("deleteContentBackward", "una frase larga".slice(0, -i)); e.avanzar(80); }
  assert.deepEqual(e.reacciones, ["surprised"]);
  e.avanzar(3000);
  e.vida.escribir("insertText", "adiós");
  e.vida.escribir("deleteContentBackward", "");
  assert.deepEqual(e.reacciones, ["surprised", "wink"]);
});

test("con movimiento reducido o sin permiso no se mueve ni reacciona", () => {
  for (const ajuste of [{ reducido: true }, { puede: false }]) {
    const e = entorno(ajuste);
    e.vida.escribir("insertText", "hola");
    e.vida.escribir("deleteContentBackward", "");
    e.vida.apuntar(300, 40);
    e.avanzar(1000);
    assert.deepEqual(e.estilo, { translate: "", rotate: "", scale: "" });
    assert.deepEqual(e.reacciones, []);
    assert.equal(e.cuadros(), 0);
  }
});

test("el cuerpo sigue al puntero, crece al acercarse y vuelve al quedar quieto", () => {
  const e = entorno();
  e.vida.apuntar(400, 50);          // a la derecha, lejos
  e.avanzar(600);
  assert.ok(e.x() > 3, `se desvía hacia el puntero (${e.x()})`);
  assert.ok(e.escala() < 1.01, "lejos no crece");
  e.vida.apuntar(80, 50);           // muy cerca
  e.avanzar(600);
  assert.ok(e.escala() > 1.03, `cerca crece (${e.escala()})`);
  e.avanzar(4000);                  // sin mover: vuelve
  assert.equal(e.estilo.translate, "");
  assert.equal(e.cuadros(), 0);
});

test("si deja de poder moverse (por ejemplo, pensando) vuelve al centro", () => {
  const e = entorno();
  e.vida.apuntar(400, 50);
  e.avanzar(600);
  e.puede = false;
  e.avanzar(2500);
  assert.equal(e.estilo.translate, "");
});

test("destruir cancela todo y limpia el estilo", () => {
  const e = entorno();
  e.vida.apuntar(400, 50);
  e.vida.escribir("insertText", "a");
  e.avanzar(100);
  e.vida.destruir();
  assert.equal(e.cuadros(), 0);
  assert.equal(e.esperas(), 0);
  assert.equal(e.estilo.translate, "");
});

test("reemplazar el texto por uno más corto es escribir, no borrar", () => {
  const e = entorno();
  e.vida.escribir("insertText", "una frase larga");
  for (let i = 0; i < 6; i++) { e.vida.escribir("insertText", "x".repeat(i)); e.avanzar(80); }
  assert.deepEqual(e.reacciones, []);
});
