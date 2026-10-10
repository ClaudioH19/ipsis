"""Ejecuta el medidor con código congelado y registra intenciones efectivas."""
from pathlib import Path
import json
import runpy
import sys

runpy.run_path(sys.argv[1])["_importar_codigo"]()
script = sys.argv[2]
destino = Path(sys.argv[3]).with_suffix(".intenciones.json")
argumentos = sys.argv[2:]

from ipsis.consulta.etapas.recuperacion import EtapaSenales

original = EtapaSenales.ejecutar
registros = []


def ejecutar(self, ctx):
    original(self, ctx)
    intencion = ctx.diagnostico.get("intencion") or {}
    registros.append({
        "sesion": ctx.id_sesion,
        "idioma": getattr(getattr(self.motor, "idioma", None), "codigo", None),
        "perfil": getattr(getattr(self.motor, "perfil_instalacion", None), "perfil", None),
        "pregunta_efectiva": ctx.consulta.pregunta_original,
        "intencion": ctx.consulta.intencion,
        "diagnostico": intencion,
    })


EtapaSenales.ejecutar = ejecutar
sys.argv = argumentos
runpy.run_path(script, run_name="__main__")
destino.write_text(json.dumps(registros, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
