# Laboratorio del reranker

Estado: **etapa 3 lista (OBS-0012) y herramienta de afinado verificada (OBS-0013); falta entrenar en la GPU.** 1 716 grupos (SQAC, MIRACL y sintético
propio); prueba sintética congelada. Se afinarán las capas 12–24 y la cabeza de una **copia** del modelo
(variante: afinado completo). La cuantización int8 no es la causa (OBS-0005,
OBS-0007). En CPU de portátil el presupuesto corta el reranking (OBS-0008). De los 15 errores del reranker en el
banco real, 10 son de formulación o del modelo (D + E) y 5 de la tubería o la medición (OBS-0009). Vive dentro del repo para reutilizar los volcados de candidatos y
el modelo ONNX del motor, pero **no modifica `ipsis/`**: solo importa. No entra al paquete (`pyproject.toml`
empaqueta `ipsis*`) ni al sdist.

## 1. Pregunta

En español, `medium` usa `onnx-community/bge-reranker-v2-m3-ONNX`: int8, 10 candidatos, 256 tokens y lotes de 2.
En los documentos reales, la fuente correcta queda casi siempre entre las tres primeras, pero no siempre en el
primer puesto:

| Banco (estructural, `medium`, es) | n | hit@1 | hit@3 | Errores de orden (correcta en 2–3) |
|---|---|---|---|---|
| 56 adversarias (formal + informal) | 56 | 0,857 (0,893 con rasgos) | 0,946 | ≈ 5 |
| 33 formales | 33 | 0,849 | 1,000 | ≈ 5 |
| Banco de pasajes sintético, `test` | 44 | 1,000 | 1,000 | 0 (saturado) |

Fuente: `docs/plan/precision-ingesta-avance.md`. Lo que ya se probó y **no** movió hit@1:

- otro modelo denso;
- la ventana de 256 → 512 tokens;
- más candidatos (10 → 20 → 60);
- otros rerankers integrables de ≤ 0,6 B.

**Pregunta del laboratorio:** ¿por qué bge deja la fuente correcta en el puesto 2–3, y esa causa se corrige
afinando el modelo o en otro lugar?

**Fuera de alcance:** los fallos de recuperación (la correcta no está entre los 10 candidatos), la abstención y
la presentación.

## 2. Decisiones y restricciones

- **Experimento aparte de la regla «producto sin entrenamiento»** (decisión del usuario, 2026-10-17). Si el
  afinado se justifica, se entrena **una sola vez** y se publica como un checkpoint ONNX int8, que el producto
  reutiliza como cualquier otro modelo descargable. Ningún cliente entrena. El modelo tiene que ser genérico (no
  aprender un dominio) y conservar la arquitectura y el costo de bge.
- **Primero se descarta la cuantización** (control C1, § 4) antes de cualquier otra hipótesis.
- **Prueba en dos fuentes** (§ 5): conjuntos públicos con juicios de «responde / solo relacionado», y un banco
  sintético propio.
- **Los textos sintéticos los escribe Claude** (paráfrasis informales, documentos y preguntas). Cada ejemplo
  registra su `origen`.
- **CPU y tiempo.** Todo se ejecuta en CPU. **Máximo 3 s por consulta** (decisión del usuario, 2026-10-17). En
  CPU de portátil el costo por par de bge (≈ 500 ms en un Ryzen 5 7530U) hace que el presupuesto corte el
  reranking (OBS-0008). Las arquitecturas y optimizaciones para CPU (pasajes más cortos, modelos más chicos,
  destilación, otra cuantización) quedan como línea futura, separada de la pregunta del afinado. El afinado de la
  etapa 4 puede usar GPU si conviene; el modelo publicado debe correr en CPU.
- **Privacidad.** Los documentos reales no están en el repo. Ni los volcados ni la bitácora se versionan con su
  texto: la bitácora cita solo `id` de caso.
- **Informal primero.** Toda métrica se reporta también separada en formal e informal.

## 3. Archivos (carpeta plana)

