# Instantáneas completas de Wiktionary/Kaikki

Español, inglés y portugués, extracción 2026-10-03 del dump enwiktionary
2026-09-02. Los tres gzip descargados suman 675.305.401 bytes.

Cada descarga se conserva íntegra en `*.jsonl.gz.<número>.part`, en bloques
de hasta 24 MiB. Las partes no son gzip independientes: concatenarlas en
el orden de `parts` en [diccionarios.json](../../diccionarios.json)
recupera exactamente el archivo descargado. El constructor las lee como
un único flujo sin crear otro archivo gigante.

`*.lexical.*.jsonl.gz` son proyecciones verificadas de los campos léxicos
necesarios. Se mantienen aparte del original, que conserva toda la información.
La reconstrucción habitual comprueba también los hashes de los originales
completos y de cada parte. `--raw-dictionaries` permite regenerar desde
las descargas originales sin usar las proyecciones.

Las páginas de procedencia y el texto de CC BY-SA 4.0 están preservados.
Los datos derivados conservan la atribución a Wiktionary y Kaikki/Wiktextract.
No se convierten las flexiones, alternativas o traducciones en sinónimos.

Ver [README.md](../../README.md) para construcción, formatos y mantenimiento.
