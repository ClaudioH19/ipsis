"""Etapa 4: afina una COPIA de bge-reranker-v2-m3 y la exporta a ONNX int8 para el motor (CPU).

El original nunca se modifica: se lee de la caché de Hugging Face con la revisión fijada, se calcula el SHA-256 de
``model.safetensors`` antes y después, y la copia se guarda en ``.cache/laboratorio-reranker/modelos/<run_id>/``.
Si la copia rinde peor, se descarta y el motor sigue con el bge actual.

**Qué se entrena** (puerta 2, bitácora): las capas ``--desde-capa`` (12 por defecto) a 23 y la cabeza; el resto
queda congelado. ``--desde-capa 0`` es el afinado completo (solo en CPU o en GPU de más de 8 GB).

**GPU de 4 GB (GTX 1650):** las capas congeladas se cargan en fp16 y las entrenables en fp32; atención «eager»
(la ruta SDPA no admite la mezcla de tipos), Adafactor (estado factorizado, casi sin memoria) y recálculo de
activaciones. En CPU todo va en fp32.

**Pérdida:** entropía cruzada sobre cada grupo (1 positivo y N negativos, ``datos.py entrenamiento``), con
acumulación de gradientes.

    # 1) medir 20 pasos (velocidad y memoria) y detenerse
    python laboratorio_reranker/afinar.py entrenar --pasos-prueba 20
    # 2) entrenar de verdad
    python laboratorio_reranker/afinar.py entrenar
    # 3) exportar la copia a ONNX fp32 + int8 (misma receta que onnx-community) y comprobar la paridad
    python laboratorio_reranker/afinar.py exportar .cache/laboratorio-reranker/modelos/<run_id>

Para la máquina con GPU, ver README § 3 («Entrenar en otra máquina»).

**Conjunto v2 y LoRA (rama ``lab061126``, ``experimento1_afinado.md``).** ``--metodo lora`` entrena adaptadores LoRA
en las 24 capas y la cabeza completa, y al guardar los **fusiona**: la copia tiene la arquitectura y el costo de bge.
``--grupos`` y ``--desarrollo`` aceptan los archivos congelados del conjunto v2 (``entrenamiento.jsonl`` y
``nomiracl-dev.jsonl``, formato de volcado); con este último la parada se decide por hit@1. En CUDA, ``--amp`` (por
defecto) usa precisión mixta fp16 con pesos maestros en fp32. Para entrenar en Kaggle, ver ``kaggle.md``.

    python laboratorio_reranker/afinar.py entrenar --metodo lora --grupos <entrenamiento.jsonl> \
        --desarrollo <nomiracl-dev.jsonl> --semilla 13
    python laboratorio_reranker/afinar.py volcar-capas --grupos <entrenamiento.jsonl>   # experimento 2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

from comun import MAX_TOKENS_MOTOR, ONNX_ID, SALIDA, TORCH_ID, TORCH_REV, Ejecucion, huella

AFINADO = SALIDA / "afinado"


# ---------------------------------------------------------------------------
# El original, intacto
# ---------------------------------------------------------------------------
def pesos_originales() -> Path:
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(TORCH_ID, "model.safetensors", revision=TORCH_REV))


def sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 24), b""):
            digest.update(bloque)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Modelo con capas congeladas
# ---------------------------------------------------------------------------
def entrenables(nombre: str, desde_capa: int) -> bool:
    """Cabeza de clasificación y capas ``encoder.layer.{desde_capa..23}``."""
    if nombre.startswith("classifier."):
        return True
    if ".encoder.layer." in nombre:
        return int(nombre.split(".encoder.layer.")[1].split(".")[0]) >= desde_capa
    return desde_capa == 0  # embeddings: solo en el afinado completo


# Módulos con LoRA en cada capa: Q, K, V y la salida de la atención, y las dos matrices del MLP.
LORA_MODULOS = r".*encoder\.layer\.\d+\.(attention\.self\.(query|key|value)|attention\.output\.dense|intermediate\.dense|output\.dense)"


def aplicar_lora(modelo, rango: int, alfa: int, dropout: float):
    from peft import LoraConfig, get_peft_model

    config = LoraConfig(r=rango, lora_alpha=alfa, lora_dropout=dropout, target_modules=LORA_MODULOS,
                        modules_to_save=["classifier"], bias="none")
    return get_peft_model(modelo, config)


def cargar_modelo(desde_capa: int, dispositivo: str, checkpointing: bool, mixto: bool | None = None,
                  metodo: str = "parcial", lora: tuple[int, int, float] = (16, 32, 0.1)):
    """``mixto`` (por defecto, solo en CUDA sin ``--amp``): lo congelado en fp16 y lo entrenable en fp32.
    ``metodo="lora"``: todo el modelo base congelado en fp32 y adaptadores LoRA entrenables."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizador = AutoTokenizer.from_pretrained(TORCH_ID, revision=TORCH_REV)
    modelo = AutoModelForSequenceClassification.from_pretrained(
        TORCH_ID, revision=TORCH_REV, dtype=torch.float32, attn_implementation="eager")
    if metodo == "lora":
        if checkpointing:
            modelo.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
            modelo.enable_input_require_grads()
        modelo = aplicar_lora(modelo, *lora)
        modelo.to(dispositivo)
        return tokenizador, modelo
    for nombre, parametro in modelo.named_parameters():
        parametro.requires_grad = entrenables(nombre, desde_capa)
    if mixto if mixto is not None else dispositivo == "cuda":
        # Lo congelado en fp16 (no necesita precisión de gradiente); lo entrenable en fp32.
        modelo.roberta.embeddings.half()
        for i, capa in enumerate(modelo.roberta.encoder.layer):
            if i < desde_capa:
                capa.half()
        if 0 < desde_capa < len(modelo.roberta.encoder.layer):
            def a_fp32(_modulo, args, kwargs):
                args = tuple(a.float() if torch.is_tensor(a) and a.is_floating_point() else a for a in args)
                kwargs = {k: (v.float() if torch.is_tensor(v) and v.is_floating_point() else v)
                          for k, v in kwargs.items()}
                return args, kwargs
            modelo.roberta.encoder.layer[desde_capa].register_forward_pre_hook(a_fp32, with_kwargs=True)
    if checkpointing:
        modelo.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    modelo.to(dispositivo)
    return tokenizador, modelo


