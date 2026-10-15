"""``ipsis profile show | cambiar`` con manifiestos y calibraciones sintéticos (sin modelos)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ipsis.cli import main
from apoyo import escribir_proyecto, leer_proyecto

E5_SMALL, E5_BASE = "intfloat/multilingual-e5-small", "intfloat/multilingual-e5-base"
HASH = "sha256:corpus-del-proyecto"


@pytest.fixture
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    def crear(perfil: str) -> Path:
        assert main(["init", "--profile", perfil]) == 0
        return tmp_path

    return crear


def _indice(modelo: str, dimension: int | None = None) -> Path:
    """Manifiesto de un índice construido con ``modelo`` (lo que deja ``ipsis index``)."""
    from ipsis.configuracion.carga import config_recuperacion
    from ipsis.indice.manifiesto import ManifiestoIndice, guardar_manifiesto
    from ipsis.indice.qdrant import nombre_coleccion_versionada
    from ipsis.modelos.catalogo import obtener

    rec = config_recuperacion()
    nombre = nombre_coleccion_versionada(rec["coleccion_base"], modelo, rec["version_coleccion"])
    return guardar_manifiesto(ManifiestoIndice(coleccion=nombre, modelo_denso=modelo,
                                               dimension=dimension or obtener(modelo).dimension,
                                               hash_corpus=HASH, n_chunks=3))


def _calibracion(perfil: str) -> Path:
    from ipsis.aplicacion.proyecto import perfil_de_instalacion
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.lenguaje.sinonimos import huella_lexica

    ruta = Path("config/calibration.yaml")
    ruta.write_text(yaml.safe_dump({
        "version": 2,
        "estado": "calibrado", "alfa": 0.05, "confianza": 0.95,
        "procedencia": {"perfil": perfil, "modelos": perfil_de_instalacion(perfil).modelos.model_dump(),
                        "hash_corpus": HASH, "banco": "golden@1.0.0", "hash_banco": "x",
                        "hash_lexico": huella_lexica(cargar_paquete("es", proyecto=Path.cwd()))},
        "umbrales": {"ok": 0.9},
    }), encoding="utf-8")
    return ruta


def _ajustes_del_proyecto():
    """Los ajustes con los que el motor resuelve el perfil (incluido el reranker del idioma del proyecto)."""
    from ipsis.configuracion.carga import cargar_dominio
    from ipsis.configuracion.perfiles import ajustes_de_idioma

    return ajustes_de_idioma("medium", None, cargar_dominio().get("idioma"))[0]


def _perfil_activo() -> str:
    return leer_proyecto(Path("config/assistant.yaml"))["perfil"]


# --- mostrar ----------------------------------------------------------------------------
def test_mostrar_lee_modelos_y_presupuesto_del_perfil(proyecto, capsys):
    from ipsis.aplicacion.proyecto import perfil_de_instalacion

    proyecto("medium")
    assert main(["profile", "show"]) == 0
    salida = capsys.readouterr().out
    medium = perfil_de_instalacion("medium")  # con el reranker del idioma del proyecto
    assert "Perfil activo: medium" in salida and f"{medium.presupuesto_p95_ms} ms" in salida
    for modelo in medium.modelos.model_dump().values():
        assert modelo in salida
    assert "todavía no existe" in salida and "incompatible" not in salida  # sin índice ≠ incompatible
    assert "Calibración: no hay" in salida


def test_mostrar_indice_compatible_e_incompatible(proyecto, capsys):
    proyecto("medium")
    _indice(E5_BASE)  # índice construido con otro modelo denso
    assert main(["profile", "show"]) == 0
    salida = capsys.readouterr().out
    assert "incompatible" in salida and E5_BASE in salida and E5_SMALL in salida and "ipsis index" in salida
    _indice(E5_SMALL)  # después de reindexar para medium
    assert main(["profile", "show"]) == 0
    assert "Índice: compatible" in capsys.readouterr().out


def test_dimension_distinta_es_incompatible(proyecto, capsys):
    proyecto("light")
    _indice(E5_SMALL, dimension=768)
    assert main(["profile", "show"]) == 0
    assert "incompatible" in capsys.readouterr().out


def test_mostrar_calibracion_vigente_y_obsoleta_con_la_regla_del_motor(proyecto, capsys):
    from ipsis.configuracion.perfiles import perfil_efectivo

    proyecto("medium")
    _indice(E5_SMALL)
    calibracion = _calibracion("medium")
    assert main(["profile", "show"]) == 0
    assert "Calibración: vigente" in capsys.readouterr().out
    assert perfil_efectivo("medium", _ajustes_del_proyecto(), hash_corpus=HASH).origen_umbrales == "calibracion"

    assert main(["profile", "set", "light"]) == 0
    salida = capsys.readouterr().out
    assert "ya no corresponde al perfil activo" in salida and "ipsis calibrate --apply" in salida
    assert main(["profile", "show"]) == 0
    assert "Calibración: obsoleta" in capsys.readouterr().out
    assert calibracion.is_file()  # se conserva para auditoría
    assert perfil_efectivo("light", hash_corpus=HASH).origen_umbrales == "perfil"  # el motor la ignora


# --- cambiar ------------------------------------------------------------------------------
@pytest.mark.parametrize(("origen", "destino", "indice", "reindexar"), [
    ("light", "medium", E5_SMALL, False),
    ("medium", "light", E5_SMALL, False),
    ("light", "medium", E5_BASE, True),  # índice de otro modelo denso
])
def test_transiciones_segun_el_manifiesto(proyecto, capsys, origen, destino, indice, reindexar):
    proyecto(origen)
    manifiesto = _indice(indice)
    capsys.readouterr()
    assert main(["profile", "set", destino]) == 0  # requerir reindexar no es un fallo
    salida = capsys.readouterr().out
    assert _perfil_activo() == destino
    assert ("Acción: ipsis index" in salida) is reindexar
    assert ("sigue siendo compatible" in salida) is not reindexar
    assert manifiesto.is_file()  # el índice no se borra


def test_cambio_sin_indice_no_habla_de_incompatibilidad(proyecto, capsys):
    proyecto("light")
    assert main(["profile", "set", "medium"]) == 0
    salida = capsys.readouterr().out
    assert "Todavía no hay índice" in salida and "incompatible" not in salida and "Acción" not in salida


def test_mismo_perfil_es_idempotente_y_no_toca_la_calibracion(proyecto, capsys):
    proyecto("medium")
    _indice(E5_SMALL)
    _calibracion("medium")
    asistente = Path("config/assistant.yaml").read_bytes()
    capsys.readouterr()
    assert main(["profile", "set", "medium"]) == 0
    salida = capsys.readouterr().out
    assert "ya está activo" in salida and "calibración" not in salida.lower()
    assert Path("config/assistant.yaml").read_bytes() == asistente
    assert main(["profile", "show"]) == 0
    assert "Calibración: vigente" in capsys.readouterr().out


@pytest.mark.parametrize(("perfil", "mensaje"), [("bm25", "diagnóstico"), ("turbo", "desconocido"),
                                                ("heavy", "desconocido")])
def test_perfiles_no_instalables_se_rechazan_sin_tocar_el_proyecto(proyecto, capsys, perfil, mensaje):
    proyecto("light")
    antes = Path("config/assistant.yaml").read_bytes()
    assert main(["profile", "set", perfil]) == 1
    salida = capsys.readouterr().out
    assert mensaje in salida and "light, medium" in salida and "Traceback" not in salida
    assert Path("config/assistant.yaml").read_bytes() == antes


def test_conserva_ajustes_perfil_y_rechaza_los_invalidos(proyecto, capsys):
    proyecto("light")
    motor = Path("config/engine.yaml")
    datos = leer_proyecto(motor)
    datos["ajustes_perfil"] = {"cascada": {"rerank_k": 5}}
    escribir_proyecto(motor, datos)
    assert main(["profile", "set", "medium"]) == 0
    assert leer_proyecto(motor)["ajustes_perfil"] == {"cascada": {"rerank_k": 5}}

    datos["ajustes_perfil"] = {"cascada": {"rerank_k": -3}}  # inválido para cualquier perfil
    escribir_proyecto(motor, datos)
    capsys.readouterr()
    assert main(["profile", "set", "light"]) == 1
    assert "profile_overrides" in capsys.readouterr().out
    assert _perfil_activo() == "medium"  # no quedó a medio cambiar
