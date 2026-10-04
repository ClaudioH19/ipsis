# Recuperación híbrida

## 1. Propósito

Encontrar los fragmentos del corpus que pueden responder la pregunta,
combinando similitud semántica (vector denso) y coincidencia léxica (BM25),
sin redactar nada.

## 2. Alcance y no-alcance

- **Alcance:** codificar la pregunta, buscar en Qdrant y devolver candidatos
  con su payload completo (texto, documento, sección y offsets); recuperación
  dirigida por entidad.
- **No-alcance:** decidir si hay respuesta (lo hace la
  [política](politica.md)), reordenar con un modelo (lo hace el
  [reranker](reranker.md)) ni elegir el tramo.

## 3. Entradas y salidas versionadas

- **Entrada:** pregunta, `recuperar_n` del perfil, modo (`hibrida`,
  `vectorial` o `dispersa`) y filtro opcional por entidad.
- **Salida:** `RetrievalCandidate` en orden (id, payload, score) y la señal
  `s_ret`.
- **Índice:** colección `{coleccion}_{modelo}_v{n}` con su manifiesto en
  `.ipsis/indice/` (modelo, dimensión, stemmer, hash del corpus, versión del
  payload). Si el modelo cambia, se crea otra colección: nunca se mezclan
  vectores de modelos distintos.

## 4. Algoritmo y desempates

1. El codificador denso (e5) codifica `query: <pregunta>`; los pasajes se
   indexaron con `passage: `. Pooling promedio y norma L2.
2. La pregunta pasa por `terminos()` (ver [léxico](lexico.md)) y forma el
   vector disperso BM25 (1 por término único).
3. Qdrant ejecuta las dos búsquedas como `prefetch` y las fusiona con **RRF**
   nativo (`query_points`). En modo `vectorial` solo el denso; en `dispersa`,
   solo BM25 (perfil de diagnóstico `bm25`).
4. `s_ret` = coseno denso del primer candidato normalizado desde el piso del
   modelo: `(coseno − piso) / (1 − piso)`, recortado a [0, 1]. Para e5 el piso
   es 0,7 (coseno típico entre textos sin relación).
5. **Recuperación dirigida:** si una entidad de la pregunta (fecha, monto,
   artículo…) existe en el inventario del corpus pero no llegó a los
   candidatos, se busca con un filtro exacto por `valor_norm`.
6. Empates: el orden de Qdrant; el reranker desempata por `chunk_id`.

## 5. Supuestos

- El corpus es de un solo idioma, el del proyecto.
- Los fragmentos conservan la sección: un fragmento no cruza secciones.

## 6. Invariantes

- El payload recuperado conserva documento, sección, texto y offsets.
- La pregunta se codifica una sola vez por consulta.
- La recuperación no modifica ni redacta texto.
- El índice de un perfil solo se abre si su manifiesto es compatible
  (`ipsis doctor` lo comprueba).

## 7. Parámetros y defaults

| Parámetro | light | medium | heavy |
|---|---|---|---|
| Modelo denso | e5-small (384) | e5-small (384) | e5-base (768) |
| `recuperar_n` | 10 | 20 | 30 |
| BM25 `k1`, `b` | 1,2 / 0,75 | 1,2 / 0,75 | 1,2 / 0,75 |

Se ajustan en `configuracion/motor.yaml::ajustes_perfil`.

## 8. Complejidad y recursos

Codificar la pregunta y consultar Qdrant toma 20–60 ms con e5-small y
50–150 ms con e5-base en CPU. Disco del modelo: 470 MB (small) y 1,1 GB
(base).

## 9. Fallos y fallback

- Sin índice o con índice incompatible: el servicio no está listo y `/ready`
  dice `ipsis indexar`.
- Sin candidatos: la política se abstiene.
- Qdrant local bloqueado por otro proceso: error accionable (detén
  `ipsis servir`).

## 10. Seguridad y privacidad

La pregunta no sale de la máquina: el modelo y Qdrant son locales. El
registro de consultas está apagado por defecto.

## 11. Pruebas técnicas

`tests/indice/`, `tests/consulta/` (motor con dobles), pruebas `slow` con el
modelo real y la caracterización (`tests/integracion/test_caracterizacion.py`).

## 12. Limitaciones

- Con corpus muy chicos (5 documentos), denso y BM25 recuperan casi lo mismo:
  el banco universal no tiene potencia para medir el aporte del denso.
- El modo local de Qdrant no aplica índices de payload; con corpus grandes
  conviene Qdrant como servidor.

## 13. Referencias y procedencia

- Wang et al., *Multilingual E5 Text Embeddings* (2024);
  [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small).
- Cormack et al., *Reciprocal Rank Fusion* (SIGIR 2009).
- [Qdrant: hybrid queries](https://qdrant.tech/documentation/concepts/hybrid-queries/).

## 14. Estado

Estable. Los umbrales que usan `s_ret` dependen de la
[calibración](calibracion.md) de cada proyecto.
