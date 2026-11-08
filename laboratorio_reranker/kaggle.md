# Entrenar en Kaggle (experimento 1) y volcar las capas para Astra (experimento 2)

El conjunto v2 se congeló en el PC del usuario (OBS-0016), cuya GPU (GTX 1650 de portátil) es demasiado lenta para
entrenar. El entrenamiento se hace en un notebook de Kaggle con GPU, y la medición final en int8 vuelve al PC.

| Dónde | Qué |
|---|---|
| PC | Conjunto congelado, línea base y evaluación final int8 (`conjunto.py evaluar`) |
| Kaggle (GPU) | Entrenamiento B1 y B2 (`afinar.py entrenar`), exportación a ONNX int8 y salidas por capa del modelo base |

## 1. Preparar la cuenta (una vez)

1. Crear la cuenta en kaggle.com y **verificar el teléfono** (Settings → Phone verification). Sin eso no hay GPU
   ni internet en los notebooks.
2. La cuota gratuita es de unas 30 h de GPU por semana. Una sesión dura como máximo 12 h.

## 2. Subir el conjunto congelado como dataset privado (una vez)

Desde el PC, sube estos archivos de `.cache\laboratorio-reranker\conjunto-v2\7-congelado\`:

- `entrenamiento.jsonl`
- `nomiracl-dev.jsonl`
- `nomiracl-dev-informal.jsonl`
- `manifiesto.json`

En Kaggle: **Datasets → New Dataset**, nombre `ipsis-conjunto-v2`, visibilidad **Private**. Los textos tienen
licencias CC BY-SA y Apache: el dataset queda privado y no se publica.

**No subas los archivos de prueba.** Así, el entrenamiento no puede verlos ni por accidente.

## 3. Crear el notebook

**Code → New Notebook**, y en el panel derecho:

- **Accelerator:** GPU T4 x2 (el código usa una sola GPU). Sirve también P100.
- **Internet:** On.
- **Add Input:** el dataset `ipsis-conjunto-v2`.

Las celdas siguientes se ejecutan en orden.

### Celda 1: código y dependencias

```python
!git clone -b lab061126 --depth 1 https://github.com/ClaudioH19/ipsis.git
%cd ipsis
!pip install -q peft==0.21.2 transformers==4.57.6 onnx==1.23.2 onnxruntime==1.31.0
```

### Celda 2: verificar que el conjunto es el congelado

```python
import json, hashlib, pathlib
D = pathlib.Path("/kaggle/input/ipsis-conjunto-v2")
m = json.loads((D / "manifiesto.json").read_text())
for nombre in ("entrenamiento.jsonl", "nomiracl-dev.jsonl", "nomiracl-dev-informal.jsonl"):
    sha = hashlib.sha256((D / nombre).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    print(nombre, "OK" if sha == m["archivos"][nombre]["sha256"] else "DISTINTO: no seguir")
```

### Celda 3: medir la velocidad (20 pasos)

```python
D = "/kaggle/input/ipsis-conjunto-v2"
!python laboratorio_reranker/afinar.py entrenar --metodo lora --lr 1e-4 --acumulacion 16 \
    --grupos {D}/entrenamiento.jsonl --desarrollo {D}/nomiracl-dev.jsonl --n-desarrollo 0 --pasos-prueba 20
```

Imprime los s/grupo, la memoria pico y una estimación de las horas restantes. Con 10 230 grupos por época:

- si una época de LoRA cabe holgada en 12 h, se corren 2 épocas por sesión;
- si no, se usa `--epocas 1`.

### Celda 4: una corrida (un brazo y una semilla)

Las variables `METODO` y `SEMILLA` se cambian en cada corrida:

```python
METODO, SEMILLA = "lora", 13          # brazos: "lora" (B2) y "parcial" (B1); semillas: 13, 17, 23
LR = "1e-4" if METODO == "lora" else "1e-5"
!python laboratorio_reranker/afinar.py entrenar --metodo {METODO} --desde-capa 12 --lr {LR} --semilla {SEMILLA} \
    --acumulacion 16 --epocas 2 --evaluar-cada 160 \
    --grupos {D}/entrenamiento.jsonl --desarrollo {D}/nomiracl-dev.jsonl --n-desarrollo 0
```

- **Parada temprana:** evalúa hit@1 en `nomiracl-dev` (617 preguntas, fp16) cada 160 pasos, que son ≈ ¼ de época,
  y guarda la copia del mejor punto.
- **Corridas:** son 6 (2 brazos × 3 semillas). Conviene una sesión por corrida, con **Save Version → Save & Run
  All**: corre en segundo plano y deja la salida guardada.

### Celda 5: exportar a ONNX int8 y dejar solo lo necesario

```python
import glob, os, shutil
run = sorted(glob.glob(".cache/laboratorio-reranker/*-e4-afinado-*"))[-1]
!python laboratorio_reranker/afinar.py exportar {run} --paridad {D}/nomiracl-dev.jsonl --n-paridad 50
nombre = f"{METODO}-s{SEMILLA}"
destino = f"/kaggle/working/salidas/{nombre}"
os.makedirs(f"{destino}/onnx", exist_ok=True)
shutil.copy(f"{run}/onnx/onnx/model_int8.onnx", f"{destino}/onnx/")
for archivo in ("tokenizer.json", "config.json", "exportacion.json"):
    shutil.copy(f"{run}/onnx/{archivo}", destino)
shutil.copy(f"{run}/run.json", destino)
print(open(f"{destino}/exportacion.json").read())
```

Se descarga solo `salidas/<nombre>/`, unos 570 MB por modelo. La copia fp32 y el ONNX fp32 (≈ 4,5 GB) se quedan
fuera.

### Celda 6 (una sola vez): salidas por capa del modelo base para Astra

```python
!python laboratorio_reranker/afinar.py volcar-capas --grupos {D}/entrenamiento.jsonl \
    --destino /kaggle/working/salidas/astra
```

- **Contenido:** el vector `<s>` de las 25 salidas, más el logit y la etiqueta, para cada pasaje de los grupos
  `muestra_capas`. Son ≈ 10 % del entrenamiento: unos 1 000 grupos y 8 000 pares.
- **Fuente:** siempre del modelo **base**.
- **Archivos:** `capas_base.npz`, `capas_base_indice.jsonl` y `capas_base.json`, con el SHA-256.

## 4. Volver al PC

1. En Kaggle, en la pestaña **Output** de la versión, descargar `salidas/`.
2. Copiar cada modelo a `.cache\laboratorio-reranker\modelos\<nombre>\`. Debe quedar `onnx\model_int8.onnx` junto
   a `tokenizer.json` y `config.json`.
3. La evaluación final en int8, **una sola vez**, con los finalistas de los dos experimentos:

   ```bat
   python laboratorio_reranker\conjunto.py evaluar --modelo local:.cache\laboratorio-reranker\modelos\lora-s13 --incluir-prueba
   ```

## Qué se registra

Cada corrida deja `run.json` con:

- el método, los hiperparámetros, la semilla y el SHA de los grupos;
- la GPU y su memoria pico;
- la curva de desarrollo y el mejor punto;
- `original_intacto: true`.

`exportacion.json` guarda la paridad entre PyTorch y el int8. Las dos cosas se suben a la bitácora como una
observación por brazo.
