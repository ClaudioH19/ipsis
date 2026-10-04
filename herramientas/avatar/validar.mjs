// Valida avatares con la librería real (parseAvatarDefinition de avatar-core).
//
//   node validar.mjs [archivo.avatar.json ...]   # por defecto, los avatares incluidos
//
// Sale con 1 si alguno no es válido.
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseAvatarDefinition } from "@bible-strong/avatar-core";

const aqui = dirname(fileURLToPath(import.meta.url));
const incluidos = resolve(aqui, "../../rag/recursos/avatares");
const argumentos = process.argv.slice(2);
const archivos = argumentos.length ? argumentos
  : readdirSync(incluidos).filter((n) => n.endsWith(".avatar.json")).map((n) => join(incluidos, n));

let fallos = 0;
for (const archivo of archivos) {
  const resultado = parseAvatarDefinition(readFileSync(archivo, "utf8"));
  if (!resultado.ok) {
    fallos += 1;
    for (const e of resultado.errors.slice(0, 10)) console.error(`${archivo}: ${e.path} ${e.code}: ${e.message}`);
    continue;
  }
  console.log(`${archivo}: válido (${Object.keys(resultado.value.expressions).length} expresiones, ` +
    `${Object.keys(resultado.value.animations).length} animaciones)`);
}
process.exit(fallos ? 1 : 0);
