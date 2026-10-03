# Recuperación híbrida

## Propósito

Encontrar pasajes relevantes combinando coincidencia semántica y léxica sin
usar un modelo generativo.

## Estado

Implementación V1 estable en funcionamiento; parámetros pendientes de
calibración final. La separación multietapa V2 aún está planificada.

## Entradas y salidas

Entrada: pregunta, modo, límite, filtro opcional y vector denso opcionalmente
precalculado. Salida: IDs, payloads, scores y latencias en el mismo orden.

## Algoritmo actual

1. `multilingual-e5-small` codifica la consulta normalizada.
2. Qdrant ejecuta una búsqueda densa.
3. En modo híbrido ejecuta además BM25 sparse.
4. Qdrant fusiona ambos rankings mediante RRF.
5. El servicio aplica verificación de premisa y puede buscar por una entidad
   exacta que existe en el inventario del corpus.
6. Las oraciones o filas más pertinentes se seleccionan sin reescribirlas.

## Invariantes

- El payload recuperado conserva documento, sección, texto y offsets.
- Una consulta se codifica una sola vez por petición y el vector se reutiliza.
- La búsqueda dirigida solo filtra entidades detectadas determinísticamente.
- Retrieval no redacta la respuesta.

## Configuración actual

`configuracion/motor.yaml` define modelo, prefijo de consulta, estrategia de
chunking, modo, `top_k`, colección y Qdrant. `prefijo_documento` ya está
declarado para la migración V2, pero su uso durante indexación aún debe
implementarse antes de considerarlo activo.

## Fallos y fallback

- Sin índice o modelo: servicio no listo.
- Sin candidatos: abstención.
- Entidad ausente del corpus: abstención con motivo de premisa.
- Componente opcional futuro: fallback al ranking híbrido y estado degradado.

## Limitaciones conocidas

- El mismo `top_k` limita actualmente candidatos y resultados finales.
- No existe todavía reranker de segunda etapa.
- Los scores denso, sparse y fusionado no se exponen todos por candidato.
- Los umbrales actuales se identifican como no calibrados.

## Referencias

- <https://github.com/qdrant/qdrant>
- <https://github.com/qdrant/examples>
- <https://huggingface.co/intfloat/multilingual-e5-small>
- <https://github.com/castorini/pyserini>

