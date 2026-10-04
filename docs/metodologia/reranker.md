# Reranker (cross-encoder)

## 1. Propósito

Reordenar los candidatos de la recuperación leyendo pregunta y pasaje
juntos, para que el lector reciba los más pertinentes.

## 2. Alcance y no-alcance

- **Alcance:** puntuar pares (pregunta, pasaje), ordenar y conservar
  `rerank_k`; aportar `s_rr` a la señal de dominio.
- **No-alcance:** negar el dominio ni decidir la respuesta.

## 3. Entradas y salidas versionadas

Entrada: pregunta y textos de los candidatos. Salida: un logit por par
(`ctx.puntajes_rerank`) y la lista reordenada.

## 4. Algoritmo y desempates

1. `RerankerOnnx` tokeniza cada par y obtiene un logit.
2. Ordena por logit descendente; empate por `chunk_id`.
3. Conserva `rerank_k` candidatos.
4. `s_rr = sigmoide(logit del primero)`.

La señal de dominio de la política es `max(s_ret, s_rr)`: los logits de un
cross-encoder ordenan bien dentro de una consulta pero no son una escala
absoluta (mmarco da 0,08 a un pasaje correcto). Por eso el reranker puede
**confirmar** el dominio, no negarlo.

## 5. Supuestos

El modelo es multilingüe y el idioma de pregunta y corpus coinciden.

## 6. Invariantes

No modifica textos ni offsets; solo cambia el orden y recorta la lista.

## 7. Parámetros y defaults

| Perfil | Modelo | `rerank_k` |
|---|---|---|
| light | — (no se ejecuta) | 0 |
| medium | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1, int8 publicado (118 M, 119 MB) | 4 |
| heavy | onnx-community/bge-reranker-v2-m3-ONNX, int8 (568 M, 571 MB) | 8 |

## 8. Complejidad y recursos

p95 medido en el banco universal: 293 ms (medium) y 1.207 ms (heavy). En
P7.1, mmarco puntuó 20 pasajes en 124 ms.

## 9. Fallos y fallback

- Modelo ausente: `ipsis doctor` y `/ready` piden `ipsis modelos descargar`.
- Salida temprana léxica (ningún candidato con término foco): la etapa no
  corre.

## 10. Seguridad y privacidad

Inferencia local en CPU (onnxruntime); nada sale de la máquina.

## 11. Pruebas técnicas

`tests/consulta/` (etapa con doble en memoria) y pruebas `modelos` con el
ONNX real.

## 12. Limitaciones

Con el banco universal, heavy no separa las dos trampas del mismo tema que
medium tampoco separa: el reranker grande no compra seguridad material con
esa evidencia.

## 13. Referencias y procedencia

- [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1) (Apache-2.0).
- [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) (Apache-2.0).
- Descartado: `jinaai/jina-reranker-v2-base-multilingual` (licencia no
  comercial).

## 14. Estado

Estable.
