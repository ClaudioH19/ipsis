"""Grupo consulta: servir la API y preguntarle desde la terminal."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from rag.aplicacion import diagnostico
from rag.aplicacion.corpus import archivos_de_ruta
from rag.aplicacion.proyecto import completar_proyecto_existente
from rag.cli.base import Comando
from rag.cli.comandos.corpus import ComandoCargar, ComandoIndexar
from rag.cli.comandos.proyecto import ComandoInit


class ComandoServir(Comando):
    """Si recibe una carpeta, la prepara componiendo ``init``, ``cargar`` e
    ``indexar`` (los mismos comandos, con su salida) antes de servir."""

    nombre = "servir"
    ayuda = "Levanta la API del servicio."

    def __init__(self, init: ComandoInit, cargar: ComandoCargar, indexar: ComandoIndexar) -> None:
        self.init, self.cargar, self.indexar = init, cargar, indexar

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("carpeta", nargs="?",
                            help="Carpeta de documentos o proyecto existente; se prepara automáticamente.")
        parser.add_argument("--host", default="127.0.0.1",
                            help="Dirección donde escucha el servicio (por defecto: '127.0.0.1', solo local; "
                                 "usa '0.0.0.0' para aceptar conexiones externas).")
        parser.add_argument("--port", type=int, default=8000,
                            help="Puerto donde escucha el servicio (por defecto: 8000).")
        parser.add_argument("--reindexar", action="store_true",
                            help="Reconstruye el índice aunque el catálogo no haya cambiado.")
        parser.add_argument("--modo", choices=["produccion", "desarrollo"], default=None,
                            help="produccion (por defecto, o RAG_MODO): /admin exige HTTPS desde fuera. "
                                 "desarrollo: /admin por HTTP, /docs y sin caché de los archivos del widget.")

    def _preparar_modo(self, modo: str | None) -> dict:
        """Fija RAG_MODO para el proceso del servicio y devuelve las opciones de proxy de uvicorn."""
        from rag.aplicacion.modo import generar_token, modo_servicio

        if modo:
            os.environ["RAG_MODO"] = modo
        efectivo = modo_servicio()
        if efectivo.desarrollo:
            print("Modo desarrollo: /admin acepta HTTP desde cualquier IP. No lo uses en un servicio público.")
            if not os.environ.get("RAG_ADMIN_TOKEN"):
                os.environ["RAG_ADMIN_TOKEN"] = generar_token()
                print(f"Token temporal de /admin (solo esta ejecución): {os.environ['RAG_ADMIN_TOKEN']}")
        for problema in efectivo.problemas:
            print(f"Aviso: {problema}")
        # El esquema (https) y la IP real solo se aceptan de los X-Forwarded-* del proxy declarado.
        return {"proxy_headers": True,
                "forwarded_allow_ips": ",".join(efectivo.proxy_confiable) or "127.0.0.1"}

    def _preparar_carpeta(self, carpeta: str, *, reindexar: bool = False) -> Path:
        """Completa un proyecto o crea uno privado junto a una carpeta documental."""
        fuente = Path(carpeta).resolve()
        if not fuente.is_dir():
            raise ValueError(f"no existe la carpeta {fuente}")

        es_proyecto = (
            (fuente / "configuracion" / "asistente.yaml").is_file()
            or (fuente / "documentos" / "catalogo.yaml").is_file()
        )
        if not es_proyecto and not archivos_de_ruta(fuente):
            raise ValueError(f"no hay documentos compatibles en {fuente}")
        proyecto = fuente if es_proyecto else fuente / ".rag-extractivo"
        proyecto.mkdir(parents=True, exist_ok=True)
        os.chdir(proyecto)

        if not Path("configuracion/asistente.yaml").is_file():
            inicio = argparse.Namespace(nombre_asistente=None, descripcion_dominio=None, idioma=None, perfil=None,
                                        force=False)
            if self.init.ejecutar(inicio) != 0:
                raise RuntimeError("no se pudo inicializar el proyecto automático")
        else:
            completar_proyecto_existente()

        catalogo = Path("documentos/catalogo.yaml")
        catalogo_antes = catalogo.read_bytes() if catalogo.is_file() else b""
        if not es_proyecto:
            if self.cargar.ejecutar(argparse.Namespace(ruta=str(fuente))) != 0:
                raise RuntimeError("no se pudieron cargar los documentos")
        catalogo_despues = catalogo.read_bytes() if catalogo.is_file() else b""

        indice = diagnostico.verificar_indice()
        if reindexar or catalogo_antes != catalogo_despues or not indice.ok:
            print("Preparando el índice antes de iniciar el servicio...")
            if self.indexar.ejecutar(argparse.Namespace(corpus="documentos")) != 0:
                raise RuntimeError("no se pudo construir el índice")
        else:
            print("El índice existente está vigente; se reutiliza.")
        return proyecto

    def ejecutar(self, args: argparse.Namespace) -> int:
        import uvicorn

        anterior = Path.cwd()
        try:
            if args.carpeta:
                proyecto = self._preparar_carpeta(args.carpeta, reindexar=args.reindexar)
                print(f"Proyecto activo: {proyecto}")
            proxy = self._preparar_modo(args.modo)
            print(f"Sirviendo en http://{args.host}:{args.port} (Ctrl+C para detener)...")
            uvicorn.run("rag.servicio.api:app", host=args.host, port=args.port, log_level="info", **proxy)
            return 0
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"No se pudo preparar el servicio: {exc}")
            return 1
        finally:
            os.chdir(anterior)


ETIQUETA_ESTADO = {
    "ok": "[OK]",
    "relacionado": "[RELACIONADO -- no es una respuesta directa]",
    "sin_respuesta": "[SIN RESPUESTA]",
    "conversacional": "[CONVERSACIONAL]",
    "degradado": "[DEGRADADO]",
    "saturado": "[SATURADO]",
}


class ComandoPreguntar(Comando):
    nombre = "preguntar"
    ayuda = "Consulta el servicio desde la terminal."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("pregunta", help="La pregunta a enviar (entre comillas si tiene espacios).")
        parser.add_argument("--url", default="http://127.0.0.1:8000",
                            help="Base del servicio a consultar (por defecto: 'http://127.0.0.1:8000').")
        parser.add_argument("--timeout", type=float, default=30.0,
                            help="Segundos de espera máxima por una respuesta antes de fallar (por defecto: 30).")
        parser.add_argument("--diagnostico", action="store_true",
                            help="Ejecuta la pregunta con el motor del proyecto en este proceso (sin el servicio) y "
                                 "muestra etapas con su latencia, señales, términos foco, la regla que decidió y el "
                                 "tramo exacto. En modo Qdrant local, detén 'rag servir' antes.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        if args.diagnostico:
            return self._diagnostico(args.pregunta)
        import httpx

        url = f"{args.url.rstrip('/')}/consultar"
        try:
            resp = httpx.post(url, json={"pregunta": args.pregunta, "id_sesion": "rag-cli"}, timeout=args.timeout)
        except httpx.ConnectError:
            print(f"No se pudo conectar a {url}. ¿Está el servicio arriba? Ejecuta 'rag servir' primero.")
            return 1
        except httpx.TimeoutException:
            print(f"El servicio no respondió en {args.timeout}s.")
            return 1

        if resp.status_code != 200:
            print(f"El servicio respondió {resp.status_code}: {resp.text}")
            return 1

        datos = resp.json()
        estado = datos.get("estado", "?")
        print(ETIQUETA_ESTADO.get(estado, f"[{estado.upper()}]"))
        print(datos.get("respuesta", ""))
        fragmentos = datos.get("fragmentos") or []
        if fragmentos:
            print("\nCitas:")
            for f in fragmentos:
                print(f"  - {f['doc_titulo']} > {f['seccion']} "
                      f"(offsets {f['offset_inicio']}-{f['offset_fin']}, score={f['score']:.3f})")
        return 0


    @staticmethod
    def _diagnostico(pregunta: str) -> int:
        from rag.aplicacion.consulta import MotorNoListo, diagnosticar_pregunta

        try:
            d = diagnosticar_pregunta(pregunta)
        except MotorNoListo as e:
            print(f"El motor no está listo: {e}")
            print("  Acción: rag doctor")
            return 1
        except Exception as e:  # noqa: BLE001 -- índice bloqueado, modelo faltante, configuración inválida...
            print(f"No se pudo ejecutar el motor del proyecto: {e}")
            print("  Acción: rag doctor")
            return 1
        print(ETIQUETA_ESTADO.get(d.estado, f"[{d.estado.upper()}]"))
        print(d.respuesta)
        print(f"\nRegla: {d.regla or '—'} (motivo: {d.motivo}; perfil: {d.perfil or '—'})")
        print("Etapas (ms):")
        for nombre, ms in d.etapas:
            print(f"  {nombre:16} {ms:>6}")
        print(f"  {'total':16} {d.total_ms:>6}" + ("   (salida temprana: sin modelos)" if d.salto_modelos else ""))
        if d.senales:
            print("Señales:")
            print("  " + "  ".join(f"{k}={_valor(v)}" for k, v in d.senales.items()))
        print(f"Términos foco: encontrados: {', '.join(d.foco_encontrados) or '—'}; "
              f"ausentes: {', '.join(d.foco_ausentes) or '—'}")
        if d.ausentes_del_corpus:
            print(f"Términos que no están en el corpus: {', '.join(d.ausentes_del_corpus)}")
        if d.oracion_foco:
            print(f"Oración evaluada: «{d.oracion_foco}»")
        if d.tramo:
            print(f"Tramo exacto: «{d.tramo['texto']}» ({d.tramo['chunk_id']}, "
                  f"offsets {d.tramo['offset_inicio']}-{d.tramo['offset_fin']})")
        else:
            print("Tramo exacto: —")
        for e in d.evidencias:
            print(f"Evidencia: {e['doc_id']} offsets {e['offset_inicio']}-{e['offset_fin']}")
        if d.tono:
            print(f"Tono: {d.tono}; plantillas: {', '.join(d.plantillas) or '—'}")
        for a in d.advertencias:
            print(f"Advertencia: {a}")
        return 0


def _valor(v) -> str:
    return f"{v:.3f}" if isinstance(v, float) else str(v)


__all__ = ["ComandoPreguntar", "ComandoServir", "ETIQUETA_ESTADO"]
