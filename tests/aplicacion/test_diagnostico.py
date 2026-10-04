"""``rag doctor``: cada chequeo sano y con fallo, sin red ni modelos reales.

Los modelos se simulan en la caché (archivos vacíos detrás de un
``snapshot_download`` falso), el índice es una colección Qdrant local vacía
con su manifiesto, y el golden se importa de verdad (no usa modelos).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import yaml

from rag.cli import main

E5_SMALL, E5_BASE = "intfloat/multilingual-e5-small", "intfloat/multilingual-e5-base"
MMARCO, LECTOR = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "dewdev/mdeberta-v3-base-squad2-onnx"
MANUAL = "# Manual\n\n## Filtro\n\nEl filtro de sedimentos se cambia cada 6 meses.\n\n## Garantía\n\nLa garantía dura dos años.\n"
GOLDEN = ("pregunta,tipo,respuesta_literal,documento\n"
          "¿Cada cuánto se cambia el filtro?,respondible,cada 6 meses,manual\n"
          "¿Cuál es el precio?,sin_respuesta,,\n")


@pytest.fixture
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Crea un proyecto con ``perfil``; los modelos en caché se instalan con ``instalar``."""
    cache = tmp_path / "cache"

    def snapshot_download(repo_id, allow_patterns, cache_dir, local_files_only):
        assert local_files_only, "doctor nunca descarga"
        carpeta = Path(cache_dir) / repo_id.replace("/", "--")
        if not carpeta.exists():
            raise OSError("no está en caché")
        return str(carpeta)

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", snapshot_download)
    monkeypatch.setenv("RAG_MODELOS_DIR", str(cache))
    monkeypatch.chdir(tmp_path)
    for variable in ("RAG_MODO", "RAG_ADMIN_TOKEN", "RAG_PROXY_CONFIABLE"):
        monkeypatch.delenv(variable, raising=False)  # el modo lo fija el entorno de quien corre doctor

    def crear(perfil: str = "light") -> Path:
        assert main(["init", "--perfil", perfil]) == 0
        return tmp_path

    return crear


def instalar(*ids: str) -> None:
    import os

    from rag.modelos.catalogo import obtener
    from rag.modelos.descarga import archivos_requeridos

    for id_hf in ids:
        carpeta = Path(os.environ["RAG_MODELOS_DIR"]) / id_hf.replace("/", "--")
        for archivo in archivos_requeridos(obtener(id_hf)):
            (carpeta / archivo).parent.mkdir(parents=True, exist_ok=True)
            (carpeta / archivo).write_text("x", encoding="utf-8")


def cargar_manual(texto: str = MANUAL) -> None:
    Path("manual.md").write_text(texto, encoding="utf-8")
    assert main(["cargar", "manual.md"]) == 0


def modificar_documento() -> None:
    """Cambia el documento ya cargado (lo que haría el cliente al editarlo)."""
    documento = next(Path("documentos").glob("*.md"))
    documento.write_text(documento.read_text(encoding="utf-8") + "\n## Nuevo\n\nOtro texto.\n", encoding="utf-8")


def indexar(modelo: str = E5_SMALL, stemmer: str | None = "spanish", hash_corpus: str | None = None,
            coleccion_qdrant: bool = True, con_hash_archivos: bool = False) -> str:
    """Lo que deja ``rag indexar``, sin modelos: colección vacía, estadísticas y manifiesto."""
    from qdrant_client.models import Distance, VectorParams

    from rag.configuracion.carga import cargar_proyecto, config_recuperacion
    from rag.indice.manifiesto import ManifiestoIndice, guardar_manifiesto
    from rag.indice.qdrant import crear_cliente_qdrant, nombre_coleccion_versionada, ruta_estadisticas
    from rag.ingesta.ingesta import huella_archivos, huella_corpus
    from rag.modelos.catalogo import obtener

    cfg_rec = config_recuperacion(cargar_proyecto())
    nombre = nombre_coleccion_versionada(cfg_rec["coleccion_base"], modelo, cfg_rec["version_coleccion"])
    dimension = obtener(modelo).dimension
    if coleccion_qdrant:
        cliente = crear_cliente_qdrant(qdrant_path=cfg_rec["qdrant_path"], modo="local")
        if not cliente.collection_exists(nombre):
            cliente.create_collection(nombre, vectors_config=VectorParams(size=dimension, distance=Distance.COSINE))
        cliente.close()
    ruta_estadisticas(nombre).parent.mkdir(parents=True, exist_ok=True)
    ruta_estadisticas(nombre).write_text("{}", encoding="utf-8")
    huella = hash_corpus or huella_corpus("documentos", cfg_rec)
    archivos = huella_archivos("documentos", cfg_rec) if con_hash_archivos else None
    guardar_manifiesto(ManifiestoIndice(coleccion=nombre, modelo_denso=modelo, dimension=dimension,
                                        stemmer=stemmer, hash_corpus=huella, n_chunks=2, hash_archivos=archivos))
    return huella


