// Señales del borrador: se reconocen localmente, sin consultar el servicio.
import diccionario from "./reacciones-texto.json" with { type: "json" };

const normalizar = texto => texto.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
const escapar = texto => texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const BORDE = "[^\\p{L}\\p{N}_]";
// Se compila una vez; el JSON es el punto de edición del vocabulario.
const reglas = Object.entries(diccionario).flatMap(([clave, grupo]) => {
  const palabras = [...(grupo.palabras ?? []), ...(grupo.frases ?? [])];
  return [...palabras.map(texto => ({ texto, literal: false })),
    ...(grupo.emoticonos ?? []).map(texto => ({ texto, literal: true }))]
    .map(({ texto, literal }) => {
      const termino = escapar(normalizar(texto)).replace(/\s+/g, "\\s+");
      const usaBordes = !literal || /^[\p{L}\p{N}]+$/u.test(texto);
      return { clave, patron: new RegExp(`(^|${usaBordes ? BORDE : ""})(${termino})${usaBordes ? `(?=$|${BORDE})` : ""}`, "gu"),
        literal };
    });
});

export function reactionForText(texto) {
  const textoFinal = String(texto ?? "").trim().slice(-480);
  if (!textoFinal) return "attentive";
  if (/[¿?]/u.test(textoFinal)) return "curious";
  const normalizado = normalizar(textoFinal), coincidencias = [];
  for (const { clave, patron, literal } of reglas) {
    patron.lastIndex = 0;
    for (const match of normalizado.matchAll(patron)) {
      const inicio = match.index + match[1].length, fin = inicio + match[2].length;
      // «No estoy triste» no provoca tristeza; frases como «no entiendo»
      // se reconocen completas en el propio diccionario.
      const antes = normalizado.slice(Math.max(0, inicio - 36), inicio);
      if (!literal && /(?:^|\s)(?:no|nunca)(?:\s+(?:estoy|soy|tengo|es|me siento))?\s+$/u.test(antes)) continue;
      coincidencias.push({ clave, inicio, fin });
    }
  }
  // La frase completa gana a una palabra contenida («no me queda claro»).
  const completas = coincidencias.filter(c => !coincidencias.some(otra =>
    otra !== c && otra.inicio <= c.inicio && otra.fin >= c.fin && otra.fin - otra.inicio > c.fin - c.inicio));
  completas.sort((a, b) => b.fin - a.fin || a.inicio - b.inicio);
  if (completas.length) return completas[0].clave;
  if (/[¡!]/u.test(textoFinal)) return "surprised";
  return "reading";
}

// Las 15 miradas se añaden solo a la definición de esta instancia.
export function withPointerGaze(definicion, amplitudOjos = 6, amplitudCabeza = 8) {
  const neutral = definicion.expressions?.neutral;
  if (!neutral || Object.keys(definicion.expressions).length + 15 > 128) return definicion;
  const expressions = { ...definicion.expressions }, expressionOrder = [...(definicion.expressionOrder ?? [])];
  for (let col = 0; col < 5; col++) {
    for (let fila = 0; fila < 3; fila++) {
      const dx = (col - 2) / 2, dy = fila - 1;
      const e = JSON.parse(JSON.stringify(neutral));
      for (const lado of ["left", "right"]) {
        e.eyes[lado].x += dx * amplitudOjos * 2;
        e.eyes[lado].y += dy * amplitudOjos * 1.5;
      }
      e.head.y += dx * amplitudCabeza * 2;
      e.head.x -= dy * amplitudCabeza;
      const clave = `mirada-c${col}-f${fila}`;
      expressions[clave] = e;
      if (!expressionOrder.includes(clave)) expressionOrder.push(clave);
    }
  }
  return { ...definicion, expressions, expressionOrder };
}
