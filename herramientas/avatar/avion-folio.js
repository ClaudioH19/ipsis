// Origami en cuatro paneles: esquinas, pliegue central y alas. Los mismos
// fotogramas se recorren al revés para que el avión vuelva a ser Folio.
// Velocidad y aceleración nulas en cada extremo de los dobleces y del vuelo.
const suave = p => { const t = Math.max(0, Math.min(1, p)); return t * t * t * (t * (t * 6 - 15) + 10); };
const tramo = (p, a, b) => suave((p - a) / (b - a));
const VUELO_BASE = { sentido: 1, distancia: 136, altura: 62, curva: -8, fase: 0 };

// Se elige al comenzar; la pausa conserva tanto el recorrido como las ráfagas.
export function elegirVuelo(random = Math.random) {
  return { sentido: random() < 0.5 ? -1 : 1, distancia: 128 + random() * 16,
    altura: 48 + random() * 22, curva: (random() - 0.5) * 24, fase: random() };
}

export function contornoRedondo(puntos, radio = 4.5) {
  const vertices = puntos.filter((p, i) => i === 0 || Math.hypot(p[0] - puntos[i - 1][0], p[1] - puntos[i - 1][1]) > 0.001);
  if (vertices.length > 1 && Math.hypot(vertices[0][0] - vertices.at(-1)[0], vertices[0][1] - vertices.at(-1)[1]) < 0.001) vertices.pop();
  if (vertices.length < 3) return "";
  const esquinas = vertices.map((p, i) => {
    const anterior = vertices[(i + vertices.length - 1) % vertices.length];
    const siguiente = vertices[(i + 1) % vertices.length];
    const antes = Math.hypot(anterior[0] - p[0], anterior[1] - p[1]);
    const despues = Math.hypot(siguiente[0] - p[0], siguiente[1] - p[1]);
    const r = Math.min(radio, antes * 0.22, despues * 0.22);
    const hacia = (otro, largo) => p.map((v, eje) => v + (otro[eje] - v) * r / Math.max(0.001, largo));
    return { p, entrada: hacia(anterior, antes), salida: hacia(siguiente, despues) };
  });
  const par = p => p.map(v => Number(v.toFixed(3))).join(" ");
  return `M${par(esquinas[0].salida)} ` + esquinas.map((_, i) => {
    const e = esquinas[(i + 1) % esquinas.length];
    return `L${par(e.entrada)} Q${par(e.p)} ${par(e.salida)}`;
  }).join(" ") + " Z";
}
const FORMAS = [
  // Hoja abierta: paneles contiguos sobre el mismo papel.
  [
    [[-39,-46],[0,-46],[0,-7],[-39,-7]],
    [[0,-46],[39,-46],[39,-7],[0,-7]],
    [[-39,-7],[0,-7],[0,46],[-39,46]],
    [[0,-7],[39,-7],[39,46],[0,46]],
  ],
  // Las dos esquinas superiores se doblan hacia la línea central.
  [
    [[0,-7],[0,-46],[0,-7],[-39,-7]],
    [[0,-46],[0,-7],[39,-7],[0,-7]],
    [[-39,-7],[0,-7],[0,46],[-39,46]],
    [[0,-7],[39,-7],[39,46],[0,46]],
  ],
  // Los laterales se acercan al centro y forman la punta alargada.
  [
    [[0,-46],[-20,28],[0,10],[0,10]],
    [[0,-46],[0,10],[20,28],[20,28]],
    [[-20,28],[0,10],[0,46],[-12,46]],
    [[0,10],[20,28],[12,46],[0,46]],
  ],
  // Pliegue central cerrado y alas extendidas: nariz hacia arriba y derecha.
  [
    [[45,-25],[-43,-17],[-6,8],[-6,8]],
    [[45,-25],[-6,8],[-22,36],[-22,36]],
    [[45,-25],[-6,8],[-19,15],[-19,15]],
    [[-6,8],[-22,36],[-19,15],[-19,15]],
  ],
];

