# Lector QA extractivo

## 1. Propósito

Marcar, dentro de un pasaje, el tramo literal que responde la pregunta, o
decir que el pasaje no la responde (estilo SQuAD 2.0). Da la señal `s_qa`.

## 2. Alcance y no-alcance

- **Alcance:** leer `leer_m` candidatos, elegir el mejor tramo y compararlo
  con la opción «sin respuesta».
- **No-alcance:** redactar; decidir el estado final (la
  [política](politica.md) manda sobre el lector).

## 3. Entradas y salidas versionadas

Entrada: pregunta y pasajes. Salida: `LecturaQA` por pasaje con
`indice_pasaje`, `inicio`, `fin` (offsets de carácter), `texto ==
pasaje[inicio:fin]`, `prob_respuesta` y `prob_sin_respuesta`. El contrato
HTTP publica `respuesta_exacta` solo si el estado es `ok`.

## 4. Algoritmo y desempates

1. El pasaje se lee en ventanas de `max_tokens_pasaje` tokens con `stride`
   de solapamiento (truncado `only_second`).
2. Por ventana se consideran los 20 mejores bordes de inicio y de fin
   (tramos de hasta 30 tokens) y gana la suma de logits más alta.
3. Se compara con «sin respuesta» (`[CLS]`): softmax sobre {mejor tramo, sin
   respuesta}.
4. Gana la ventana con mayor `prob_respuesta`; los offsets se recortan de
   espacios.
5. `s_qa = max(0, prob_respuesta − prob_sin_respuesta)`; la política usa el
   máximo entre pasajes.

El lector recibe una ventana de `max_caracteres_lectura` alrededor de la
oración ancla (centrada, con contexto a ambos lados), no el pasaje completo:
bajó la lectura de ~1 s a ~0,5 s en medium. Lo que se **muestra** empieza en
la oración ancla y solo agrega contexto a la derecha.

## 5. Supuestos

Pregunta y corpus en el mismo idioma; el modelo es multilingüe (también lee
una pregunta en inglés sobre un texto en español, sin garantía).

## 6. Invariantes

- El tramo es siempre un substring literal del pasaje.
- En `relacionado` nunca se publica el tramo como respuesta.

## 7. Parámetros y defaults

| Perfil | `leer_m` | `max_caracteres_lectura` | Ventanas |
|---|---|---|---|
| medium | 2 | 600 | 384 tokens, stride 128 |
| heavy | 4 | 1200 | 384 tokens, stride 128; además, concordancia |

Modelo: [dewdev/mdeberta-v3-base-squad2-onnx](https://huggingface.co/dewdev/mdeberta-v3-base-squad2-onnx),
exportación de `timpal0l/mdeberta-v3-base-squad2` (MIT, 278 M), en **fp32**:
el int8 publicado da logits planos y el int16 no carga (medido en P7.2).

**Concordancia (heavy):** si los dos mejores tramos confiables de pasajes
distintos traen entidades del mismo tipo con valores distintos, un `ok` baja a
`relacionado` (regla `concordancia`).

## 8. Complejidad y recursos

50–110 ms por pasaje; p95 de la etapa en el banco universal: 513 ms (medium)
y 874 ms (heavy). Disco: 1,1 GB.

## 9. Fallos y fallback

- Sin modelo: el perfil no arranca y la acción es `ipsis modelos descargar`.
- Salida temprana léxica: no corre.

## 10. Seguridad y privacidad

Inferencia local.

## 11. Pruebas técnicas

`tests/modelos/` con el ONNX real (offsets verificados: «6 meses», «24
meses»; la pregunta por la garantía contra el pasaje del filtro da
`s_qa = 0`) y la etapa con dobles en `tests/consulta/`.

## 12. Limitaciones

- El lector da el mismo tramo a «¿Cuándo vence la garantía?» y a «¿Qué
  incluye la garantía?»: distinguir el tipo de respuesta esperado exigiría
  reglas por idioma. Lo cubren `s_oov < τ_oov_ok` y `s_foco`.
- Dos trampas del banco universal (`es-trampa-001`, `en-trampa-004`) dan
  `s_qa` 0,82–0,83 con `τ_ok` 0,8: falsos `ok` en medium y heavy sin calibrar.
  Con `τ_ok` 0,85 desaparecen sin perder cobertura; el umbral de cada cliente
  lo elige `ipsis calibrar`.
- Heavy usa el mismo lector que medium: `deepset/xlm-roberta-large-squad2`
  no tiene un ONNX confiable con licencia declarada.

## 13. Referencias y procedencia

- Rajpurkar et al., *Know What You Don't Know: Unanswerable Questions for
  SQuAD* (2018).
- He et al., *DeBERTaV3* (2021).

## 14. Estado

Estable; `τ_ok` pendiente de calibración por proyecto.
