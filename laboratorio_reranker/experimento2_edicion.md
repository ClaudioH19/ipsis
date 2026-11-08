# Experimento 2: edición directa de pesos de bge-reranker-v2-m3 por GPT-6 Astra

Estado: **protocolo (2026-11-06), sin ejecutar.** Depende del conjunto v2 congelado ([`conjunto_v2.md`](conjunto_v2.md)).
Se contrasta con el experimento 1 ([`experimento1_afinado.md`](experimento1_afinado.md)).

## Pregunta

¿Puede un LLM general mejorar el orden de un cross-encoder pequeño (568 M parámetros) **leyendo y editando sus pesos
directamente**, sin gradientes ni entrenamiento? El objetivo es demostrar si es posible; no se espera superar al
afinado.

## Referencia que se replica

Takehi, Teoh, Zhang y Khattab, «Sparks of Weight-Space Programming», MIT CSAIL, 2026-11-02:

- [post](https://rikiyat.github.io/blog/weight-space-programming/);
- [logs del experimento 8](https://github.com/RikiyaT/lm_understand-logs/blob/main/exp8_math/README.md).

En el experimento 8, Astra editó 131 072 pesos de Qwen3.5-0.8B (MLP de las capas 15 y 19) y MATH-500 pasó de 7,9 %
a 48,1 %, porque quitó una dirección que causaba bucles. Su propio control (Gemma 3 270M, sin bucles) no mejoró.

**Expectativa previa: baja.** bge no tiene un obstáculo patológico: prefiere el pasaje del mismo tema sin el dato
(OBS-0010), y ninguna dirección lineal de una sola capa rescata sus errores (OBS-0011). Un resultado negativo es un
resultado válido.

## Qué se replica tal cual y qué se adapta

| Elemento | En el experimento 8 | Aquí |
|---|---|---|
| Editor | `gpt-6-astra` por Codex CLI, esfuerzo `max`, herramientas propias desactivadas | igual |
| Conversaciones | una por corrida; traspaso (*handoff*) cada 40 turnos | igual |
| Kernel | Python persistente en CPU con los pesos; `save_edit(nombre, tensor)`; tope de 300 ejecuciones | igual, con los pesos fp32 de `BAAI/bge-reranker-v2-m3@953dc6f` |
| Prohibido | backward, autograd, optimizadores, ajuste iterativo a una pérdida; ejecutar el modelo en el kernel; internet | igual |
| `save_edit` rechaza | la norma final, la capa de embeddings y de salida, y el escalado constante de un tensor entero | embeddings, `classifier.out_proj` (la salida) y el escalado de un tensor entero |
| Explicaciones | obligatorias antes del código desde cierto turno | obligatorias desde el turno 1 |
| Presupuesto | 10, 25 o 50 pasadas | 10, 25 y 50 |
| Práctica | problemas de GSM8K y MATH `train` con respuesta | `entrenamiento.jsonl` del conjunto v2 |
| **Variante pedida** | — | al empezar, Astra recibe las **salidas por capa** del 10 % `muestra_capas` (no gastan presupuesto) |

### Herramienta de pasadas

Cada pedido cuesta 1 pasada, sea del tamaño que sea; los pedidos fallidos no cuentan. Hay dos tipos:

1. **`puntuar`:** hasta 512 grupos de `entrenamiento` o de `desarrollo`, con el modelo original, el editado o los
   dos (pareados). Devuelve los logits por candidato y hit@1, hit@3 y MRR, en total y por fuente y registro.
2. **`leer`:** hasta 1 024 pares (pregunta, pasaje) de `entrenamiento`. Devuelve, por capa, el vector `<s>` y,
   si se pide, las activaciones del MLP y la atención de una capa.

Astra **nunca** ve `prueba`, ni los archivos `*-informal` de prueba, ni el banco del cliente.

### Salidas por capa entregadas al inicio

Para cada grupo `muestra_capas` (≈ 10 % del entrenamiento, el mismo en cualquier máquina), y para su positivo y sus
7 negativas, se entregan:

- el vector `<s>` de las 25 salidas (embeddings y capas 1–24), en fp16;
- el logit final;
- la etiqueta.

Se generan una sola vez en Kaggle, en la misma sesión de GPU del experimento 1 (`afinar.py volcar-capas`,
`kaggle.md`, celda 6), y se guardan en `capas_base.npz` con su SHA-256. **Solo se entregan las del modelo base.**
Las del modelo afinado (`volcar-capas --copia`) y el diff de LoRA no van a Astra, porque le darían la solución del
experimento 1 y romperían el contraste. Sirven solo para el análisis humano posterior: dónde difieren el afinado y
la edición. Es lo que la bitácora usó para las sondas por
capa (OBS-0011), así que Astra parte del mismo material que el diagnóstico humano.

## Línea base sin Astra: ablación de una dirección hecha a mano

Para saber si Astra aporta algo más que la técnica estándar (la crítica principal al post), se hace a mano la
edición más simple que la publicación describe:

1. Con la muestra de capas, calcular en cada capa *l* la dirección media `u_l = media(h(q, competidor)) −
   media(h(q, correcto))`, normalizada. Los competidores son las negativas que bge pone sobre el positivo.
2. Quitarla de las matrices de salida de atención y MLP de las capas elegidas: `W' = W − α u (uᵀ W)`.
3. Elegir *l*, las capas y α con evaluaciones en `desarrollo`, contando **cada evaluación como una pasada**, con
   los mismos presupuestos de 10, 25 y 50.

## Corridas

- **Astra:** 2 corridas por presupuesto (10, 25 y 50 pasadas), en conversaciones independientes y con el mismo
  prompt versionado (`prompt_astra.md`, por escribir y congelar antes de la primera corrida). La publicación hizo
  una sola corrida por presupuesto, y sus resultados no fueron monótonos.
- **Línea base manual:** 1 corrida por presupuesto.
- **Registro de cada corrida:**
  - todos los mensajes;
  - el código ejecutado y su salida;
  - los pedidos de pasadas con su respuesta;
  - el `edit.npz` como diff exacto contra el base, más su `manifest.json` (tensores, forma, filas o columnas
    tocadas y número de pesos cambiados);
  - turnos, ejecuciones, horas y pasadas usadas.

  Todo va a `.cache/laboratorio-reranker/astra/<run_id>/`.

## Del diff al modelo evaluado

1. Aplicar el `edit.npz` a una copia de los pesos base (el original nunca se toca; se verifica su SHA-256).
2. Exportar a ONNX fp32 y a int8 con la misma receta que los brazos del experimento 1 y el base re-exportado.
3. Repetir C1: una edición pequeña puede quedar por debajo del ruido del int8 (|Δlogit| p50 de 0,18).

## Evaluación y criterios

- **Evaluador:** el mismo del experimento 1 (`conjunto.py evaluar`), con los mismos archivos congelados.
- **Criterio primario:** el mismo hit@1 en `nomiracl-test`, con McNemar y corrección de Holm conjunta con los
  brazos del experimento 1.
- **Criterios secundarios:** los mismos (hit@3, informal, retención y latencia).
- **Además se reporta:**
  - el número de pesos cambiados;
  - el ajuste en la muestra de capas frente al resto del entrenamiento (si solo mejora donde vio las capas, es
    sobreajuste a la muestra);
  - el costo en pasadas, turnos y horas.

## Privacidad y términos de uso

- **Privacidad:** a OpenAI solo se envían pesos de bge y textos del conjunto v2, que son públicos. Nada del cliente.
- **Términos de uso:** las ediciones de Astra se usan para un ajuste de un modelo pequeño ya entrenado, no para
  entrenar un modelo desde cero (decisión del usuario, 2026-11-06).

## Contraste entre los experimentos 1 y 2

| Eje | Experimento 1 | Experimento 2 |
|---|---|---|
| Datos | `entrenamiento.jsonl` completo | el mismo archivo, leído por pasadas, más las capas del 10 % |
| Selección | `nomiracl-dev` | `desarrollo`, con presupuesto de pasadas |
| Exportación | fusión → ONNX → int8 | diff → ONNX → int8, con la misma receta |
| Evaluador | `conjunto.py evaluar` | igual |
| Prueba | `nomiracl-test`, una vez y junto con el exp. 2 | igual |
| Costo reportado | horas de GPU, parámetros entrenables | pasadas, turnos, horas, pesos cambiados |