// El rostro sigue el papel visible y se acomoda sobre el ala superior.
const ROSTROS = [
  { x: 0, y: 0, escala: 1, giro: 0 },
  { x: 0, y: 2, escala: 0.88, giro: 0 },
  { x: 0, y: 4, escala: 0.55, giro: 0 },
  { x: 0, y: -4, escala: 0.72, giro: -8 },
];

function rostro(progreso, sentido) {
  const p = Math.max(0, Math.min(1, progreso)) * 3;
  const etapa = Math.min(2, Math.floor(p));
  const t = suave(p - etapa);
  return Object.fromEntries(Object.keys(ROSTROS[0]).map(clave => {
    const destino = ROSTROS[etapa + 1][clave] * (etapa === 2 && clave === "giro" ? sentido : 1);
    return [clave, ROSTROS[etapa][clave] + (destino - ROSTROS[etapa][clave]) * t];
  }));
}

function paneles(progreso, sentido) {
  const p = Math.max(0, Math.min(1, progreso)) * 3;
  const etapa = Math.min(2, Math.floor(p));
  const t = suave(p - etapa);
  return FORMAS[etapa].map((panel, i) => panel.map((punto, j) => {
    const destino = FORMAS[etapa + 1][i][j];
    return punto.map((valor, eje) => valor + (destino[eje] * (etapa === 2 && eje === 0 ? sentido : 1) - valor) * t);
  }));
}

export function avionFolio(clave, progreso, variante = VUELO_BASE) {
  const p = Math.max(0, Math.min(1, progreso));
  const { sentido, distancia, altura, curva, fase } = variante;
  let pliegue, x = 0, y = 0, giro = 0, opacidad = 1, estela = 0, vuelo, escala;
  if (clave === "paper-plane-out") {
    pliegue = tramo(p, 0.04, 0.58);
    vuelo = tramo(p, 0.60, 0.94);
    x = sentido * distancia * vuelo;
    y = -altura * vuelo + curva * Math.sin(Math.PI * vuelo);
    escala = 1 - 0.16 * vuelo;
    opacidad = 1 - tramo(p, 0.86, 0.94);
  } else {
    vuelo = tramo(p, 0, 0.34);
    x = -sentido * distancia * (1 - vuelo);
    y = altura * (1 - vuelo) + curva * Math.sin(Math.PI * vuelo);
    escala = 0.84 + 0.16 * vuelo;
    opacidad = tramo(p, 0, 0.08);
    pliegue = 1 - tramo(p, 0.38, 0.96);
  }
  estela = vuelo > 0 && vuelo < 1 ? Math.sin(Math.PI * vuelo) : 0;
  // Se inclina hacia la tangente de la curva y se endereza para aterrizar.
  const rumbo = Math.atan2(-altura + curva * Math.PI * Math.cos(Math.PI * vuelo), sentido * distancia) * 180 / Math.PI;
  const base = sentido === 1 ? -30 : -150;
  giro = (rumbo - base) * Math.sin(Math.PI * vuelo);
  const rafagas = Array.from({ length: 3 }, (_, i) => {
    const ciclo = (p * 9 + i / 3 + fase) % 1;
    const pulso = Math.sin(Math.PI * ciclo);
    const inicio = -35 - 20 * ciclo;
    const fin = inicio - 12 - 16 * pulso;
    const alto = 18 + 6 * i;
    const onda = 4 * Math.sin(p * 26 + i * 2 + fase * 6);
    return { d: `M${sentido * inicio} ${alto} Q${sentido * (inicio + fin) / 2} ${alto + 10 + onda} ${sentido * fin} ${alto + 12 + onda}`,
      opacidad: pulso * pulso, longitud: 10 + 18 * pulso, avance: -p * 120 - i * 12 };
  });
  const origami = tramo(pliegue, 0, 0.14) * opacidad;
  const hoja = clave === "paper-plane-out"
    ? 1 - tramo(pliegue, 0, 0.14) + tramo(p, 0.90, 1)
    : 1 - tramo(pliegue, 0, 0.14);
  return { x, y, giro, escala, sentido, rafagas, paneles: paneles(pliegue, sentido),
    rostro: rostro(pliegue, sentido), origami, hoja: Math.min(1, hoja), estela };
}
