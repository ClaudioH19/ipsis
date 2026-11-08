# Experimento 1: afinado eficiente (LoRA) de bge-reranker-v2-m3

Estado: **protocolo (2026-11-06), sin ejecutar.** Depende del conjunto v2 congelado ([`conjunto_v2.md`](conjunto_v2.md)).
Se contrasta con el experimento 2 ([`experimento2_edicion.md`](experimento2_edicion.md)) con los mismos datos, la
misma exportación y el mismo evaluador.

## Pregunta

Cuando la fuente correcta está entre los candidatos pero no en el primer puesto, ¿un afinado eficiente en
parámetros sube hit@1 de forma significativa, sin perder hit@3 ni el registro informal, y conservando el costo del
modelo?

## Lo que ya se sabe y fija el diseño

- La cuantización int8 no explica los errores (OBS-0005, OBS-0007).
- Los errores del modelo son de formulación (D) y de preferencia por el tema sobre el aspecto preguntado (E)
  (OBS-0009, OBS-0010).
- La decisión se forma en las capas 12–24 y ninguna dirección lineal la rescata (OBS-0011): recalibrar la cabeza no
  alcanza.
- El afinado v1 (capas 12–23 y cabeza, 1 716 grupos) no fue significativo en hit@1. Este experimento cambia **dos
  cosas a la vez**, los datos y el método, y por eso incluye un brazo que cambia solo los datos.

## Brazos

Todos parten de `BAAI/bge-reranker-v2-m3@953dc6f` en fp32 y usan el mismo `entrenamiento.jsonl` congelado.

| Brazo | Qué cambia | Para qué |
|---|---|---|
| **B0 base** | nada (re-exportado con la misma receta) | control |
| **B1 datos** | afinado parcial del v1 (capas 12–23 y cabeza, lr 1e-5) con el conjunto v2 | separa el efecto de los datos del efecto del método |
| **B2 LoRA** | adaptadores LoRA en las 24 capas más la cabeza entrenable | el método propuesto |
| B3 LoRA superior (opcional) | LoRA solo en las capas 12–23 | ¿basta la mitad superior? (OBS-0011) |

**LoRA (B2).** Configuración de partida:

- rango r = 16, α = 32, dropout 0,1;
- módulos `query`, `key`, `value` y `attention.output.dense`, más `intermediate.dense` y `output.dense` de cada capa;
- la cabeza `classifier` entrenable completa.

Al final los adaptadores se **fusionan** en los pesos (`merge_and_unload`): el modelo exportado tiene la arquitectura
y el costo de bge. En la GPU de 4 GB cabe el modelo completo en fp16 con adaptadores en fp32.

## Entrenamiento (común a B1–B3)

| Parámetro | Valor | Nota |
|---|---|---|
| Pérdida | entropía cruzada sobre el grupo (1 positivo y 7 negativas) | igual que FlagEmbedding y el v1 |
| Ventana | 256 tokens, `longest_first` | la del motor |
| lr | 1e-4 (LoRA), 1e-5 (B1) | warmup 10 %, decaimiento lineal |
| Grupos por paso | 16 (acumulación) | — |
| Épocas | hasta 2; parada temprana por hit@1 en `nomiracl-dev` cada 0,25 época | sin mirar la prueba |
| Semillas | 13, 17 y 23 por brazo | se reporta la media ± la desviación, y la prueba se mide con la semilla elegida en desarrollo |
| Precisión | fp16 o bf16 con escalado de pérdida; adaptadores en fp32 | — |

Antes de entrenar se miden 20 pasos (`--pasos-prueba 20`) para estimar la duración y la memoria. Cada corrida
registra en `run.json`:

- el SHA-256 de `entrenamiento.jsonl` y del manifiesto;
- el commit, las versiones y la GPU;
- la curva de desarrollo;
- `original_intacto: true`.

## Exportación y paridad

1. Se fusiona y se exporta a ONNX fp32 y a int8 con la receta de `afinar.py exportar` (la misma que el base
   re-exportado, OBS-0013).
2. Paridad del exportado contra PyTorch fp32 sobre 50 preguntas de desarrollo: top-1 igual en ≥ 95 % y |Δlogit|
   del orden del ruido de C1.
3. C1 sobre el modelo afinado: la mejora tiene que sobrevivir al int8.

## Evaluación

`conjunto.py evaluar --modelo local:<carpeta>`, idéntica para todos los brazos y para el experimento 2:

- **durante el desarrollo:** solo `desarrollo` (formal e informal);
- **ajuste y olvido:** `--incluir-entrenamiento` sobre el entrenamiento (cuánto aprendió) y sobre la retención
  (`banco_pasajes` `test`, `general.py`);
- **una sola vez, al final:** `--incluir-prueba`, para todos los brazos ganadores de los dos experimentos a la vez.

## Criterios de éxito (fijados antes de entrenar)

1. **Primario:** hit@1 en `nomiracl-test` mejor que B0, con McNemar exacto bilateral y p < 0,05 tras corregir por
   Holm sobre los brazos que llegan a la prueba.
2. hit@3 en `nomiracl-test` no baja más de 0,5 puntos.
3. hit@1 en `nomiracl-test-informal` no baja.
4. Sin pérdida en la retención.
5. p95 de latencia dentro de ±10 % del base, en la misma CPU.

Si B1 cumple y B2 no lo supera, la mejora la explicaban los datos y no el método. Si ninguno cumple, se registra
como resultado negativo.

## Cómo se corre

En Kaggle con GPU, paso a paso en [`kaggle.md`](kaggle.md). La evaluación final en int8 se hace en el PC del
usuario.

## Implementado (2026-11-08)

- `afinar.py entrenar --metodo lora|parcial`: LoRA (peft) con la fusión al guardar, precisión mixta en CUDA, y
  parada por hit@1 sobre `nomiracl-dev.jsonl` congelado.
- `afinar.py exportar --paridad <nomiracl-dev.jsonl>`.
- Probado en CPU con 6 grupos: 8,1 M parámetros entrenables, 148 tensores cambiados tras la fusión, int8 de
  570,7 MB y top-1 igual en 5/5 preguntas de paridad.