def puntuar_grupo(tokenizador, modelo, consulta: str, pasajes: list[str], dispositivo: str, max_tokens: int):
    import torch

    cod = tokenizador([consulta] * len(pasajes), pasajes, truncation="longest_first", max_length=max_tokens,
                      padding=True, return_tensors="pt").to(dispositivo)
    return modelo(**cod).logits[:, 0].float()


def leer_grupos(ruta: Path, negativos: int) -> list[dict]:
    """Grupos ``{query, pos, neg}`` (v1 y ``entrenamiento.jsonl`` del v2) o volcados ``{pregunta, pasajes}`` del v2
    (``nomiracl-dev.jsonl``): estos se evalúan por hit@1 con **todos** sus candidatos, como ``conjunto.py evaluar``."""
    grupos = [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
    for g in grupos:
        if "pasajes" in g:
            g["query"] = g["pregunta"]
            g["candidatos"] = [p["texto"] for p in g["pasajes"]]
            g["correctos"] = [bool(p["correcto"]) for p in g["pasajes"]]
        else:
            g["neg"] = g["neg"][:negativos]
    return grupos


def evaluar(tokenizador, modelo, grupos: list[dict], dispositivo: str, max_tokens: int) -> dict:
    import torch

    modelo.eval()
    if grupos and "candidatos" in grupos[0]:
        return evaluar_volcado(tokenizador, modelo, grupos, dispositivo, max_tokens)
    perdida, aciertos = 0.0, 0
    with torch.no_grad():
        for g in grupos:
            s = puntuar_grupo(tokenizador, modelo, g["query"], g["pos"][:1] + g["neg"], dispositivo, max_tokens)
            perdida += float(torch.nn.functional.cross_entropy(s[None], torch.zeros(1, dtype=torch.long,
                                                                                     device=s.device)))
            aciertos += int(s.argmax() == 0)
    modelo.train()
    return {"perdida": round(perdida / len(grupos), 4), "acierto_top1": round(aciertos / len(grupos), 4)}


def evaluar_volcado(tokenizador, modelo, filas: list[dict], dispositivo: str, max_tokens: int) -> dict:
    """hit@1, hit@3 y MRR@10 sobre listas con varios correctos (mismo criterio que ``conjunto.py medir``)."""
    import torch

    rangos = []
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16, enabled=dispositivo == "cuda"):
        for f in filas:
            s = puntuar_grupo(tokenizador, modelo, f["query"], f["candidatos"], dispositivo, max_tokens).tolist()
            orden = sorted(range(len(s)), key=lambda i: (-s[i], i))
            rangos.append(next(r for r, i in enumerate(orden, 1) if f["correctos"][i]))
    modelo.train()

    def resumen(rs: list[int]) -> dict:
        n = len(rs)
        return {"hit@1": round(sum(r == 1 for r in rs) / n, 4), "hit@3": round(sum(r <= 3 for r in rs) / n, 4),
                "mrr@10": round(sum(1 / r for r in rs if r <= 10) / n, 4), "n": n}

    salida = resumen(rangos)
    conjuntos = sorted({f.get("conjunto", "") for f in filas})
    if len(conjuntos) > 1:  # varios archivos de desarrollo: desglose por archivo en la misma pasada
        salida["por_archivo"] = {c: resumen([r for r, f in zip(rangos, filas, strict=True)
                                             if f.get("conjunto", "") == c]) for c in conjuntos}
    return salida


