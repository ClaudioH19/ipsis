# Candidatos para revisar heavy

Consulta: 2026-10-08. La investigación siguiente conserva la propuesta inicial.
Actualización: Granite 311M/97M, Harrier, EmbeddingGemma 2 y Horizon base/small
ya están integrados con revisiones fijas y ejecutados en CPU. Ver el
[procedimiento y comandos de evaluación](../../../herramientas/evaluacion/README.md)
y las [mediciones locales](implementacion.md). Su integración
no demuestra superioridad; la elección del perfil debe seguir los resultados.

## Decisión propuesta

Comparar primero **Granite-311M Multilingual R2** y **Harrier-270M** como
recuperadores. Usar **Granite-97M R2** como control de eficiencia. Para el
reranker, probar **Horizon multilingual base/small** y **GTE multilingual**
por separado. **EmbeddingGemma 2** merece una segunda tanda: su publicación
es muy reciente y necesita adaptar entradas adicionales.

Esta prioridad es una inferencia de adecuación a CPU, entrenamiento publicado
y contratos ONNX. No demuestra que ningún candidato supere a medium en nuestro
corpus. Los valores de MTEB completo, MTEB Retrieval y MIRACL no se pueden
ordenar como si fueran la misma prueba.

El [benchmark actual](../evaluacion-v2/README.md) es la referencia:
medium tiene 25 directas correctas de 25 y p95 de 3.099,6 ms; heavy,
21 de 23 y p95 de 17.081,8 ms. Heavy no tiene aciertos exclusivos frente
a medium en ese banco. La etapa de reranking tiene p95 de 14.971,4 ms.
Estos percentiles por etapa no se suman para obtener el percentil total.

## Recuperación

