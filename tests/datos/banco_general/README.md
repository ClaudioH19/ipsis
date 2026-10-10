# Banco documental de regresión

Cuatro temas independientes, representados en cuatro formatos: RRHH/Markdown,
compras/PDF digital, mantenimiento/DOCX y logística/texto. Las carpetas
`bueno`, `medio` y `malo` contienen versiones de los mismos hechos con
distinta estructura documental. Hay 28 casos por calidad: 12 respondibles,
12 negativos de esos temas, dos preguntas ambiguas de regresiones anteriores,
un saludo y una consulta ajena al corpus (84 preguntas en total).
No se usan documentos ni datos personales reales.

Los valores esperados se definieron en el constructor a partir de los hechos
escritos: 12 días hábiles/jefatura de Personas; 18 días corridos/Abastecimiento;
45 días/desconectar la alimentación eléctrica; entre 2 y 6 grados Celsius/
después de verificar el embalaje. Los distractores contienen otros números.
El cambio de formato no altera esos datos, sus unidades ni condiciones.

El corpus está congelado mediante SHA-256 y evidencia literal con offsets.
Evaluar comprueba esas referencias, sin reconstruirlas a partir de la salida
del motor. `uso: regresion` impide calibrar con este banco. Las divisiones
dev/test conservan el contrato común, pero ambas participan en la regresión;
no constituyen una evaluación ciega de promoción.
La versión 1.1.0 agrega «¿Quién lo aprueba?» y «¿Cuánto es?» sin antecedente;
conserva documentos, hashes de corpus y evidencias de los 26 casos originales.

`linea_base.json` conserva la medición real de los tres perfiles sobre las
tres calidades. Es una referencia de comportamiento, no una garantía de
precisión. Los casos no contestados y los errores conocidos permanecen
visibles; no se modifican las preguntas para hacer pasar modelos.

Comandos, CI, variantes, actualización explícita de referencias y límites:
[procedimiento](../../../herramientas/evaluacion/README.md).
El formato malo incluye encabezados repetidos, orden irregular, texto
pegado, espacios, ruido y un cierre truncado. Mantiene íntegros los hechos;
no cubre escaneos/OCR ilegible, tablas complejas ni bytes dañados.
