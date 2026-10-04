# Multilenguaje: paquetes de idioma

## 1. Propósito

Que la librería funcione en cualquier idioma sin texto de un idioma en el
código Python: todo lo que depende del idioma vive en un paquete.

## 2. Alcance y no-alcance

- **Alcance:** stemmer, entidades con palabras (números, meses, plazos,
  referencias a partes del documento), marcadores de excepción y condición,
  patrones conversacionales, mensajes, textos del widget y tonos.
- **No-alcance:** detectar el idioma de cada pregunta y corpus con varios
  idiomas a la vez.

## 3. Entradas y salidas versionadas

- `rag/recursos/idiomas/<código>.yaml`: paquete del idioma.
- `rag/recursos/tonos/<código>/<tono>.yaml` y `_reglas.yaml`: los 7 tonos y
  su linter.
- `configuracion/idioma.yaml` (opcional): sobrescrituras del proyecto.
- El manifiesto del índice guarda el stemmer: cambiar de idioma exige
  reindexar.

## 4. Algoritmo y desempates

- `asistente.yaml::idioma` elige el paquete. Una variante regional (`pt-br`)
  usa el de su idioma base. Un código sin paquete funciona con las reglas
  universales, `terminos()` sin stem y los textos en inglés; `rag doctor` lo
  advierte.
- **Entidades universales:** cifras, porcentajes, fechas numéricas y montos
  con moneda. Su `valor_norm` no depende del idioma (`2024-03-15`, `6_mes`).
- **Entidades del paquete:** las que se escriben con palabras («seis meses»,
  «quince de marzo», «artículo cuarto»).
- **Oraciones:** una sola `dividir_oraciones()` con `. ? ! 。 ！ ？ ؟ ।`.
- **Tonos:** 7 tonos × 18 situaciones × 5 variantes por idioma. La variante
  se elige por (sesión, turno, situación) y no se repite en turnos seguidos.

## 5. Supuestos

Pregunta y corpus en el idioma del proyecto. Los modelos son multilingües:
una pregunta en otro idioma puede funcionar, pero `s_oov` alto suele llevar a
abstenerse (lado seguro).

## 6. Invariantes

- Ningún texto de un idioma en Python (regla de código). El widget recibe
  sus textos del paquete vía `/config` y solo trae textos de respaldo en
  español por si `/config` no responde.
- Los tonos incluidos son neutros: sin regionalismos, sin formas con género
  para la persona y sin saludos según la hora (prueba de neutralidad). En los
  textos propios de un proyecto es un aviso.
- El linter de tonos exige una línea de hasta 200 caracteres, sin dígitos,
  URLs, HTML ni Markdown, y signos ¡ ¿ cerrados.

## 7. Parámetros y defaults

Paquetes incluidos: `es`, `en` y `pt`. Idioma por defecto de `rag init`: el
de `--idioma` (`es` si no se indica).

## 8. Complejidad y recursos

Carga única por proceso, con caché.

## 9. Fallos y fallback

Código de idioma inválido: error con los disponibles. Sin paquete: inglés
universal y aviso.

## 10. Seguridad y privacidad

Sin efecto.

## 11. Pruebas técnicas

`tests/lenguaje/` (paquetes, entidades, linter de 1.890 plantillas y
neutralidad) y el banco universal en tres idiomas.

## 12. Limitaciones

- Sin detección de idioma por pregunta.
- El banco universal es multilingüe, no cross-lingual: no mide preguntas en
  un idioma sobre un corpus en otro.

## 13. Referencias y procedencia

- [snowballstemmer](https://pypi.org/project/snowballstemmer/) (29 stemmers,
  28 idiomas).
- Unicode UAX #29 para los límites de palabra (`\w+`).

## 14. Estado

Estable para `es`, `en` y `pt`; experimental para otros idiomas.
