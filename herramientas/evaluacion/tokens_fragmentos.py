"""F0.3: longitud en tokens de los fragmentos y posición de la evidencia (sin Qdrant).

Indexa en memoria (parseo + fragmentado, sin codificar) con cada estrategia y, con el
tokenizador real de cada modelo, mide:

* tokens del ``texto_embebido`` frente a ``max_tokens`` del modelo denso;
* tokens de pregunta + pasaje del reranker frente a ``reranker_max_tokens`` (por defecto el de
  la configuración y, además, 384 y 512), para el pasaje que contiene la evidencia de cada caso
  respondible del banco: qué porcentaje se trunca y en cuántos casos la evidencia queda
  (total o parcialmente) después del punto de corte.

El pasaje del reranker es el que publica el motor v2: ``texto_fuente`` del fragmento en el modo
legacy y, con la preparación estructural, la unidad padre (``texto_embedding`` con su sección).

    python herramientas/evaluacion/tokens_fragmentos.py --perfil medium --idioma es \
        --salida /tmp/claude-0/medidas/tokens_es
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
from pathlib import Path

BANCOS = Path(__file__).resolve().parents[2] / "tests" / "datos" / "banco_pasajes"
ESTRATEGIAS = ["CH-F256", "CH-PAR", "CH-SEC", "CH-F256S", "estructural_v1"]
LIMITES_EXTRA = (384, 512)


def percentil(valores: list[int], q: float) -> int:
    if not valores:
        return 0
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(round(q * (len(ordenados) - 1))))]


def tokenizador_de(id_hf: str):
    from ipsis.modelos.catalogo import obtener
    from ipsis.modelos.onnx import ModeloOnnx

    modelo = ModeloOnnx(obtener(id_hf))
    return modelo.tokenizador, modelo.spec


def n_tokens(tokenizador, texto: str, par: str | None = None) -> int:
    return len(tokenizador.encode(texto, par).ids) if par is not None else len(tokenizador.encode(texto).ids)


def pasajes_legacy(docs, estrategia, taxonomia):
    from ipsis.ingesta.ingesta import construir_chunks_y_payloads

    chunks, payloads = construir_chunks_y_payloads(docs, estrategia, True, taxonomia)
    pasajes = [{"doc_id": c.doc_id, "inicio": c.offset_inicio, "fin": c.offset_fin, "texto": c.texto,
                "prefijo": 0} for c in chunks]
    embebidos = [p.get("texto_embebido") or p["texto"] for p in payloads]
    return pasajes, embebidos


def pasajes_estructurales(docs, taxonomia):
    from ipsis.ingesta.unidades import construir_payloads_estructurados

    config = {"modo": "estructural_v1", "max_palabras_unidad": 400, "palabras_hijo": 80}
    hijos, payloads, padres, _ = construir_payloads_estructurados(docs, taxonomia, config)
    pasajes = []
    for padre in padres.values():
        prefijo = len(padre.texto_embedding) - len(padre.texto_fuente)
        pasajes.append({"doc_id": padre.doc_id, "inicio": padre.offset_inicio, "fin": padre.offset_fin,
                        "texto": padre.texto_embedding, "prefijo": prefijo})
    return pasajes, [h.texto_embedding for h in hijos]


def medir_estrategia(nombre, pasajes, embebidos, casos, tok_denso, spec_denso, tok_rerank, spec_rerank, limites):
    dens = [n_tokens(tok_denso, t) for t in embebidos]
    maximo_denso = spec_denso.max_tokens
    filas_pasaje = [n_tokens(tok_rerank, p["texto"]) for p in pasajes]
    resumen = {
        "fragmentos": len(pasajes), "palabras_p50": int(statistics.median(len(p["texto"].split()) for p in pasajes)),
        "denso": {"max_tokens": maximo_denso, "p50": percentil(dens, 0.5), "p95": percentil(dens, 0.95),
                  "truncados_pct": round(100 * sum(d > maximo_denso for d in dens) / len(dens), 1)},
        "reranker_pasaje": {"p50": percentil(filas_pasaje, 0.5), "p95": percentil(filas_pasaje, 0.95)},
        "evidencia": {},
    }
    medidos = []
    for caso in casos:
        for ev in caso.evidencias:
            candidatos = [p for p in pasajes if p["doc_id"] == ev.doc_id and p["inicio"] <= ev.offset_inicio < p["fin"]]
            if not candidatos:
                continue
            p = candidatos[0]
            fin_relativo = p["prefijo"] + max(0, min(ev.offset_fin, p["fin"]) - p["inicio"])
            inicio_relativo = p["prefijo"] + (ev.offset_inicio - p["inicio"])
            pregunta = caso.pregunta
            q = n_tokens(tok_rerank, pregunta)
            medidos.append({
                "q": q, "total": n_tokens(tok_rerank, pregunta, p["texto"]),
                "hasta_inicio": n_tokens(tok_rerank, pregunta, p["texto"][:inicio_relativo]),
                "hasta_fin": n_tokens(tok_rerank, pregunta, p["texto"][:fin_relativo])})
            break
    for limite in limites:
        n = len(medidos) or 1
        resumen["evidencia"][str(limite)] = {
            "pasaje_truncado_pct": round(100 * sum(m["total"] > limite for m in medidos) / n, 1),
            "evidencia_cortada_pct": round(100 * sum(m["hasta_fin"] > limite for m in medidos) / n, 1),
            "evidencia_fuera_pct": round(100 * sum(m["hasta_inicio"] > limite for m in medidos) / n, 1)}
    resumen["evidencia"]["casos"] = len(medidos)
    resumen["evidencia"]["pregunta_p95_tokens"] = percentil([m["q"] for m in medidos], 0.95)
    return resumen


def a_markdown(informe) -> str:
    lim = informe["limites"]
    cab = "| Estrategia | Fragmentos | Palabras p50 | Denso p95 / trunc. | Pasaje reranker p50 / p95 |"
    sep = "|---|---|---|---|---|"
    for limite in lim:
        cab += f" evidencia cortada @{limite} |"
        sep += "---|"
    filas = [cab, sep]
    for nombre, r in informe["estrategias"].items():
        fila = (f"| {nombre} | {r['fragmentos']} | {r['palabras_p50']} | {r['denso']['p95']} / "
                f"{r['denso']['truncados_pct']} % | {r['reranker_pasaje']['p50']} / {r['reranker_pasaje']['p95']} |")
        for limite in lim:
            e = r["evidencia"][str(limite)]
            fila += f" {e['evidencia_cortada_pct']} % (pasaje truncado {e['pasaje_truncado_pct']} %) |"
        filas.append(fila)
    return (f"Modelo denso `{informe['modelo_denso']}` (ventana {informe['ventana_denso']}), reranker "
            f"`{informe['modelo_reranker']}` (ventana del motor {informe['limite_motor']}); "
            f"{informe['casos']} casos respondibles.\n\n" + "\n".join(filas))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--banco", help="manifiesto.json del banco (por defecto el sintético del idioma)")
    ap.add_argument("--perfil", default="medium")
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--particion", default="todas", choices=["dev", "test", "todas"])
    ap.add_argument("--estrategias", nargs="+", default=ESTRATEGIAS)
    ap.add_argument("--salida", default="tokens_fragmentos")
    args = ap.parse_args(argv)

    from ipsis.aplicacion.proyecto import perfil_de_instalacion
    from ipsis.cli import main as ipsis
    from ipsis.configuracion import rutas
    from ipsis.configuracion.archivos import leer
    from ipsis.evaluacion.banco import cargar_banco
    from ipsis.ingesta.ingesta import parsear_corpus

    manifiesto = Path(args.banco or BANCOS / args.idioma / "manifiesto.json").resolve()
    banco = cargar_banco(manifiesto)
    corpus = (manifiesto.parent / banco.manifiesto.corpus.directorio).resolve()
    casos = [c for c in banco.casos if c.respondible and args.particion in (c.split, "todas")]
    anterior = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="tokens_fragmentos_") as temporal:
        try:
            os.chdir(temporal)
            if ipsis(["init", "--profile", args.perfil, "--language", args.idioma]) != 0:
                raise RuntimeError("ipsis init falló")
            for archivo in banco.manifiesto.corpus.archivos:
                if ipsis(["load", str(corpus / archivo.ruta)]) != 0:
                    raise RuntimeError(f"ipsis load falló para {archivo.ruta}")
            cfg = leer(rutas.MOTOR, "motor")
            instalacion = perfil_de_instalacion(args.perfil)
            modelo_denso, modelo_reranker = instalacion.modelos.denso, instalacion.modelos.reranker
            tok_denso, spec_denso = tokenizador_de(modelo_denso)
            tok_rerank, spec_rerank = tokenizador_de(modelo_reranker)
            limite_motor = int(cfg.get("v2", {}).get("max_tokens_reranker", 256))
            limites = sorted({limite_motor, *LIMITES_EXTRA})
            taxonomia = cargar_taxonomia_proyecto()
            informe = {"modelo_denso": modelo_denso, "ventana_denso": spec_denso.max_tokens,
                       "modelo_reranker": modelo_reranker, "limite_motor": limite_motor, "limites": limites,
                       "casos": len(casos), "idioma": args.idioma, "estrategias": {}}
            docs_legacy = parsear_corpus(rutas.DOCUMENTOS, "legacy")
            docs_estructura = None
            for estrategia in args.estrategias:
                if estrategia == "estructural_v1":
                    docs_estructura = docs_estructura or parsear_corpus(rutas.DOCUMENTOS, "estructural_v1")
                    pasajes, embebidos = pasajes_estructurales(docs_estructura, taxonomia)
                else:
                    pasajes, embebidos = pasajes_legacy(docs_legacy, estrategia, taxonomia)
                informe["estrategias"][estrategia] = medir_estrategia(
                    estrategia, pasajes, embebidos, casos, tok_denso, spec_denso, tok_rerank, spec_rerank, limites)
        finally:
            os.chdir(anterior)
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "tokens.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = a_markdown(informe)
    (salida / "tokens.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


def cargar_taxonomia_proyecto():
    from ipsis.ingesta.ingesta import cargar_taxonomia

    return cargar_taxonomia()


if __name__ == "__main__":
    raise SystemExit(main())
