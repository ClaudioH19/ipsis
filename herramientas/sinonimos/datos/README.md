# Fuentes originales guardadas

Las tres fuentes fueron aprobadas el 2026-10-06. Esta carpeta conserva la
descarga completa para reconstruir el léxico y cambiar filtros sin red,
incluso después de eliminar `.cache` o clonar el repositorio en otra máquina.

En `fuentes/`:

- `es.tab.gz`: TAB original de MCR/OMW, comprimido sin pérdida.
- `pt.tab.gz`: TAB original de OpenWN-PT/OMW, comprimido sin pérdida.
- `en.xml.gz`: archivo original de Open English Wordnet 2025, sin cambios.
- Avisos `*.LICENSE`, `*.citation.bib` y `en.WNDB_License.txt` originales.
- `manifest.json`: tamaño y SHA-256 de los archivos almacenados, y la
  especificación de descarga original. Para TAB el hash de origen se verifica
  después de descomprimir; el hash de almacenamiento corresponde al gzip.

Los originales y sus avisos conservan las licencias especificadas en
[`fuentes.json`](../fuentes.json) y en los propios archivos. La compresión
de los TAB no modifica sus datos. No editar estos originales para corregir
una equivalencia: las correcciones futuras deben quedar en tablas separadas.

El comando habitual es offline:

```bash
python herramientas/sinonimos/construir.py all
python herramientas/sinonimos/construir.py all --check
```

El léxico maestro y la tabla filtrada resultantes están en
`ipsis/recursos/sinonimos/`. Una actualización de versión es una operación
explícita con `--download`, una nueva carpeta de revisión y nuevos hashes.
No hace falta repetir la descarga para el desarrollo habitual.

Estos originales se incluyen en el sdist para desarrollo, mientras el wheel
contiene las tablas derivadas y sus atribuciones.

Las ampliaciones posteriores también se conservan localmente:

- [tesauros/README.md](tesauros/README.md): cuatro tesauros LibreOffice/MyThes.
- [diccionarios/README.md](diccionarios/README.md): descargas completas
  Wiktionary/Kaikki es/en/pt, sin pérdida, con proyecciones léxicas verificadas.

`all` y `all --check` incluyen estas fuentes sin consultar la red.