| Candidato | Evidencia publicada | Integración en ipsis | Orden |
|---|---|---|---|
| [IBM Granite-311M Multilingual R2](https://huggingface.co/ibm-granite/granite-embedding-311m-multilingual-r2) | Publicado el 29 de abril de 2026; español entre los idiomas con entrenamiento específico; destilación de múltiples profesores, aprendizaje contrastivo y fusión de modelos; ONNX del fabricante | 768 dimensiones, vector del primer token (CLS), sin prefijos de búsqueda; FP32 de 1.247 MB o variante AVX2 de 313 MB | Primera tanda |
| [Microsoft Harrier-270M](https://huggingface.co/microsoft/harrier-oss-v1-270m) | Repositorio creado el 30 de marzo de 2026; entrenamiento contrastivo multilingüe y destilación; incluye español | 640 dimensiones e instrucción de búsqueda en consultas; el [ONNX comunitario](https://huggingface.co/onnx-community/harrier-oss-v1-270m-ONNX) ya devuelve el vector de oración, no estados por token; variante quantized de unos 344 MB con datos externos | Primera tanda |
| [IBM Granite-97M Multilingual R2](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2) | Misma generación R2, destinada a despliegues sensibles a latencia | 384 dimensiones, CLS; FP32 de 390 MB o AVX2 de 98 MB | Control de eficiencia |
| [Google EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2) | [Anunciado el 6 de octubre de 2026](https://blog.google/innovation-and-ai/technology/developers-tools/embeddinggemma-2/); 270M parámetros para texto, módulos opcionales para otras modalidades; multilingüe | [ONNX comunitario](https://huggingface.co/onnx-community/embeddinggemma-2-ONNX), 768 dimensiones, prefijos por tarea y proyección; el grafo exige entradas de imagen, vídeo y audio incluso para el camino de texto; faltan pruebas con entradas vacías | Segunda tanda |
| [Qwen3-Embedding-0.6B, conversión de Qdrant](https://huggingface.co/Qdrant/Qwen3-Embedding-0.6B-onnx) | Multilingüe, 1024 dimensiones, extracción del último token; conversión ONNX identificada | Los estados por token requieren pooling del último token y normalización; la variante quantized ocupa 1.121 MB | Reserva por coste |

Los tamaños son bytes publicados expresados en MB decimales, **no RAM ni
tiempo de inferencia**. Menos parámetros y menor archivo no garantizan menor
latencia. Hay que verificar la cuantización en esta CPU y contrastar su salida
con FP32; no basta con que el archivo se llame `quantized`.

Granite y EmbeddingGemma 2 declaran Apache-2.0; Harrier declara MIT. La tarjeta
de Granite también atribuye su tokenizador a Gemma y remite a sus términos:
esa atribución debe conservarse al empaquetar. Las conversiones comunitarias
se verifican frente a su origen y revisión antes de incluirlas en el catálogo.

## Reranking

| Candidato | Entrenamiento y formato | Valoración |
|---|---|---|
| [Horizon multilingual-reranker-base](https://huggingface.co/Horizon-Labs/multilingual-reranker-base) | 308M, mmBERT, destilado de Qwen3-Reranker-4B; datos y código publicados; repositorio creado el 1 de octubre de 2026; un logit por par; ONNX FP32 y quantized, Apache-2.0 | Probar como candidato experimental. Su propia tabla lo coloca por debajo de BGE-v2-m3 en MIRACL español (0,703 frente a 0,781), aunque por encima en ESCI español (0,861 frente a 0,846). La evaluación usa 60 consultas MIRACL por idioma; no prueba superioridad general ni latencia en ipsis |
| [Horizon multilingual-reranker-small](https://huggingface.co/Horizon-Labs/multilingual-reranker-small) | 141M, también destilado; ONNX publicado, variante quantized de 268 MB | Control de coste; calidad y velocidad locales pendientes |
| [Alibaba GTE multilingual-reranker-base](https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base) | 306M, multilingüe, Apache-2.0; encoder con un logit; generación de 2024, no novedad de 2026 | Candidato de eficiencia. [Conversión ONNX comunitaria](https://huggingface.co/onnx-community/gte-multilingual-reranker-base) con int8 de 341 MB; su tarjeta no declara licencia, por lo que debe documentarse origen/licencia de los pesos y conversión |
| [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) | 596M, instrucciones y puntuación basada en logits de `yes`/`no`, Apache-2.0 | Reserva: requiere formatear la consulta y adaptar puntuación; no encaja en el cross-encoder actual que lee `fila[0]`. Tener una conversión ONNX no elimina esa diferencia |

No elegiría [Jina reranker v3.5](https://huggingface.co/jinaai/jina-reranker-v3.5)
ni [Jina embeddings v5 nano](https://huggingface.co/jinaai/jina-embeddings-v5-text-nano)
como dependencia predeterminada para despliegues generales: sus tarjetas
declaran CC BY-NC 4.0 y remiten a una licencia comercial para ese uso.
Los rerankers Granite English R2 y GTE ModernBERT English tampoco sustituyen
un componente multilingüe sin medir los idiomas que usa el producto.

## Lector extractivo

La búsqueda no identificó un sustituto reciente con una mejora demostrada en
español, abstención SQuAD2 y ONNX compatible que justifique promoverlo ahora.
Conservar mDeBERTa como control permite atribuir las mejoras a recuperación
o reranking. La fecha de una conversión ONNX no es la fecha de entrenamiento.

[XLM-RoBERTa large SQuAD2](https://huggingface.co/deepset/xlm-roberta-large-squad2)
es un lector multilingüe mayor, de 560M, entrenado en SQuAD2. Su tarjeta actual
declara CC BY-4.0 y el repositorio no contiene ONNX ni `tokenizer.json`.
Necesita exportar el modelo y serializar un tokenizador compatible con el
runtime antes de evaluarlo con atribución; no es una novedad de 2026 ni hay evidencia
de mejora local. La mención histórica de licencia no declarada en ADR 0003
queda corregida por esta consulta, sin afirmar que ya exista una exportación
validada para ipsis.

## Adaptaciones necesarias

El [codificador](../../../ipsis/modelos/denso.py) originalmente promediaba
estados por token. La integración ahora distingue:
media en e5, CLS en Granite, último token en Qwen y salida ya agrupada en
Harrier. EmbeddingGemma 2 también proporciona `sentence_embedding`; se debe
seleccionar esa salida y alimentar sus entradas adicionales.

La inspección de los grafos sin sus pesos confirmó:

| Conversión | Entradas | Salidas relevantes |
|---|---|---|
| Qdrant Qwen3 Embedding | `input_ids`, `attention_mask` | `last_hidden_state`: lote × tokens × 1024 |
| Harrier ONNX | `input_ids`, `attention_mask` | `sentence_embedding`: lote × 640 |
| EmbeddingGemma 2 ONNX | ids, máscara, `image_features`, `video_features`, `audio_features` | estados de 768 dimensiones y `sentence_embedding`: lote × 768 |

La inspección inicial no ejecutó grafos ni descargó pesos externos. La fase
posterior verificó inferencia real de los seis candidatos integrados, incluidos
los datos externos de Harrier y EmbeddingGemma 2 y sus entradas vacías de
imagen/vídeo/audio. Qwen continúa como reserva sin integración validada.

Todos los nuevos recuperadores requieren un índice propio, incluso si
coinciden en dimensión con e5. El piso de coseno 0,7 de e5 no se reutiliza:
se mide la distribución de similitud del candidato y se revisan las señales
y umbrales. Las calibraciones existentes quedan apartadas durante las pruebas.

## Matriz de experimentos

Usar inicialmente la cascada de medium: 20 candidatos, reranking de 4 y
lectura de 2, con la misma longitud de lectura. Así se cambia un componente
cada vez antes de añadir más trabajo.

| Experimento | Recuperador | Reranker | Lector |
|---|---|---|---|
| Referencia | e5-small de medium | mmarco de medium | mDeBERTa actual |
| E1 | Granite-311M R2 | mmarco | mDeBERTa |
| E2 | Harrier-270M | mmarco | mDeBERTa |
| E3 | Granite-97M R2 | mmarco | mDeBERTa |
| R1 / R2 | e5-small | Horizon base / small | mDeBERTa |
| R3 | e5-small | GTE multilingual | mDeBERTa |
| E4 | EmbeddingGemma 2, solo texto | mmarco | mDeBERTa |
| Combinada | Ganador de E1–E4 | Ganador de R1–R3 | mDeBERTa |

Evaluar bancos de consultas, universal y conversaciones, en es/en/pt;
sesiones independientes donde corresponda. Comparar Recall@k/MRR,
cobertura de la respuesta completa, errores entre directas, QA separado,
unidades/condiciones/actor correctos, ambigüedad y abstenciones. Medir p50/p95,
tiempos por etapa, memoria máxima, arranque y tamaño del índice. Mantener
CPU, hilos y concurrencia iguales, y repetir las mediciones de finalistas.

El banco ya inspeccionado orienta experimentos; un banco apartado decide
la promoción para reducir el ajuste a esas 60 preguntas. La concordancia
y el número de ventanas se prueban después, por separado. Las dos respuestas
ambiguas de heavy requieren verificar la resolución de referencias y la
decisión de aclarar; un modelo reciente no garantiza que esa política mejore.

Para afirmar una ventaja de heavy sobre medium, debe aportar aciertos adicionales
sin aumentar errores aceptados, conservar abstenciones y alcanzar p95 de 4 s
en la CPU objetivo. La sustitución del heavy anterior puede justificarse por
eliminar sus regresiones y reducir su coste aunque empate con medium: esa es
una mejora sobre el heavy anterior y no una ventaja de precisión sobre medium.
Los [resultados de implementación](implementacion.md) distinguen ambos criterios.

## Trazabilidad

[metadatos.json](metadatos.json) conserva revisiones de 15 repositorios,
licencias declaradas, nombres/tamaños/hashes LFS de los archivos ONNX,
configuraciones de pooling y contratos de tres grafos. Los campos de creación
y modificación son fechas del repositorio, no una afirmación de lanzamiento.
Los grafos se consultaron por revisión fija y se comprobó su SHA-256.
El catálogo incorpora los seis candidatos con sus contratos y revisiones
verificadas. La evaluación guarda estos contratos completos para reproducir
los resultados. GTE y Qwen continúan como opciones de investigación.