| Archivo | Etapa | Qué hace |
|---|---|---|
| `README.md` | — | Diseño y protocolo |
| `bitacora.md` | todas | Observaciones `OBS-nnnn`: lo visto separado de lo interpretado |
| `requisitos.txt` | 0 | Versiones del entorno aparte |
| `comun.py` | 0 | Scorers fieles al motor (ONNX int8/fp32/fp16 y PyTorch fp32 con los **mismos ids**), `run_id`, registro |
| `datos.py` | 0, 3 | `nomiracl`: conjunto público → formato de volcado; `sintetico` y `real`: materializan los bancos (§ 5.2, § 7); más adelante, el conjunto de afinado |
| `banco_sintetico.yaml` | 0 | Piloto sintético (`dev`, descubrimiento; § 5.2), escrito por Claude |
| `sintetico_entrenamiento.yaml` | 3 | Documentos y preguntas sintéticos para afinar (6 dominios, 68 preguntas) |
| `sintetico_prueba.yaml` | 4 | Prueba sintética **congelada** (4 dominios, 52 preguntas); hash en la bitácora |
| `diagnostico.py` | 0–1 | Controles por caso. Implementado: `cuantizacion` (C1) |
| `interior.py` | 2 | Oclusión por palabra y sondas lineales por capa (pendiente) |
| `afinar.py` | 4 | Entrena una **copia** del modelo (el original de la caché no se toca y su hash se verifica), la exporta a ONNX int8 y comprueba la paridad (pendiente) |

Las salidas, los datos descargados y el entorno van a `.cache/laboratorio-reranker/`, que git ignora. En esta
carpeta no se crean subcarpetas.

**Reutiliza, no duplica:**

- `herramientas/evaluacion/ranking_pasajes.py --volcar-candidatos` graba los pasajes exactos que recibe el
  reranker;
- `puntuar_fuera.py` aporta `cargar_candidatos`, `rango_de`, `metricas` y `es_informal`;
- `tokens_fragmentos.py` mide si la evidencia cae fuera de la ventana.

### Entorno

```bash
uv venv .cache/laboratorio-reranker/venv --python 3.12
uv pip install --python .cache/laboratorio-reranker/venv/Scripts/python.exe torch --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .cache/laboratorio-reranker/venv/Scripts/python.exe -e . -r laboratorio_reranker/requisitos.txt
```

### Entrenar en otra máquina (GPU de 4 GB, p. ej. GTX 1650)

El entrenamiento (`afinar.py entrenar`) solo necesita torch, transformers y los grupos de la etapa 3; no necesita
ipsis, ni los modelos ONNX, ni el banco real. **Los grupos no contienen nada del cliente**, así que se pueden copiar.

1. Clonar el repo y pasar a la rama `laboratorio-reranker`.
2. Entorno (Windows o Linux, con el driver de NVIDIA y `nvidia-smi` funcionando). No hace falta instalar ipsis:

   ```bash
   uv venv .cache/laboratorio-reranker/venv --python 3.12
   uv pip install --python <venv>/python torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126
   uv pip install --python <venv>/python transformers==4.57.6 huggingface_hub scikit-learn==1.9.1 pyarrow
   ```

   (En Windows, `<venv>/python` es `.cache/laboratorio-reranker/venv/Scripts/python.exe`.)
3. Regenerar el conjunto de afinado: descarga SQAC, MIRACL y la lista de exclusión de NoMIRACL con revisiones
   fijadas, y toma los grupos sintéticos versionados (`grupos_sinteticos.jsonl`). Es determinista:

   ```bash
   python laboratorio_reranker/datos.py entrenamiento
   ```

   Debe imprimir `sha256.entrenamiento = 94aaf75221e886b7…` y `sha256.desarrollo = dc9be08b6931a184…`, los mismos
   del portátil (se verificó regenerando desde cero). Si no coinciden, revisar la versión de scikit-learn antes de
   entrenar. Los datos de SQAC y MIRACL no se versionan porque tienen licencias propias.

4. Medir antes de entrenar. Se detiene a los 20 pasos e informa los s/grupo y la memoria pico de la GPU:

   ```bash
   python laboratorio_reranker/afinar.py entrenar --pasos-prueba 20
   ```

