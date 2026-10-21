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


def cargar_modelo(desde_capa: int, dispositivo: str, checkpointing: bool, mixto: bool | None = None):
    """``mixto`` (por defecto, solo en CUDA): lo congelado en fp16 y lo entrenable en fp32."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizador = AutoTokenizer.from_pretrained(TORCH_ID, revision=TORCH_REV)
    modelo = AutoModelForSequenceClassification.from_pretrained(
        TORCH_ID, revision=TORCH_REV, dtype=torch.float32, attn_implementation="eager")
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
    grupos = [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
    for g in grupos:
        g["neg"] = g["neg"][:negativos]
    return grupos


def evaluar(tokenizador, modelo, grupos: list[dict], dispositivo: str, max_tokens: int) -> dict:
    import torch

    modelo.eval()
    perdida, aciertos = 0.0, 0
    with torch.no_grad():
        for g in grupos:
            s = puntuar_grupo(tokenizador, modelo, g["query"], g["pos"][:1] + g["neg"], dispositivo, max_tokens)
            perdida += float(torch.nn.functional.cross_entropy(s[None], torch.zeros(1, dtype=torch.long,
                                                                                     device=s.device)))
            aciertos += int(s.argmax() == 0)
    modelo.train()
    return {"perdida": round(perdida / len(grupos), 4), "acierto_top1": round(aciertos / len(grupos), 4)}


def guardar_copia(modelo, tokenizador, destino: Path, desde_capa: int) -> None:
    """Original completo en fp32 + solo los parámetros entrenados: lo congelado no pasa por fp16 al guardar."""
    import torch
    from transformers import AutoModelForSequenceClassification

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
    if dispositivo == "cuda" and args.desde_capa < 8:
        props = torch.cuda.get_device_properties(0)
        if props.total_memory < 8 * 1024 ** 3:
            raise SystemExit(f"--desde-capa {args.desde_capa} no cabe en {props.name} "
                             f"({props.total_memory / 1024 ** 3:.1f} GB); usa CPU o --desde-capa ≥ 8")
    random.seed(args.semilla)
    torch.manual_seed(args.semilla)
    original = pesos_originales()
    hash_antes = sha256(original)

    grupos = leer_grupos(Path(args.grupos), args.negativos)
    desarrollo = leer_grupos(Path(args.desarrollo), args.negativos)[:args.n_desarrollo]
    config = {k: v for k, v in vars(args).items() if k != "func"} | {
        "dispositivo": dispositivo, "base": f"{TORCH_ID}@{TORCH_REV}", "grupos_sha": huella(args.grupos),
        "desarrollo_sha": huella(args.desarrollo), "original_sha256": hash_antes}
    ejecucion = Ejecucion("e4-afinado" if not args.pasos_prueba else "e4-prueba-velocidad", config, args.hilos)
    if args.hilos:
        torch.set_num_threads(args.hilos)

    tokenizador, modelo = cargar_modelo(args.desde_capa, dispositivo, args.checkpointing, args.mixto)
    parametros = [p for p in modelo.parameters() if p.requires_grad]
    n_entrenables = sum(p.numel() for p in parametros)
    optimizador = Adafactor(parametros, lr=args.lr, scale_parameter=False, relative_step=False, warmup_init=False,
                            weight_decay=0.01)
    pasos_totales = math.ceil(len(grupos) * args.epocas / args.acumulacion)
    if args.pasos_prueba:
        pasos_totales = args.pasos_prueba
    programador = get_linear_schedule_with_warmup(optimizador, int(0.1 * pasos_totales), pasos_totales)
    print(f"{dispositivo}: {n_entrenables / 1e6:.0f} M parámetros entrenables (capas {args.desde_capa}–23 y cabeza); "
          f"{len(grupos)} grupos, {pasos_totales} pasos de optimización", flush=True)

    historia = {"inicial": evaluar(tokenizador, modelo, desarrollo, dispositivo, args.max_tokens)}
    print(f"  desarrollo inicial: {historia['inicial']}", flush=True)
    mejor, paso, inicio, perdidas = None, 0, time.time(), []
    modelo.train()
    orden = [g for _ in range(math.ceil(args.epocas)) for g in random.sample(grupos, len(grupos))]
    orden = orden[:int(len(grupos) * args.epocas)]
    if dispositivo == "cuda":
        torch.cuda.reset_peak_memory_stats()
    for k, g in enumerate(orden, 1):
        s = puntuar_grupo(tokenizador, modelo, g["query"], g["pos"][:1] + g["neg"], dispositivo, args.max_tokens)
        perdida = torch.nn.functional.cross_entropy(s[None], torch.zeros(1, dtype=torch.long, device=s.device))
        (perdida / args.acumulacion).backward()
        perdidas.append(perdida.detach().item())
        if k % args.acumulacion:
            continue
        torch.nn.utils.clip_grad_norm_(parametros, 1.0)
        optimizador.step()
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
            if mejor is None or dev["perdida"] < mejor[1]["perdida"]:
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
        if mejor is None or final["perdida"] < mejor[1]["perdida"]:
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
    grupos = leer_grupos(AFINADO / "grupos-desarrollo.jsonl", 3)[:5]
    sesion = ort.InferenceSession(str(int8), providers=["CPUExecutionProvider"])
    deltas, acuerdos = [], 0
    for g in grupos:
        pasajes = g["pos"][:1] + g["neg"]
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("entrenar")
    p.add_argument("--grupos", default=str(AFINADO / "grupos-entrenamiento.jsonl"))
    p.add_argument("--desarrollo", default=str(AFINADO / "grupos-desarrollo.jsonl"))
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
    p.set_defaults(func=entrenar)
    p = sub.add_parser("exportar")
    p.add_argument("copia", help="carpeta de la ejecución de entrenamiento (o su subcarpeta copia/)")
    p.set_defaults(func=exportar)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
