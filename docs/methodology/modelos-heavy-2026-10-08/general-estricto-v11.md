# Regresión documental general

Criterio: `respuesta_completa_v2`.

Corpus sintético. Los errores conocidos de la referencia no son una garantía de precisión.

| Perfil / variante | Banco | Correctas / respondibles | Errores / directas | Negativas sin directa | Estados negativos esperados | QA completas / evaluadas | p95 ms | Presupuesto p95 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| light | general_bueno_es | 9/12 | 3/12 | 13/16 | 4/16 | — | 42.0 | sí (150 ms) |
| light | general_medio_es | 9/12 | 3/12 | 13/16 | 4/16 | — | 46.3 | sí (150 ms) |
| light | general_malo_es | 9/12 | 3/12 | 13/16 | 4/16 | — | 51.9 | sí (150 ms) |
| medium | general_bueno_es | 10/12 | 0/10 | 16/16 | 4/16 | 10/10 | 571.8 | sí (1000 ms) |
| medium | general_medio_es | 10/12 | 0/10 | 16/16 | 4/16 | 10/10 | 674.1 | sí (1000 ms) |
| medium | general_malo_es | 10/12 | 0/10 | 16/16 | 4/16 | 10/10 | 974.6 | sí (1000 ms) |
| heavy | general_bueno_es | 10/12 | 0/10 | 16/16 | 4/16 | 10/10 | 614.5 | sí (4000 ms) |
| heavy | general_medio_es | 10/12 | 0/10 | 16/16 | 4/16 | 10/10 | 658.5 | sí (4000 ms) |
| heavy | general_malo_es | 10/12 | 0/10 | 16/16 | 4/16 | 10/10 | 958.0 | sí (4000 ms) |

## Fallos de ejecución o regresión

- light / general_bueno_es: incumple modo estricto
- light / general_medio_es: incumple modo estricto
- light / general_malo_es: incumple modo estricto

## Errores de contenido observados

- light / general_bueno_es / `tecnico-neg-1`: ¿Cuánto cuesta cambiar el filtro de la bomba de recirculación?
- light / general_bueno_es / `logistica-neg-1`: ¿Cuánto cuesta el despacho de paquetes refrigerados?
- light / general_bueno_es / `logistica-neg-2`: ¿Por qué los paquetes refrigerados se conservan a 15 grados Celsius?
- light / general_medio_es / `tecnico-neg-1`: ¿Cuánto cuesta cambiar el filtro de la bomba de recirculación?
- light / general_medio_es / `logistica-neg-1`: ¿Cuánto cuesta el despacho de paquetes refrigerados?
- light / general_medio_es / `logistica-neg-2`: ¿Por qué los paquetes refrigerados se conservan a 15 grados Celsius?
- light / general_malo_es / `tecnico-neg-1`: ¿Cuánto cuesta cambiar el filtro de la bomba de recirculación?
- light / general_malo_es / `logistica-neg-1`: ¿Cuánto cuesta el despacho de paquetes refrigerados?
- light / general_malo_es / `logistica-neg-2`: ¿Por qué los paquetes refrigerados se conservan a 15 grados Celsius?
