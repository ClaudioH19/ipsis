# Originales de los tesauros complementarios

Descargas fijadas de LibreOffice, commit
`32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4`, preparadas el 2026-10-06.

Los `.dat.gz` son compresiones sin pérdida de los archivos originales.
Los hashes de `fuentes.json` corresponden a los bytes descomprimidos;
`manifest.json` registra además tamaño y hash de cada archivo almacenado.
Los avisos de cada fuente se conservan sin modificaciones. No se cambia
su licencia por almacenarlos junto al código AGPL.

Español: ISO8859-1. Inglés y portugués: UTF-8. No editar ni mezclar estos
originales. Revisar las filas y etiquetas en `*.thesaurus.tsv`; cambiar
el extractor para producir nuevas vistas reproducibles.

Desde la raíz, `python herramientas/sinonimos/construir.py all --check`
verifica la reconstrucción offline. El procedimiento completo está en
[README.md](../../README.md).
