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
D = "/kaggle/input/ipsis-conjunto-v2"   # la ruta de tu dataset en Kaggle
for por_pasada in (1, 2, 4):
    !python laboratorio_reranker/afinar.py entrenar --metodo lora --lr 1e-4 --acumulacion 16 --no-checkpointing \
        --grupos-por-pasada {por_pasada} --grupos {D}/entrenamiento.jsonl --desarrollo {D}/nomiracl-dev.jsonl \
        --n-desarrollo 0 --pasos-prueba 20
```

Hay que elegir el `--grupos-por-pasada` con menos s/grupo que no se quede sin memoria («CUDA out of memory»).
`--no-checkpointing` ya bajó de 0,38 a 0,25 s/grupo con 6,7 GB de memoria pico, y la pérdida fue idéntica.
Agrupar no cambia la pérdida: probado sin dropout, con la misma pérdida por grupo hasta el quinto decimal.

### Celda 4: dos corridas en paralelo, una por GPU (T4 x2)

La parada se decide con **todo el desarrollo junto**: `nomiracl-dev`, `nomiracl-dev-informal` y `sqac-dev`, unas
2 700 preguntas, con menos ruido que `nomiracl-dev` solo (OBS-0017). El log muestra además el desglose por archivo.

```python
import os, subprocess
D = "/kaggle/input/datasets/claudioag/ipsis-private"   # la ruta de tu dataset
DEV = f"{D}/nomiracl-dev.jsonl {D}/nomiracl-dev-informal.jsonl {D}/sqac-dev.jsonl"

def correr(gpu, nombre, extra):
    cmd = (f"python laboratorio_reranker/afinar.py entrenar --desde-capa 12 --acumulacion 16 --no-checkpointing "
           f"--evaluar-cada 80 --grupos {D}/entrenamiento.jsonl --desarrollo {DEV} --n-desarrollo 0 {extra}")
    log = open(f"/kaggle/working/log-{nombre}.txt", "w")
    return subprocess.Popen(cmd, shell=True, stdout=log, stderr=subprocess.STDOUT, cwd="/kaggle/working/ipsis",
                            env=dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu)))

procesos = [
    correr(0, "lora-lr1e4-s13", "--metodo lora --lr 1e-4 --epocas 1 --semilla 13"),
    correr(1, "lora-lr5e5-miracl3-s13", "--metodo lora --lr 5e-5 --epocas 1 --semilla 13 --repetir-fuente miracl=3"),
]
print([p.wait() for p in procesos])   # [0, 0] = terminaron bien
```

Para ver el avance sin detener nada, desde otra celda:
`!grep desarrollo /kaggle/working/log-*.txt | tail -n 4`.

### Celda 5: exportar a ONNX int8 y dejar solo lo necesario

```python
import glob, json, os, shutil
for run in sorted(glob.glob(".cache/laboratorio-reranker/*-e4-afinado-*")):
    datos = json.load(open(f"{run}/run.json"))
    c = datos["config"]
    nombre = f"{c['metodo']}-lr{c['lr']}-{'-'.join(c.get('repetir_fuente') or ['mezcla'])}-s{c['semilla']}"
    destino = f"/kaggle/working/salidas/{nombre}"
    if os.path.exists(f"{destino}/onnx/model_int8.onnx"):
        continue
    !python laboratorio_reranker/afinar.py exportar {run} --paridad {D}/nomiracl-dev.jsonl --n-paridad 50
    os.makedirs(f"{destino}/onnx", exist_ok=True)
    shutil.copy(f"{run}/onnx/onnx/model_int8.onnx", f"{destino}/onnx/")
    for archivo in ("tokenizer.json", "config.json", "exportacion.json"):
        shutil.copy(f"{run}/onnx/{archivo}", destino)
    shutil.copy(f"{run}/run.json", destino)
    shutil.rmtree(f"{run}/onnx")   # libera ~2,3 GB; copia/ se conserva para evaluar-dev (celda 7)
    print(nombre, open(f"{destino}/exportacion.json").read())
```

Se descarga solo `salidas/<metodo>-s<semilla>/`, unos 570 MB por modelo.

### Celda 7: diagnóstico en desarrollo (antes de decidir la siguiente configuración)

```python
import glob
runs = " ".join(sorted(glob.glob(".cache/laboratorio-reranker/*-e4-afinado-*")))
!python laboratorio_reranker/afinar.py evaluar-dev --copia {runs} \
    --desarrollo {D}/nomiracl-dev.jsonl {D}/nomiracl-dev-informal.jsonl {D}/sqac-dev.jsonl \
    --salida /kaggle/working/salidas/evaluar-dev.json
```

Mide el base y cada copia (la del mejor paso de desarrollo) en fp16, con hit@1 ganado y perdido frente al base y
McNemar exacto por archivo. Necesita `sqac-dev.jsonl` en el dataset (es de desarrollo). Se niega a medir
archivos de prueba.

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
