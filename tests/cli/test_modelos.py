"""``ipsis models list | descargar | verificar | exportar`` con la descarga simulada (sin red).

La simulación reemplaza solo ``huggingface_hub.snapshot_download``: el camino
CLI → aplicacion → modelos.descarga es el real.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ipsis.cli import main
from apoyo import leer_proyecto

E5_SMALL, E5_BASE = "intfloat/multilingual-e5-small", "intfloat/multilingual-e5-base"
MMARCO, BGE = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "onnx-community/bge-reranker-v2-m3-ONNX"
LECTOR = "dewdev/mdeberta-v3-base-squad2-onnx"
MEDIUM = [E5_SMALL, MMARCO, LECTOR]


@pytest.fixture
def hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Hub falso: descarga «escribe» los archivos pedidos; registra cada llamada."""
    llamadas: list[dict] = []

    def snapshot_download(repo_id, allow_patterns, cache_dir, local_files_only, revision=None):
        llamadas.append({"repo_id": repo_id, "allow_patterns": list(allow_patterns),
                         "cache_dir": cache_dir, "local_files_only": local_files_only})
        carpeta = Path(cache_dir) / repo_id.replace("/", "--")
        if local_files_only:
            if not carpeta.exists():
                raise OSError("no está en caché")
            return str(carpeta)
        for patron in allow_patterns:
            if not patron.endswith("_data"):
                (carpeta / patron).parent.mkdir(parents=True, exist_ok=True)
                (carpeta / patron).write_text("x", encoding="utf-8")
        return str(carpeta)

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", snapshot_download)
    monkeypatch.setenv("IPSIS_MODELS_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.chdir(tmp_path)
    return llamadas


def _descargas(llamadas) -> list[str]:
    return [ll["repo_id"] for ll in llamadas if not ll["local_files_only"]]


def _proyecto(perfil: str) -> None:
    assert main(["init", "--profile", perfil, "--language", "en"]) == 0


def _perfil_activo() -> str:
    return leer_proyecto(Path("config/assistant.yaml"))["perfil"]


# --- listar -------------------------------------------------------------------------------
def test_light_lista_solo_el_denso(hub, capsys):
    _proyecto("light")
    capsys.readouterr()
    assert main(["models", "list"]) == 0
    salida = capsys.readouterr().out
    assert "denso: " + E5_SMALL in salida and "reranker" not in salida and "lector" not in salida
    assert _descargas(hub) == []  # listar nunca descarga


def test_default_v2_descarga_solo_los_modelos_que_ejecuta(hub):
    _proyecto("medium")
    assert leer_proyecto(Path("config/engine.yaml"))["pipeline"] == "v2"
    assert main(["models", "download"]) == 0
    assert _descargas(hub) == [E5_SMALL, MMARCO]
    assert _perfil_activo() == "medium"


def test_medium_lista_sus_roles_con_datos_del_catalogo_y_estado_de_cache(hub, capsys, monkeypatch):
    from ipsis.modelos.catalogo import obtener

    _proyecto("medium")
    assert main(["models", "download", "--profile", "light"]) == 0  # solo e5-small queda en caché
    capsys.readouterr()
    monkeypatch.setattr("platform.machine", lambda: "aarch64")
    assert main(["models", "list"]) == 0
    salida = capsys.readouterr().out
    bloques = {b.split(":")[0]: b for b in salida.split("\n\n")[1:] if not b.startswith(" ")}
    assert set(bloques) == {"denso", "reranker"}
    for rol, id_hf in zip(("denso", "reranker"), MEDIUM[:2]):
        spec = obtener(id_hf)
        assert id_hf in bloques[rol] and spec.licencia in bloques[rol]
        assert spec.archivo_onnx("aarch64") in bloques[rol]  # el ONNX de la CPU actual
    assert "onnx/model_qint8_arm64.onnx" in bloques["reranker"]
    assert "Caché:      disponible" in bloques["denso"] and "Caché:      falta" in bloques["reranker"]
    assert "Acción: ipsis models download" in salida


def test_listar_y_verificar_sin_proyecto_piden_rag_init(hub, capsys):
    assert main(["models", "list"]) == 1
    assert "ipsis init" in capsys.readouterr().out
    assert main(["models", "verify"]) == 1


# --- descargar ----------------------------------------------------------------------------
def test_descargar_usa_el_perfil_activo_y_la_frontera_de_cache(hub, capsys, tmp_path):
    from ipsis.modelos.catalogo import obtener

    _proyecto("medium")
    assert main(["models", "download"]) == 0
    assert _descargas(hub) == MEDIUM[:2]
    for llamada in (ll for ll in hub if not ll["local_files_only"]):
        assert llamada["allow_patterns"] == obtener(llamada["repo_id"]).patrones()
        assert llamada["cache_dir"] == str(tmp_path / "cache")  # caché global, no el proyecto
    salida = capsys.readouterr().out
    assert salida.count("-- descargado") == 2 and "Licencia: Apache-2.0" in salida
    assert not Path("modelos").exists()

    hub.clear()
    assert main(["models", "download"]) == 0  # todo está: no se vuelve a descargar
    assert _descargas(hub) == [] and capsys.readouterr().out.count("ya disponible") == 2


def test_v1_explicito_conserva_la_descarga_del_lector(hub):
    from apoyo import escribir_proyecto

    _proyecto("medium")
    archivo = Path("config/engine.yaml")
    cfg = leer_proyecto(archivo)
    cfg["pipeline"] = "v1"
    escribir_proyecto(archivo, cfg)
    assert main(["models", "download"]) == 0
    assert _descargas(hub) == MEDIUM


def test_descargar_otro_perfil_no_cambia_el_activo_y_reutiliza_lo_compartido(hub, capsys):
    _proyecto("light")
    assert main(["models", "download"]) == 0
    assert main(["models", "download", "--profile", "medium"]) == 0
    # e5-small (light y medium) baja una sola vez.
    assert _descargas(hub) == [E5_SMALL, MMARCO, LECTOR]
    assert _perfil_activo() == "light"


def test_descargar_con_perfil_funciona_fuera_de_un_proyecto(hub):
    assert main(["models", "download", "--profile", "light"]) == 0
    assert _descargas(hub) == [E5_SMALL] and not Path("config").exists()
    assert main(["models", "download"]) == 1  # sin --profile necesita el perfil activo


@pytest.mark.parametrize(("perfil", "mensaje"), [("turbo", "desconocido"), ("bm25", "diagnóstico")])
def test_perfil_no_instalable_falla_sin_descargar(hub, capsys, perfil, mensaje):
    _proyecto("light")
    capsys.readouterr()
    assert main(["models", "download", "--profile", perfil]) == 1
    salida = capsys.readouterr().out
    assert mensaje in salida and "light, medium" in salida
    assert hub == [] and _perfil_activo() == "light"


def test_sin_red_falla_con_un_mensaje_accionable(hub, capsys, monkeypatch):
    import huggingface_hub

    def sin_red(repo_id, allow_patterns, cache_dir, local_files_only):
        hub.append({"repo_id": repo_id, "local_files_only": local_files_only})
        raise OSError("offline")

    _proyecto("medium")
    monkeypatch.setattr(huggingface_hub, "snapshot_download", sin_red)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    capsys.readouterr()
    assert main(["models", "download"]) == 1
    salida = capsys.readouterr().out
    assert "HF_HUB_OFFLINE=1" in salida and E5_SMALL in salida and "Traceback" not in salida
    assert _descargas(hub) == [E5_SMALL]  # se detiene en el primero; no hay otra ruta de red


# --- verificar ----------------------------------------------------------------------------
def test_verificar_falta_un_modelo_y_no_lo_descarga(hub, capsys, monkeypatch):
    _proyecto("medium")
    assert main(["models", "download", "--profile", "light"]) == 0
    monkeypatch.setattr("ipsis.modelos.verificacion.probar", lambda spec, carpeta: None)
    capsys.readouterr()
    assert main(["models", "verify"]) == 1
    salida = capsys.readouterr().out
    assert f"{E5_SMALL:45} OK" in salida and f"{MMARCO:45} FALTA" in salida
    assert "Acción: ipsis models download" in salida
    assert _descargas(hub) == [E5_SMALL]

    assert main(["models", "download"]) == 0
    assert main(["models", "verify"]) == 0


def test_onnx_presente_pero_no_cargable_no_se_reporta_como_faltante(hub, capsys):
    _proyecto("light")
    assert main(["models", "download"]) == 0  # el hub falso deja archivos de texto, no ONNX
    capsys.readouterr()
    assert main(["models", "verify"]) == 1
    salida = capsys.readouterr().out
    assert "NO CARGA" in salida and "onnx/model.onnx no carga" in salida
    assert "FALTA" not in salida and "Traceback" not in salida


def test_inferencia_invalida_identifica_al_modelo(hub, capsys, monkeypatch):
    from ipsis.modelos import verificacion

    class Cargado:  # sesión y tokenizador «cargan»; solo se prueba la inferencia
        def __init__(self, spec, carpeta, hilos=None):
            self.sesion = self.tokenizador = object()

        def puntuar(self, pregunta, pasajes):
            return [float("nan")]

    inferir = verificacion._inferir
    _proyecto("medium")
    assert main(["models", "download"]) == 0
    monkeypatch.setattr(verificacion, "_clase", lambda spec: Cargado)
    # El reranker pasa por la validación real; los otros dos, como sanos.
    monkeypatch.setattr(verificacion, "_inferir",
                        lambda spec, m: inferir(spec, m) if spec.tarea == "reranker" else None)
    capsys.readouterr()
    assert main(["models", "verify"]) == 1
    lineas = capsys.readouterr().out.splitlines()
    fila = next(i for i, linea in enumerate(lineas) if MMARCO in linea)
    assert lineas[fila].endswith("FALLA") and "puntaje inválido" in lineas[fila + 1]
    assert sum(linea.endswith(" OK") for linea in lineas) == 1


# --- exportar -----------------------------------------------------------------------------
def test_exportar_sin_el_extra_dice_que_instalar(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(sys.modules, "optimum", None)  # simula un entorno sin [export]
    monkeypatch.setitem(sys.modules, "torch", None)
    assert main(["models", "export", "org/modelo", "--int8"]) == 1
    salida = capsys.readouterr().out
    assert 'Acción: uv tool install --force --python 3.12 "ipsis[export] @ git+https://github.com/ClaudioH19/ipsis.git"' in salida
    assert "Traceback" not in salida and "ModuleNotFoundError" not in salida
    assert not Path("exported").exists()


def test_exportar_int8_llega_al_caso_de_uso_y_no_registra_el_modelo(tmp_path, capsys, monkeypatch):
    from ipsis.modelos import exportacion
    from ipsis.modelos.catalogo import CATALOGO

    llamadas = []

    def convertir(id_hf, salida):
        llamadas.append(("convertir", id_hf))
        salida.mkdir(parents=True)
        (salida / "model.onnx").write_bytes(b"onnx")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(exportacion, "dependencias_faltantes", lambda: [])
    monkeypatch.setattr(exportacion, "_convertir", convertir)
    monkeypatch.setattr(exportacion, "_cuantizar", lambda origen, destino: llamadas.append(("int8", origen.name,
                                                                                            destino.name)))
    assert main(["models", "export", "org/modelo", "--int8"]) == 0
    assert llamadas == [("convertir", "org/modelo"), ("int8", "model.onnx", "model_int8.onnx")]
    salida = capsys.readouterr().out
    assert str(Path("exported/org--modelo/model.onnx")) in salida and "model_int8.onnx" in salida
    assert "org/modelo" not in CATALOGO

    assert main(["models", "export", "otra/cosa"]) == 0
    assert llamadas[-1] == ("convertir", "otra/cosa")  # sin --int8 no se cuantiza
    assert main(["models", "export", "org/modelo"]) == 1  # no pisa una exportación previa
    assert "ya existe" in capsys.readouterr().out


def test_exportacion_que_falla_no_muestra_traceback_ni_deja_carpeta(tmp_path, capsys, monkeypatch):
    from ipsis.modelos import exportacion

    def convertir(id_hf, salida):
        salida.mkdir(parents=True)
        raise ImportError("cannot import name 'get_parameter_dtype' from 'transformers.modeling_utils'")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(exportacion, "dependencias_faltantes", lambda: [])
    monkeypatch.setattr(exportacion, "_convertir", convertir)
    assert main(["models", "export", "org/modelo"]) == 1
    salida = capsys.readouterr().out
    assert "falló" in salida and "get_parameter_dtype" in salida and "Traceback" not in salida
    assert not Path("exported/org--modelo").exists()


# --- imports ------------------------------------------------------------------------------
def test_listar_y_descargar_no_cargan_torch_ni_onnxruntime(tmp_path):
    codigo = """
import sys
from pathlib import Path
import huggingface_hub

def falso(repo_id, allow_patterns, cache_dir, local_files_only):
    carpeta = Path(cache_dir) / repo_id.replace('/', '--')
    if local_files_only and not carpeta.exists():
        raise OSError('no')
    for p in allow_patterns:
        (carpeta / p).parent.mkdir(parents=True, exist_ok=True)
        (carpeta / p).write_text('x')
    return str(carpeta)

huggingface_hub.snapshot_download = falso
from ipsis.cli import main
assert main(['init', '--profile', 'medium']) == 0
assert main(['models', 'download']) == 0
assert main(['models', 'list']) == 0
print('PESADOS=' + ','.join(m for m in ('torch', 'optimum', 'onnxruntime', 'transformers') if m in sys.modules))
"""
    import os

    entorno = {**os.environ, "IPSIS_MODELS_DIR": str(tmp_path / "cache"), "PYTHONIOENCODING": "utf-8"}
    salida = subprocess.run([sys.executable, "-c", codigo], cwd=tmp_path, capture_output=True, text=True,
                            encoding="utf-8", env=entorno)
    assert salida.returncode == 0, salida.stderr
    assert "PESADOS=\n" in salida.stdout + "\n"


# --- modelos reales ------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.modelos(*MEDIUM)
def test_verificar_medium_con_los_modelos_reales(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _proyecto("medium")
    capsys.readouterr()
    assert main(["models", "verify"]) == 0
    assert capsys.readouterr().out.count(" OK") == 2