def _mejor(dev: dict, actual) -> bool:
    """Criterio de parada: hit@1 en desarrollo (volcados v2) o la pérdida (grupos del v1)."""
    if actual is None:
        return True
    if "hit@1" in dev:
        return (dev["hit@1"], dev["mrr@10"]) > (actual[1]["hit@1"], actual[1]["mrr@10"])
    return dev["perdida"] < actual[1]["perdida"]


def guardar_copia(modelo, tokenizador, destino: Path, desde_capa: int) -> None:
    """Original completo en fp32 + solo los parámetros entrenados: lo congelado no pasa por fp16 al guardar."""
    import torch
    from transformers import AutoModelForSequenceClassification

    if hasattr(modelo, "merge_and_unload"):  # LoRA: se fusiona una copia en CPU; el modelo en entrenamiento sigue igual
        import copy

        fusionado = copy.deepcopy(modelo).to("cpu").float().merge_and_unload()
        destino.mkdir(parents=True, exist_ok=True)
        fusionado.save_pretrained(destino, safe_serialization=True)
        tokenizador.save_pretrained(destino)
        return
    limpio = AutoModelForSequenceClassification.from_pretrained(TORCH_ID, revision=TORCH_REV,
                                                                dtype=torch.float32)
    entrenados = {n: p.detach().float().cpu() for n, p in modelo.named_parameters() if entrenables(n, desde_capa)}
    faltan = limpio.load_state_dict(entrenados, strict=False)
    if faltan.unexpected_keys:
        raise RuntimeError(f"parámetros inesperados: {faltan.unexpected_keys[:5]}")
    destino.mkdir(parents=True, exist_ok=True)
    limpio.save_pretrained(destino, safe_serialization=True)
    tokenizador.save_pretrained(destino)


