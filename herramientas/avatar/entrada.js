// Lo único que el widget usa del motor del avatar.
import { createAvatar as createProceduralAvatar } from "@bible-strong/avatar-web";
import { createFolioAvatar } from "./folio.js";
export { reactionForText, withPointerGaze } from "./interacciones-folio.js";
export { crearVida } from "./vida-folio.js";

export function createAvatar(target, options) {
  return options.definition?.name === "Folio"
    ? createFolioAvatar(target, options)
    : createProceduralAvatar(target, options);
}
