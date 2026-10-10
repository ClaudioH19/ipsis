# Reranker (cross-encoder)

## 1. Purpose

Reorder the retrieval candidates by reading the question and the passage
together, so the reader receives the most relevant ones.

## 2. Scope and non-scope

- **Scope:** score (question, passage) pairs, sort and keep `rerank_k`;
  contribute `s_rr` to the domain signal.
- **Non-scope:** denying the domain or deciding the answer.

## 3. Versioned inputs and outputs

Input: the question and the candidates' texts. Output: one logit per pair
(`ctx.puntajes_rerank`) and the reordered list.

## 4. Algorithm and tie-breaking

1. `RerankerOnnx` tokenizes each pair and gets a logit.
2. It sorts by descending logit; ties by `chunk_id`.
3. It keeps `rerank_k` candidates.
4. `s_rr = sigmoid(logit of the first)`.

The policy's domain signal is `max(s_ret, s_rr)`: a cross-encoder's logits
order well within a query but are not an absolute scale (mmarco gives 0.08
to a correct passage). That is why the reranker can **confirm** the domain,
never deny it.

## 5. Assumptions

The model is multilingual and the question and corpus languages match.

## 6. Invariants

It modifies no texts or offsets; it only changes the order and trims the
list.

## 7. Parameters and defaults

| Profile | Model | `rerank_k` |
|---|---|---|
| light | — (does not run) | 0 |
| medium | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1, published int8 (118 M, 119 MB) | 4 |

`rerank_candidates` (medium: 5) is how many fused candidates the reranker
scores; the rest keep their fusion order behind them. With semantic reading
the fine ordering is per sentence, so scoring 20 long chunks was redundant: on
678 questions (query, informal and guarantee banks) 20 → 5 candidates kept
308 correct answers and 11 errors, and cut medium's p50 from 5.3 s to 2.5 s
(reranking 4.0 s → 0.64 s) on a 2-thread CPU. With 8 candidates: 307 and 11.

## 8. Complexity and resources

Historical p95 on the universal bank: 293 ms (medium) and 1,207 ms (former heavy, BGE).
mmarco scored 20 passages in 124 ms.
Horizon multilingual base/small are supported experimental replacements;
on the Spanish query bank they added no correct answer, one accepted error
and 1.6–4× the p95. BGE remains available
by override. See [candidate regression](../../herramientas/evaluacion/README.md).

## 9. Failures and fallback

- Missing model: `ipsis doctor` and `/ready` ask for `ipsis models download`.
- Lexical early exit (no candidate with a focus term): the stage does not
  run.

## 10. Security and privacy

Local inference on CPU (onnxruntime); nothing leaves the machine.

## 11. Technical tests

`tests/consulta/` (the stage with an in-memory double) and `modelos` tests
with the real ONNX.

## 12. Limitations

On the universal bank, the former heavy (BGE) did not separate the two
same-topic traps that medium does not separate either: the large reranker
bought no material safety with that evidence. On colloquial paraphrases
mmarco can rank another passage of the same document above the one that
answers; no larger reranker fixed that in the measured banks.

## 13. References and provenance

- [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1) (Apache-2.0).
- [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) (Apache-2.0).
- Discarded: `jinaai/jina-reranker-v2-base-multilingual` (non-commercial
  license).

## 14. Status

Stable.
