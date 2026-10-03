"""Benchmark reproducible de los modos Qdrant sobre un banco versionado."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

from rag.banco_evaluacion import cargar_banco
from rag.comparacion import cargar_artefacto, comparar_artefactos


def ejecutar_benchmark(ruta_banco: str, directorio_salida: str) -> Path:
    from rag.cli import main

    manifiesto = Path(ruta_banco).resolve()
    banco = cargar_banco(manifiesto)
    corpus = (manifiesto.parent / banco.manifiesto.corpus.directorio).resolve()
    salida = Path(directorio_salida).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    anterior = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="rag_benchmark_") as temporal:
        proyecto = Path(temporal)
        try:
            os.chdir(proyecto)
            if main(["init"]) != 0:
                raise RuntimeError("falló rag init durante el benchmark")
            for archivo in banco.manifiesto.corpus.archivos:
                if main(["cargar", str(corpus / archivo.ruta)]) != 0:
                    raise RuntimeError(f"falló la carga de {archivo.ruta}")

            ruta_cfg = proyecto / "configuracion" / "motor.yaml"
            cfg = yaml.safe_load(ruta_cfg.read_text(encoding="utf-8"))
            artefactos = []
            ejecuciones = [
                ("qdrant", "vectorial", True),
                ("qdrant", "hibrida", False),
            ]
            for retriever, modo, reindexar in ejecuciones:
                cfg["componentes"]["retriever"] = retriever
                cfg["recuperacion"]["modo"] = modo
                ruta_cfg.write_text(
                    yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                if reindexar and main(["indexar"]) != 0:
                    raise RuntimeError(f"falló la indexación de {retriever}/{modo}")
                etiqueta = f"qdrant_{modo}"
                ruta_artefacto = salida / f"{etiqueta}.json"
                main([
                    "evaluar", "--banco", str(manifiesto),
                    "--salida", str(ruta_artefacto),
                ])
                if not ruta_artefacto.is_file():
                    raise RuntimeError(f"no se produjo el artefacto {etiqueta}")
                artefactos.append(cargar_artefacto(ruta_artefacto))

            informe = comparar_artefactos(artefactos)
            ruta_informe = salida / "comparacion.json"
            ruta_informe.write_text(informe.model_dump_json(indent=2), encoding="utf-8")
            return ruta_informe
        finally:
            os.chdir(anterior)


__all__ = ["ejecutar_benchmark"]
