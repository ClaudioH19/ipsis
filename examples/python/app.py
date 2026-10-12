"""Página HTML con widget; el servicio ipsis se ejecuta por separado."""
import html
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def pagina():
    api = html.escape(os.environ.get("IPSIS_API", "http://127.0.0.1:8000").rstrip("/"), quote=True)
    clave = html.escape(os.environ.get("IPSIS_WIDGET_KEY", ""), quote=True)
    return f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Python example · ipsis</title></head>
<body>
<main><h1>Knowledge base</h1><p>Ask about the published documents.</p></main>
<ipsis-chat api="{api}" widget-key="{clave}" position="bottom-right"></ipsis-chat>
<script src="{api}/widget.js" defer></script>
</body></html>'''