def calibracion(perfil: str, hash_corpus: str, estado: str = "calibrado") -> None:
    from rag.configuracion.perfiles import cargar_perfil_instalacion

    Path("configuracion/calibracion.yaml").write_text(yaml.safe_dump({
        "estado": estado, "alfa": 0.05, "confianza": 0.95,
        "procedencia": {"perfil": perfil, "modelos": cargar_perfil_instalacion(perfil).modelos.model_dump(),
                        "hash_corpus": hash_corpus, "banco": "golden@1.0.0", "hash_banco": "x"},
        "umbrales": {"ok": 0.9} if estado == "calibrado" else {},
    }), encoding="utf-8")


def importar_golden() -> None:
    Path("golden").mkdir(exist_ok=True)
    Path("golden/golden.csv").write_text(GOLDEN, encoding="utf-8")
    assert main(["golden", "importar", "golden/golden.csv"]) == 0


def editar(ruta: str, **cambios) -> None:
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
    datos.update(cambios)
    Path(ruta).write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")


def reporte():
    from rag.aplicacion.diagnostico import diagnosticar

    return diagnosticar()


def estados(r) -> dict[str, str]:
    return {c.clave: c.estado.value for c in r.chequeos}


def sano(perfil: str = "light") -> str:
    from rag.configuracion.perfiles import cargar_perfil_instalacion

    instalar(*(m for m in cargar_perfil_instalacion(perfil).modelos.model_dump().values() if m))
    cargar_manual()
    return indexar()


# --- sano ---------------------------------------------------------------------------------
def test_proyecto_sano_sin_golden_ni_calibracion_esta_listo(proyecto):
    from rag.aplicacion.diagnostico import ORDEN

    proyecto("medium")
    sano("medium")
    r = reporte()
    assert [c.clave for c in r.chequeos] == list(ORDEN)
    assert estados(r) == {"configuracion": "ok", "perfil": "ok", "idioma": "ok", "stemmer": "ok", "modelos": "ok",
                          "indice": "ok", "calibracion": "aviso", "golden": "aviso", "cors": "ok",
                          "personalidad": "ok", "modo": "ok"}  # Folio incluido
    assert r.listo and r.errores == [] and r.perfil == "medium"
    assert r.chequeo("modelos").datos["faltantes"] == []
    assert r.chequeo("calibracion").acciones == () and r.chequeo("golden").acciones == ()


def test_proyecto_sano_con_calibracion_y_golden_vigentes_queda_todo_ok(proyecto):
    proyecto("light")
    huella = sano("light")
    importar_golden()
    calibracion("light", huella)
    editar("configuracion/personalidad.yaml", avatar={"activo": False})  # sin avatar: el ícono, sin aviso
    r = reporte()
    assert set(estados(r).values()) == {"ok"}, estados(r)
    assert "vigente" in r.chequeo("calibracion").mensaje and "vigente" in r.chequeo("golden").mensaje


