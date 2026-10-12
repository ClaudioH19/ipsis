# Banco de términos

Preguntas que nombran un término con otras palabras que las del documento: «la
primera práctica» por «Práctica Profesional I (P1)», «el comité» por lo que el
reglamento definió «en adelante», «cuánto vale» por una fila de tabla de
ponderaciones. Mide el grafo de términos del índice (siglas, glosario, «en
adelante», ordinales), las tablas con encabezado y la intención de duración.

- `diseno/`: 17 casos por idioma (es/en/pt) sobre un reglamento de prácticas y
  uno de bibliotecas, con los documentos del banco de consultas como
  distractores. Se puede mirar para diseñar.
- `validacion/`: 16 casos por idioma sobre reglamentos distintos (titulación y
  beneficios). **Retenido**: se escribió el 2026-10-10 antes de implementar el
  grafo y se mide una vez antes y otra después, solo en agregados.

Fuentes: `<conjunto>/<idioma>/casos.yaml` y `corpus/`. Derivados:
`python tests/datos/banco_terminos/construir.py`.
