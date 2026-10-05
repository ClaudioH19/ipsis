# Banco de evaluación y métricas

## 1. Propósito

Separar la calidad esperada del comportamiento actual. La caracterización
detecta cambios; un banco normativo dice si esos cambios son mejoras o
regresiones, y el golden del cliente permite [calibrar](calibracion.md).

## 2. Alcance y no-alcance

- **Alcance:** formato versionado de bancos, métricas de cobertura y riesgo,
  `ipsis evaluar`, `ipsis benchmark` y `ipsis comparar`.
- **No-alcance:** elegir umbrales (lo hace `ipsis calibrar`) o cambiar defaults
  automáticamente.

## 3. Entradas y salidas versionadas

Cada banco es un `manifiesto.json` (esquema `1`: id, versión, tipo, estado,
`uso`, corpus con su SHA-256 conjunto y categorías) y un JSONL de casos. Cada
caso declara `id`, `split`, `categoria`, `pregunta`, `estado_esperado`,
`respondible` y, si es respondible, la `respuesta_literal` y la evidencia con
`doc_id` y offsets exactos.

| Banco | Dónde | Uso |
|---|---|---|
| Sintético `aqualis_sintetico@1.1.0` | `tests/datos/banco/` | 27 casos (56% no respondibles), regresión y caracterización |
| Universal | `tests/datos/banco_universal/{es,en,pt}` | 90 casos (30 por idioma), `uso: regresion`: no se puede calibrar con él |
| Golden del cliente | `golden/bank/` del proyecto | el único que calibra (ver [guía](../guia/golden.md)) |

## 4. Algoritmo y desempates

Categorías: `exacta`, `parafrasis`, `sin_respuesta`, `premisa_falsa`,
`ambigua` y `conversacional`. Una `sin_respuesta` o `premisa_falsa` puede
llevar el subtipo `trampa_mismo_tema` y su `par` (la respondible del mismo
tema): es el par mínimo que mide si el sistema distingue «se parece» de
«responde». El estado esperado distingue además `fuera_dominio`.

Métricas (`ipsis/evaluacion/metricas.py`), globales, por grupo y por idioma:

- cobertura directa y relacionada sobre las respondibles;
- recall de abstención sobre las no respondibles;
- **falsos `ok`:** no respondible que termina en respuesta directa;
- directas sin la respuesta literal;
- riesgo de las aceptadas `x/n` con su cota de Clopper-Pearson;
- Recall@k y MRR sobre la evidencia, exactitud de offsets;
- latencia p50/p95, total y por etapa.

Un falso `ok` tiene prioridad sobre el recall: recuperar más evidencia no
compensa afirmar algo que el corpus no respalda. `ipsis evaluar` sale con ≠ 0
si encuentra alguno.

`ipsis benchmark --banco … --perfiles bm25,light,medium,heavy` crea un proyecto
temporal por perfil y banco, evalúa con el motor caliente y escribe
`benchmark-perfiles.{json,md}` y un artefacto por perfil para `ipsis comparar`.
Sale con ≠ 0 si un perfil excede su presupuesto o, con un banco de
evaluación, da falsos `ok`. `--solo-latencia` mide p50/p95 por etapa.

`ipsis comparar` exige el mismo hash de banco, versión y `k`.

## 5. Supuestos

Los casos y sus offsets fueron revisados por una persona. El banco sintético
y el universal son ficticios: no contienen datos de una institución.

## 6. Invariantes

- `test` nunca elige umbrales.
- Un banco con `uso: regresion` no se acepta para calibrar.
- Cada artefacto guarda el hash del banco, la configuración efectiva y la
  identidad del índice.

## 7. Parámetros y defaults

Split 50/50 estratificado por tipo, ordenado por hash (determinista).

## 8. Complejidad y recursos

Lineal en los casos; el costo es el de las consultas del perfil.

## 9. Fallos y fallback

Corpus del banco cambiado: el hash no coincide y el comando lo dice
(`ipsis golden validar` para el golden).

## 10. Seguridad y privacidad

El golden del cliente queda en su proyecto; el repositorio no distribuye
corpus, perfiles ni métricas de una institución concreta.

## 11. Pruebas técnicas

`tests/evaluacion/` y la prueba lenta del banco universal, que falla si
aparece un falso `ok` nuevo respecto de su línea base.

## 12. Limitaciones

Los bancos incluidos son chicos: sirven para detectar defectos y verificar el
proceso, no para certificar un perfil ni elegir defaults por sí solos.

## 13. Referencias y procedencia

Formato de exportación compatible con SQuAD 2.0 (`ipsis golden exportar
--formato squad2`).

## 14. Estado

Estable.
