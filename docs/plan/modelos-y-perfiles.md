# Modelos y perfiles

## 1. Runtime: ONNX con dependencias mínimas

| Dependencia | Para qué |
|---|---|
| `onnxruntime` | Inferencia en CPU de los tres tipos de modelo |
| `tokenizers` | Tokenizadores de Hugging Face, con offsets de carácter |
| `huggingface-hub` | Descarga a la caché local y modo offline |
| `snowballstemmer` | Stemmer de la capa léxica ([lexico-y-multilenguaje.md](lexico-y-multilenguaje.md)) |
| `qdrant-client` | Índice denso + disperso |

- **Sin torch, sin sentence-transformers y sin fastembed.** Los tres tipos de
  modelo comparten una base propia, `ModeloOnnx` (Template Method), que
  carga la sesión y el tokenizador. Cada subclase solo implementa lo
  específico:
  - `CodificadorDenso`: prefijo `query: `/`passage: `, pooling promedio y
    normalización L2.
  - `RerankerOnnx`: logit del par (pregunta, pasaje).
  - `LectorOnnx`: logits de inicio y fin, ventanas con solapamiento y
    comparación con el «sin respuesta» de `[CLS]`, como en SQuAD 2.0.
- **Cuantización int8:** si el repositorio publica la variante, se usa; si
  no, `rag modelos exportar` la genera con
  `onnxruntime.quantization.quantize_dynamic`. Es solo para desarrollo y usa
  el extra `[exportar]`, con `optimum` y `torch`.
- **Hilos:** `intra_op_num_threads` configurable y una sola sesión por modelo
  y proceso.

## 2. Candidatos

✔ = confirmado en una ficha consultada el 2026-10-03. ⚠ = la tarea P5.1 lo
verifica antes de usarlo.

### Codificador denso (define el índice)

| Modelo | Parámetros | Dim. | Licencia | Perfil |
|---|---|---|---|---|
| `intfloat/multilingual-e5-small` | ~118M ⚠ | 384 | MIT ⚠ | light, medium |
| `intfloat/multilingual-e5-base` | ~278M ⚠ | 768 | MIT ⚠ | heavy |
| `BAAI/bge-m3` | ~568M ⚠ | 1024 | MIT ⚠ | candidato para heavy (indexación lenta en CPU) |

`light` y `medium` comparten índice. Pasar a `heavy` obliga a reindexar.

### Disperso: BM25 propio

No es un modelo. Lo generan `terminos()` y `EstadisticasLexicas`: TF
saturado calculado en el cliente e IDF aplicado en Qdrant (`modifier: idf`).
Ver [lexico-y-multilenguaje.md](lexico-y-multilenguaje.md) §4.

### Reranker cross-encoder

| Modelo | Tamaño | Licencia | Idiomas | Perfil |
|---|---|---|---|---|
| `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | MiniLM 12 capas, ~470 MB fp32 ✔ | Apache-2.0 ✔ | 14 (mMARCO) ✔ | **medium** |
| `BAAI/bge-reranker-v2-m3` | ~568M ⚠ | Apache-2.0 ⚠ | ~100 | **heavy** |
| `jinaai/jina-reranker-v2-base-multilingual` | 278M ✔ | CC-BY-NC ⚠ | multilingüe | **excluido** (no comercial) |

El repositorio de mmarco publica ONNX ✔.

### Lector QA extractivo (SQuAD 2.0)

| Modelo | Parámetros | Licencia | Idiomas | Perfil |
|---|---|---|---|---|
| `timpal0l/mdeberta-v3-base-squad2` | 278M ✔ | MIT ✔ | 94 ✔ | **medium** |
| `deepset/xlm-roberta-large-squad2` | ~560M ⚠ | CC-BY-4.0 ⚠ (atribución) | 100+ | **heavy** |
| `deepset/xlm-roberta-base-squad2` | ~278M ⚠ | CC-BY-4.0 ⚠ | 100+ | alternativa para medium |
| `mrm8488/distill-bert-base-spanish-wwm-cased-finetuned-spa-squad2-es` | DistilBERT ⚠ | ⚠ | solo español | solo referencia en el benchmark |

Hay una exportación ONNX publicada de mdeberta
(`dewdev/mdeberta-v3-base-squad2-onnx`) ✔. Estos lectores se entrenaron en
inglés: su calidad en cada idioma se **mide** con `rag benchmark`.

## 3. Perfiles

Archivos: `rag/recursos/perfiles/{light,medium,heavy}.yaml`. El proyecto
sobrescribe en `configuracion/motor.yaml`. Además existe `bm25`, que no se
instala: es un perfil de diagnóstico de `rag benchmark` que muestra cuánto
aportan el denso y los modelos.

```yaml
# rag/recursos/perfiles/medium.yaml (borrador)
perfil: medium
presupuesto_p95_ms: 1000
modelos:
  denso: intfloat/multilingual-e5-small
  reranker: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
  lector: timpal0l/mdeberta-v3-base-squad2
  cuantizacion: int8
lexico: {k1: 1.2, b: 0.75, max_terminos_foco: 2}
cascada:
  recuperar_n: 20
  rerank_k: 4
  leer_m: 2
  max_tokens_pasaje: 384
  stride: 128
  salida_temprana_sin_foco: true
etapas: [conversacional, analisis, recuperacion, filtros, reranking, lectura, seleccion, politica, verificacion, redaccion]
umbrales_por_defecto:        # conservadores; `rag calibrar` los reemplaza
  oov: 0.60
  dominio: 0.30
  relacionado: 0.50
  foco: 0.50                 # al menos uno de los 2 términos foco
  ok: 0.80
  cov: 0.60                  # solo lo usa light
```

| Parámetro | light | medium | heavy |
|---|---|---|---|
| Presupuesto p95 | 150 ms | 1.000 ms | 4.000 ms (máximo 5.000) |
| Denso | e5-small | e5-small | e5-base |
| `recuperar_n` | 10 | 20 | 30 |
| Reranker / `rerank_k` | — | mmarco int8 / 4 | bge-reranker-v2-m3 int8 / 8 |
| Lector / `leer_m` | — | mdeberta int8 / 2 | xlm-roberta-large int8 / 4 |
| Decide `ok` con | `s_ret`, `s_cov`, `s_foco`, `acuerdo` | `s_qa`, `s_foco` | `s_qa`, `s_foco` + concordancia |
| Extras | — | — | recuperación dirigida por entidad; concordancia entre los 2 mejores tramos |

### Latencia estimada (P7.6 la mide de verdad)

| Etapa | light | medium | heavy |
|---|---|---|---|
| Análisis + señales léxicas | < 5 ms | < 5 ms | < 5 ms |
| Codificar pregunta + Qdrant | 20–60 ms | 20–60 ms | 50–150 ms |
| Reranker | — | 100–300 ms | 1–2 s |
| Lector | — | 200–500 ms | 1–2 s |
| Redacción y verificación | < 10 ms | < 10 ms | < 20 ms |

En preguntas sin términos foco en los candidatos, la salida temprana deja a
medium y heavy con latencias de light.

## 4. Licencias

`rag modelos listar` muestra la licencia y la atribución de cada modelo del
perfil, y `rag modelos descargar` imprime las obligaciones de atribución
(CC-BY-4.0). Ningún modelo con licencia no comercial puede ser default.