# --- todos los fallos a la vez ------------------------------------------------------------------
def test_acumula_todos_los_fallos_y_cada_error_trae_una_accion(proyecto):
    proyecto("medium")
    instalar(E5_SMALL)  # faltan reranker y lector
    cargar_manual()
    importar_golden()
    indexar(E5_BASE)  # índice de heavy
    calibracion("heavy", "sha256:viejo")
    modificar_documento()  # el corpus cambió después del golden y del índice
    editar("configuracion/asistente.yaml", claves_widget=["clave-sitio"])
    r = reporte()
    assert estados(r) == {"configuracion": "ok", "perfil": "ok", "idioma": "ok", "stemmer": "ok", "modelos": "error",
                          "indice": "error", "calibracion": "aviso", "golden": "aviso", "cors": "error",
                          "personalidad": "ok", "modo": "ok"}
    assert r.chequeo("modelos").datos["faltantes"] == [MMARCO, LECTOR]
    assert r.chequeo("modelos").acciones == ("rag modelos descargar",)
    assert "e5-base" in r.chequeo("indice").mensaje and r.chequeo("indice").acciones == ("rag indexar",)
    assert "obsoleta" in r.chequeo("calibracion").mensaje
    assert r.chequeo("golden").acciones == ("rag golden validar", "rag golden importar <archivo>")
    assert all(c.acciones for c in r.errores)
    assert not r.listo
    assert r.acciones[:3] == ["rag modelos descargar", "rag indexar", "rag configurar cors_origenes=https://tu-sitio.cl"]
    assert len(r.acciones) == len(set(r.acciones))


# --- proyecto y configuración -------------------------------------------------------------------
def test_fuera_de_un_proyecto(proyecto, capsys):
    from rag.aplicacion.diagnostico import ProyectoNoEncontrado

    with pytest.raises(ProyectoNoEncontrado):
        reporte()
    assert main(["doctor"]) == 1
    salida = capsys.readouterr().out
    assert "No se encontró un proyecto RAG" in salida and "Acción: rag init" in salida
    assert not Path("configuracion").exists()


def test_configuracion_invalida_nombra_el_archivo_y_no_evalua_lo_que_depende_de_ella(proyecto):
    proyecto("light")
    editar("configuracion/asistente.yaml", perfil="turbo")
    r = reporte()
    configuracion = r.chequeo("configuracion")
    assert configuracion.estado.value == "error" and "configuracion/asistente.yaml" in configuracion.mensaje
    assert "perfil" in configuracion.mensaje and configuracion.acciones
    for clave in ("perfil", "idioma", "stemmer", "modelos", "indice", "calibracion", "cors"):
        assert r.chequeo(clave).estado.value == "no_evaluado", clave


def test_politica_de_abstencion_desconocida(proyecto):
    proyecto("light")
    editar("configuracion/motor.yaml", componentes={**yaml.safe_load(
        Path("configuracion/motor.yaml").read_text(encoding="utf-8"))["componentes"], "abstention_policy": "nada"})
    c = reporte().chequeo("configuracion")
    assert c.estado.value == "error" and "política de abstención 'nada'" in c.mensaje and c.acciones


# --- perfil ---------------------------------------------------------------------------------
def test_perfil_bm25_editado_a_mano_es_error(proyecto):
    proyecto("light")
    editar("configuracion/asistente.yaml", perfil="bm25")
    r = reporte()
    perfil = r.chequeo("perfil")
    assert perfil.estado.value == "error" and "diagnóstico" in perfil.mensaje
    assert perfil.acciones == ("rag perfil cambiar light|medium|heavy",)
    assert r.chequeo("modelos").estado.value == "no_evaluado"


def test_ajustes_perfil_invalidos_son_error(proyecto):
    proyecto("light")
    editar("configuracion/motor.yaml", ajustes_perfil={"cascada": {"rerank_k": -3}})
    perfil = reporte().chequeo("perfil")
    assert perfil.estado.value == "error" and "ajustes_perfil" in perfil.mensaje
    assert "ajustes_perfil" in perfil.acciones[0]


# --- idioma y stemmer -----------------------------------------------------------------------
@pytest.mark.parametrize("codigo", ["en", "pt"])
def test_idiomas_con_paquete(proyecto, codigo):
    proyecto("light")
    editar("configuracion/asistente.yaml", idioma=codigo)
    r = reporte()
    assert r.chequeo("idioma").estado.value == "ok" and r.chequeo("stemmer").estado.value == "ok"


def test_idioma_sin_paquete_es_aviso_y_funciona_sin_stemmer(proyecto):
    proyecto("light")
    sano("light")
    editar("configuracion/asistente.yaml", idioma="ru")
    indexar(stemmer=None)  # reindexado con el idioma nuevo
    r = reporte()
    idioma = r.chequeo("idioma")
    assert idioma.estado.value == "aviso" and "reglas universales" in idioma.mensaje and idioma.datos["respaldo"]
    assert r.chequeo("stemmer").estado.value == "ok" and "no configurado" in r.chequeo("stemmer").mensaje
    assert r.listo


