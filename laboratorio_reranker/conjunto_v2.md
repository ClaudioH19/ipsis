# Conjunto v2: datos compartidos por los experimentos 1 y 2

Estado: **congelado (2026-11-08)** en el PC del usuario; ver OBS-0016 en la bitácora. Código: `conjunto.py`. Salidas: `.cache/laboratorio-reranker/conjunto-v2/<etapa>/`, cada
una con su `resumen.json`.

Reemplaza al conjunto de la etapa 3 del laboratorio (OBS-0012) para los dos experimentos de la rama `lab061126`:

- **Exp. 1** ([`experimento1_afinado.md`](experimento1_afinado.md)): afinado con LoRA de bge-reranker-v2-m3.
- **Exp. 2** ([`experimento2_edicion.md`](experimento2_edicion.md)): edición directa de pesos por GPT-6 Astra.

Los dos usan **los mismos archivos congelados** y el mismo evaluador (`conjunto.py evaluar`) antes y después.

## Regla de etiquetas: sin juez externo

Un candidato es **correcto** o **incorrecto** solo por una de estas razones:

| Verificación | Fuentes | Significa |
|---|---|---|
| `humano` | MIRACL, NoMIRACL | Un hablante nativo juzgó el pasaje (publicado en los qrels) |
| `tramo` | SQAC, MLQA, XQuAD | Correcto: contiene todo el tramo de respuesta anotado. Incorrecto: no contiene ninguna de las respuestas aceptadas |
| `regla_otro_documento` | todas (relleno) | Pasaje de **otro** artículo; en las fuentes de tramo, además, sin la respuesta |

Ningún modelo decide una etiqueta. bge base solo **ordena** candidatos (para elegir las negativas difíciles y medir
la línea base), y los redactores de paráfrasis solo cambian la **redacción** de la pregunta; los pasajes y las
etiquetas quedan iguales. Así, cuando un modelo pone primero un pasaje incorrecto, el error es del modelo y no de un
juez.

Por esta regla quedaron fuera las fuentes sin etiqueta verificable: ALIA/BOJA (respuestas generadas por un LLM),
Horizon multilingual-rerank-distill (puntajes de un modelo) y MessIRve (fragmento destacado de Google, además
CC BY-NC).

## Por qué un conjunto nuevo

El afinado de la etapa 4 con el conjunto v1 se reprodujo en GPU y no dio una mejora significativa en hit@1.
Límites del v1:

| Límite del v1 | Dato | Cómo lo corrige el v2 |
|---|---|---|
| Una sola negativa juzgada en MIRACL | El v1 usaba `sentence-transformers/miracl` `es-triplet` | Juicios originales (qrels): 5,6 negativas juzgadas por pregunta en promedio |
| Pocas hermanas | SQAC: 2,4 hermanas por grupo | Hermanas del mismo párrafo **y** del mismo artículo; se eligen las que bge puntúa más alto |
| Tamaño | 1 716 grupos | Unas 15 000 preguntas candidatas a entrenamiento (etapa 2) |
| Negativas fáciles | TF-IDF, sin mirar a bge | Se toman primero las negativas que bge pone sobre el positivo (etapa 5) |
| Registro informal | Solo reglas ortográficas | Paráfrasis redactadas con brecha léxica (etapa 6), también en desarrollo y prueba |
| Prueba sin potencia | 52 preguntas sintéticas | NoMIRACL `test`: 1 408 preguntas con juicios humanos (§ Potencia) |

## Etapas

Se ejecutan en orden con `python laboratorio_reranker/conjunto.py <etapa>`. Cada una es determinista (semilla 13,
revisiones fijadas, orden estable) y registra conteos y SHA-256.

### 1. `recolectar`: descargar las fuentes

**Qué hace.** Baja cada archivo desde una revisión fijada de Hugging Face (o URL con SHA-256 fijado, en MLQA) a
`1-fuentes/`, y anota la licencia y la huella de cada uno.

