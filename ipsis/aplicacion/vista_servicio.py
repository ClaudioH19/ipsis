"""Abre la página local de prueba cuando el servidor ya puede servirla."""
from __future__ import annotations

from threading import Event, Thread
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


def url_local(host, puerto, ruta="/widget/demo.html"):
    host = "127.0.0.1" if host == "0.0.0.0" else "::1" if host == "::" else host
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{puerto}{ruta}"


def abrir_cuando_listo(url, *, intentos=120):
    cancelar = Event()

    def abrir():
        for _ in range(intentos):
            if cancelar.is_set():
                return
            try:
                with urlopen(url, timeout=.5) as respuesta:
                    listo = respuesta.status == 200
            except (URLError, OSError, TimeoutError):
                listo = False
            if listo:
                if not cancelar.is_set():
                    webbrowser.open(url)
                return
            if cancelar.wait(.5):
                return

    Thread(target=abrir, name="ipsis-demo", daemon=True).start()
    return cancelar
