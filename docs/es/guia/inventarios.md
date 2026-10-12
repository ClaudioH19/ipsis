# Recuperación de inventarios

Se admiten XLSX, XLS, CSV y TSV, tanto con `ipsis load` como desde Documentos
en el panel. Cada resultado conserva la fila completa del producto con sus
etiquetas de columna y referencias de origen. En v2 se muestran hasta tres
fuentes ordenadas, con contexto desplegable y continuación de búsqueda.

```bash
ipsis load ./inventario.xlsx
ipsis index
ipsis serve --demo --open
```

La página de prueba utiliza el widget y los estilos del proyecto. `--open`
la abre cuando el servicio puede servirla. Para habilitar también el panel,
usa `ipsis serve --mode development --open`: la consola imprime un token
temporal de administración. La página de prueba por sí sola no habilita el
panel ni modifica sus controles de acceso.

| Formato | Contrato de lectura |
|---|---|
| XLSX | Todas las hojas; las tablas declaradas conservan sus rangos y encabezados. Sin tablas, la primera fila no vacía se usa como etiquetas, con aviso. Las notas fuera de tablas y las tablas sin encabezados usan letras de columna. |
| XLS | Todas las hojas y sus valores guardados; primera fila no vacía como etiquetas, con aviso. |
| CSV | Primera fila no vacía como etiquetas; separador coma, punto y coma, tabulación o barra detectado. Admite celdas entrecomilladas con separadores y saltos de línea. |
| TSV | El mismo contrato, con tabulación como separador. |

Excel conserva localizadores como `'Bodega'!C2`. CSV/TSV cuentan registros
lógicos: una celda multilínea no inicia otro registro. Los offsets de las
citas corresponden al texto extraído, no a posiciones en el archivo binario.
Las celdas vacías mantienen sus columnas y el stock `0` se conserva. Los
códigos textuales como `0007` mantienen sus ceros; también se admite el formato
entero simple `0000` de Excel. Las fechas se presentan como texto ISO.
Otros formatos visuales de Excel, como moneda o porcentaje, muestran el valor
numérico almacenado. CSV/TSV admiten UTF-8 con BOM y Windows-1252 con aviso.

Las fórmulas XLSX nunca se ejecutan. Se recupera el resultado guardado si
existe; de lo contrario se conserva la fórmula literal, con aviso. XLS aporta
valores guardados sin las expresiones. Pedir «total de stock» no ejecuta una
suma ni crea una respuesta calculada: el motor recupera los registros.

Las hojas ocultas se incluyen con aviso. Las celdas combinadas no propagan
valores a otros productos. No se extraen macros ni objetos incrustados y no
se admiten archivos protegidos por contraseña. Se requiere una fila clara de
encabezados o tablas declaradas; los tableros arbitrarios de Excel y múltiples
regiones sin encabezados requieren preparación. Se rechazan archivos sin
registros de datos y rangos de más de 500.000 celdas por hoja o archivo delimitado.

El fragmentado normal utiliza `CH-ROW1` para inventarios: una fila con sus
etiquetas, sin mezclar productos vecinos. `ipsis prepare` también admite
estos formatos en su copia estructural y permite revisar avisos y tablas
antes de indexar. El parser participa en la huella de vigencia del índice.
