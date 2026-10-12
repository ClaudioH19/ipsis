"""Grupo consulta: servir la API y preguntarle desde la terminal."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from ipsis.aplicacion import diagnostico
from ipsis.aplicacion.corpus import archivos_de_ruta
from ipsis.aplicacion.proyecto import carpeta_de_proyecto, completar_proyecto_existente, migrar_proyecto_activo
from ipsis.cli.base import Comando
from ipsis.cli.comandos.corpus import ComandoCargar, ComandoIndexar
from ipsis.cli.comandos.proyecto import ComandoInit
from ipsis.recursos.mensajes import t


class ComandoServir(Comando):
    """Si recibe una carpeta, la prepara componiendo ``init``, ``load`` e
    ``index`` (los mismos comandos, con su salida) antes de servir."""

    nombre = "serve"
    ayuda = "serve.help"

    def __init__(self, init: ComandoInit, cargar: ComandoCargar, indexar: ComandoIndexar) -> None:
        self.init, self.cargar, self.indexar = init, cargar, indexar

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = t("serve.examples")
        parser.add_argument("carpeta", metavar="folder", nargs="?", help=t("serve.arg_folder"))
        parser.add_argument("--host", default="127.0.0.1", help=t("serve.opt_host"))
        parser.add_argument("--port", type=int, default=8000, help=t("serve.opt_port"))
        parser.add_argument("--reindex", dest="reindexar", action="store_true", help=t("serve.opt_reindex"))
        parser.add_argument("--mode", dest="modo", choices=["production", "development"], default=None,
                            help=t("serve.opt_mode"))
        parser.add_argument("--demo", action="store_true", help=t("serve.opt_demo"))
        parser.add_argument("--open", dest="abrir", action="store_true", help=t("serve.opt_open"))

    def _preparar_modo(self, modo: str | None) -> dict:
        """Fija IPSIS_MODE para el proceso del servicio y devuelve las opciones de proxy de uvicorn."""
        from ipsis.aplicacion.modo import generar_token, modo_servicio

        if modo:
            os.environ["IPSIS_MODE"] = modo
        efectivo = modo_servicio()
        if efectivo.desarrollo:
            print(t("serve.development"))
            if not os.environ.get("IPSIS_ADMIN_TOKEN"):
                os.environ["IPSIS_ADMIN_TOKEN"] = generar_token()
                print(t("serve.temporary_token", token=os.environ["IPSIS_ADMIN_TOKEN"]))
        for problema in efectivo.problemas:
            print(t("cli.warning", warning=problema))
        # El esquema (https) y la IP real solo se aceptan de los X-Forwarded-* del proxy declarado.
        return {"proxy_headers": True,
                "forwarded_allow_ips": ",".join(efectivo.proxy_confiable) or "127.0.0.1"}

    def _preparar_carpeta(self, carpeta: str, *, reindexar: bool = False) -> Path:
        """Completa un proyecto o crea uno privado junto a una carpeta documental."""
        fuente = Path(carpeta).resolve()
        if not fuente.is_dir():
            raise ValueError(t("serve.no_folder", path=fuente))

        es_proyecto = carpeta_de_proyecto(fuente)
        if not es_proyecto and not archivos_de_ruta(fuente):
            raise ValueError(t("serve.no_documents", path=fuente))
        proyecto = fuente if es_proyecto else fuente / ".ipsis-project"
        proyecto.mkdir(parents=True, exist_ok=True)
        os.chdir(proyecto)
        for cambio in migrar_proyecto_activo():
            print(t("cli.migration", change=cambio))

        if not Path("config/assistant.yaml").is_file():
            inicio = argparse.Namespace(nombre_asistente=None, descripcion_dominio=None, idioma=None, perfil=None,
                                        force=False)
            if self.init.ejecutar(inicio) != 0:
                raise RuntimeError(t("serve.init_failed"))
        else:
            completar_proyecto_existente()

        catalogo = Path("documents/catalog.yaml")
        catalogo_antes = catalogo.read_bytes() if catalogo.is_file() else b""
        if not es_proyecto:
            if self.cargar.ejecutar(argparse.Namespace(ruta=str(fuente))) != 0:
                raise RuntimeError(t("serve.load_failed"))
        catalogo_despues = catalogo.read_bytes() if catalogo.is_file() else b""

        indice = diagnostico.verificar_indice()
        if reindexar or catalogo_antes != catalogo_despues or not indice.ok:
            print(t("serve.preparing_index"))
            if self.indexar.ejecutar(argparse.Namespace(corpus="documents")) != 0:
                raise RuntimeError(t("serve.index_failed"))
        else:
            print(t("serve.index_reused"))
        return proyecto

    def ejecutar(self, args: argparse.Namespace) -> int:
        import uvicorn

        anterior = Path.cwd()
        demo_anterior = os.environ.get("IPSIS_DEMO")
        demo = bool(getattr(args, "demo", False) or getattr(args, "abrir", False))
        apertura = None
        try:
            if args.carpeta:
                from ipsis.cli.progreso import actividad

                with actividad("serve"):
                    proyecto = self._preparar_carpeta(args.carpeta, reindexar=args.reindexar)
                print(t("serve.active_project", path=proyecto))
            if demo:
                os.environ["IPSIS_DEMO"] = "1"
            proxy = self._preparar_modo(args.modo)
            print(t("serve.serving", host=args.host, port=args.port))
            if demo:
                from ipsis.aplicacion.vista_servicio import abrir_cuando_listo, url_local

                url = url_local(args.host, args.port)
                print(t("serve.demo_url", url=url))
                if getattr(args, "abrir", False):
                    apertura = abrir_cuando_listo(url)
            uvicorn.run("ipsis.servicio.api:crear_app", factory=True, host=args.host, port=args.port,
                        log_level="info", **proxy)
            return 0
        except (OSError, RuntimeError, ValueError) as exc:
            print(t("serve.failed", error=exc))
            return 1
        finally:
            if apertura is not None:
                apertura.set()
            if demo:
                if demo_anterior is None:
                    os.environ.pop("IPSIS_DEMO", None)
                else:
                    os.environ["IPSIS_DEMO"] = demo_anterior
            os.chdir(anterior)


# Estado de la respuesta → clave de su etiqueta en el catálogo.
ETIQUETA_ESTADO = {
    "ok": "ask.status_ok",
    "relacionado": "ask.status_related",
    "sin_respuesta": "ask.status_no_answer",
    "conversacional": "ask.status_conversational",
    "degradado": "ask.status_degraded",
    "saturado": "ask.status_saturated",
    # Los mismos estados con los nombres del contrato público de POST /ask.
    "related": "ask.status_related",
    "no_answer": "ask.status_no_answer",
    "conversational": "ask.status_conversational",
    "degraded": "ask.status_degraded",
    "saturated": "ask.status_saturated",
}


def etiqueta_estado(estado: str) -> str:
    clave = ETIQUETA_ESTADO.get(estado)
    return t(clave) if clave else f"[{estado.upper()}]"


class ComandoPreguntar(Comando):
    nombre = "ask"
    ayuda = "ask.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("pregunta", metavar="question", help=t("ask.arg_question"))
        parser.add_argument("--url", default="http://127.0.0.1:8000", help=t("ask.opt_url"))
        parser.add_argument("--timeout", type=float, default=30.0, help=t("ask.opt_timeout"))
        parser.add_argument("--diagnostics", dest="diagnostico", action="store_true", help=t("ask.opt_diagnostics"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        if args.diagnostico:
            return self._diagnostico(args.pregunta)
        import httpx

        url = f"{args.url.rstrip('/')}/ask"
        try:
            resp = httpx.post(url, json={"question": args.pregunta, "session_id": "ipsis-cli"}, timeout=args.timeout)
        except httpx.ConnectError:
            print(t("ask.no_connection", url=url))
            return 1
        except httpx.TimeoutException:
            print(t("ask.timeout", seconds=args.timeout))
            return 1

        if resp.status_code != 200:
            print(t("ask.http_error", status=resp.status_code, body=resp.text))
            return 1

        datos = resp.json()
        print(etiqueta_estado(datos.get("status", "?")))
        print(datos.get("answer") or "")
        fragmentos = datos.get("fragments") or []
        if fragmentos:
            print(t("ask.citations"))
            for f in fragmentos:
                print(t("ask.citation", title=f["doc_title"], section=f["section"], start=f["offset_start"],
                        end=f["offset_end"], score=f["score"]))
        return 0

    @staticmethod
    def _diagnostico(pregunta: str) -> int:
        from ipsis.aplicacion.consulta import MotorNoListo, diagnosticar_pregunta

        try:
            d = diagnosticar_pregunta(pregunta)
        except MotorNoListo as e:
            print(t("ask.not_ready", error=e))
            print(t("cli.action", action="ipsis doctor"))
            return 1
        except Exception as e:  # noqa: BLE001 -- índice bloqueado, modelo faltante, configuración inválida...
            print(t("ask.engine_failed", error=e))
            print(t("cli.action", action="ipsis doctor"))
            return 1
        imprimir_diagnostico(d)
        return 0


def imprimir_diagnostico(d) -> None:
    """Lo que muestra ``ipsis ask --diagnostics`` (y ``/diagnostics`` en ``ipsis chat``)."""
    nada = t("cli.none")
    print(etiqueta_estado(d.estado))
    print(d.respuesta)
    print(t("ask.rule", rule=d.regla or nada, reason=d.motivo, profile=d.perfil or nada))
    if d.nivel_confianza:
        print(t("ask.confidence_level", level=t(f"ask.confidence_{d.nivel_confianza}")))
    print(t("ask.stages"))
    for nombre, ms in d.etapas:
        print(f"  {nombre:16} {ms:>6}")
    print(f"  {'total':16} {d.total_ms:>6}" + (t("ask.early_exit") if d.salto_modelos else ""))
    if d.senales:
        print(t("ask.signals"))
        print("  " + "  ".join(f"{k}={_valor(v)}" for k, v in d.senales.items()))
    if d.intencion:
        if d.intencion.get("origen") == "similitud":
            print(t("ask.intention_similarity", name=d.intencion["nombre"],
                    score=_valor(d.intencion["similitud"]), margin=_valor(d.intencion["margen"])))
        else:
            print(t("ask.intention", name=d.intencion["nombre"], relation=d.intencion.get("relacion") or nada))
    if d.ortografia:
        print(t("ask.spelling", values="; ".join(f"{p} → {f}" for p, f in d.ortografia.items())))
    if d.sinonimos:
        print(t("ask.synonyms", values="; ".join(f"{p} → {', '.join(f)}" for p, f in d.sinonimos.items())))
    for recurso in d.recursos_lexicos:
        print(t("ask.lexical_source", word=recurso["palabra"], forms=", ".join(recurso["formas"]),
                source=recurso["fuente"], sense=recurso["sentido"], pos=recurso["pos"]))
    if d.conversacion:
        print(t("ask.conversation", action=t(f"ask.conversation_{d.conversacion['accion']}"),
                topic=d.conversacion.get("tema") or nada))
    if d.pregunta_interpretada:
        print(t("ask.interpreted", question=d.pregunta_interpretada))
    print(t("ask.focus", found=", ".join(d.foco_encontrados) or nada, missing=", ".join(d.foco_ausentes) or nada))
    if d.ausentes_del_corpus:
        print(t("ask.absent", terms=", ".join(d.ausentes_del_corpus)))
    if d.oracion_foco:
        print(t("ask.sentence", sentence=d.oracion_foco))
    if d.tramo:
        print(t("ask.span", text=d.tramo["texto"], chunk_id=d.tramo["chunk_id"], start=d.tramo["offset_inicio"],
                end=d.tramo["offset_fin"]))
    else:
        print(t("ask.no_span"))
    for e in d.evidencias:
        print(t("ask.evidence", doc_id=e["doc_id"], start=e["offset_inicio"], end=e["offset_fin"]))
    if d.candidatos:
        print(t("ask.candidates"))
        for c in d.candidatos:
            qa = f"{c['qa']:.2f}" if c["qa"] is not None else "-"
            rr = f"{c['rerank']} ({c['rerank_score']:+.2f})" if c["rerank"] is not None else "-"
            print(t("ask.candidate", chunk_id=c["chunk_id"], dense=c["denso"] or "-", bm25=c["bm25"] or "-",
                    fusion=c["fusion"] or "-", rerank=rr, qa=qa, start=c["inicio"][:70]))
    if d.oraciones:
        print(t("ask.sentences"))
        for o in d.oraciones:
            print(t("ask.scored_sentence", score=o["score"], text=o["texto"][:110]))
    if d.alternativas is not None:
        print(t("ask.alternatives", offered=len(d.alternativas["ofrecidas"]),
                discarded=len(d.alternativas["descartadas"])))
        for clave, lista in (("ask.alternative_offered", d.alternativas["ofrecidas"]),
                             ("ask.alternative_discarded", d.alternativas["descartadas"][:5])):
            for a in lista:
                senales = " ".join(f"{k}={v:.2f}" for k, v in a["senales"].items() if v)
                print(t(clave, affinity=a["afinidad"], signals=senales, text=a["texto"][:90]))
    if d.tono:
        print(t("ask.tone", tone=d.tono, templates=", ".join(d.plantillas) or nada))
    for a in d.advertencias:
        print(t("ask.warning", warning=a))


def _valor(v) -> str:
    return f"{v:.3f}" if isinstance(v, float) else str(v)


__all__ = ["ComandoPreguntar", "ComandoServir", "ETIQUETA_ESTADO", "etiqueta_estado", "imprimir_diagnostico"]
