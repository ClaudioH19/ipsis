# herramientas/avatar

Empaqueta el motor del avatar ([@bible-strong/avatar-web](https://github.com/smontlouis/bible-strong-avatar-lab),
AGPL-3.0) para el widget. Solo desarrollo: no entra en el wheel; se versiona
el resultado.

```bash
cd herramientas/avatar
npm ci                  # versiones exactas de package-lock.json
npm run construir       # escribe rag/servicio/estaticos/avatar.js, .LICENSE.txt y .sha256
npm run verificar       # falla si el resultado difiere de lo versionado
node validar.mjs        # valida los avatares incluidos con la librería real
```

- `construir.mjs`: esbuild, un solo ESM minificado. Las licencias de cada
  paquete incluido salen del metafile y van a `avatar.js.LICENSE.txt`.
- El build es reproducible: mismas versiones, mismo sha256. Git no convierte
  los fines de línea de esos archivos (ver `.gitattributes`).
- Para actualizar la librería: cambia la versión exacta en `package.json`,
  `npm install`, `npm run construir`, y corre las pruebas de navegador.