def test_idioma_yaml_invalido_es_error(proyecto):
    proyecto("light")
    Path("configuracion/idioma.yaml").write_text("mensajes: [1, 2]\n", encoding="utf-8")
    idioma = reporte().chequeo("idioma")
    assert idioma.estado.value == "error" and "configuracion/idioma.yaml" in idioma.mensaje and idioma.acciones


def test_stemmer_inexistente_es_error_y_sin_stemmer_es_valido(proyecto):
    proyecto("light")
    Path("configuracion/idioma.yaml").write_text("stemmer: klingon\n", encoding="utf-8")
    stemmer = reporte().chequeo("stemmer")
    assert stemmer.estado.value == "error" and "klingon" in stemmer.mensaje
    assert "configuracion/idioma.yaml" in stemmer.mensaje and "spanish" in stemmer.acciones[0]

    Path("configuracion/idioma.yaml").write_text("stemmer: null\n", encoding="utf-8")
    stemmer = reporte().chequeo("stemmer")
    assert stemmer.estado.value == "ok" and "no configurado" in stemmer.mensaje


# --- modelos ----------------------------------------------------------------------------------
def test_modelo_parcial_cuenta_como_faltante(proyecto):
    proyecto("light")
    instalar(E5_SMALL)
    Path(Path.cwd() / "cache" / E5_SMALL.replace("/", "--") / "tokenizer.json").unlink()
    modelos = reporte().chequeo("modelos")
    assert modelos.estado.value == "error" and modelos.datos["faltantes"] == [E5_SMALL]


def test_light_solo_requiere_el_denso(proyecto):
    proyecto("light")
    instalar(E5_SMALL)
    modelos = reporte().chequeo("modelos")
    assert modelos.estado.value == "ok" and len(modelos.detalles) == 1


# --- índice -----------------------------------------------------------------------------------
def test_sin_indice_es_aviso_sin_documentos_y_error_con_documentos(proyecto):
    proyecto("light")
    indice = reporte().chequeo("indice")
    assert indice.estado.value == "aviso" and indice.acciones == ("rag cargar <archivo|carpeta>", "rag indexar")
    cargar_manual()
    indice = reporte().chequeo("indice")
    assert indice.estado.value == "error" and "1 documento" in indice.mensaje
    assert indice.acciones == ("rag indexar",)


def test_indice_de_otro_stemmer_es_incompatible(proyecto):
    proyecto("light")
    cargar_manual()
    indexar(stemmer="english")
    indice = reporte().chequeo("indice")
    assert indice.estado.value == "error" and "stemmer 'english'" in indice.mensaje


def test_corpus_cambiado_es_error(proyecto):
    proyecto("light")
    cargar_manual()
    indexar()
    assert reporte().chequeo("indice").estado.value == "ok"
    modificar_documento()
    indice = reporte().chequeo("indice")
    assert indice.estado.value == "error" and "cambiaron" in indice.mensaje and indice.acciones == ("rag indexar",)


def test_con_huella_de_archivos_no_parsea_el_corpus_si_no_cambio(proyecto, monkeypatch):
    proyecto("light")
    cargar_manual()
    indexar(con_hash_archivos=True)
    llamadas = []
    import rag.ingesta.ingesta as ingesta

    original = ingesta.huella_corpus
    monkeypatch.setattr(ingesta, "huella_corpus", lambda *a: llamadas.append(1) or original(*a))
    assert reporte().chequeo("indice").estado.value == "ok" and llamadas == []
    modificar_documento()
    indice = reporte().chequeo("indice")
    assert indice.estado.value == "error" and "cambiaron" in indice.mensaje and llamadas == [1]


def test_manifiesto_sin_coleccion_qdrant_es_error(proyecto):
    proyecto("light")
    cargar_manual()
    indexar(coleccion_qdrant=False)
    indice = reporte().chequeo("indice")
    assert indice.estado.value == "error" and "no existe" in indice.mensaje and indice.acciones == ("rag indexar",)


