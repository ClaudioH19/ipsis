"""Ablaciones offline de v2 sobre una copia; no modifica el motor ni el proyecto.

El JSON de preguntas puede declarar oracle_parent_ids para leer unidades conocidas
como correctas. Es información de diagnóstico, nunca una regla del asistente.
Las inferencias se memoizan: tiempos agregados NO son latencias de producción.
Se guardan las entradas, salidas y tiempos de cada inferencia nueva.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comparar_motores import aislar_indice, copiar_proyecto, preguntas_desde_json


class RerankerAuditado:
    def __init__(self, modelo):
        self.modelo, self.cache, self.inferencias = modelo, {}, []

    def puntuar(self, pregunta, pasajes):
        clave = (pregunta, tuple(pasajes))
        if clave not in self.cache:
            inicio = time.perf_counter()
            scores = self.modelo.puntuar(pregunta, pasajes)
            ms = (time.perf_counter() - inicio) * 1000
            tokens = []
            for pasaje in pasajes:
                entero = self.modelo.tokenizador.encode(pregunta, pasaje)
                limitado = self.modelo.tokenizar([(pregunta, pasaje)])[0]
                fines = [o[1] for o, sec in zip(limitado.offsets, limitado.sequence_ids) if sec == 1]
                tokens.append({"tokens_totales": len(entero.ids), "tokens_limite": self.modelo.spec.max_tokens,
                    "caracteres_pasaje": len(pasaje), "caracteres_vistos": max(fines, default=0),
                    "truncado": len(entero.ids) > self.modelo.spec.max_tokens})
            self.cache[clave] = scores
            self.inferencias.append({"pregunta": pregunta, "pasajes": list(pasajes), "scores": scores,
                "duracion_ms": ms, "tokens": tokens, "lote": self.modelo.lote})
        return list(self.cache[clave])


class LectorAuditado:
    def __init__(self, modelo):
        self.modelo, self.cache, self.inferencias = modelo, {}, []

    def leer(self, pregunta, pasajes):
        salida = []
        for i, pasaje in enumerate(pasajes):
            clave = (pregunta, pasaje, self.modelo.max_tokens_respuesta)
            if clave not in self.cache:
                inicio = time.perf_counter()
                lectura = self.modelo.leer(pregunta, [pasaje])[0]
                ms = (time.perf_counter() - inicio) * 1000
                assert pasaje[lectura.inicio:lectura.fin] == lectura.texto
                self.cache[clave] = lectura
                self.inferencias.append({"pregunta": pregunta, "pasaje": pasaje,
                    "lectura": lectura.model_dump(mode="json"), "duracion_ms": ms,
                    "ventanas": len(self.modelo._ventanas(pregunta, pasaje)),
                    "max_tokens_respuesta": self.modelo.max_tokens_respuesta})
            salida.append(self.cache[clave].model_copy(update={"indice_pasaje": i}))
        return salida


def resultado_lectura(candidatos, lector, pregunta, n):
    """Control histórico max-QA sobre fuente literal, no selección actual de v2."""
    seleccionados = candidatos[:n]
    lecturas = lector.leer(pregunta, [c.chunk.texto_fuente[:12000] for c in seleccionados])
    positivas = [l for l in lecturas if l.texto and l.s_qa > 0]
    mejor = max(positivas, key=lambda l: (l.s_qa, -l.indice_pasaje)) if positivas else None
    return {"padres_leidos": [c.chunk.chunk_id for c in seleccionados],
        "lecturas": [l.model_dump(mode="json") for l in lecturas],
        "padre_elegido": seleccionados[mejor.indice_pasaje].chunk.chunk_id if mejor else None,
        "tramo": mejor.texto if mejor else None}


def formatos_oraculo(padre, documento):
    """Representaciones de diagnóstico; las derivadas no son citas literales.

    La primera fila como nombres de campos es una hipótesis controlada incluso
    cuando Word no la declara encabezado. Nunca se activa en producción aquí.
    """
    fuente = padre.texto_fuente
    formatos = {"literal": fuente, "una_linea": " ".join(fuente.split()),
                "con_seccion_declarada": "\n".join([*padre.seccion_path, fuente])}
    tid = padre.metadata.get("table_id")
    tabla = next((t for t in documento["tablas"] if t["table_id"] == tid), None)
    if tabla is None:
        return formatos
    celdas = tabla["celdas"]
    headers = {c["columna"]: c["texto"] for c in celdas if c["fila"] == 0 and not c["continuacion_de"]}
    elementos = {e["element_id"]: e for e in documento["elementos"]}
    previo = elementos.get(tabla["contexto_previo_id"])
    lineas = [previo["texto"]] if previo else []
    filas = {elementos[eid]["metadata"]["fila"] for eid in padre.metadata["elementos"]}
    for fila in sorted(filas - {0}):
        campos = [headers.get(c["columna"], "") + ": " + c["texto"] for c in celdas
                  if c["fila"] == fila and not c["continuacion_de"] and c["texto"].strip()]
        lineas.append("; ".join(campos) + ".")
    formatos["fila_como_campos"] = "\n".join(lineas)
    return formatos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--alternate-reranker", help="modelo ya disponible en caché; sin descargas")
    parser.add_argument("--oracle-formats", action="store_true", help="probar formatos derivados solo en unidades oráculo")
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("threads debe ser positivo")
    origen, destino, preguntas = (p.resolve() for p in (args.project, args.output, args.questions))
    if destino == origen or destino.is_relative_to(origen) or origen.is_relative_to(destino):
        parser.error("output debe estar fuera del proyecto original")
    casos = preguntas_desde_json(preguntas)
    os.environ.update(HF_HUB_OFFLINE="1", IPSIS_ONNX_THREADS=str(args.threads), QDRANT_MODE="local")
    destino.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=destino))
    copia = run / "project"
    copiar_proyecto(origen, copia)
    os.chdir(copia)
    from ipsis.aplicacion.consulta import construir_motor
    from ipsis.aplicacion.registro import entrada_de_registro
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto
    from ipsis.nucleo.esquemas import QueryAnalysis
    from ipsis.nucleo.traza import capturar_traza

    cfg = cargar_proyecto()
    cfg["pipeline"] = "v2"
    aislar_indice(cfg, copia)
    motor = construir_motor(cfg, cfg_dominio=cargar_dominio())
    report = {"experimental": True, "timing_includes_memoization": True,
        "questions_sha256": hashlib.sha256(preguntas.read_bytes()).hexdigest(),
        "environment": {"threads": args.threads}, "records": [], "alternate": []}
    try:
        if motor.reranker is None or motor.lector is None or not getattr(motor.retriever, "padres", None):
            raise ValueError("esta auditoría requiere reranker, lector e índice estructural con padres")
        motor.calentar()
        report["configuration"] = motor.metadatos_auditoria
        reranker, lector = RerankerAuditado(motor.reranker), LectorAuditado(motor.lector)
        motor.reranker, motor.lector = reranker, lector
        opciones = dict(motor.opciones)
        report["model_paths"] = {"reranker": str(reranker.modelo.carpeta), "reader": str(lector.modelo.carpeta)}
        variantes = [
            ("base_20_5_4_2", 20, 5, 4, 2, True, True),
            ("leer4_20_5_4_4", 20, 5, 4, 4, True, True),
            ("puntuar20_20_20_4_2", 20, 20, 4, 2, True, True),
            ("puntuar20_leer4_20_20_8_4", 20, 20, 8, 4, True, True),
            ("sin_reranker_leer2", 20, 20, 4, 2, False, True),
            ("sin_reranker_leer4", 20, 20, 4, 4, False, True),
            ("recuperar60_puntuar60_leer4", 60, 60, 8, 4, True, True),
            ("sin_correccion", 20, 5, 4, 2, True, False),
        ]
        padres = getattr(motor.retriever, "padres", {})
        documentos = {}
        if args.oracle_formats:
            from ipsis.indice.contextos import ruta_contextos

            almacen = json.loads(ruta_contextos(motor.retriever.coleccion.nombre).read_text(encoding="utf-8"))
            documentos = {d["doc_id"]: d for d in almacen["documentos"]}
        for caso in casos:
            print("Case " + caso["id"], flush=True)
            fila = {"case": caso, "variants": [], "retrieval": {}, "oracle": None, "child_first": None}
            for nombre, recuperar, puntuar, conservar, leer, ce, ortografia in variantes:
                motor.reranker = reranker if ce else None
                motor.opciones = {**opciones, "corregir_erratas": ortografia,
                    "recuperar_n": recuperar, "rerank_candidatos": puntuar,
                    "rerank_k": conservar, "leer_m": leer}
                motor.metadatos_auditoria = {**report["configuration"], "audit_variant": nombre,
                    "presupuestos_v2": dict(motor.opciones)}
                with capturar_traza():
                    salida = motor.consultar(caso["question"], "audit-" + caso["id"])
                    registro = entrada_de_registro(caso["question"], salida)
                fila["variants"].append({"name": nombre, "budgets": {"retrieve": recuperar,
                    "rerank": puntuar if ce else 0, "keep": conservar, "read": leer}, "record": registro})
            q = QueryAnalysis(pregunta_original=caso["question"], pregunta_normalizada=caso["question"])
            for modo in ("hibrida", "vectorial", "dispersa"):
                sub = getattr(motor.retriever, "recuperador", motor.retriever)
                anterior = sub.modo
                try:
                    sub.modo = modo
                    candidatos = motor.retriever.recuperar(q, 60)
                finally:
                    sub.modo = anterior
                fila["retrieval"][modo] = [{"rank": i + 1, "child": c.chunk.chunk_id,
                    "parent": c.chunk.parent_id, "source": c.chunk.texto_fuente,
                    "search": c.chunk.texto_embedding, "score": c.score} for i, c in enumerate(candidatos)]
            candidatos = motor.retriever.recuperar(q, 20)
            # Rerankear los hijos ANTES de ampliar; solo una variante de diagnóstico.
            scores = reranker.puntuar(caso["question"], [c.chunk.texto_embedding for c in candidatos])
            orden = sorted(range(len(scores)), key=lambda i: (-scores[i], candidatos[i].chunk.chunk_id))
            ordenados = [candidatos[i] for i in orden]
            ampliados, _ = motor.retriever.ampliar_contextos(ordenados, 12000)
            fila["child_first"] = {"ranked_children": [{"id": candidatos[i].chunk.chunk_id,
                "parent": candidatos[i].chunk.parent_id, "score": scores[i]} for i in orden],
                **resultado_lectura(ampliados, lector, caso["question"], 4)}
            ids = caso.get("oracle_parent_ids", [])
            if not isinstance(ids, list) or not all(isinstance(pid, str) for pid in ids):
                raise ValueError("oracle_parent_ids debe ser una lista de identificadores")
            if ids:
                if any(pid not in padres for pid in ids):
                    raise ValueError("oracle_parent_ids contiene una unidad ausente")
                pasajes = [padres[pid].texto_fuente for pid in ids]
                lecturas = lector.leer(caso["question"], pasajes)
                fila["oracle"] = {"parent_ids": ids, "source": pasajes,
                    "readings": [l.model_dump(mode="json") for l in lecturas]}
                if args.oracle_formats:
                    fila["oracle_formats"] = []
                    for pid in ids:
                        p = padres[pid]
                        for nombre, texto in formatos_oraculo(p, documentos[p.doc_id]).items():
                            lectura = lector.leer(caso["question"], [texto])[0]
                            fila["oracle_formats"].append({"parent_id": pid, "format": nombre,
                                "literal_source": nombre == "literal", "text": texto,
                                "reading": lectura.model_dump(mode="json")})
                        largo_anterior = lector.modelo.max_tokens_respuesta
                        try:
                            lector.modelo.max_tokens_respuesta = 128
                            lectura = lector.leer(caso["question"], [p.texto_fuente])[0]
                            fila["oracle_formats"].append({"parent_id": pid, "format": "literal_respuesta128",
                                "literal_source": True, "text": p.texto_fuente, "reading": lectura.model_dump(mode="json")})
                        finally:
                            lector.modelo.max_tokens_respuesta = largo_anterior
            report["records"].append(fila)
            report["reranker_inferences"], report["reader_inferences"] = reranker.inferencias, lector.inferencias
            (run / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        # Sensibilidad al padding/lote, conservando la misma pregunta y los mismos textos.
        primera = report["records"][0]
        pregunta = primera["case"]["question"]
        q = QueryAnalysis(pregunta_original=pregunta, pregunta_normalizada=pregunta)
        cs, _ = motor.retriever.ampliar_contextos(motor.retriever.recuperar(q, 20), 12000)
        textos = [c.chunk.texto_embedding for c in cs[:5]]
        report["batch_sensitivity"] = {"question": pregunta, "parent_ids": [c.chunk.chunk_id for c in cs[:5]],
            "batch_scores": reranker.puntuar(pregunta, textos),
            "single_scores": [reranker.puntuar(pregunta, [t])[0] for t in textos]}
        if args.alternate_reranker:
            from ipsis.modelos.catalogo import obtener
            from ipsis.modelos.descarga import ruta_local
            from ipsis.modelos.reranker import RerankerOnnx

            spec = obtener(args.alternate_reranker)
            if spec.tarea != "reranker":
                raise ValueError("alternate-reranker debe ser un cross-encoder")
            carpeta = ruta_local(spec)
            motor.reranker = None
            reranker.modelo._sesion = None
            gc.collect()
            # Igual techo de 512 tokens; no atribuir un cambio de contexto a los pesos.
            otro = RerankerAuditado(RerankerOnnx(spec.model_copy(update={"max_tokens": 512}), carpeta=carpeta))
            otro.modelo.lote = 2
            report["alternate_model"] = {"id": spec.id_hf, "path": str(carpeta), "max_tokens": 512, "batch": 2}
            for fila in report["records"]:
                caso = fila["case"]
                print("Alternate " + caso["id"], flush=True)
                q = QueryAnalysis(pregunta_original=caso["question"], pregunta_normalizada=caso["question"])
                cs, _ = motor.retriever.ampliar_contextos(motor.retriever.recuperar(q, 20), 12000)
                scores = otro.puntuar(caso["question"], [c.chunk.texto_embedding for c in cs])
                orden = sorted(range(len(cs)), key=lambda i: (-scores[i], cs[i].chunk.chunk_id))
                report["alternate"].append({"case_id": caso["id"], "ranking": [{"parent": cs[i].chunk.chunk_id,
                    "score": scores[i]} for i in orden], **resultado_lectura([cs[i] for i in orden], lector, caso["question"], 4)})
                report["alternate_inferences"] = otro.inferencias
                report["reader_inferences"] = lector.inferencias
                (run / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        report["reranker_inferences"] = reranker.inferencias
        (run / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print("Report: " + str(run / "audit.json"), flush=True)
    finally:
        motor.cerrar()


if __name__ == "__main__":
    main()