5. Entrenar con `python laboratorio_reranker/afinar.py entrenar`. La copia queda en
   `.cache/laboratorio-reranker/<run_id>/copia/`; `run.json` registra el desarrollo y `original_intacto: true`.
6. Exportar (en cualquiera de las dos máquinas; necesita `onnx` y `onnxruntime`) con
   `afinar.py exportar <run_id>`. Para medir en el portátil basta traer `onnx/` (int8, ~570 MB, más el tokenizador
   y la config).

En la GPU de 4 GB, lo congelado (embeddings y capas 0–11) va en fp16 y lo entrenable (capas 12–23 y cabeza) en
fp32. `--desde-capa` menor que 8 se rechaza: el afinado completo no cabe en 4 GB y se hace en CPU.

Los modelos ONNX se descargan a la caché de ipsis (`IPSIS_MODELS_DIR` o `~/.cache/ipsis/models`). El modelo
PyTorch se descarga a la caché de Hugging Face. Las revisiones están fijadas en `comun.py`.

## 4. Etapas y puertas

Cada etapa termina en una puerta que puede detener el experimento. Que la investigación termine en la puerta 1
es un resultado válido.

### Etapa 0: línea base congelada

1. Volcar los candidatos del motor (estructural, `medium`, es, 10 candidatos) para el banco real (56 + 33), el
   banco sintético del laboratorio y el banco de pasajes `dev`.
2. Volver a puntuarlos con el scorer int8 de `comun.py` y comprobar que el orden coincide con el del motor.
3. Repetir la ejecución y exigir órdenes idénticos.
4. Listar los **errores de orden** (correcta en el rango 2–3), con su margen de logit, su longitud en tokens y si
   la evidencia cae dentro de la ventana.

### Etapa 1: diagnóstico sin tocar pesos

**C0, presupuesto y determinismo (OBS-0003).** El motor deja de puntuar cuando el lote siguiente no cabe en
`presupuesto_consulta_ms`, y los candidatos sin puntuar quedan en el orden híbrido. Por eso cada error de orden del
motor se repite fuera de él, con los mismos 10 candidatos y sin presupuesto. Si fuera del motor la correcta queda
primera, la causa es **G (presupuesto)**: el modelo no tuvo la oportunidad de equivocarse. Las mediciones del
motor se hacen con la CPU sin otra carga y se repiten dos veces.

**C1 va primero y se mide sobre todos los casos, no solo sobre los errores.** Se usan siempre los mismos ids de
token (los del motor):

| Efecto | Condición | Referencia | Si difiere… |
|---|---|---|---|
| Exportación | ONNX fp32, lote 2 | PyTorch fp32, lote 2 | la conversión a ONNX altera el modelo |
| Cuantización | ONNX int8, lote 2 | ONNX fp32, lote 2 | la cuantización es la causa (A) |
| Lote | ONNX int8, lote 1 y lote 10 | ONNX int8, lote 2 | la escala dinámica depende de los vecinos de lote |

La receta de onnx-community es dinámica, por canal y con `reduce_range` (pesos a 7 bits). Por eso el lote es un
efecto posible: la escala de las activaciones se calcula sobre el lote entero, padding incluido.

Se reporta por comparación:

- coincidencia del primer puesto;
- Kendall τ medio;
- pares invertidos;
- |Δlogit| p50/p95/máx;
- ganados y perdidos en hit@1, con McNemar exacto;
- el margen de la referencia en los casos discordantes.

**Criterio de C1, fijado antes de medir.** La cuantización se declara causa si se cumple al menos una de dos
condiciones:

- en el banco real, int8 pierde frente a fp32 al menos 2 de los errores de orden;
- en los conjuntos grandes, el McNemar de hit@1 tiene p < 0,05 a favor de fp32.

Si se declara causa, la solución se busca sin entrenar: otra cuantización (sin `reduce_range`, estática con
calibración, fp16, o excluyendo capas) y se vuelve a medir.

