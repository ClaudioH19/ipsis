import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createAvatarPlaybackState, sampleAvatarFrame } from "@bible-strong/avatar-core";
import { crearAutonomia } from "./autonomia-folio.js";
import { reactionForText, withPointerGaze } from "./interacciones-folio.js";

const definicion = JSON.parse(readFileSync(new URL("../../ipsis/recursos/avatares/folio.avatar.json", import.meta.url)));
const entorno = { random: () => 0, reduceMotion: true };
const pose = clave => sampleAvatarFrame(definicion,
  { ...createAvatarPlaybackState(), activeExpression: clave }, 0, entorno);
const poses = Object.fromEntries(Object.keys(definicion.expressions).map(clave => [clave, pose(clave).expression]));
const base = pose("attentive");
function iniciar(azar) {
  let valor = 0;
  const auto = crearAutonomia(definicion, poses, () => valor);
  assert.equal(auto.muestrear(0, base).clave, null);
  valor = azar;
  return auto;
}

test("la espera entre reacciones se mantiene entre 1,8 y 3,6 segundos", () => {
  for (const [azar, demora] of [[0, 1800], [1, 3600]]) {
    const auto = crearAutonomia(definicion, poses, () => azar);
    auto.muestrear(0, base);
    assert.equal(auto.muestrear(demora - 1, base).clave, null);
    assert.ok(auto.muestrear(demora, base).clave);
  }
});

test("ofrece las 16 reacciones, con mayor frecuencia de gestos discretos", () => {
  const conteos = new Map();
  for (let i = 0; i < 200; i++) {
    const clave = iniciar((i + 0.5) / 200).muestrear(4500, base).clave;
    conteos.set(clave, (conteos.get(clave) ?? 0) + 1);
  }
  const discretos = ["look-left", "look-right", "curious", "reading", "kind", "wink"];
  const animados = ["nod", "wave", "listening", "sway", "bounce", "float"];
  const ocasionales = ["dance", "spin", "flip", "plane-trip"];
  assert.deepEqual([...conteos.keys()].sort(), [...discretos, ...animados, ...ocasionales].sort());
  const total = claves => claves.reduce((n, clave) => n + conteos.get(clave), 0);
  assert.ok(total(discretos) > total(animados));
  assert.ok(total(animados) > total(ocasionales) * 3);
});

test("reproduce el giro completo y una sola vuelta de los bucles", () => {
  const giro = iniciar(0.95);
  assert.equal(giro.muestrear(4500, base).clave, "spin");
  assert.equal(giro.muestrear(5400, base).giro, 180);
  assert.equal(giro.muestrear(6500, base).giro, 360);
  assert.equal(giro.muestrear(7100, base).clave, null);
  const balanceo = iniciar(0.75);
  assert.equal(balanceo.muestrear(4500, base).clave, "sway");
  assert.ok(Math.abs(balanceo.muestrear(5200, base).giro) > 10);
  assert.equal(balanceo.muestrear(7900, base).clave, null);
});

test("el avioncito sale, llega y conserva el recorrido al pausar", () => {
  const auto = iniciar(0.999);
  assert.equal(auto.muestrear(4500, base).clave, "plane-trip");
  const despegue = auto.muestrear(6000, base);
  assert.ok(despegue.avion.origami > 0.5);
  assert.equal(despegue.blink, 1);
  auto.reanudar(10000);
  assert.deepEqual(auto.muestrear(16000, base), despegue);
  const llegada = auto.muestrear(19300, base);
  assert.ok(llegada.avion.origami > 0.5);
  assert.ok(llegada.avion.hoja < 0.5);
  assert.equal(llegada.blink, 1);
  assert.equal(auto.muestrear(21700, base).clave, null);
});

test("separa los gestos llamativos aunque el azar siempre los favorezca", () => {
  const auto = iniciar(0.999);
  assert.equal(auto.muestrear(4500, base).clave, "plane-trip");
  assert.equal(auto.muestrear(11700, base).clave, null);
  assert.equal(auto.muestrear(23000, base).clave, "float");
  auto.reiniciar();
  assert.equal(auto.muestrear(24000, base).clave, null);
  assert.equal(auto.muestrear(35500, base).clave, "bounce"); // tampoco repite float
});

test("tolera una definición parcial y cancela una reacción al reiniciar", () => {
  const auto = crearAutonomia({ ...definicion, animations: {} }, { curious: poses.curious }, () => 0);
  auto.muestrear(0, base);
  assert.equal(auto.muestrear(5000, base).clave, "curious");
  auto.reiniciar();
  assert.equal(auto.muestrear(5100, base).clave, null);
  const vacio = crearAutonomia({ animations: {} }, {}, () => 0);
  assert.equal(vacio.muestrear(10000, base).expression, base.expression);
});

