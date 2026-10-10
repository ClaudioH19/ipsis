# Regresión documental general

Criterio: `respuesta_completa_v2`.

Corpus sintético. Los errores conocidos de la referencia no son una garantía de precisión.

| Perfil / variante | Banco | Correctas / respondibles | Errores / directas | Negativas sin directa | Estados negativos esperados | QA completas / evaluadas | p95 ms | Presupuesto p95 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| medium | consultas_es | 25/34 | 0/25 | 26/26 | 3/26 | 8/25 | 3441.7 | NO (1000 ms) |
| heavy+granite | consultas_es | 25/34 | 0/25 | 26/26 | 3/26 | 8/25 | 3352.0 | sí (4000 ms) |
| heavy+harrier | consultas_es | 25/34 | 0/25 | 26/26 | 3/26 | 8/25 | 3517.3 | sí (4000 ms) |
| heavy+gemma2 | consultas_es | 25/34 | 0/25 | 26/26 | 3/26 | 8/25 | 3660.4 | sí (4000 ms) |
| heavy+granite97 | consultas_es | 25/34 | 0/25 | 26/26 | 3/26 | 8/25 | 4157.2 | NO (4000 ms) |
| heavy+horizon-base | consultas_es | 25/34 | 1/26 | 25/26 | 3/26 | 8/25 | 13785.7 | NO (4000 ms) |
| heavy+horizon-small | consultas_es | 25/34 | 1/26 | 25/26 | 3/26 | 8/25 | 5391.1 | NO (4000 ms) |

## Fallos de ejecución o regresión

Ninguno.

## Errores de contenido observados

- heavy+horizon-base / consultas_es / `es-ambigua-002`: ¿Quién lo aprueba?
- heavy+horizon-small / consultas_es / `es-ambigua-002`: ¿Quién lo aprueba?
