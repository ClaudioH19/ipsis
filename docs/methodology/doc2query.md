# Expansión de pasajes con consultas (doc2query): descartada

Experimento del 2026-10-20 para saber si agregar a la ingesta un modelo que genere consultas por pasaje
(doc2query) mejora el hit@1. **Resultado: no se integra.** Con un generador local real empeora `medium`. Las
herramientas del experimento se retiraron; este documento conserva lo que importa. Contexto de la medición en
[precision-ingesta.md](precision-ingesta.md).

## Hipótesis

El recuperador deja la fuente correcta en el top 20 (95–98 %), pero el reranker solo puntúa los 10 primeros
candidatos y las preguntas informales con brecha de vocabulario («cuanto vale la bitacora» frente a
«Ponderación») a veces no llegan a esos 10. Agregar al texto buscable de cada unidad algunas consultas que ese
pasaje respondería debería subirlas. Solo cambia lo que se busca (vector denso y BM25 sobre `texto_embebido`);
el texto literal, los offsets y lo que lee el reranker no cambian.

## Método

- Documentos reales: tres documentos institucionales (reglamento de prácticas con tablas P1/P2 y dos versiones de
  una rúbrica), 366 unidades de preparación estructural y 64 preguntas (32 formales y 32 informales). Privados:
  nunca estuvieron en el repositorio.
- Las consultas se inyectaban envolviendo `ipsis.ingesta.ingesta.indexar_qdrant` y se medía con
  `herramientas/evaluacion/ranking_pasajes.py` (`--preparacion estructural_v1`, `--particion todas`).
- **Cota superior:** 3 consultas por unidad (una natural, una coloquial y una de palabras clave) escritas por un
  agente de Claude que solo vio el texto de las unidades, nunca las preguntas.
- **Generador local:** `doc2query/msmarco-spanish-mt5-base-v1` (Apache-2.0, mT5-base entrenado con mMARCO), búsqueda
  en haz de 3 haces sin muestreo (determinista), 3 consultas por unidad, 320 tokens de entrada. Unos 2,8 s por
  unidad en CPU (12 hilos), unos 17 minutos para 366 unidades.
- El banco sintético en español no sirve para esta pregunta: ya da 1,000 en `light` y no deja margen.

## Resultados (64 preguntas, hit@1 final)

| Perfil | Base | Cota superior (Claude) | Generador local |
|---|---|---|---|
| `medium` | 0,828 | 0,891 (8 ganados, 4 perdidos) | **0,781** (1 ganado, 4 perdidos) |
| `light` | 0,734 | 0,875 (13 ganados, 4 perdidos) | 0,766 (7 ganados, 5 perdidos) |

| Recuperador (ambos perfiles) | Base | Cota superior | Generador local |
|---|---|---|---|
| híbrido hit@1 | 0,578 | 0,719 | 0,641 |
| híbrido hit@10 | 0,875 | 1,000 | 0,922 |

Informales en `medium`: 0,750 → 0,812 con la cota superior y 0,750 → 0,656 con el generador local.

## Conclusiones

1. **Con consultas ideales sí hay ganancia** (+6 puntos en `medium`, +14 en `light`): el mecanismo existe.
2. **Con un generador local real empeora `medium`** (−4,7 puntos). El híbrido@10 sube, pero las consultas
   inventadas meten pasajes equivocados entre los 10 candidatos y desplazan al correcto. Es el falso positivo que
   se temía; ya aparecía en portadas («universidad de California»).
3. El criterio fijado antes (al menos +3 puntos en `medium`) no se cumple con el generador local, y no se justifican
   el costo de ingesta, el modelo adicional (mT5-base, ~2,3 GB y `torch`) ni la enmienda del
   [ADR 0001](../decisions/0001-non-generative-answers.md) (doc2query genera texto nuevo, aunque nunca se muestre).

## Límites

Un solo modelo y una sola configuración; sin filtrado de consultas al estilo doc2query--; sin generadores más grandes
ni ajustados a español institucional; 64 preguntas sobre 3 documentos, con dos de ellos casi gemelos; la cota
superior la escribió el mismo asistente que escribió las preguntas del banco, así que es optimista. El camino
barato para la brecha informal sigue siendo el vocabulario determinista y versionado
([ADR 0007](../decisions/0007-versioned-lexical-sources.md)).
