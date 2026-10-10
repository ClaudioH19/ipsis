# Banco de erratas

Preguntas existentes con errores de tipeo realistas, para medir la **robustez**
de la normalización: de lo que el sistema responde bien con la pregunta limpia,
cuánto sigue respondiendo cuando viene con erratas.

- `diseno/`: 118 preguntas por idioma desde el [banco de garantías](../banco_garantias/)
  (con su corpus). Se usa para diseñar la capa de normalización.
- `validacion/`: 87 preguntas por idioma desde el [banco de validación](../banco_validacion/).
  Se mide una vez antes y otra después, solo en agregados.

Cada caso guarda la pregunta limpia (`original`) y los tipos de errata
(`erratas`): omisión, duplicación, transposición, tecla vecina, confusión por
sonido (s/z/c, b/v, ll/y, ç/ss, ie/ei…), dos palabras pegadas o una separada.
La mitad va además sin tildes ni signos de apertura, como se escribe apurado.
Las trampas también llevan erratas: una corrección que las vuelva respondibles
es un error.

Generado, no escrito a mano: `python tests/datos/banco_erratas/generar.py`
(determinista: la semilla sale del id del caso) y luego
`python tests/datos/banco_erratas/construir.py`. Como todo banco sintético,
no reemplaza preguntas reales de usuarios.