**Resto de controles**, una variable a la vez y solo sobre los errores de orden, más igual número de casos bien
ordenados como control:

| Control | Variable | Si arregla el caso, la causa es… |
|---|---|---|
| C2 Ventana | 256 / 512 / sin límite; ¿la palabra que distingue entra en la ventana? | el truncamiento (B) |
| C3 Vista | hijo recuperado / padre completo / solo la oración de la evidencia (oráculo) | la dilución o la posición (B). **El oráculo se descartó:** rompe 7 de 12 aciertos (OBS-0009). B se diagnostica buscando la evidencia en el texto exacto que ve el reranker |
| C4 Información | anteponer a **todos** los candidatos su alcance y su ruta de sección | falta información en el pasaje (C) |
| C5 Formulación | la versión formal del mismo objetivo | la brecha de vocabulario informal (D) |
| C6 Etiqueta | revisión humana: ¿el primero también responde? | etiqueta dudosa (F) |
| C7 Consenso | los mismos candidatos con mMiniLM, Horizon base y mxbai v2 | orienta, no asigna causa |

**Asignación de causa:** se aplica el primer control que arregla el caso, en este orden: C0, C6, C1, C2/C3, C4, C5.
Si ninguno lo arregla, la causa es **E**: el modelo ve la información y aun así ordena mal.

**Puerta 1.** El afinado solo apunta a **D** (vocabulario informal) y **E** (discriminación fina con la
información presente). Si D + E son menos de la mitad de los errores de orden, no se afina y se informa dónde
está la solución:

- A: la cuantización;
- B: la ventana o la vista;
- C: la ingesta;
- F: el banco.

### Etapa 2: interior, solo para D y E

bge-reranker-v2-m3 es XLM-RoBERTa large (24 capas) más una cabeza de clasificación. Lo que se mide es **dónde se
vuelve separable** la diferencia entre el pasaje correcto y su competidor, y si esa separación se pierde al final:

- **Oclusión** (fp32): quitar cada palabra, una a la vez, y medir la variación del logit. ¿La palabra que
  distingue pesa algo?
- **Sondas por capa:** el vector `[CLS]` de cada capa para los pares (pregunta, correcto) y (pregunta,
  competidor), con una regresión logística validada por grupo de pregunta. Se reporta separado en formal e
  informal.
- La atención es opcional y no se usa para concluir.

| Patrón | Lectura | Afinado indicado |
|---|---|---|
| La separación aparece en capas medias y cae al final | las capas superiores pierden la señal | últimas capas y cabeza |
| Nunca hay separación | la representación no la tiene | completo, o volver a C |
| Hay separación en la última capa pero el logit falla | calibración de la cabeza | solo la cabeza |

**Puerta 2.** Elegir qué capas descongelar, justificado con la gráfica.

### Etapa 3: conjunto de afinado

Unidad: `(pregunta, positivo, 7 negativos difíciles)`, en el formato de grupos de FlagEmbedding.

- **Negativos:** unidades hermanas del mismo documento y candidatos que el bge actual pone por encima del
  positivo.
- **Fuentes:** el banco sintético (§ 5.2, particiones de entrenamiento), SQAC (positivo verificable por el tramo
  de respuesta; negativos entre los párrafos hermanos del mismo artículo que no contienen ese tramo) y MIRACL-es
  `train`. Solo se usan fuentes con licencia compatible con publicar el modelo.
- **Retención:** `banco_validacion`, `banco_coloquial` y `banco_garantias` (es), más NoMIRACL `dev`, para
  detectar olvido.

### Etapa 4: afinado piloto

- Base: `BAAI/bge-reranker-v2-m3` fp32 con revisión fijada; `max_length` 256.
- Pérdida: entropía cruzada sobre el grupo.
- Hiperparámetros: lr 1e-5, warmup 10 %, 1 época; capas según la puerta 2.
- Antes de lanzar, medir 20 pasos para estimar la duración. Repetir con 3 semillas si cabe.
- Exportar a ONNX int8 y repetir C1 sobre el modelo afinado.
- Evaluar fuera de línea con los candidatos volcados. La medición dentro del motor se hace una sola vez, al final.

