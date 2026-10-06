"""Mide un banco caso por caso: el de consultas naturales o el universal.

    python tests/datos/banco_consultas/medir.py <salida.json> [light,medium] [es,en,pt] [banco_consultas|banco_universal]
    python tests/datos/banco_consultas/medir.py --comparar <antes.json> <despues.json>

Cada idioma se indexa en un proyecto temporal (``ipsis init``, ``load``,
``index``) y se evalúa con ``ipsis evaluate``. Por caso guarda el estado, la
regla, las señales y si fue:

- **correcta:** respuesta directa que muestra el texto literal esperado;
- **errónea:** falso ok (directa en un caso sin respuesta) o directa sin el
  literal esperado.

Para medir otro árbol de código (un worktree de un commit anterior, para
comparar), ``IPSIS_CODIGO=<carpeta del worktree>``: se importa ``ipsis`` de
ahí en vez del paquete instalado. ``--comparar`` imprime, por perfil e
idioma, correctas y erróneas antes → después y los casos que cambiaron.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

DATOS = Path(__file__).resolve().parents[1]
IDIOMAS = ("es", "en", "pt")


def _importar_codigo() -> None:
    codigo = os.environ.get("IPSIS_CODIGO")
    if not codigo:
        return
    # El paquete está instalado en modo editable (import hook): se quita para importar desde ``codigo``.
    sys.meta_path[:] = [f for f in sys.meta_path if "editable" not in type(f).__name__.lower()
                        and "editable" not in getattr(f, "__module__", "").lower()]
    sys.path.insert(0, codigo)
    import ipsis

    assert Path(ipsis.__file__).resolve().is_relative_to(Path(codigo).resolve()), ipsis.__file__


def correcta(caso: dict) -> bool:
    return caso["directa"] and not caso["falso_ok"] and not caso["sin_literal"]


def erronea(caso: dict) -> bool:
    return caso["directa"] and (caso["falso_ok"] or caso["sin_literal"])


def medir(idioma: str, perfil: str, banco: str = "banco_consultas") -> dict:
    from ipsis.aplicacion.evaluacion import evaluar_backend_activo
    from ipsis.cli import main
    from ipsis.lenguaje.entidades import configurar_idioma, configurar_perfil, idioma_activo, perfil_activo

    raiz = DATOS / banco
    previo = (idioma_activo(), perfil_activo())
    anterior = Path.cwd()
    with tempfile.TemporaryDirectory(prefix=f"{banco}_{idioma}_{perfil}_", ignore_cleanup_errors=True) as tmp:
        try:
            os.chdir(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(["init", "--profile", perfil, "--language", idioma]) == 0
                assert main(["load", str(raiz / idioma / "corpus")]) == 0
                assert main(["index"]) == 0
                artefacto = evaluar_backend_activo(str(raiz / idioma / "manifiesto.json"))
        finally:
            os.chdir(anterior)
            configurar_idioma(previo[0])
            configurar_perfil(previo[1])
    casos = {
        f.caso_id: {"pregunta": f.pregunta, "estado": f.estado, "regla": f.regla, "directa": f.directa,
                    "falso_ok": f.falso_ok, "sin_literal": f.directa_sin_literal,
                    "senales": f.senales if isinstance(f.senales, dict) else getattr(f.senales, "__dict__", None)}
        for f in artefacto.reporte.cobertura.casos
    }
    reporte = artefacto.reporte
    return {"casos": casos, "correctas": sum(map(correcta, casos.values())),
            "erroneas": sum(map(erronea, casos.values())),
            "media_ms": round(reporte.latencia_media_ms, 1), "p95_ms": reporte.latencia_p95_ms}


def comparar(antes: dict, despues: dict) -> list[str]:
    lineas = []
    for perfil, idiomas in despues.items():
        for idioma, d in idiomas.items():
            a = antes.get(perfil, {}).get(idioma)
            if a is None:
                continue
            lineas.append(f"{perfil} {idioma}: correctas {a['correctas']} → {d['correctas']}, "
                          f"erróneas {a['erroneas']} → {d['erroneas']}, media {a['media_ms']} → {d['media_ms']} ms")
            for caso_id, c in d["casos"].items():
                p = a["casos"].get(caso_id)
                if p and (p["estado"], correcta(p), erronea(p)) != (c["estado"], correcta(c), erronea(c)):
                    marca = lambda x: x["estado"] + (" ✓" if correcta(x) else " ✗" if erronea(x) else "")  # noqa: E731
                    lineas.append(f"    {caso_id}: {marca(p)} → {marca(c)}  {c['pregunta']}")
    return lineas


def main_cli(argv: list[str]) -> None:
    if argv and argv[0] == "--comparar":
        antes, despues = (json.loads(Path(a).read_text(encoding="utf-8")) for a in argv[1:3])
        print("\n".join(comparar(antes, despues)))
        return
    _importar_codigo()
    salida = Path(argv[0])
    perfiles = (argv[1] if len(argv) > 1 else "light,medium").split(",")
    idiomas = (argv[2] if len(argv) > 2 else ",".join(IDIOMAS)).split(",")
    banco = argv[3] if len(argv) > 3 else "banco_consultas"
    resultado: dict = {}
    for perfil in perfiles:
        for idioma in idiomas:
            r = medir(idioma, perfil, banco)
            resultado.setdefault(perfil, {})[idioma] = r
            print(perfil, idioma, f"correctas={r['correctas']}/{len(r['casos'])}", f"erróneas={r['erroneas']}",
                  f"media={r['media_ms']} ms", flush=True)
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main_cli(sys.argv[1:])
