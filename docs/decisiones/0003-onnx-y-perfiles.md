# ADR 0003: modelos ONNX en CPU y perfiles de instalación

## Contexto

El asistente se instala en el servidor de quien lo usa (un VPS sin GPU). La
versión anterior dependía de torch y sentence-transformers: instalaciones de
varios GB y un solo nivel de calidad. Hacía falta elegir entre latencia y
calidad sin cambiar de producto, y que cualquier modelo fuera preentrenado,
multilingüe, con licencia compatible y sin fine-tuning.

## Decisión

- **Runtime propio sobre onnxruntime y tokenizers.** Sin torch,
  sentence-transformers ni fastembed en producción. Una base común,
  `ModeloOnnx` (Template Method), carga la sesión y el tokenizador; cada
  modelo implementa lo suyo: `CodificadorDenso`, `RerankerOnnx` y
  `LectorOnnx`. torch solo aparece en el extra de desarrollo `[exportar]`.
- **Caché global de modelos** (`RAG_MODELOS_DIR`) y uso sin red
  (`HF_HUB_OFFLINE=1`).
- **Tres perfiles** en `rag/recursos/perfiles/`, más `bm25` solo para
  diagnóstico:

  | Perfil | Modelos | p95 objetivo | p95 medido (banco universal) |
  |---|---|---|---|
  | light | e5-small | 150 ms | 85 ms |
  | medium | e5-small + mmarco (int8) + mdeberta (fp32) | 1 s | 815 ms |
  | heavy | e5-base + bge-reranker-v2-m3 (int8) + mdeberta (fp32), más pasajes y concordancia | 4 s (máx. 5) | 2.130 ms |

- **Un perfil significa más cómputo y más comprobaciones**, no
  necesariamente un modelo distinto en cada etapa. Heavy usa el mismo lector
  que medium leyendo más pasajes: `deepset/xlm-roberta-large-squad2` no tiene
  un ONNX confiable con licencia declarada, y no se introduce una exportación
  dudosa solo para diferenciar perfiles.
- **Cuantización por evidencia:** el reranker usa el int8 publicado; el
  lector va en fp32 (el int8 publicado da logits planos y el int16 no carga);
  e5 va en fp32 (su int8 exige AVX-512 VNNI).
- **Configuración por capas:** perfil ← `motor.yaml::ajustes_perfil` ←
  `calibracion.yaml`, esta última solo si su procedencia coincide.

## Consecuencias

- La instalación de producción pesa cientos de MB más los modelos del
  perfil, y corre igual en Linux, Windows y macOS.
- Cambiar de modelo denso exige reindexar: la colección lleva el modelo en
  su nombre y el manifiesto lo comprueba.
- Un modelo nuevo entra solo si es preentrenado, multilingüe, con licencia
  compatible y ONNX para CPU, sin fine-tuning, mejora el benchmark de forma
  significativa y respeta el presupuesto del perfil.
- Con el banco universal, heavy no compra seguridad material frente a medium
  (2,6 veces el p95). Se mantiene para corpus grandes y como opción.

## Estado

Aceptado e implementado. Abierto: un lector más grande para heavy, si
aparece un ONNX confiable.