test("las reacciones de contacto funcionan con la autonomía apagada y se interrumpen", () => {
  const auto = crearAutonomia(definicion, poses, () => 0);
  assert.equal(auto.reaccionar("curious", 0, base), true);
  assert.equal(auto.muestrear(700, base, false).clave, "curious");
  assert.equal(auto.muestrear(1800, base, false).clave, null);
  assert.equal(auto.tieneInteraccion(), false);
  assert.equal(auto.reaccionar("inexistente", 2000, base), false);
  auto.reaccionar("wink", 3000, base);
  auto.reiniciar();
  assert.equal(auto.muestrear(3010, base, false).clave, null);
});

test("un cambio de señal parte de la expresión visible sin saltar a la neutral", () => {
  const auto = crearAutonomia(definicion, poses, () => 0);
  auto.reaccionar("wink", 0, base);
  const visible = auto.muestrear(700, base, false).expression;
  auto.reaccionar("curious", 700, { ...base, expression: visible });
  assert.deepEqual(auto.muestrear(700, base, false).expression, visible);
  assert.equal(auto.muestrear(1400, base, false).expression.heightRight, poses.curious.heightRight);
});

test("el borrador reconoce señales concretas sin confundirlas con una respuesta", () => {
  for (const [texto, clave] of [["", "attentive"], ["hola", "wink"], ["Hello Folio", "wink"],
    ["Dónde leo?", "curious"], ["¡Mira!", "surprised"], ["gracias 😊", "kind"],
    [":)", "kind"], ["🙁", "sorry"], ["hola?", "curious"], ["una palabra", "reading"],
    ["mejorar", "reading"]]) assert.equal(reactionForText(texto), clave, texto);
});

test("cada entrada del diccionario produce una expresión existente de Folio", () => {
  const diccionario = JSON.parse(readFileSync(new URL("./reacciones-texto.json", import.meta.url)));
  for (const [clave, grupo] of Object.entries(diccionario)) {
    assert.ok(definicion.expressions[clave], `Expresión inexistente: ${clave}`);
    assert.ok(Object.values(grupo).flat().length > 0, `Grupo vacío: ${clave}`);
    for (const [tipo, entradas] of Object.entries(grupo)) {
      assert.ok(["palabras", "frases", "emoticonos"].includes(tipo), tipo);
      assert.ok(Array.isArray(entradas), tipo);
      for (const entrada of entradas) {
        assert.equal(typeof entrada, "string");
        assert.ok(entrada.trim().length > 0);
        assert.equal(reactionForText(entrada), clave, `${clave}: ${entrada}`);
      }
    }
  }
});

test("el vocabulario ignora mayúsculas y tildes y respeta palabras completas", () => {
  for (const [texto, clave] of [["INCREIBLE", "surprised"], ["tengo SUENO", "sleepy"],
    ["TE   QUIERO", "kind"], ["me siento nerviosa", "worried"], ["JAJAJA", "happy"],
    ["de acuerdo", "nod-down"], ["investigar", "thinking"], ["explicame", "curious"],
    ["Holanda", "reading"], ["amortizar", "reading"], ["guaucho", "reading"],
    ["xdentro", "reading"], ["solo una palabra", "reading"]]) {
    assert.equal(reactionForText(texto), clave, texto);
  }
});

test("la señal más reciente gana, las frases tienen prioridad y se evitan negaciones simples", () => {
  for (const [texto, clave] of [["hola, tengo sueño", "sleepy"], ["estoy triste, pero gracias", "kind"],
    ["gracias, estoy triste", "sorry"], ["hola, no me queda claro", "unsure"],
    ["hola, no estoy triste", "wink"], ["no tengo sueño", "reading"],
    ["no estoy nervioso", "reading"], ["no entiendo", "unsure"], ["no lo puedo creer", "surprised"],
    ["hola, te quiero ❤️", "kind"], ["¡hola!", "wink"], ["estoy cansado?", "curious"],
    [`triste ${"palabra ".repeat(80)}hola`, "wink"]]) {
    assert.equal(reactionForText(texto), clave, texto);
  }
  // No se conserva una coincidencia de una llamada anterior al borrar el texto.
  assert.equal(reactionForText("sueño sueño"), "sleepy");
  assert.equal(reactionForText(""), "attentive");
  assert.equal(reactionForText("borrador"), "reading");
});

test("la grilla de mirada se comparte sin modificar la definición ni duplicar claves", () => {
  const antes = JSON.stringify(definicion);
  const mirada = withPointerGaze(definicion);
  assert.equal(JSON.stringify(definicion), antes);
  assert.equal(Object.keys(mirada.expressions).length, Object.keys(definicion.expressions).length + 15);
  assert.ok(mirada.expressions['mirada-c4-f0'].eyes.left.x > mirada.expressions['mirada-c0-f0'].eyes.left.x);
  assert.equal(withPointerGaze(mirada).expressionOrder.length, mirada.expressionOrder.length);
});
