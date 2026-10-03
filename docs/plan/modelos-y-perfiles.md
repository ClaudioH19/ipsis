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

## 2. Modelos (verificados en P5.1, 2026-10-03, con la API de Hugging Face)

Licencia y parámetros salen de la ficha de cada repositorio. «Archivo» es el
ONNX que descarga `rag modelos descargar`.

| Uso | Modelo (ficha) | Licencia | Parámetros | Archivo ONNX | Perfil |
|---|---|---|---|---|---|
| Denso | [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) | MIT | 118M | `onnx/model.onnx` (470 MB, fp32) | light, medium |
| Denso | [intfloat/multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base) | MIT | 278M | `onnx/model.onnx` (1,1 GB, fp32) | heavy |
| Reranker | [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1) | Apache-2.0 | 118M | `onnx/model_quint8_avx2.onnx` (119 MB; en ARM `model_qint8_arm64.onnx`) | medium |
| Reranker | [onnx-community/bge-reranker-v2-m3-ONNX](https://huggingface.co/onnx-community/bge-reranker-v2-m3-ONNX) (exportación de [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3), Apache-2.0) | Apache-2.0 (del modelo base; la exportación no declara licencia propia) | 568M | `onnx/model_int8.onnx` (571 MB) | heavy |
| Lector QA | [dewdev/mdeberta-v3-base-squad2-onnx](https://huggingface.co/dewdev/mdeberta-v3-base-squad2-onnx) (exportación de [timpal0l/mdeberta-v3-base-squad2](https://huggingface.co/timpal0l/mdeberta-v3-base-squad2)) | MIT | 278M | `onnx/model.onnx` (1,1 GB, fp32). La variante int8 publicada da logits planos (inservible) y la int16 no carga: medido en P7.2 | medium |
| Lector QA | ⛔ [deepset/xlm-roberta-large-squad2](https://huggingface.co/deepset/xlm-roberta-large-squad2) | CC-BY-4.0 | 560M | **sin ONNX oficial**; la única exportación ([holisticon](https://huggingface.co/holisticon/xlm-roberta-large-squad2-onnx)) no declara licencia y tiene 11 descargas | heavy (decisión pendiente) |

Descartados: `jinaai/jina-reranker-v2-base-multilingual` (licencia no
comercial) y `BAAI/bge-m3` como denso (su ONNX trae los pesos en un archivo
externo de 2,2 GB; demasiado para CPU sin una ganancia medida).

**Decisión pendiente para `heavy` (la toma el usuario):** opciones para el lector:

1. Usar el mismo lector de medium (mdeberta int8) leyendo más pasajes
   (`leer_m: 4`), con el reranker y el codificador grandes. Es la opción
   recomendada: no requiere exportar nada.
2. Exportar `deepset/xlm-roberta-large-squad2` con `rag modelos exportar`
   (extra `[exportar]`, requiere torch una vez) y publicar el ONNX en un
   repositorio propio. Implica atribución CC-BY-4.0.

Mientras tanto, `heavy` usa la opción 1.

### Disperso: BM25 propio

No es un modelo. Lo generan `terminos()` y `EstadisticasLexicas`: TF
saturado en el cliente e IDF aplicado en Qdrant (`modifier: idf`). Ver
[lexico-y-multilenguaje.md](lexico-y-multilenguaje.md) §4.

### Cuantización

- **Reranker:** se usa la variante int8 publicada.
- **Lector:** fp32, porque la cuantización dinámica degrada DeBERTa-v3 (verificado en P7.2).
- **Codificador e5:** se usa fp32. Su int8 publicado (`qint8_avx512_vnni`)
  exige AVX-512 VNNI. Como solo codifica la pregunta en línea, el costo es
  bajo; la indexación es la que más lo nota.

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
| Lector / `leer_m` | — | mdeberta int8 / 2 | mdeberta int8 / 4 (pendiente: ver §2) |
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
