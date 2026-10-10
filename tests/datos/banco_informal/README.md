# Banco informal de validación

32 preguntas por idioma (es/en/pt) escritas como las escribe un usuario
apurado: minúsculas, sin tildes ni signos, erratas («pasword», «hows»),
abreviaturas («q», «pa», «wfh», «pc»), modismos regionales («refri», «al
tiro», «der pau», «home office») y palabras que el documento no usa.

- 20 paráfrasis respondibles, una o más por documento;
- 8 trampas del mismo tema, cada una junto a su paráfrasis («pasajes de bus»
  frente a «pasajes de avión»);
- 2 premisas falsas y 2 preguntas fuera de dominio.

El corpus es una copia byte a byte del [banco de consultas](../banco_consultas/)
(lo comprueba `tests/evaluacion/test_banco_consultas.py`): el banco mide la
forma de preguntar, no otros documentos.

**Es un banco de validación.** Ninguna pregunta se usó para diseñar reglas ni
elegir umbrales: el diseño se hace con el banco de consultas y este banco
confirma, una vez, si el cambio generaliza. No se ajusta nada para que pase.
Como todo banco sintético, es de regresión y no certifica un cliente.

Fuentes: `<idioma>/casos.yaml`. Derivados versionados (`banco.jsonl`,
`manifiesto.json`): `python tests/datos/banco_informal/construir.py`.
Medición: `python herramientas/evaluacion/general.py --profiles light,medium
--qualities none --extra-bank tests/datos/banco_informal/es/manifiesto.json …
--no-baseline`.