# --- calibración ------------------------------------------------------------------------------
def test_calibracion_no_habilitada_y_obsoleta_son_avisos(proyecto):
    proyecto("light")
    huella = sano("light")
    calibracion("light", huella, estado="muestra_insuficiente")
    c = reporte().chequeo("calibracion")
    assert c.estado.value == "aviso" and "auditoría" in c.mensaje and "obsoleta" not in c.mensaje

    calibracion("medium", huella)
    c = reporte().chequeo("calibracion")
    assert c.estado.value == "aviso" and "obsoleta" in c.mensaje
    assert c.acciones == ("rag golden importar <archivo>", "rag calibrar --aplicar")  # no hay golden
    importar_golden()
    assert reporte().chequeo("calibracion").acciones == ("rag calibrar --aplicar",)
    assert Path("configuracion/calibracion.yaml").is_file()  # doctor no la toca


def test_calibracion_ilegible_es_error(proyecto):
    proyecto("light")
    sano("light")
    Path("configuracion/calibracion.yaml").write_text("estado: inventado\n", encoding="utf-8")
    c = reporte().chequeo("calibracion")
    assert c.estado.value == "error" and c.acciones


# --- golden -----------------------------------------------------------------------------------
def test_banco_de_regresion_es_ok_e_ilegible_es_aviso(proyecto):
    proyecto("light")
    cargar_manual()
    importar_golden()
    manifiesto = Path("golden/banco/manifiesto.json")
    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    manifiesto.write_text(json.dumps({**datos, "uso": "regresion"}), encoding="utf-8")
    golden = reporte().chequeo("golden")
    assert golden.estado.value == "ok" and "no para calibrar" in golden.mensaje

    manifiesto.write_text("{roto", encoding="utf-8")
    golden = reporte().chequeo("golden")
    assert golden.estado.value == "aviso" and "bloqueados" in golden.mensaje and golden.acciones


# --- CORS -------------------------------------------------------------------------------------
def test_cors_configurado_es_ok(proyecto):
    proyecto("light")
    editar("configuracion/asistente.yaml", cors_origenes=["https://mi-sitio.cl"], claves_widget=["k"])
    cors = reporte().chequeo("cors")
    assert cors.estado.value == "ok" and "https://mi-sitio.cl" in cors.mensaje


# --- CLI y efectos ------------------------------------------------------------------------------
def test_cli_resume_y_no_repite_acciones(proyecto, capsys):
    proyecto("medium")
    cargar_manual()
    editar("configuracion/asistente.yaml", claves_widget=["k"])
    capsys.readouterr()
    assert main(["doctor"]) == 1
    salida = capsys.readouterr().out
    assert "[ERROR]   Modelos" in salida and "[ERROR]   Índice" in salida and "[AVISO]   Golden" in salida
    assert "3 errores, 2 avisos. El proyecto no está listo." in salida
    resumen = salida.split("Acciones:\n")[1].splitlines()
    assert resumen[:3] == ["  rag modelos descargar", "  rag indexar", "  rag configurar cors_origenes=https://tu-sitio.cl"]
    assert resumen[3:] == []  # con Folio incluido, el avatar no pide acción


def test_cli_sano_sale_con_cero(proyecto, capsys):
    proyecto("light")
    sano("light")
    capsys.readouterr()
    assert main(["doctor"]) == 0
    assert "0 errores, 2 avisos. El proyecto puede funcionar." in capsys.readouterr().out


def test_doctor_no_usa_red_ni_onnx_ni_escribe(proyecto, monkeypatch):
    import sys

    proyecto("medium")
    sano("medium")
    antes = {p: p.stat().st_mtime_ns for p in Path.cwd().rglob("*") if p.is_file() and "qdrant" not in p.parts}
    for modulo in ("onnxruntime", "torch", "optimum"):
        monkeypatch.setitem(sys.modules, modulo, None)  # importarlos fallaría
    monkeypatch.setattr("rag.aplicacion.modelos.descargar_modelos", lambda *a, **k: pytest.fail("descargó"))
    monkeypatch.setattr("rag.aplicacion.corpus.indexar_proyecto", lambda *a, **k: pytest.fail("indexó"))
    assert reporte().listo
    despues = {p: p.stat().st_mtime_ns for p in Path.cwd().rglob("*") if p.is_file() and "qdrant" not in p.parts}
    assert despues == antes