| Fuente | Revisión | Licencia | Tipo de etiqueta |
|---|---|---|---|
| [MIRACL](https://huggingface.co/datasets/miracl/miracl) es `train` (topics y qrels) y su [corpus](https://huggingface.co/datasets/miracl/miracl-corpus) | `5be20db9` / `d921ec7e` | Apache-2.0 | humano |
| [NoMIRACL](https://huggingface.co/datasets/miracl/nomiracl) es `dev` y `test` (`relevant`) | `ecd08778` | Apache-2.0 (textos CC BY-SA) | humano |
| [SQAC](https://huggingface.co/datasets/PlanTL-GOB-ES/SQAC) `train`, `dev`, `test` | `f9928e88` | CC BY-SA 4.0 | tramo |
| [MLQA](https://github.com/facebookresearch/MLQA) es-es `dev`, `test` | zip `246e8089…` | CC BY-SA 3.0 | tramo |
| [XQuAD](https://huggingface.co/datasets/google/xquad) es | `51adfef1` | CC BY-SA 4.0 | tramo |

**Advertencia.** La versión `es-triplet-all` de sentence-transformers trae 100 negativas por pregunta, pero son
**minadas, no juzgadas**. Por eso se usan los qrels originales.

### Ejecutar en otra máquina

Las etapas 1 y 2 son deterministas. En otra máquina deben dar los mismos SHA-256 (los 16 primeros caracteres):

| Archivo de `2-candidatos/` | SHA-256 |
|---|---|
| miracl-train | `08e4b8c6ea2a80aa` |
| nomiracl-dev | `10aa93bd55ec44d5` |
| nomiracl-test | `79d23d879582ca0c` |
| sqac-train | `6aeaf59b403af23a` |
| sqac-dev | `214fe7bbf8c6728b` |
| sqac-test | `4269ee9f8431aa1a` |
| mlqa-dev | `84bcd03ab0864fce` |
| mlqa-test | `4d6ca5601718c6c2` |
| xquad-test | `f9fa2a9a2b9d30f8` |

Si un hash no coincide, revisar la versión de scikit-learn (TF-IDF) antes de seguir. Las paráfrasis ya redactadas
viajan versionadas en `parafrasis_<parte>.jsonl`, y `importar-parafrasis` las restaura.

### 2. `armar-candidatos`: pasajes y candidatos etiquetados

**Qué hace.** Por pregunta, arma una lista de candidatos con su etiqueta, su `tipo` y su `verificacion`, y la
baraja con una semilla derivada del id. El orden es arbitrario pero fijo, así el vecino de lote del int8 no depende
de la etiqueta (OBS-0002).

| Fuente | Positivos | Negativas, en orden de prioridad |
|---|---|---|
| NoMIRACL | juzgados (hasta 9) | juzgadas; hasta 10 candidatos, **igual que el v1** para poder comparar |
| MIRACL `train` | juzgados (hasta 3) | todas las juzgadas; después `otro_documento` hasta 11 |
| SQAC, MLQA, XQuAD | el tramo de 2 oraciones (con título) que contiene la respuesta | hasta 4 `hermana_contexto` (mismo párrafo), hasta 3 `hermana_articulo` (otro párrafo del mismo artículo) y `otro_documento` (TF-IDF) hasta 11 |

Las preguntas cuya respuesta cruza dos tramos se descartan. SQAC `train` se limita a 6 000 preguntas, sorteadas por
hash, para acotar el costo de CPU de la etapa 3.

**Resultado** (`2-candidatos/resumen.json`):

| Conjunto | Preguntas | Pares |
|---|---|---|
| miracl-train | 2 037 | 27 555 |
| sqac-train | 6 000 | 72 000 |
| mlqa-dev + mlqa-test | 5 729 | 68 737 |
| nomiracl-dev | 617 | 6 137 |
| sqac-dev | 1 861 | 22 332 |
| **nomiracl-test** | **1 408** | 14 018 |
| xquad-test | 1 182 | 14 184 |
| sqac-test | 1 906 | 22 872 |

### 3. `puntuar-base`: ordenar con el modelo sin tocar

**Qué hace.** Puntúa cada par con el bge int8 del motor (`onnx-community/bge-reranker-v2-m3-ONNX@6f5ff65`, lote 2
y 256 tokens, igual que en producción) y guarda el logit en `base`. Es la **línea base del «antes»** de los dos
experimentos y define qué grupos son difíciles. Se puede reanudar: salta las preguntas ya puntuadas. En el
contenedor de 4 CPU cuesta unos 115 ms por par con pasajes reales (≈ 8 h en total, en tramos de 2 h que se reanudan).

**En una máquina con GPU** (p. ej. GTX 1650 de 4 GB), `--gpu fp16` puntúa los conjuntos de **entrenamiento** con
PyTorch en la GPU. Desarrollo y prueba se puntúan siempre con el int8 del motor en CPU, porque esa es la línea
base. `3-puntuados/resumen.json` anota qué modelo puntuó cada archivo. En entrenamiento el puntaje solo ordena las
negativas y marca la dificultad, así que fp16 frente a int8 no cambia ninguna etiqueta.

**Si la GPU no rinde**, los conjuntos de entrenamiento se pueden puntuar en otra máquina y traer solo los
números:

- en la máquina que puntúa, `exportar-puntajes` escribe `puntajes_base.json.gz` (sin textos) con el SHA-256 de cada
  archivo de candidatos;
- en la otra, `importar-puntajes` rearma `3-puntuados/` y se niega si los candidatos locales difieren.

En la GTX 1650 de portátil del usuario, bge fp16 tardó unos 4,6 s por pregunta, lo mismo que el int8 en su CPU. Por
eso el entrenamiento se puntuó en int8 en el contenedor de 4 CPU (unos 1,2 s por pregunta).

**Diferencia observada entre Windows y Linux (2026-11-08).** Al importar en el PC del usuario, `miracl-train`,
`mlqa-test` y `sqac-train` coincidieron pregunta por pregunta. En `mlqa-dev`, 15 de 495 preguntas cambiaron 57
negativas `otro_documento`: son empates de TF-IDF que se ordenan distinto según la plataforma. Las etiquetas y los
demás tipos de candidato son idénticos. Ese archivo se puntuó en la propia máquina (int8) y se conservó con
`importar-puntajes --conservar-locales`. Por eso los hashes de las etapas 2 a 7 **no** son iguales entre
plataformas. La referencia del experimento es el manifiesto congelado en la máquina que evalúa.

**Misma máquina para el antes y el después.** El int8 dinámico puede dar logits algo distintos según la CPU
(instrucciones VNNI o AVX). Por eso la etapa 3 de desarrollo y prueba y todas las corridas de `evaluar` se hacen
en **la misma máquina**.

### 4. `descartar-dudosas`: quitar negativas que podrían responder (solo reglas)

**Qué hace.** Quita una negativa si:

- es idéntica a un positivo;
- está vacía;
- es de una fuente de tramo y contiene la respuesta de forma parcial: la palabra única de una respuesta de una
  palabra, o el 80 % de las palabras de contenido de una respuesta más larga.

Las negativas juzgadas por persona **no se tocan**. Se descarta la pregunta que queda sin positivo o sin negativa.
Las reglas son conservadoras a propósito: es preferible perder una negativa difícil que entrenar o evaluar con una
etiqueta falsa.

### 5. `separar-particiones`: entrenamiento, desarrollo y prueba sin fugas

**Particiones:**

| Partición | Conjuntos | Exp. 1 | Exp. 2 (Astra) |
|---|---|---|---|
| `entrenamiento` | miracl-train, sqac-train, mlqa-dev, mlqa-test | entrena | **práctica**: lee textos y pide pasadas; el 10 % marcado `muestra_capas` se le entrega con las salidas por capa |
| `desarrollo` | nomiracl-dev, sqac-dev | elige hiperparámetros y el punto de parada | lo único que puede evaluar con su presupuesto de pasadas |
| `prueba` | **nomiracl-test** (principal), xquad-test y sqac-test (secundarias) | se mide una vez, al final | no la ve nunca |

**Fugas.** Se saca del entrenamiento toda pregunta que coincida con desarrollo o prueba en cualquiera de estos
puntos:

- la pregunta normalizada, contando también las preguntas `non_relevant` de NoMIRACL;
- el texto exacto de un pasaje correcto;
- el documento o artículo, salvo en MIRACL, donde el documento es un artículo de Wikipedia compartido por diseño
  y la fuga se controla por pregunta y por pasaje.

**Grupos de entrenamiento.** Cada pregunta da un grupo con:

- **1 positivo**: el que bge puntúa peor;
- **7 negativas**: primero las que bge pone sobre ese positivo, después las de mayor puntaje.

Es el formato de FlagEmbedding que ya lee `afinar.py`, con campos extra para estratificar (`neg_tipo`,
`verificacion`, `base`, `registro`).

**Cuota de dificultad.** Un grupo es *difícil* si bge no pone un correcto primero o gana por menos de 1 logit. Se
conservan todos los difíciles y se agregan fáciles, sorteados por hash, hasta que los difíciles sean el 40 %. Los
fáciles sirven de retención dentro del propio entrenamiento.

**Muestra para el experimento 2.** `muestra_capas` marca el 10 % de los grupos por hash del id. Es la misma muestra
en cualquier máquina.

### 6. `exportar-parafrasis` / `importar-parafrasis`: registro informal

**Qué hace.** Exporta solo las **preguntas**, sin pasajes ni respuestas, para que los redactores no copien la
evidencia. Hay dos pedidos:

- `--parte evaluacion`: 200 de NoMIRACL `dev` y 500 de NoMIRACL `test`. Sale de la etapa 2 y se pidió mientras
  corría la 3;
- `--parte entrenamiento`: 1 000 grupos, 60 % difíciles. Sale de la etapa 5.

Cada pedido se parte en dos mitades, una por redactor. Los redactores son dos subagentes Claude Haiku en paralelo
que siguen [`guia_parafrasis.md`](guia_parafrasis.md). La importación valida cada paráfrasis por reglas:

- es distinta del original;
- tiene de 2 a 30 palabras;
- no agrega la respuesta;
- conserva al menos una palabra de contenido;
- no está en inglés.

Una paráfrasis **reusa los pasajes y las etiquetas** de su pregunta, así que no introduce etiquetas nuevas.

- En **entrenamiento**, cada paráfrasis agrega una copia informal del grupo.
- En **desarrollo y prueba**, las paráfrasis van en archivos aparte (`nomiracl-dev-informal`,
  `nomiracl-test-informal`). Así la métrica informal se reporta separada de la formal, sobre las mismas preguntas.

### 7. `congelar`: archivos finales, hashes y línea base

**Qué hace.** Escribe `7-congelado/` con:

- `entrenamiento.jsonl` (grupos formales e informales);
- un archivo por conjunto de desarrollo y de prueba, en el formato de volcado que ya leen `diagnostico.py` y
  `puntuar_fuera.py`, con el logit `base` de cada pasaje;
- `manifiesto.json`: SHA-256 de cada archivo, licencias, la regla de etiquetas, la prueba principal y la línea
  base (hit@1, hit@3 y MRR@10 del modelo sin tocar).

Desde aquí **nada cambia**. `evaluar` se niega a correr si un hash no coincide.

### `evaluar`: antes y después, igual para los dos experimentos

```bash
python laboratorio_reranker/conjunto.py evaluar --modelo onnx-int8                 # el base (control)
python laboratorio_reranker/conjunto.py evaluar --modelo local:<carpeta exportada>  # cada candidato
python laboratorio_reranker/conjunto.py evaluar --modelo local:<…> --incluir-prueba # medición final, una vez
```

- **Qué reporta, por archivo:** hit@1, hit@3 y MRR@10 del modelo; las mismas métricas del base; hit@1 ganados y
  perdidos; McNemar exacto.
- **Entrenamiento y práctica:** con `--incluir-entrenamiento` mide también el ajuste sobre el entrenamiento, o
  solo sobre la muestra de Astra con `--solo-muestra-capas`.
- **Registro:** guarda una ejecución en `.cache/laboratorio-reranker/<run_id>/` con los puntajes por caso.

## Potencia

Potencia del McNemar exacto (α = 0,05) simulada según el tamaño de la prueba y las tasas de casos ganados y
perdidos:

| n de la prueba | gana 3 %, pierde 1,5 % | gana 5 %, pierde 3 % | gana 4 %, pierde 1 % |
|---|---|---|---|
| 52 (sintética v1) | 0,01 | 0,01 | 0,02 |
| 300 | 0,17 | 0,15 | 0,57 |
| 648 (NoMIRACL `dev`) | 0,39 | 0,38 | 0,94 |
| 1 515 (NoMIRACL `test`) | 0,79 | 0,75 | 1,00 |

Tras la etapa 2 quedan 1 408 preguntas (las 107 restantes no tienen negativa juzgada), con potencia ≈ 0,75 para
una mejora neta de 1,5 puntos. La prueba **primaria** es una sola: hit@1 en NoMIRACL `test`. Las secundarias
(informal, XQuAD y SQAC) se corrigen por Holm.