**Criterios de éxito (se fijan antes de la etapa 4 y no se mueven):**

1. **Prueba congelada:** McNemar exacto bilateral, α = 0,05. Mínimos: 6 ganados con 0 perdidos, 8 con 1, o 10
   con 2. Se reporta por fuente (pública y sintética) y por registro (formal e informal).
2. hit@3 no baja; hit@1 informal no baja.
3. **Retención:** ninguna pérdida en `general.py` frente a su referencia, ni en `banco_pasajes` `test`.
4. p95 dentro de ±10 % del bge actual.

Si no se cumplen, se registra como resultado negativo y el laboratorio se cierra.

## 5. Datos de prueba

Los ≈ 10 errores de orden del banco real original ya se usaron para elegir bge, la ventana y los rasgos; el banco
real nuevo (§ 7) se escribió mirando los mismos documentos. Ambos sirven para **descubrir**, no para probar. La prueba sale de dos fuentes que el laboratorio no ha mirado.

### 5.1 Conjuntos públicos: «responde» frente a «solo relacionado»

No encontré un conjunto en español que etiquete explícitamente los negativos relacionados que no responden. Los
que más se acercan:

| Conjunto | Qué aporta | Juicio | Licencia | Uso |
|---|---|---|---|---|
| [NoMIRACL](https://huggingface.co/datasets/miracl/nomiracl) es | Pasajes recuperados para cada pregunta, juzgados por nativos como relevantes o no relevantes. Su subconjunto `non_relevant` no tiene ningún pasaje que responda | humano | Apache-2.0 en la ficha; el artículo dice CC BY-SA (Wikipedia) | C1 (`dev`), prueba congelada (`test`), retención |
| [MIRACL](https://huggingface.co/datasets/miracl/miracl) es | 2 162 preguntas de `train` con negativos juzgados por nativos (no solo «no recuperados») | humano | Apache-2.0 | entrenamiento |
| [SQAC](https://huggingface.co/datasets/PlanTL-GOB-ES/SQAC) | 18 817 preguntas extractivas sobre 6 247 contextos; el tramo de respuesta permite verificar que un pasaje responde | derivado del tramo | CC BY-SA 4.0 | entrenamiento; prueba de hermanos |
| [MessIRve](https://huggingface.co/datasets/spanish-ir/messirve) | ~700 mil consultas reales de autocompletado de Google (registro coloquial) | fragmento destacado de Google, no humano | **CC BY-NC 4.0** | solo evaluación interna, nunca entrenamiento |
| mMARCO-es | traducción de MS MARCO | — | términos no comerciales | descartado |
| Horizon multilingual-rerank-distill | 47 idiomas | puntajes de un modelo maestro | — | descartado: no dice si responde |

Advertencias:

- BGE-M3 usó MIRACL `train` en su entrenamiento. NoMIRACL `dev`/`test` no aparecen en esa lista, pero las cifras
  absolutas pueden salir optimistas. Para C1 no importa, porque se comparan precisiones del mismo modelo.
- Entrenar con textos CC BY-SA y publicar pesos es una cuestión de licencia sin resolver del todo. Hay que
  revisarla antes de publicar.

### 5.2 Banco sintético del laboratorio (lo escribe Claude)

Su objetivo es reproducir los fallos observados, no las preguntas fáciles: el banco de pasajes actual está
saturado (0,98–1,00 con cualquier reranker), así que este banco tiene que ser **más difícil a propósito**.

- **Documentos** en Markdown, de dominios distintos a los de `banco_pasajes` (universidad, salud, municipio,
  transporte, banca, RRHH público…). Cada documento tiene:
  - unidades hermanas que solo se distinguen por un actor, un período o una columna, con **filas de tabla** como
    las P1/P2 reales;
  - pasajes del mismo tema que responden **otro aspecto** (la pregunta pide un plazo y el pasaje da un monto).
- **Preguntas:** cada objetivo tiene una versión formal y otra informal (sin tildes, abreviaturas, coloquial, con
  brecha léxica), una evidencia con offsets exactos y un tipo de dificultad (`hermana`, `otro_aspecto`,
  `brecha_lexica`). Además hay trampas en las que ningún pasaje responde.
- **Particiones por documento y por dominio:** entrenamiento, desarrollo y prueba no comparten documentos ni
  plantillas de pregunta.
- **Formato:** un solo `banco_sintetico.yaml` versionado en esta carpeta (documentos y casos). La respuesta se
  ubica dentro de su sección, porque las tablas hermanas repiten cifras. `datos.py sintetico` lo materializa en
  `.cache/laboratorio-reranker/banco-sintetico/` con el formato de `banco_pasajes`, y `ranking_pasajes.py` lo
  pasa por el **motor completo**: los candidatos salen de la recuperación real, no de listas armadas a mano.
- **Piloto (hecho, `dev`):** 2 documentos (prácticas clínicas con tres tablas hermanas; ordenanza de
  estacionamiento con tres zonas) y 24 objetivos, es decir, 48 preguntas. Primero se mide la tasa de error de bge
  con el motor. Si produce errores de orden, el banco se escala a unos 10 documentos y 240 preguntas, y los
  documentos de prueba se escriben aparte. Si bge acierta todo, el diseño se endurece antes de escalar.

**Tamaño:** para que el criterio 1 sea alcanzable, la prueba necesita del orden de 15 o más errores de orden de
partida por fuente. Antes de congelar la prueba, se mide la tasa de error de bge en cada fuente.

**Reglas:**

- la prueba se congela (con su hash) antes de la etapa 4 y se mide una sola vez;
- ningún documento, dominio ni plantilla de prueba aparece en el entrenamiento;
- el banco real privado queda como descubrimiento y como confirmación final.

## 6. Registro por ejecución

Cada `run_id` guarda en `.cache/laboratorio-reranker/<run_id>/`:

- `run.json`: configuración, huella de cada volcado, commit, versiones, hardware, hilos, resumen y duración;
- `casos.jsonl`: por caso y condición, los logits, el rango de la correcta, los tokens y si hubo truncado.

El juicio humano se guarda aparte de la salida del modelo.

## 7. Banco real (privado)

Las 56 + 33 preguntas originales no están en esta máquina: se escribieron en una sesión remota. Por eso se armó
un banco **nuevo** sobre los mismos tres documentos del cliente (el reglamento y las dos versiones de la rúbrica).
Tiene 32 objetivos, con una pregunta formal y otra informal cada uno: pares P1/P2, reglas sueltas y rúbrica. Las
preguntas las escribió Claude imitando el banco original.

**Privacidad:**

- los documentos se leen desde su carpeta, fuera del repo;
- la copia, las preguntas (`casos.yaml`), el banco y los volcados viven solo en
  `.cache/laboratorio-reranker/banco-real/` y en `.cache/laboratorio-reranker/datos/real.jsonl`, que git ignora;
- `datos.py real` se niega a copiar los documentos dentro del repo fuera de `.cache/`;
- en el repo y en la bitácora solo aparecen `id` de caso y cifras agregadas.

```bash
PY=.cache/laboratorio-reranker/venv/Scripts/python.exe
L="$(pwd)/.cache/laboratorio-reranker"     # rutas absolutas: ranking_pasajes trabaja en un proyecto temporal
$PY laboratorio_reranker/datos.py real <carpeta_de_documentos>     # lee $L/banco-real/casos.yaml
$PY herramientas/evaluacion/ranking_pasajes.py $L/banco-real/manifiesto.json --perfil medium --idioma es \
    --particion todas --rasgos 5 --umbral-hermanos 0.6 --volcar-candidatos $L/datos/real.jsonl --salida $L/banco-real/ranking
$PY laboratorio_reranker/diagnostico.py cuantizacion $L/datos/real.jsonl --condiciones onnx-int8@2,onnx-int8@1,onnx-fp32@2
```

`ipsis load` nombra cada documento con el slug de su archivo; el `doc_id` del YAML es solo un alias para las
evidencias.