# --- /ready (P12.11): el mismo diagnóstico, publicado por el servicio --------------------------
class _MotorListo:
    """Motor que arranca sin modelos: lo que importa aquí es el diagnóstico del proyecto."""

    politica_abstencion = None
    backend = "memoria"
    retriever = None
    control_admision = None

    def calentar(self):
        pass

    def cerrar(self):
        pass

    def n_chunks(self):
        return 2

    def inventario_entidades(self):
        return set()


def _ready():
    from fastapi.testclient import TestClient

    from rag.servicio.api import crear_app

    with TestClient(crear_app(_MotorListo())) as cliente:
        return cliente.get("/ready")


def test_ready_proyecto_sano(proyecto):
    proyecto("light")
    calibracion("light", sano("light"))
    r = _ready()
    assert r.status_code == 200, r.json()
    cuerpo = r.json()
    assert cuerpo["listo"] and cuerpo["proyecto"]["listo"] and cuerpo["proyecto"]["perfil"] == "light"
    assert cuerpo["proyecto"]["bloqueante"] == []
    assert cuerpo["proyecto"]["chequeos"]["indice"] == "ok" and cuerpo["proyecto"]["chequeos"]["calibracion"] == "ok"


def test_ready_indice_incompatible_no_esta_listo_y_dice_que_hacer(proyecto):
    proyecto("light")
    instalar(E5_SMALL)
    cargar_manual()
    indexar(stemmer="english")
    r = _ready()
    assert r.status_code == 503
    cuerpo = r.json()
    assert cuerpo["listo"] is False and cuerpo["proyecto"]["listo"] is False
    bloqueo = cuerpo["proyecto"]["bloqueante"][0]
    assert bloqueo["clave"] == "indice" and "incompatible" in bloqueo["mensaje"]
    assert bloqueo["acciones"] == ["rag indexar"]
    assert "indice: incompatible" in cuerpo["detail"]


def test_ready_sin_calibracion_esta_listo_con_aviso(proyecto):
    proyecto("light")
    sano("light")
    r = _ready()
    assert r.status_code == 200
    avisos = {a["clave"]: a for a in r.json()["proyecto"]["avisos"]}
    assert "opcional" in avisos["calibracion"]["mensaje"]


def test_ready_no_repite_el_diagnostico_en_cada_llamada(proyecto, monkeypatch):
    import rag.aplicacion.diagnostico as diagnostico
    from fastapi.testclient import TestClient

    from rag.servicio.api import crear_app

    proyecto("light")
    sano("light")
    llamadas = []
    original = diagnostico.diagnosticar
    monkeypatch.setattr(diagnostico, "diagnosticar", lambda **k: llamadas.append(k) or original(**k))
    with TestClient(crear_app(_MotorListo())) as cliente:
        for _ in range(5):
            cliente.get("/ready")
    assert llamadas == [{"abrir_indice": False}]  # una vez cada 30 s y sin abrir Qdrant


