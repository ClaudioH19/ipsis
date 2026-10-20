"""Rango de la fuente correcta por etapa (F0.2 de docs/methodology/precision-ingesta.md).

Dice si el error de «la fuente correcta no sale primera» es de recuperación o de
orden. Por cada pregunta respondible de un banco con evidencias (por ejemplo
``tests/datos/banco_pasajes``) registra el rango de la primera evidencia correcta:

* **híbrido**: el orden de ``retriever.recuperar`` (denso + BM25 fusionados), antes
  de ampliar contextos y de reranquear;
* **final**: el orden de las fuentes que publica el motor v2 (con reranker en
  ``medium``; en ``light`` coincide con el híbrido).

Un candidato es correcto si su fragmento recuperado se solapa con alguna
evidencia (misma regla que ``ipsis.evaluacion.metricas._solapa``). Para
candidatos ampliados con vecinos o al padre se usan los offsets del fragmento
recuperado, no los del texto publicado.

Cada ejecución copia el corpus a un proyecto temporal, indexa con la
configuración pedida y lo descarta: nunca toca ``.ipsis/`` del proyecto actual.
Sin calibración (``ruta_calibracion=None`` en v2). Requiere los modelos en caché
(``IPSIS_MODELS_DIR``) o red hacia huggingface.co.

    python herramientas/evaluacion/ranking_pasajes.py \\
        tests/datos/banco_pasajes/es/manifiesto.json --perfil light --perfil medium \\
        --salida /tmp/linea_base
    python herramientas/evaluacion/ranking_pasajes.py <banco> --perfil medium \\
        --con-cabecera --salida /tmp/e1 --comparar /tmp/linea_base/ranking.json

La partición por defecto es ``dev``; ``test`` se mide solo al cerrar (F5.1).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CORTES = (1, 3, 5)


# ---------------------------------------------------------------------------
# Núcleo puro (se prueba sin modelos)
# ---------------------------------------------------------------------------
def percentil(valores: list[float], q: float) -> float:
    """Percentil con interpolación lineal (el de ``ipsis.evaluacion.benchmark``)."""
    ordenados = sorted(valores)
    if not ordenados:
        return 0.0
    posicion = (len(ordenados) - 1) * q
    abajo = int(posicion)
    arriba = min(abajo + 1, len(ordenados) - 1)
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * (posicion - abajo)


def solapa(doc_id: str, inicio: int, fin: int, evidencias) -> bool:
    return any(doc_id == e.doc_id and inicio < e.offset_fin and fin > e.offset_inicio for e in evidencias)


def rango_correcto(items: list[tuple[str, int, int]], evidencias) -> int | None:
    """Posición (desde 1) del primer ``(doc_id, inicio, fin)`` que toca una evidencia."""
    for rango, (doc_id, inicio, fin) in enumerate(items, start=1):
        if solapa(doc_id, inicio, fin, evidencias):
            return rango
    return None


class GrabadorCandidatos:
    """Registra, por pregunta, los pasajes exactos que ve el reranker (en el orden híbrido) y si cada
    uno toca una evidencia. Sirve para puntuar rerankers fuera del motor (``--volcar-candidatos``)."""

    def __init__(self, ruta, maximo: int = 30):
        self.ruta, self.maximo, self.caso, self.filas = Path(ruta), maximo, None, []

    def envolver(self, puntuar_progresivo):
        def grabando(candidatos, pregunta, reranker, opciones, **kw):
            if self.caso is not None:
                pendientes = [c for c in candidatos if c.signals.reranker_score is None][:self.maximo]
                pasajes = []
                for c in pendientes:
                    vista = c.chunk.metadata.get("vista_reranking") or {}
                    ini = vista.get("offset_inicio", c.chunk.offset_inicio)
                    fin = vista.get("offset_fin", c.chunk.offset_fin)
                    from ipsis.consulta.v2.resultados import texto_reranking

                    # ``correcto``: el pasaje que ve la persona (el padre ampliado) toca una evidencia, como en
                    # el rango final del motor; ``correcto_hijo``: el hijo que representa al pasaje la toca.
                    pasajes.append({"doc_id": c.chunk.doc_id, "inicio": ini, "fin": fin,
                                    "texto": texto_reranking(c),
                                    "correcto": solapa(c.chunk.doc_id, c.chunk.offset_inicio, c.chunk.offset_fin,
                                                       self.caso.evidencias),
                                    "correcto_hijo": solapa(c.chunk.doc_id, ini, fin, self.caso.evidencias)})
                self.filas.append({"id": self.caso.id, "split": self.caso.split,
                                   "pregunta": self.caso.pregunta, "pasajes": pasajes})
            return puntuar_progresivo(candidatos, pregunta, reranker, opciones, **kw)
        return grabando

    def guardar(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in self.filas) + "\n",
                             encoding="utf-8")


GRABADOR: GrabadorCandidatos | None = None


class GrabadorPublicados:
    """Registra, por pregunta, las fuentes que publica el motor v2, en su orden y sin su texto
    (``--volcar-publicados``): puntaje y su tipo, documento, ruta de sección, alcance, términos distintivos y si cada
    una toca una evidencia. Alimenta ``forma_resultados.py`` (plan de presentación, P0). El banco real es privado:
    no se escribe ni el texto de los pasajes ni el de la pregunta, solo el ``id`` del caso."""

    def __init__(self, ruta, perfil: str):
        self.ruta, self.perfil, self.filas = Path(ruta), perfil, []

    def registrar(self, caso, resultado, final: list[tuple[str, int, int]]) -> None:
        """``final`` son los ``(doc_id, inicio, fin)`` de las evidencias, alineados con ``resultado.evidencias``."""
        contrato = getattr(resultado, "contrato_http", None) or resultado.diagnostico.get("contrato_http") or {}
        fragmentos = {f["chunk_id"]: f for f in contrato.get("fragmentos") or []}
        publicadas = []
        for rango, (evidencia, huella) in enumerate(zip(resultado.evidencias, final), start=1):
            fragmento = fragmentos.get(evidencia.chunk_id, {})
            publicadas.append({
                "rango": rango, "chunk_id": evidencia.chunk_id, "doc_id": evidencia.doc_id,
                "seccion_path": list(getattr(evidencia, "seccion_path", None) or []),
                "score": fragmento.get("score", getattr(evidencia, "score", None)),
                "tipo_puntaje": fragmento.get("tipo_puntaje"),
                "alcance": fragmento.get("alcance"), "rasgos": fragmento.get("rasgos"),
                "correcto": solapa(*huella, caso.evidencias)})
        self.filas.append({"id": caso.id, "split": caso.split, "perfil": self.perfil,
                           "rango_final": rango_correcto(final, caso.evidencias), "publicadas": publicadas})

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in self.filas), encoding="utf-8")


PUBLICADOS: GrabadorPublicados | None = None


def ruta_publicados(ruta, perfil: str) -> Path:
    """``publicados.jsonl`` → ``publicados-medium.jsonl``: un archivo por perfil, para que no se pisen."""
    ruta = Path(ruta)
    return ruta.with_name(f"{ruta.stem}-{perfil}{ruta.suffix}")


def observar_caso(motor, caso, k_hibrido: int | None = None) -> dict:
    """Pregunta ``caso.pregunta`` al motor v2 y devuelve ambos rangos y la latencia."""
    from ipsis.nucleo.esquemas import QueryAnalysis

    k = k_hibrido or motor.opciones["recuperar_n"]
    consulta = QueryAnalysis(pregunta_original=caso.pregunta,
                             pregunta_normalizada=" ".join(caso.pregunta.lower().split()))
    candidatos = motor.retriever.recuperar(consulta, k)
    hibrido = [(c.chunk.doc_id, c.chunk.offset_inicio, c.chunk.offset_fin) for c in candidatos]
    por_id = {c.chunk.chunk_id: (c.chunk.doc_id, c.chunk.offset_inicio, c.chunk.offset_fin) for c in candidatos}
    if GRABADOR is not None:
        GRABADOR.caso = caso
    inicio = time.perf_counter()
    resultado = motor.consultar(caso.pregunta, f"ranking:{caso.id}")
    latencia = (time.perf_counter() - inicio) * 1000
    final = [por_id.get(e.chunk_id, (e.doc_id, e.offset_inicio, e.offset_fin)) for e in resultado.evidencias]
    if PUBLICADOS is not None:
        PUBLICADOS.registrar(caso, resultado, final)
    etapas = {nombre.removesuffix("_ms"): ms
              for nombre, ms in (resultado.diagnostico.get("etapas") or {}).items()}
    return {
        "id": caso.id, "split": caso.split, "pregunta": caso.pregunta,
        "rango_hibrido": rango_correcto(hibrido, caso.evidencias),
        "rango_final": rango_correcto(final, caso.evidencias),
        "latencia_ms": round(latencia, 1), "etapas_ms": etapas,
    }


def metricas_de_rangos(rangos: list[int | None]) -> dict:
    """hit@1/3/5 y MRR; un rango ``None`` (no apareció) cuenta como fallo."""
    n = len(rangos)
    if n == 0:
        return {"n": 0, **{f"hit@{c}": 0.0 for c in CORTES}, "mrr": 0.0}
    salida: dict = {"n": n}
    for corte in CORTES:
        salida[f"hit@{corte}"] = round(sum(1 for r in rangos if r is not None and r <= corte) / n, 4)
    salida["mrr"] = round(sum(1 / r for r in rangos if r) / n, 4)
    return salida


def resumir(observaciones: list[dict]) -> dict:
    """Métricas por etapa, latencia p50/p95 y los casos cuyo rango final no es 1."""
    latencias = [o["latencia_ms"] for o in observaciones]
    por_etapa: dict[str, list[float]] = {}
    for o in observaciones:
        for nombre, ms in o["etapas_ms"].items():
            por_etapa.setdefault(nombre, []).append(ms)
    return {
        "hibrido": metricas_de_rangos([o["rango_hibrido"] for o in observaciones]),
        "final": metricas_de_rangos([o["rango_final"] for o in observaciones]),
        "latencia_ms": {"p50": round(percentil(latencias, 0.5), 1), "p95": round(percentil(latencias, 0.95), 1)},
        "etapas_ms": {n: {"p50": round(percentil(v, 0.5), 1), "p95": round(percentil(v, 0.95), 1)}
                      for n, v in sorted(por_etapa.items())},
        "casos_no_primeros": sorted(
            ({"id": o["id"], "rango_hibrido": o["rango_hibrido"], "rango_final": o["rango_final"]}
             for o in observaciones if o["rango_final"] != 1), key=lambda c: c["id"]),
    }


def comparar(base: dict, nuevo: dict) -> dict:
    """Casos ganados (pasan a rango final 1) y perdidos, por perfil, frente a ``base``."""
    salida = {}
    for perfil, datos in nuevo["perfiles"].items():
        anterior = base.get("perfiles", {}).get(perfil)
        if anterior is None:
            continue
        antes = {o["id"]: o["rango_final"] for o in anterior["observaciones"]}
        ganados, perdidos = [], []
        for o in datos["observaciones"]:
            if o["id"] not in antes:
                continue
            era_primero, es_primero = antes[o["id"]] == 1, o["rango_final"] == 1
            if es_primero and not era_primero:
                ganados.append({"id": o["id"], "antes": antes[o["id"]], "ahora": o["rango_final"]})
            elif era_primero and not es_primero:
                perdidos.append({"id": o["id"], "antes": 1, "ahora": o["rango_final"]})
        salida[perfil] = {"ganados": sorted(ganados, key=lambda c: c["id"]),
                          "perdidos": sorted(perdidos, key=lambda c: c["id"])}
    return salida


def _fila(nombre: str, m: dict) -> str:
    return (f"| {nombre} | {m['n']} | {m['hit@1']:.3f} | {m['hit@3']:.3f} | {m['hit@5']:.3f} | {m['mrr']:.3f} |")


def a_markdown(informe: dict, comparacion: dict | None = None) -> str:
    lineas = [f"# Ranking de pasajes: {informe['banco']}", "",
              f"Partición: `{informe['particion']}`. Configuración: `{json.dumps(informe['configuracion'], ensure_ascii=False, sort_keys=True)}`.", ""]
    for perfil, datos in informe["perfiles"].items():
        r = datos["resumen"]
        lineas += [f"## Perfil `{perfil}`", "",
                   "| Etapa | n | hit@1 | hit@3 | hit@5 | MRR |", "|---|---|---|---|---|---|",
                   _fila("híbrido", r["hibrido"]), _fila("final", r["final"]), "",
                   f"Latencia total: p50 {r['latencia_ms']['p50']} ms, p95 {r['latencia_ms']['p95']} ms.", ""]
        if r["etapas_ms"]:
            lineas += ["| Etapa del motor | p50 ms | p95 ms |", "|---|---|---|"]
            lineas += [f"| {n} | {v['p50']} | {v['p95']} |" for n, v in r["etapas_ms"].items()]
            lineas.append("")
        lineas.append(f"Casos con rango final distinto de 1: {len(r['casos_no_primeros'])}.")
        lineas += [f"- `{c['id']}`: híbrido {c['rango_hibrido']}, final {c['rango_final']}"
                   for c in r["casos_no_primeros"]]
        if comparacion and perfil in comparacion:
            c = comparacion[perfil]
            lineas += ["", f"Frente a la base: {len(c['ganados'])} ganados, {len(c['perdidos'])} perdidos.",
                       *[f"- ganado `{x['id']}`: {x['antes']} → {x['ahora']}" for x in c["ganados"]],
                       *[f"- perdido `{x['id']}`: {x['antes']} → {x['ahora']}" for x in c["perdidos"]]]
        lineas.append("")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Proyecto temporal y ejecución real (requiere modelos)
# ---------------------------------------------------------------------------
def aplicar_configuracion(cfg: dict, args) -> dict:
    """Aplica los cambios pedidos (nombres internos del motor) y devuelve un resumen."""
    rec, v2 = cfg["recuperacion"], cfg.setdefault("v2", {})
    if args.estrategia:
        rec["estrategia_chunking"] = args.estrategia
    if args.con_cabecera is not None:
        rec["con_header"] = args.con_cabecera
    if args.modo:
        rec["modo"] = args.modo
    if args.detalle_cabecera:
        rec["detalle_cabecera"] = args.detalle_cabecera
    if args.preparacion:
        rec["preparacion"] = {**rec.get("preparacion", {}), "modo": args.preparacion}
    if args.alcance or args.rasgos or args.umbral_hermanos or args.similitud_hermanos or args.umbral_vectores:
        prep = rec.setdefault("preparacion", {})
        if args.alcance:
            prep["alcance"] = True
        if args.rasgos:
            prep["rasgos_distintivos"] = args.rasgos
        if args.umbral_hermanos:
            prep["umbral_hermanos"] = args.umbral_hermanos
        if args.similitud_hermanos:
            prep["similitud_hermanos"] = args.similitud_hermanos
        if args.umbral_vectores:
            prep["umbral_vectores"] = args.umbral_vectores
    if args.modelo_denso:
        rec["modelo"] = args.modelo_denso
    if args.modelo_reranker:
        cfg.setdefault("ajustes_perfil", {}).setdefault("modelos", {})["reranker"] = args.modelo_reranker
    if args.rerank_candidatos:
        v2["rerank_candidatos"] = args.rerank_candidatos
    if args.reranker_max_tokens:
        v2["max_tokens_reranker"] = args.reranker_max_tokens
    v2["resultados_n"] = max(args.resultados, 1)  # solo cambia cuántas fuentes se publican, no su orden
    return {"estrategia": rec.get("estrategia_chunking"), "con_cabecera": rec.get("con_header"), "detalle_cabecera": rec.get("detalle_cabecera", "basico"),
            "preparacion": rec.get("preparacion", {}).get("modo", "legacy"),
            "alcance": rec.get("preparacion", {}).get("alcance", False),
            "rasgos": rec.get("preparacion", {}).get("rasgos_distintivos", 0),
            "umbral_hermanos": rec.get("preparacion", {}).get("umbral_hermanos"),
            "modo": rec.get("modo"), "modelo_denso": rec.get("modelo"), "reranker_max_tokens": v2.get("max_tokens_reranker"), "rerank_candidatos": v2.get("rerank_candidatos"),
            "modelo_reranker": (cfg.get("ajustes_perfil") or {}).get("modelos", {}).get("reranker"),
            "resultados": v2["resultados_n"]}


def medir_perfil(banco, directorio_corpus: Path, perfil: str, args) -> tuple[dict, dict]:
    from ipsis.cli import main
    from ipsis.aplicacion.consulta import construir_motor
    from ipsis.configuracion import rutas
    from ipsis.configuracion.archivos import escribir, leer
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto

    anterior = Path.cwd()
    with tempfile.TemporaryDirectory(prefix=f"ranking_pasajes_{perfil}_") as temporal:
        try:
            os.chdir(temporal)
            if main(["init", "--profile", perfil, "--language", args.idioma]) != 0:
                raise RuntimeError(f"ipsis init falló para el perfil {perfil}")
            for archivo in banco.manifiesto.corpus.archivos:
                if main(["load", str(directorio_corpus / archivo.ruta)]) != 0:
                    raise RuntimeError(f"ipsis load falló para {archivo.ruta}")
            cfg = leer(rutas.MOTOR, "motor")
            configuracion = aplicar_configuracion(cfg, args)
            escribir(rutas.MOTOR, cfg, "motor")
            if main(["index"]) != 0:
                raise RuntimeError("ipsis index falló")
            motor = construir_motor(cargar_proyecto(), cfg_dominio=cargar_dominio())
            observaciones = []
            global GRABADOR, PUBLICADOS
            PUBLICADOS = None
            if args.volcar_publicados:
                PUBLICADOS = GrabadorPublicados(ruta_publicados(args.volcar_publicados, perfil), perfil)
            if args.volcar_candidatos:
                import ipsis.consulta.v2.motor as motor_v2

                GRABADOR = GrabadorCandidatos(args.volcar_candidatos)
                motor_v2.puntuar_progresivo = GRABADOR.envolver(motor_v2.puntuar_progresivo)
            try:
                motor.calentar()
                casos = [c for c in banco.casos if c.respondible and args.particion in (c.split, "todas")]
                for caso in casos:
                    observaciones.append(observar_caso(motor, caso))
            finally:
                motor.cerrar()
                if GRABADOR is not None:
                    GRABADOR.guardar()
                if PUBLICADOS is not None:
                    PUBLICADOS.guardar()
                    PUBLICADOS = None
        finally:
            os.chdir(anterior)
    return observaciones, configuracion


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("banco", help="manifiesto.json del banco")
    p.add_argument("--perfil", action="append", choices=["light", "medium"],
                   help="perfil de instalación (repetible; por defecto light y medium)")
    p.add_argument("--particion", choices=["dev", "test", "todas"], default="dev")
    p.add_argument("--idioma", default="es")
    p.add_argument("--estrategia", help="chunking_strategy (CH-F256, CH-PAR, CH-SEC...)")
    p.add_argument("--con-cabecera", dest="con_cabecera", action="store_true", default=None)
    p.add_argument("--sin-cabecera", dest="con_cabecera", action="store_false")
    p.add_argument("--detalle-cabecera", dest="detalle_cabecera", choices=["basico", "extendido"],
                   help="header_detail; con --con-cabecera")
    p.add_argument("--preparacion", choices=["legacy", "estructural_v1"])
    p.add_argument("--modo", choices=["vectorial", "hibrida", "dispersa"],
                   help="retrieval.mode: solo vector denso, híbrido (por defecto) o solo BM25")
    p.add_argument("--alcance", action="store_true", help="agrega el alcance de la sección a lo que se indexa")
    p.add_argument("--rasgos", type=int, default=0, help="términos distintivos por unidad hermana (0 = no)")
    p.add_argument("--umbral-hermanos", type=float, default=0.0, help="coseno TF-IDF para agrupar hermanas (0,5 por defecto)")
    p.add_argument("--similitud-hermanos", choices=["tfidf", "vectores"], help="cómo se agrupan las hermanas")
    p.add_argument("--umbral-vectores", type=float, default=0.0, help="coseno de vectores para agrupar (0,95 por defecto)")
    p.add_argument("--modelo-denso")
    p.add_argument("--volcar-candidatos", dest="volcar_candidatos",
                   help="escribe en este JSONL los pasajes que ve el reranker, para puntuarlos fuera del motor")
    p.add_argument("--volcar-publicados", dest="volcar_publicados",
                   help="escribe en un JSONL por perfil (RUTA-perfil.jsonl) las fuentes publicadas por pregunta, sin texto, "
                        "para forma_resultados.py")
    p.add_argument("--modelo-reranker", dest="modelo_reranker", help="id del reranker del catálogo (solo medium)")
    p.add_argument("--rerank-candidatos", type=int, dest="rerank_candidatos",
                   help="v2.rerank_candidates: cuántos candidatos del recuperador puntúa el reranker")
    p.add_argument("--reranker-max-tokens", type=int, dest="reranker_max_tokens")
    p.add_argument("--resultados", type=int, default=5,
                   help="fuentes publicadas por el motor (para medir hit@5); no cambia el orden")
    p.add_argument("--salida", required=True, help="carpeta de salida (fuera del repo)")
    p.add_argument("--comparar", help="ranking.json de una corrida anterior")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    from ipsis.evaluacion.banco import cargar_banco

    manifiesto = Path(args.banco).resolve()
    banco = cargar_banco(manifiesto)
    corpus = (manifiesto.parent / banco.manifiesto.corpus.directorio).resolve()
    informe = {"banco": banco.manifiesto.dataset_id, "particion": args.particion, "perfiles": {}}
    for perfil in args.perfil or ["light", "medium"]:
        observaciones, informe["configuracion"] = medir_perfil(banco, corpus, perfil, args)
        informe["perfiles"][perfil] = {"resumen": resumir(observaciones), "observaciones": observaciones}
    comparacion = None
    if args.comparar:
        comparacion = comparar(json.loads(Path(args.comparar).read_text(encoding="utf-8")), informe)
        informe["comparacion"] = comparacion
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "ranking.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = a_markdown(informe, comparacion)
    (salida / "ranking.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
