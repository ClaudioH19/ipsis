"""Sirve el visualizador local de Folio; al cerrarlo conserva sus archivos."""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

HERRAMIENTA = Path(__file__).resolve().parent
PROYECTO = HERRAMIENTA.parents[1]
sys.path.insert(0, str(PROYECTO))

ARCHIVOS = {
    "/": (HERRAMIENTA / "visualizador.html", "text/html; charset=utf-8"),
    "/avatar.js": (PROYECTO / "ipsis/servicio/estaticos/avatar.js", "text/javascript; charset=utf-8"),
    "/folio.avatar.json": (PROYECTO / "ipsis/recursos/avatares/folio.avatar.json", "application/json"),
    "/logo.svg": (PROYECTO / "docs/assets/logo.svg", "image/svg+xml"),
}


class Visualizador(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def responder(self, datos: bytes, tipo: str, estado: int = 200):
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        ruta = urlsplit(self.path).path
        try:
            if ruta == "/config":
                from ipsis.aplicacion.avatar import Avatar, mapa_eventos
                from ipsis.configuracion.personalidad import cargar_personalidad

                # La vista muestra Folio incluso si el proyecto usa otro avatar.
                definicion = json.loads(ARCHIVOS["/folio.avatar.json"][0].read_text(encoding="utf-8"))
                config = cargar_personalidad()
                folio = Avatar("folio", "incluido", ARCHIVOS["/folio.avatar.json"][0],
                               tuple(definicion["expressions"]), tuple(definicion["animations"]))
                eventos = mapa_eventos(folio, config.avatar.eventos)
                self.responder(json.dumps({"events": eventos.claves}).encode("utf-8"), "application/json")
                return
            entrada = ARCHIVOS.get(ruta)
            if entrada is None:
                self.responder(b"Not found", "text/plain", 404)
                return
            archivo, tipo = entrada
            self.responder(archivo.read_bytes(), tipo)
        except Exception as error:
            self.responder(json.dumps({"error": str(error)}).encode("utf-8"), "application/json", 500)

    def do_POST(self):
        if self.path != "/cerrar":
            self.responder(b"Not found", "text/plain", 404)
            return
        origen = self.headers.get("Origin")
        esperado = f"http://127.0.0.1:{self.server.server_port}"
        if origen and origen != esperado:
            self.responder(b"Forbidden", "text/plain", 403)
            return
        self.responder(b'{"cerrado":true}', "application/json")
        Thread(target=self.server.shutdown, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puerto", type=int, default=8765, help="Puerto local (por defecto: 8765)")
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.puerto), Visualizador) as servidor:
        print(f"Visualizador de Folio: http://127.0.0.1:{servidor.server_port}/", flush=True)
        print("Detén la vista con su botón o con Ctrl+C. Los archivos se conservan.", flush=True)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