# --- rag desplegar preparar (P12.13): reúne el proyecto que diagnosticó el doctor ----------------
def test_desplegar_preparar_genera_todo(proyecto, capsys):
    import json as _json

    from apoyo import definicion_avatar
    from rag.aplicacion.personalidad import importar_avatar_desde

    proyecto("light")
    calibracion("light", sano("light"))
    importar_avatar_desde(_json.dumps(definicion_avatar()).encode(), "propio")
    Path(".rag/registros").mkdir(parents=True, exist_ok=True)
    Path(".rag/registros/consultas.jsonl").write_text("{}\n", encoding="utf-8")
    Path("mi.whl").write_bytes(b"x")
    Path("mi.whl").rename("rag_extractivo-0-py3-none-any.whl")
    capsys.readouterr()
    assert main(["desplegar", "preparar", "--dominio", "asistente.ejemplo.cl",
                 "--wheel", "rag_extractivo-0-py3-none-any.whl"]) == 0
    salida = capsys.readouterr().out
    assert "Despliegue preparado" in salida and "perfil light" in salida
    dist = Path("dist")
    for archivo in ("configuracion/asistente.yaml", "configuracion/personalidad.yaml", "configuracion/estilos.yaml",
                    "configuracion/calibracion.yaml", "configuracion/avatares/propio.avatar.json",
                    "documentos/catalogo.yaml", "Dockerfile", "docker-compose.yml", "Caddyfile", ".env.ejemplo",
                    "LEEME_despliegue.md", "paquete/rag_extractivo-0-py3-none-any.whl"):
        assert (dist / archivo).is_file(), archivo
    assert any((dist / ".rag/indice").rglob("*.manifiesto.json"))
    assert not (dist / ".rag/registros/consultas.jsonl").exists()  # los registros no viajan

    compose = yaml.safe_load((dist / "docker-compose.yml").read_text(encoding="utf-8"))
    assert compose["services"]["caddy"]["profiles"] == ["https"]
    ip_caddy = compose["services"]["caddy"]["networks"]["rag"]["ipv4_address"]
    assert compose["services"]["asistente"]["environment"]["RAG_PROXY_CONFIABLE"] == ip_caddy
    assert compose["services"]["asistente"]["build"]["args"]["PERFIL"] == "light"
    assert "RAG_ADMIN_TOKEN" not in compose["services"]["asistente"]["environment"]  # el secreto va en .env
    assert "asistente.ejemplo.cl {" in (dist / "Caddyfile").read_text(encoding="utf-8")
    leeme = (dist / "LEEME_despliegue.md").read_text(encoding="utf-8")
    assert leeme.startswith("# Despliegue de") and "https://asistente.ejemplo.cl/widget.js" in leeme
    assert "/admin/panel" in leeme and "{{" not in leeme
    assert "ARG PERFIL=light" in (dist / "Dockerfile").read_text(encoding="utf-8")
    for generado in ("Dockerfile", "docker-compose.yml", "Caddyfile", ".env.ejemplo", "LEEME_despliegue.md"):
        assert b"\r" not in (dist / generado).read_bytes(), generado  # LF también en Windows

    # Regenerar exige --forzar; una carpeta ajena nunca se borra.
    assert main(["desplegar", "preparar"]) == 1
    assert "--forzar" in capsys.readouterr().out
    assert main(["desplegar", "preparar", "--forzar"]) == 0
    assert "sin --dominio" in capsys.readouterr().out
    Path("ajena").mkdir()
    Path("ajena/importante.txt").write_text("no borrar", encoding="utf-8")
    assert main(["desplegar", "preparar", "--destino", "ajena", "--forzar"]) == 1
    assert Path("ajena/importante.txt").is_file()
    assert main(["desplegar", "preparar", "--destino", ".", "--forzar"]) == 1
    assert main(["desplegar", "preparar", "--destino", "otro", "--dominio", "https://x.cl"]) == 1


def test_desplegar_leeme_en_el_idioma_del_proyecto(proyecto, capsys):
    proyecto("light")
    editar("configuracion/asistente.yaml", idioma="pt-br")
    assert main(["desplegar", "preparar"]) == 0
    assert Path("dist/LEEME_despliegue.md").read_text(encoding="utf-8").startswith("# Implantação de")
    assert "Copie este arquivo" in Path("dist/.env.ejemplo").read_text(encoding="utf-8")


def test_ready_vencido_responde_sin_esperar_y_refresca_en_segundo_plano(proyecto, monkeypatch):
    import threading

    import rag.aplicacion.diagnostico as diagnostico
    import rag.servicio.api as api
    from fastapi.testclient import TestClient

    from rag.servicio.api import crear_app

    proyecto("light")
    sano("light")
    original = diagnostico.diagnosticar
    llamadas, liberar = [], threading.Event()

    def lento(**k):
        llamadas.append(k)
        if len(llamadas) > 1:
            liberar.wait(5)  # el refresco tarda; /ready no debe esperarlo
        return original(**k)

    monkeypatch.setattr(diagnostico, "diagnosticar", lento)
    app = crear_app(_MotorListo())
    with TestClient(app) as cliente:
        assert llamadas == [{"abrir_indice": False}]  # se calculó al arrancar
        servicio = app.state.servicio
        servicio.diagnostico = (servicio.diagnostico[0] - api._TTL_DIAGNOSTICO_S - 1, servicio.diagnostico[1])
        inicio = time.monotonic()
        assert cliente.get("/ready").status_code == 200
        assert time.monotonic() - inicio < 2  # devuelve el vigente sin esperar
        assert servicio.refrescando_diagnostico
        cliente.get("/ready")
        liberar.set()
        for _ in range(100):
            if not servicio.refrescando_diagnostico:
                break
            time.sleep(0.05)
        assert len(llamadas) == 2  # un solo refresco aunque llegaron dos /ready
