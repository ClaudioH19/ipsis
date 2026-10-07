"""Repite G5 alternando dos árboles de código bajo la misma carga.

python tests/datos/banco_universal/medir_latencia.py ANTES DESPUES SALIDA [rondas]
Conserva cada ejecución completa; no sustituye las mediciones originales.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
from pathlib import Path


def huella(raiz: Path) -> str:
    h = hashlib.sha256()
    for p in sorted((raiz / "ipsis").rglob("*")):
        if p.is_file() and p.suffix in {".py", ".yaml"}:
            h.update(p.relative_to(raiz).as_posix().encode())
            h.update(b"\0")
            h.update(p.read_bytes())
    return "sha256:" + h.hexdigest()


def main() -> None:
    antes, despues, salida = (Path(p).resolve() for p in sys.argv[1:4])
    rondas = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    if rondas < 2:
        raise ValueError("Se requieren al menos dos rondas para alternar el orden")
    salida.mkdir(parents=True, exist_ok=True)
    temporal = salida / "tmp"
    temporal.mkdir(exist_ok=True)
    medir = Path(__file__).resolve().parents[1] / "banco_consultas/medir.py"
    registros = []
    for ronda in range(rondas):
        orden = ("antes", "despues") if ronda % 2 == 0 else ("despues", "antes")
        for version in orden:
            archivo = salida / f"{ronda + 1}-{version}.json"
            print(f"RONDA {ronda + 1}: {version}", flush=True)
            subprocess.run(
                [sys.executable, str(medir), str(archivo), "light", "es,en,pt", "banco_universal"],
                cwd=despues,
                env={**os.environ, "IPSIS_CODIGO": str(antes if version == "antes" else despues),
                     "PYTHONUTF8": "1", "TEMP": str(temporal), "TMP": str(temporal)},
                check=True,
            )
            registros.append({"ronda": ronda + 1, "version": version,
                              "resultado": json.loads(archivo.read_text(encoding="utf-8"))})
    filas = []
    for idioma in ("es", "en", "pt"):
        grupos = {v: [r["resultado"]["light"][idioma] for r in registros if r["version"] == v]
                  for v in ("antes", "despues")}
        base = grupos["antes"][0]["casos"]
        for ejecuciones in grupos.values():
            for e in ejecuciones:
                assert set(e["casos"]) == set(base)
                for i, c in e["casos"].items():
                    assert all(c[k] == base[i][k] for k in ("estado", "directa", "falso_ok", "sin_literal")), i
        medias = {v: statistics.mean(e["media_ms"] for e in es) for v, es in grupos.items()}
        filas.append({"idioma": idioma, "medias_por_ronda": {
            v: [e["media_ms"] for e in es] for v, es in grupos.items()},
            "media_antes_ms": medias["antes"], "media_despues_ms": medias["despues"],
            "cambio_pct": 100 * (medias["despues"] / medias["antes"] - 1),
            "g5": medias["despues"] <= 1.1 * medias["antes"]})
    informe = {"rondas": rondas, "orden": "AB / BA alternado", "perfil": "light",
               "casos_por_idioma_y_ejecucion": 30, "python": sys.version,
               "platform": platform.platform(), "antes_code": huella(antes), "despues_code": huella(despues),
               "calidad_identica": True, "filas": filas, "g5": all(f["g5"] for f in filas)}
    (salida / "resumen.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(informe, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
