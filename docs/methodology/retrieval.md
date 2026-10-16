# Hybrid retrieval

Status: current. Hybrid retrieval is used by v1 and v2; the thresholds that use `s_ret` belong to v1.

## 1. Purpose

Find the corpus fragments that may answer the question, combining semantic
similarity (dense vector) and lexical match (BM25), without writing
anything.

## 2. Scope and non-scope

- **Scope:** encode the question, search Qdrant and return candidates with
  their full payload (text, document, section and offsets); entity-directed
  retrieval.
- **Non-scope:** deciding whether there is an answer (the
  [policy](policy.md) does it), reordering with a model (the
  [reranker](reranker.md) does it) or choosing the span.

## 3. Versioned inputs and outputs

- **Input:** the question, the profile's `retrieve_n`, the mode (`hybrid`,
  `dense` or `sparse`) and an optional entity filter.
- **Output:** ordered `RetrievalCandidate`s (id, payload, score) and the
  `s_ret` signal.
- **Index:** the `{collection}_{model}_v{n}` collection with its manifest in
  `.ipsis/index/` (model, dimension, stemmer, corpus hash, payload version).
  If the model changes, another collection is created: vectors of different
  models are never mixed.

## 4. Algorithm and tie-breaking

1. The dense encoder (e5) encodes `query: <question>`; passages were indexed
   with `passage: `. Mean pooling and L2 norm.
2. The question goes through `terminos()` (see [lexical](lexical.md)) and
   forms the sparse BM25 vector (1 per unique term).
3. Qdrant runs both searches as `prefetch` and fuses them with native
   **RRF** (`query_points`). In `dense` mode only the dense one; in
   `sparse`, only BM25 (the `bm25` diagnostic profile).
4. `s_ret` = dense cosine of the first candidate normalized from the model's
   floor: `(cosine − floor) / (1 − floor)`, clipped to [0, 1]. For e5 the
   floor is 0.7 (typical cosine between unrelated texts).
5. **Directed retrieval:** if an entity of the question (date, amount,
   article…) exists in the corpus inventory but did not reach the
   candidates, it is searched with an exact filter on `valor_norm`.
6. Ties: Qdrant's order; the reranker breaks ties by `chunk_id`.

## 5. Assumptions

- The corpus is in a single language, the project's.
- With the default structural preparation (`structural_v1`), and with `CH-SEC` and `CH-F256S`, a fragment
  never crosses sections and keeps its section path. `CH-F256` (and the older fixed-size strategies) joins
  whole blocks until about 256 words and **can cross sections**; its overlap (15 %) repeats text from the
  neighbouring fragment. Use `CH-F256S` or the structural preparation when sibling sections must stay apart.

## 6. Invariants

- The retrieved payload keeps document, section, text and offsets.
- The question is encoded once per query.
- Retrieval neither modifies nor writes text.
- A profile's index only opens if its manifest is compatible (`ipsis doctor`
  checks it).

## 7. Parameters and defaults

| Parameter | light | medium |
|---|---|---|
| Dense model | e5-small (384) | e5-small (384) |
| `retrieve_n` | 10 | 20 |
| BM25 `k1`, `b` | 1.2 / 0.75 | 1.2 / 0.75 |

They are tuned in `config/engine.yaml::profile_overrides`.

## 8. Complexity and resources

Encoding the question and querying Qdrant takes 20–60 ms with e5-small and
50–150 ms with the previous e5-base on CPU (historical). Model disk: 470 MB
(e5-small), 1.1 GB (e5-base) and 313 MB (Granite R2 x86 AVX2). Granite uses CLS
pooling without e5 prefixes or its cosine floor. Other supported candidates
declare their own contracts in the catalog; the deployment corpus needs
calibration. See [general regression](../../herramientas/evaluacion/README.md).

## 9. Failures and fallback

- No index, or an incompatible one: the service is not ready and `/ready`
  says `ipsis index`.
- No candidates: the policy abstains.
- Local Qdrant locked by another process: an actionable error (stop
  `ipsis serve`).

## 10. Security and privacy

The question never leaves the machine: the model and Qdrant are local. The
query log is off by default.

## 11. Technical tests

`tests/indice/`, `tests/consulta/` (engine with test doubles), `slow` tests
with the real model and the characterization
(`tests/integracion/test_caracterizacion.py`).

## 12. Limitations

- With very small corpora (5 documents), dense and BM25 retrieve almost the
  same: the universal bank has no power to measure the dense contribution.
- Qdrant's local mode does not apply payload indexes; with large corpora,
  Qdrant as a server is better.

## 13. References and provenance

- Wang et al., *Multilingual E5 Text Embeddings* (2024);
  [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small).
- Cormack et al., *Reciprocal Rank Fusion* (SIGIR 2009).
- [Qdrant: hybrid queries](https://qdrant.tech/documentation/concepts/hybrid-queries/).

## 14. Status

Stable. The thresholds that use `s_ret` (v1 engine) depend on each project's
[calibration](calibration.md).