# ---------------------------------------------------------------------------
# Entrenamiento
# ---------------------------------------------------------------------------
def entrenar(args) -> None:
    import torch
    from transformers.optimization import Adafactor, get_linear_schedule_with_warmup

    dispositivo = args.dispositivo if args.dispositivo != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
    if dispositivo == "cuda" and args.desde_capa < 8 and args.metodo == "parcial":
        props = torch.cuda.get_device_properties(0)
        if props.total_memory < 8 * 1024 ** 3:
            raise SystemExit(f"--desde-capa {args.desde_capa} no cabe en {props.name} "
                             f"({props.total_memory / 1024 ** 3:.1f} GB); usa CPU o --desde-capa ≥ 8")
    random.seed(args.semilla)
    torch.manual_seed(args.semilla)
    original = pesos_originales()
    hash_antes = sha256(original)

    grupos = leer_grupos(Path(args.grupos), args.negativos)
    # ``--repetir-fuente miracl=3``: cambia la mezcla sin tocar el archivo congelado (cada grupo de esa fuente se
    # repite N veces por época). Se registra en ``run.json`` con el resto de la configuración.
    for regla in args.repetir_fuente or []:
        fuente, veces = regla.split("=")
        extra = [g for g in grupos if g.get("fuente") == fuente]
        if not extra:
            raise SystemExit(f"--repetir-fuente: no hay grupos de la fuente {fuente!r}")
        grupos += extra * (int(veces) - 1)
    # Varios archivos de desarrollo: la parada se decide con todos juntos (hit@1 sobre la unión), que tiene menos
    # ruido que uno solo (OBS-0017). Cada uno se puede reportar aparte con --desarrollo-extra.
    desarrollo = []
    for ruta in args.desarrollo:
        if "test" in Path(ruta).name:
            raise SystemExit(f"{ruta}: la prueba no se usa para elegir el punto de parada")
        filas = leer_grupos(Path(ruta), args.negativos)
        desarrollo += filas[:args.n_desarrollo] if args.n_desarrollo else filas
    config = {k: v for k, v in vars(args).items() if k != "func"} | {
        "dispositivo": dispositivo, "base": f"{TORCH_ID}@{TORCH_REV}", "grupos_sha": huella(args.grupos),
        "desarrollo_sha": {Path(r).stem: huella(r) for r in args.desarrollo}, "original_sha256": hash_antes}
    ejecucion = Ejecucion("e4-afinado" if not args.pasos_prueba else "e4-prueba-velocidad", config, args.hilos)
    if args.hilos:
        torch.set_num_threads(args.hilos)

    amp = args.amp if args.amp is not None else dispositivo == "cuda"
    tokenizador, modelo = cargar_modelo(args.desde_capa, dispositivo, args.checkpointing,
                                        False if amp else args.mixto, args.metodo,
                                        (args.lora_r, args.lora_alfa, args.lora_dropout))
    parametros = [p for p in modelo.parameters() if p.requires_grad]
    n_entrenables = sum(p.numel() for p in parametros)
    if args.metodo == "lora":
        optimizador = torch.optim.AdamW(parametros, lr=args.lr, weight_decay=0.01)
    else:
        optimizador = Adafactor(parametros, lr=args.lr, scale_parameter=False, relative_step=False,
                                warmup_init=False, weight_decay=0.01)
    escalador = torch.amp.GradScaler("cuda", enabled=amp)
    pasos_totales = math.ceil(len(grupos) * args.epocas / args.acumulacion)
    if args.pasos_prueba:
        pasos_totales = args.pasos_prueba
    programador = get_linear_schedule_with_warmup(optimizador, int(0.1 * pasos_totales), pasos_totales)
    que = "LoRA en las 24 capas y cabeza" if args.metodo == "lora" else f"capas {args.desde_capa}–23 y cabeza"
    print(f"{dispositivo}{' (amp fp16)' if amp else ''}: {n_entrenables / 1e6:.1f} M parámetros entrenables ({que}); "
          f"{len(grupos)} grupos, {pasos_totales} pasos de optimización", flush=True)

    # ``--desarrollo-extra``: otros archivos de desarrollo que solo se reportan (no deciden la parada).
    extras = {}
    for ruta in args.desarrollo_extra or []:
        if "test" in Path(ruta).name:
            raise SystemExit(f"{ruta}: los archivos de prueba no se miden durante el entrenamiento")
        filas = leer_grupos(Path(ruta), args.negativos)
        extras[Path(ruta).stem] = filas[:args.n_extra] if args.n_extra else filas

    def reportar_extras(etiqueta: str) -> None:
        for nombre, filas in extras.items():
            r = evaluar(tokenizador, modelo, filas, dispositivo, args.max_tokens)
            historia[f"{etiqueta}:{nombre}"] = r
            print(f"    {nombre} {etiqueta}: {r}", flush=True)

    historia = {"inicial": evaluar(tokenizador, modelo, desarrollo, dispositivo, args.max_tokens)}
    print(f"  desarrollo inicial: {historia['inicial']}", flush=True)
    reportar_extras("inicial")
    mejor, paso, inicio, perdidas = None, 0, time.time(), []
    modelo.train()
    orden = [g for _ in range(math.ceil(args.epocas)) for g in random.sample(grupos, len(grupos))]
    orden = orden[:int(len(grupos) * args.epocas)]
    if dispositivo == "cuda":
        torch.cuda.reset_peak_memory_stats()
    # ``--grupos-por-pasada`` grupos van juntos en una sola pasada (más pares por lote: mejor uso de la GPU). La
    # pérdida es la misma: una entropía cruzada por grupo, sumada, y ``--acumulacion`` grupos por paso.
    por_pasada = args.grupos_por_pasada
    if args.acumulacion % por_pasada:
        raise SystemExit("--acumulacion debe ser múltiplo de --grupos-por-pasada")
    cero = torch.zeros(1, dtype=torch.long, device=dispositivo)
    k = 0
    for i in range(0, len(orden), por_pasada):
        lote = orden[i:i + por_pasada]
        consultas, pasajes, tamanos = [], [], []
        for g in lote:
            propios = g["pos"][:1] + g["neg"]
            consultas += [g["query"]] * len(propios)
            pasajes += propios
            tamanos.append(len(propios))
        with torch.autocast("cuda", dtype=torch.float16, enabled=amp):
            cod = tokenizador(consultas, pasajes, truncation="longest_first", max_length=args.max_tokens,
                              padding=True, return_tensors="pt").to(dispositivo)
            logits = modelo(**cod).logits[:, 0].float()
        por_grupo = [torch.nn.functional.cross_entropy(s[None], cero) for s in torch.split(logits, tamanos)]
        escalador.scale(torch.stack(por_grupo).sum() / args.acumulacion).backward()
        perdidas.extend(x.detach().item() for x in por_grupo)
        k += len(lote)
        if k % args.acumulacion and k < len(orden):
            continue
        escalador.unscale_(optimizador)
        torch.nn.utils.clip_grad_norm_(parametros, 1.0)
        escalador.step(optimizador)
        escalador.update()
        programador.step()
        optimizador.zero_grad(set_to_none=True)
        paso += 1
        if paso % 10 == 0 or paso == pasos_totales:
            s_por_grupo = (time.time() - inicio) / k
            memoria = (f", GPU pico {torch.cuda.max_memory_allocated() / 1024 ** 3:.2f} GB"
                       if dispositivo == "cuda" else "")
            restante = s_por_grupo * (len(orden) - k) / 3600
            print(f"  paso {paso}/{pasos_totales}: pérdida {sum(perdidas[-40:]) / len(perdidas[-40:]):.4f}, "
                  f"{s_por_grupo:.2f} s/grupo{memoria}, quedan ~{restante:.1f} h", flush=True)
        if args.pasos_prueba and paso >= args.pasos_prueba:
            break
        if args.evaluar_cada and paso % args.evaluar_cada == 0:
            dev = evaluar(tokenizador, modelo, desarrollo, dispositivo, args.max_tokens)
            historia[f"paso_{paso}"] = dev
            print(f"  desarrollo paso {paso}: {dev}", flush=True)
            reportar_extras(f"paso_{paso}")
            if _mejor(dev, mejor):
                mejor = (paso, dev)
                guardar_copia(modelo, tokenizador, ejecucion.carpeta / "copia", args.desde_capa)

    resumen = {"pasos": paso, "s_por_grupo": round((time.time() - inicio) / max(len(perdidas), 1), 3),
               "parametros_entrenables": n_entrenables, "historia_desarrollo": historia}
    if dispositivo == "cuda":
        resumen["gpu"] = torch.cuda.get_device_name(0)
        resumen["gpu_memoria_pico_gb"] = round(torch.cuda.max_memory_allocated() / 1024 ** 3, 2)
    if not args.pasos_prueba:
        final = evaluar(tokenizador, modelo, desarrollo, dispositivo, args.max_tokens)
        historia["final"] = final
        print(f"  desarrollo final: {final}", flush=True)
        reportar_extras("final")
        if _mejor(final, mejor):
            mejor = (paso, final)
            guardar_copia(modelo, tokenizador, ejecucion.carpeta / "copia", args.desde_capa)
        resumen["mejor"] = {"paso": mejor[0], **mejor[1]}
        resumen["copia"] = str(ejecucion.carpeta / "copia")
    hash_despues = sha256(original)
    resumen["original_intacto"] = hash_despues == hash_antes
    ruta = ejecucion.cerrar(resumen)
    print(json.dumps({k: v for k, v in resumen.items() if k != "historia_desarrollo"}, ensure_ascii=False, indent=1))
    print(f"-> {ruta}")
    if hash_despues != hash_antes:
        raise SystemExit("¡El archivo del modelo original cambió! Revisar antes de seguir.")


