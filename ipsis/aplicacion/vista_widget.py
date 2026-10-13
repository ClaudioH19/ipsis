"""Vista previa autónoma que reutiliza el widget real con fuentes de ejemplo."""
from __future__ import annotations

import html
import json
from importlib.resources import files

from ipsis.aplicacion.proyecto import interfaz_del_idioma
from ipsis.configuracion.glosario import a_externo
from ipsis.lenguaje.voz import voz_del_widget
from ipsis.recursos.mensajes import t


def _json_seguro(valor) -> str:
    # Evita cerrar un script cuando un título personalizado contiene HTML.
    return json.dumps(valor, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def vista_widget(tema: dict, css: str, presentacion: dict) -> str:
    idioma = t("runtime.preview_lang")
    voz = voz_del_widget(idioma)
    nombre = t("runtime.preview_header", preset=presentacion["preset"])
    cfg = {
        **presentacion,
        "assistant_name": nombre,
        "response_mode": "ranked_sources",
        "language": idioma,
        "interface": {**interfaz_del_idioma(idioma), **voz["interface"], "search_start": t("runtime.preview_search_heading"),
                      "search_instruction": t("runtime.preview_search_note"),
                      "search_send": t("runtime.preview_search_button"),
                      "search_read_document": t("runtime.preview_search_read")},
        "greeting": voz["messages"]["welcome"][0],
        "assistant_messages": voz["messages"],
        "suggested_questions": voz["suggestions"],
        "default_questions": voz["questions"],
        "widget_content": a_externo({"contenido": tema.get("contenido") or {}}, "estilos")["content"],
        "animations_enabled": tema.get("animaciones", {}).get("activadas", True),
        "avatar": {"enabled": False},
    }
    fragmentos = []
    for i in range(1, 4):
        titulo = t(f"runtime.preview_search_result_{i}")
        contenido = t(f"runtime.preview_search_excerpt_{i}")
        contexto = titulo + "\n\n" + contenido
        fragmentos.append({
            "chunk_id": f"ejemplo-{i}", "doc_id": "manual", "doc_title": "Manual",
            "source_name": t("runtime.preview_search_source"), "version": "1", "rank": i,
            "section": "Manual > " + titulo, "text": contexto,
            "offset_start": 0, "offset_end": len(contexto),
            "match_start": len(titulo) + 2, "match_end": len(contexto),
            "source_blocks": [
                {"kind": "heading", "text": titulo, "offset_start": 0, "offset_end": len(titulo)},
                {"kind": "paragraph", "text": contenido, "offset_start": len(titulo) + 2, "offset_end": len(contexto)},
            ],
        })
    respuesta = {"status": "related", "response_mode": "ranked_sources", "fragments": fragmentos, "has_more": False}
    widget_js = files("ipsis.servicio").joinpath("estaticos", "widget.js").read_text(encoding="utf-8")
    widget_js = widget_js.replace('temaServidor.href = API_BASE + "/styles.css";',
                                  'temaServidor.href = "data:text/css;charset=utf-8," + encodeURIComponent('
                                  + _json_seguro(css) + ');').replace("</script", "<\\/script")
    return f"""<!doctype html>
<html lang="{html.escape(idioma, quote=True)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(t('runtime.preview_title', preset=presentacion['preset']))}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;padding:24px;background:#e8eaf0;font:15px/1.5 Arial,sans-serif;color:#202334}}
main{{max-width:1040px;margin:auto;display:grid;grid-template-columns:minmax(0,680px) minmax(200px,1fr);gap:24px}}
.widget{{height:780px;min-width:0}}aside{{background:#fff;padding:24px;border-radius:12px;align-self:start}}
h1{{font-size:22px;margin-top:0}}button{{font:inherit;padding:8px 12px;cursor:pointer}}
@media(max-width:720px){{body{{padding:12px}}main{{grid-template-columns:1fr}}aside{{grid-row:1}}.widget{{height:760px}}}}
</style></head><body><main>
<div class="widget"><ipsis-chat api="/__ipsis_preview__" position="embedded"></ipsis-chat></div>
<aside><h1>{html.escape(t('runtime.preview_heading'))}</h1>
<p>{html.escape(t('runtime.preview_search_note'))}</p>
<p>{html.escape(t('runtime.preview_preset'))} <strong>{html.escape(presentacion['preset'])}</strong></p>
<button id="mostrar" type="button">{html.escape(t('runtime.preview_show_results'))}</button></aside>
</main><script>
var configuracionEjemplo = {_json_seguro(cfg)};
var respuestaEjemplo = {_json_seguro(respuesta)};
// Todo es local: esta vista no consulta el índice ni necesita un servicio.
window.fetch = function(url) {{
  var datos = String(url).endsWith('/config') ? configuracionEjemplo : respuestaEjemplo;
  return Promise.resolve(new Response(JSON.stringify(datos), {{headers:{{'Content-Type':'application/json'}}}}));
}};
</script><script>{widget_js}</script><script>
var sombra = document.querySelector('ipsis-chat').shadowRoot;
document.getElementById('mostrar').addEventListener('click', function() {{
  var entrada = sombra.querySelector('#rw-input');
  entrada.value = {_json_seguro(t('runtime.preview_question'))};
  sombra.querySelector('.rw-form').requestSubmit();
}});
</script></body></html>"""
