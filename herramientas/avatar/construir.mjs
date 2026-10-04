// Genera rag/servicio/estaticos/avatar.js (ESM minificado), avatar.js.LICENSE.txt
// con el aviso de cada paquete incluido, y avatar.js.sha256.
//
//   npm ci && npm run construir     # escribe los tres archivos
//   npm ci && npm run verificar     # falla si el resultado difiere de lo versionado
//
// El build es reproducible: mismas versiones (package-lock.json) → mismo sha256.
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const aqui = dirname(fileURLToPath(import.meta.url));
const destino = resolve(aqui, "../../rag/servicio/estaticos");
const verificar = process.argv.includes("--verificar");

const resultado = await build({
  entryPoints: [join(aqui, "entrada.js")],
  bundle: true,
  format: "esm",
  minify: true,
  target: "es2020",
  platform: "browser",
  legalComments: "none", // los avisos van completos en avatar.js.LICENSE.txt
  metafile: true,
  write: false,
  logLevel: "warning",
});

// Paquetes cuyo código quedó en el bundle, según el metafile.
const paquetes = new Map();
for (const entrada of Object.keys(resultado.metafile.inputs)) {
  const m = entrada.match(/node_modules\/((?:@[^/]+\/)?[^/]+)\//);
  if (!m || paquetes.has(m[1])) continue;
  const carpeta = join(aqui, "node_modules", m[1]);
  const manifiesto = JSON.parse(readFileSync(join(carpeta, "package.json"), "utf8"));
  const archivo = readdirSync(carpeta).find((n) => /^(LICEN[CS]E|COPYING)(\.|$)/i.test(n));
  if (!archivo) throw new Error(`${m[1]} no trae archivo de licencia: revísalo a mano`);
  paquetes.set(m[1], {
    version: manifiesto.version,
    licencia: manifiesto.license,
    texto: readFileSync(join(carpeta, archivo), "utf8").trim(),
  });
}

const nombres = [...paquetes.keys()].sort();
const aviso = [
  "avatar.js — motor del avatar de rag-extractivo, empaquetado con esbuild",
  "desde herramientas/avatar/ (ver package-lock.json). Incluye:",
  "",
  ...nombres.map((n) => `  ${n}@${paquetes.get(n).version} (${paquetes.get(n).licencia})`),
  "",
  "El código fuente de rag-extractivo, incluido este bundle, se distribuye",
  "bajo AGPL-3.0-only: ver LICENSE en la raíz del repositorio.",
  ...nombres.flatMap((n) => ["", "=".repeat(78), `${n}@${paquetes.get(n).version}`, "=".repeat(78),
    paquetes.get(n).texto]),
  "",
].join("\n");

const codigo = resultado.outputFiles[0].contents;
const cabecera = Buffer.from("/*! avatar.js | licencias: avatar.js.LICENSE.txt */\n");
const salida = Buffer.concat([cabecera, Buffer.from(codigo)]);
const sha = createHash("sha256").update(salida).digest("hex");
const archivos = {
  "avatar.js": salida,
  "avatar.js.LICENSE.txt": Buffer.from(aviso),
  "avatar.js.sha256": Buffer.from(`${sha}  avatar.js\n`),
};

if (verificar) {
  const distintos = Object.entries(archivos).filter(([nombre, contenido]) => {
    const ruta = join(destino, nombre);
    return !existsSync(ruta) || !readFileSync(ruta).equals(contenido);
  }).map(([nombre]) => nombre);
  if (distintos.length) {
    console.error(`difieren de lo versionado: ${distintos.join(", ")}. Ejecuta: npm run construir`);
    process.exit(1);
  }
  console.log(`avatar.js reproducible (sha256 ${sha})`);
} else {
  for (const [nombre, contenido] of Object.entries(archivos)) writeFileSync(join(destino, nombre), contenido);
  console.log(`avatar.js: ${salida.length} bytes, sha256 ${sha}; paquetes: ${nombres.join(", ")}`);
}