# ---------------------------------------------------------------------------
# Exportación a ONNX (fp32 e int8) y paridad
# ---------------------------------------------------------------------------
def exportar(args) -> None:
    import numpy as np
    import onnxruntime as ort
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    import gc
    import shutil

    import onnx

    copia = Path(args.copia)
    copia = copia / "copia" if (copia / "copia").is_dir() else copia
    destino = copia.parent / "onnx"
    temporal = copia.parent / "onnx-temporal"
    (destino / "onnx").mkdir(parents=True, exist_ok=True)
    temporal.mkdir(parents=True, exist_ok=True)
    modelo = AutoModelForSequenceClassification.from_pretrained(copia, dtype=torch.float32).eval()
    tokenizador = AutoTokenizer.from_pretrained(copia)
    ejemplo = tokenizador(["consulta de ejemplo"], ["pasaje de ejemplo para exportar"], return_tensors="pt")
    torch.onnx.export(modelo, (ejemplo["input_ids"], ejemplo["attention_mask"]), str(temporal / "model.onnx"),
                      input_names=["input_ids", "attention_mask"], output_names=["logits"],
                      dynamic_axes={"input_ids": {0: "lote", 1: "secuencia"},
                                    "attention_mask": {0: "lote", 1: "secuencia"}, "logits": {0: "lote"}},
                      opset_version=17, external_data=True, dynamo=False)
    del modelo  # la cuantización necesita la RAM (la matriz de embeddings ocupa ~1 GB en fp32)
    gc.collect()
    # El exportador deja un archivo por tensor: se reúnen en un solo model.onnx_data, como en onnx-community.
    fp32 = destino / "onnx" / "model.onnx"
    grafo = onnx.load(str(temporal / "model.onnx"), load_external_data=True)
    onnx.save_model(grafo, str(fp32), save_as_external_data=True, all_tensors_to_one_file=True,
                    location="model.onnx_data", size_threshold=1024)
    del grafo
    gc.collect()
    shutil.rmtree(temporal)
    int8 = destino / "onnx" / "model_int8.onnx"
    # Misma receta que onnx-community (quantize_config.json): dinámica, por canal, reduce_range, pesos QInt8.
    quantize_dynamic(str(fp32), str(int8), per_channel=True, reduce_range=True, weight_type=QuantType.QInt8,
                     use_external_data_format=False)
    gc.collect()
    modelo = AutoModelForSequenceClassification.from_pretrained(copia, dtype=torch.float32).eval()
    # El tokenizer.json del motor (mismo tokenizador que el original) y la config.
    from huggingface_hub import hf_hub_download

    from comun import ONNX_REV

    for archivo in ("tokenizer.json", "config.json"):
        Path(destino / archivo).write_bytes(Path(hf_hub_download(ONNX_ID, archivo, revision=ONNX_REV)).read_bytes())

    # Paridad: la copia en PyTorch frente a su int8 en 20 pares del desarrollo.
    grupos = leer_grupos(Path(args.paridad) if args.paridad else AFINADO / "grupos-desarrollo.jsonl", 3)[:args.n_paridad]
    sesion = ort.InferenceSession(str(int8), providers=["CPUExecutionProvider"])
    deltas, acuerdos = [], 0
    for g in grupos:
        pasajes = g["candidatos"] if "candidatos" in g else g["pos"][:1] + g["neg"]
        cod = tokenizador([g["query"]] * len(pasajes), pasajes, truncation=True, max_length=MAX_TOKENS_MOTOR,
                          padding=True, return_tensors="pt")
        with torch.no_grad():
            a = modelo(**cod).logits[:, 0].numpy()
        b = sesion.run(None, {"input_ids": cod["input_ids"].numpy(),
                              "attention_mask": cod["attention_mask"].numpy()})[0][:, 0]
        deltas.extend(np.abs(a - b).tolist())
        acuerdos += int(a.argmax() == b.argmax())
    informe = {"onnx_fp32": str(fp32), "onnx_int8": str(int8), "int8_mb": round(int8.stat().st_size / 1e6, 1),
               "paridad_dlogit_max": round(max(deltas), 4), "paridad_top1_igual": f"{acuerdos}/{len(grupos)}"}
    (destino / "exportacion.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(informe, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------------------
# Experimento 2: salidas por capa del modelo BASE para la muestra de Astra
# ---------------------------------------------------------------------------
def volcar_capas(args) -> None:
    """Para cada grupo con ``muestra_capas`` (10 % fijo del entrenamiento v2) y cada uno de sus 8 pasajes: el vector
    ``<s>`` de las 25 salidas (embeddings y capas 1–24) en fp16, el logit final y la etiqueta. Siempre del modelo
    **base** fp32 (``BAAI/bge-reranker-v2-m3`` con revisión fijada): es lo que Astra lee y edita."""
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizador = AutoTokenizer.from_pretrained(TORCH_ID, revision=TORCH_REV)
    # ``--copia``: las mismas salidas de un modelo afinado, para análisis humano posterior. **No se entregan a
    # Astra**: le darían la solución del experimento 1 y romperían el contraste (experimento2_edicion.md).
    origen = (Path(args.copia), {}) if args.copia else (TORCH_ID, {"revision": TORCH_REV})
    nombre = f"capas_{Path(args.copia).parent.name}" if args.copia else "capas_base"
    modelo = AutoModelForSequenceClassification.from_pretrained(origen[0], dtype=torch.float32,
                                                                **origen[1]).to(dispositivo).eval()
    grupos = [g for g in leer_grupos(Path(args.grupos), 7) if g.get("muestra_capas")]
    if args.limite:
        grupos = grupos[:args.limite]
    vectores, logits, etiquetas, indice = [], [], [], []
    inicio = time.time()
    with torch.no_grad():
        for k, g in enumerate(grupos, 1):
            pasajes = g["pos"][:1] + g["neg"]
            cod = tokenizador([g["query"]] * len(pasajes), pasajes, truncation="longest_first",
                              max_length=args.max_tokens, padding=True, return_tensors="pt").to(dispositivo)
            salida = modelo(**cod, output_hidden_states=True)
            vectores.append(torch.stack([h[:, 0] for h in salida.hidden_states], 1).half().cpu().numpy())
            logits.extend(salida.logits[:, 0].float().cpu().tolist())
            etiquetas.extend([1] + [0] * len(g["neg"]))
            for j, tipo in enumerate(["positivo"] + g.get("neg_tipo", ["negativa"] * len(g["neg"]))):
                indice.append({"grupo": g["id"], "pasaje": j, "tipo": tipo, "registro": g.get("registro", "formal"),
                               "fuente": g.get("fuente", "")})
            if k % 100 == 0:
                print(f"  {k}/{len(grupos)} grupos, {(time.time() - inicio) / k:.2f} s/grupo", flush=True)
    destino = Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destino / f"{nombre}.npz", cls=np.concatenate(vectores), logit=np.array(logits, np.float32),
                        etiqueta=np.array(etiquetas, np.int8))
    (destino / f"{nombre}_indice.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in indice), encoding="utf-8")
    informe = {"modelo": str(args.copia) if args.copia else f"{TORCH_ID}@{TORCH_REV}", "precision": "fp32 (vectores guardados en fp16)",
               "grupos": len(grupos), "pares": len(indice), "capas": int(vectores[0].shape[1]) if vectores else 0,
               "dim": int(vectores[0].shape[2]) if vectores else 0, "grupos_sha": huella(args.grupos),
               "npz_sha256": sha256(destino / f"{nombre}.npz"), "max_tokens": args.max_tokens}
    (destino / f"{nombre}.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(informe, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------------------
# Diagnóstico en desarrollo: varias copias contra el base, pareado por pregunta
# ---------------------------------------------------------------------------
def _mcnemar(ganados: int, perdidos: int) -> float:
    n = ganados + perdidos
    if n == 0:
        return 1.0
    cola = sum(math.comb(n, i) for i in range(min(ganados, perdidos) + 1)) / 2 ** n
    return min(1.0, 2 * cola)


def evaluar_dev(args) -> None:
    """Mide el base y cada ``--copia`` (carpeta ``copia/`` de un entrenamiento) sobre archivos de **desarrollo** del
    conjunto v2, en la GPU (fp16, igual que la parada temprana). Por archivo: hit@1, hit@3, MRR@10 y, frente al
    base, preguntas ganadas y perdidas en hit@1 con McNemar exacto. Nunca recibe archivos de prueba."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    for ruta in args.desarrollo:
        if "test" in Path(ruta).name:
            raise SystemExit(f"{ruta}: evaluar-dev no mide archivos de prueba (se miden una vez, al final)")
    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizador = AutoTokenizer.from_pretrained(TORCH_ID, revision=TORCH_REV)
    archivos = {Path(r).stem: leer_grupos(Path(r), 7) for r in args.desarrollo}

    def aciertos(modelo) -> dict:
        salida = {}
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16, enabled=dispositivo == "cuda"):
            for nombre, filas in archivos.items():
                rangos = []
                for f in filas:
                    s = puntuar_grupo(tokenizador, modelo, f["query"], f["candidatos"], dispositivo,
                                      args.max_tokens).tolist()
                    orden = sorted(range(len(s)), key=lambda i: (-s[i], i))
                    rangos.append(next(r for r, i in enumerate(orden, 1) if f["correctos"][i]))
                salida[nombre] = rangos
        return salida

    def cargar(origen, **extra):
        return AutoModelForSequenceClassification.from_pretrained(origen, dtype=torch.float32,
                                                                  **extra).to(dispositivo).eval()

    modelos = [("base", lambda: cargar(TORCH_ID, revision=TORCH_REV))]
    for copia in args.copia:
        carpeta = Path(copia) / "copia" if (Path(copia) / "copia").is_dir() else Path(copia)
        nombre = carpeta.parent.name if carpeta.name == "copia" else carpeta.name
        modelos.append((nombre, lambda c=carpeta: cargar(c)))
    rangos, informe = {}, {}
    for nombre, crear in modelos:
        modelo = crear()
        rangos[nombre] = aciertos(modelo)
        del modelo
        if dispositivo == "cuda":
            torch.cuda.empty_cache()
        informe[nombre] = {}
        for archivo, r in rangos[nombre].items():
            n = len(r)
            fila = {"n": n, "hit@1": round(sum(x == 1 for x in r) / n, 4), "hit@3": round(sum(x <= 3 for x in r) / n, 4),
                    "mrr@10": round(sum(1 / x for x in r if x <= 10) / n, 4)}
            if nombre != "base":
                b = rangos["base"][archivo]
                gan = sum(x == 1 and y != 1 for x, y in zip(r, b, strict=True))
                per = sum(x != 1 and y == 1 for x, y in zip(r, b, strict=True))
                fila |= {"hit@1_ganados": gan, "hit@1_perdidos": per, "mcnemar_p": round(_mcnemar(gan, per), 4)}
            informe[nombre][archivo] = fila
        print(nombre, json.dumps(informe[nombre], ensure_ascii=False), flush=True)
    destino = Path(args.salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"dispositivo": dispositivo, "precision": "fp16" if dispositivo == "cuda" else "fp32",
                                   "archivos": {Path(r).stem: huella(r) for r in args.desarrollo},
                                   "resultados": informe}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {destino}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("entrenar")
    p.add_argument("--grupos", default=str(AFINADO / "grupos-entrenamiento.jsonl"))
    p.add_argument("--desarrollo", nargs="+", default=[str(AFINADO / "grupos-desarrollo.jsonl")],
                   help="uno o más archivos de desarrollo; la parada usa hit@1 sobre todos juntos")
    p.add_argument("--n-desarrollo", type=int, default=100)
    p.add_argument("--desde-capa", type=int, default=12, help="primera capa que se entrena (0 = completo)")
    p.add_argument("--lr", type=float, default=1e-5)
    p.add_argument("--epocas", type=float, default=1.0)
    p.add_argument("--acumulacion", type=int, default=4, help="grupos por paso de optimización")
    p.add_argument("--negativos", type=int, default=7)
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS_MOTOR)
    p.add_argument("--evaluar-cada", type=int, default=100, help="pasos de optimización entre evaluaciones")
    p.add_argument("--pasos-prueba", type=int, default=0, help="mide velocidad y memoria N pasos y se detiene")
    p.add_argument("--checkpointing", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--dispositivo", choices=["auto", "cuda", "cpu"], default="auto")
    p.add_argument("--mixto", action=argparse.BooleanOptionalAction, default=None,
                   help="congelado en fp16 y entrenable en fp32 (por defecto solo en CUDA; en CPU sirve para probar)")
    p.add_argument("--semilla", type=int, default=13)
    p.add_argument("--hilos", type=int, default=None)
    p.add_argument("--metodo", choices=["parcial", "lora"], default="parcial",
                   help="parcial: capas --desde-capa..23 y cabeza (v1); lora: adaptadores en 24 capas, fusionados")
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alfa", type=int, default=32)
    p.add_argument("--lora-dropout", type=float, default=0.1)
    p.add_argument("--desarrollo-extra", nargs="*", default=[],
                   help="archivos de desarrollo que solo se reportan en cada evaluación (no deciden la parada)")
    p.add_argument("--n-extra", type=int, default=0, help="preguntas por archivo extra (0 = todas)")
    p.add_argument("--repetir-fuente", nargs="*", default=[], metavar="FUENTE=N",
                   help="repite N veces por época los grupos de una fuente (p. ej. miracl=3); no toca el archivo")
    p.add_argument("--grupos-por-pasada", type=int, default=1,
                   help="grupos procesados juntos en una pasada (4 en una T4); no cambia la pérdida")
    p.add_argument("--amp", action=argparse.BooleanOptionalAction, default=None,
                   help="precisión mixta fp16 con pesos en fp32 (por defecto en CUDA)")
    p.set_defaults(func=entrenar)
    p = sub.add_parser("exportar")
    p.add_argument("copia", help="carpeta de la ejecución de entrenamiento (o su subcarpeta copia/)")
    p.add_argument("--paridad", default=None, help="archivo de desarrollo para la paridad (p. ej. nomiracl-dev.jsonl)")
    p.add_argument("--n-paridad", type=int, default=20)
    p.set_defaults(func=exportar)
    p = sub.add_parser("evaluar-dev", help="diagnóstico: el base y varias copias en archivos de desarrollo (GPU)")
    p.add_argument("--copia", nargs="*", default=[], help="carpetas de ejecución de entrenamiento (o su copia/)")
    p.add_argument("--desarrollo", nargs="+", required=True, help="archivos de desarrollo congelados del v2")
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS_MOTOR)
    p.add_argument("--salida", default=str(SALIDA / "evaluar-dev.json"))
    p.set_defaults(func=evaluar_dev)
    p = sub.add_parser("volcar-capas", help="experimento 2: salidas por capa del modelo base (muestra de Astra)")
    p.add_argument("--grupos", required=True, help="entrenamiento.jsonl congelado del conjunto v2")
    p.add_argument("--destino", default=str(SALIDA / "astra"))
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS_MOTOR)
    p.add_argument("--limite", type=int, default=0)
    p.add_argument("--copia", default=None, help="carpeta copia/ de un modelo afinado (solo análisis, no para Astra)")
    p.set_defaults(func=volcar_capas)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
