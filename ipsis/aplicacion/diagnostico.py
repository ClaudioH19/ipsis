"""Diagnóstico del proyecto (``ipsis doctor``).

Responde: ¿puede este proyecto funcionar ahora y, si no, qué comando hay que
ejecutar? Compone las reglas que ya existen (perfil e índice de P11.2, caché
de modelos de P11.3, banco golden, paquete de idioma) sin reimplementarlas.

Es de solo lectura y barato: no usa la red, no carga ONNX, no descarga, no
indexa, no calibra ni escribe nada. Para probar la inferencia de los modelos
está ``ipsis models verify``.

Cada chequeo da ``ok``, ``aviso`` (funciona, pero algo opcional falta o
merece atención), ``error`` (bloquea o invalida el funcionamiento; siempre
trae una acción) o ``no_evaluado`` (depende de un chequeo que falló). Un
chequeo nunca detiene a los demás. El reporte es estructurado para que lo
reutilice también el servicio (``/ready``).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ipsis.configuracion import rutas
from ipsis.recursos.mensajes import t


class Estado(str, Enum):
    OK = "ok"
    AVISO = "aviso"
    ERROR = "error"
    NO_EVALUADO = "no_evaluado"


@dataclass(frozen=True)
class ChequeoDoctor:
    clave: str  # identificador estable: configuracion, perfil, idioma, ...
    nombre: str
    estado: Estado
    mensaje: str
    acciones: tuple[str, ...] = ()
    detalles: tuple[str, ...] = ()
    datos: dict = field(default_factory=dict, compare=False)  # p. ej. modelos faltantes, estado del índice

    @property
    def bloqueante(self) -> bool:
        return self.estado is Estado.ERROR

    @property
    def ok(self) -> bool:
        """No bloquea (``ok``, ``aviso`` o ``no_evaluado``)."""
        return not self.bloqueante


@dataclass(frozen=True)
class ReporteDoctor:
    chequeos: tuple[ChequeoDoctor, ...]
    perfil: str | None = None

    def chequeo(self, clave: str) -> ChequeoDoctor:
        return next(c for c in self.chequeos if c.clave == clave)

    @property
    def errores(self) -> list[ChequeoDoctor]:
        return [c for c in self.chequeos if c.estado is Estado.ERROR]

    @property
    def avisos(self) -> list[ChequeoDoctor]:
        return [c for c in self.chequeos if c.estado is Estado.AVISO]

    @property
    def listo(self) -> bool:
        """Sin errores: puede servir consultas (los avisos no bloquean)."""
        return not self.errores

    @property
    def acciones(self) -> list[str]:
        """Acciones sin repetir, primero las de los errores."""
        vistas: list[str] = []
        for chequeo in self.errores + self.avisos:
            vistas.extend(a for a in chequeo.acciones if a not in vistas)
        return vistas


class ProyectoNoEncontrado(RuntimeError):
    """No hay ``config/assistant.yaml`` ni ``config/engine.yaml``."""


ORDEN = ("configuracion", "perfil", "idioma", "stemmer", "modelos", "indice", "calibracion", "golden", "cors",
         "personalidad", "modo")
_PERFIL_CAMBIAR = "ipsis profile set light|medium|heavy"


def _chequeo(clave: str, nivel: Estado, mensaje: str, acciones=(), detalles=(), **datos) -> ChequeoDoctor:
    return ChequeoDoctor(clave, t(f"check.name_{clave}"), nivel, mensaje, tuple(acciones), tuple(detalles), datos)


def _no_evaluado(clave: str, depende: str) -> ChequeoDoctor:
    return _chequeo(clave, Estado.NO_EVALUADO, t("check.not_evaluated", dependency=depende))


def _breve(error: Exception, archivo: str | None = None) -> str:
    """Error de YAML/Pydantic resumido en campo y problema; con ``archivo``, el campo
    lleva los nombres de ese archivo (los que el usuario escribe), no los internos."""
    from ipsis.configuracion.glosario import nombres_externos

    def campo(loc) -> str:
        ruta = ".".join(map(str, loc))
        return (nombres_externos(ruta, archivo) if archivo else ruta) or t("check.root")

    errores = getattr(error, "errors", None)
    if callable(errores):
        try:
            return "; ".join(f"{campo(e['loc'])}: {e['msg']}" for e in errores()[:3])
        except Exception:  # noqa: BLE001
            pass
    texto = str(error).strip()
    return texto.splitlines()[0] if texto else type(error).__name__


class _Contexto:
    """Lo que leen varios chequeos; ``None`` si no se pudo leer."""

    def __init__(self, abrir_indice: bool = True) -> None:
        self.abrir_indice = abrir_indice  # False en /ready: el servicio ya tiene Qdrant abierto
        self.dominio: dict | None = None
        self.motor: dict | None = None
        self.instalacion = None  # perfil efectivo (base + ajustes_perfil), sin calibración
        self.paquete = None
        self.indice = None  # EstadoIndice
        self._golden: tuple | None = None

    def golden(self) -> tuple[str, object | None, str | None]:
        """(estado, banco, motivo) del banco importado, leído una vez."""
        if self._golden is None:
            from ipsis.evaluacion.banco import cargar_banco

            manifiesto = Path(rutas.GOLDEN_MANIFIESTO)
            if not manifiesto.is_file():
                self._golden = ("sin_golden", None, None)
            else:
                try:
                    self._golden = ("vigente", cargar_banco(manifiesto), None)
                except FileNotFoundError as e:
                    self._golden = ("desactualizado", None,
                                    t("check.golden_missing_document", file=Path(e.filename or "").name))
                except ValueError as e:
                    if "hash del corpus" in str(e):
                        self._golden = ("desactualizado", None, t("check.golden_corpus_changed"))
                    else:
                        self._golden = ("ilegible", None, _breve(e))
                except Exception as e:  # noqa: BLE001
                    self._golden = ("ilegible", None, _breve(e))
        return self._golden


# --- chequeos ---------------------------------------------------------------------------
def _configuracion(ctx: _Contexto) -> ChequeoDoctor:
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto, config_recuperacion

    problemas: list[str] = []
    acciones: list[str] = []
    try:
        ctx.dominio = cargar_dominio()
    except Exception as e:  # noqa: BLE001
        problemas.append(f"{rutas.ASISTENTE}: {_breve(e, 'asistente')}")
        acciones.append(t("check.fix_assistant", path=rutas.ASISTENTE))
    if not Path(rutas.MOTOR).is_file():
        problemas.append(t("check.no_file", path=rutas.MOTOR))
        acciones.append(t("check.init_force"))
    else:
        try:
            motor = cargar_proyecto()
            config_recuperacion(motor, perfil="light")  # la sección recuperacion: existe
            ctx.motor = motor
        except Exception as e:  # noqa: BLE001
            problemas.append(f"{rutas.MOTOR}: {_breve(e, 'motor')}")
            acciones.append(t("check.fix_file", path=rutas.MOTOR))
    try:
        from ipsis.lenguaje.dominio import cargar_perfil

        cargar_perfil()
    except Exception as e:  # noqa: BLE001
        problemas.append(f"{rutas.DOMINIO}: {_breve(e, 'dominio')}")
        acciones.append(t("check.fix_domain", path=rutas.DOMINIO))
    if ctx.motor is not None:
        problema = _politica_abstencion(ctx.motor)
        if problema:
            problemas.append(problema)
            acciones.append(t("check.fix_policy", path=rutas.MOTOR))
    if Path(rutas.ESTILOS).is_file():
        try:
            from ipsis.aplicacion.estilos import cargar_estilos, render_css
            from ipsis.aplicacion.widget import validar_tema

            tema = cargar_estilos()
            validar_tema(tema)
            render_css(tema=tema)
        except Exception as e:  # noqa: BLE001
            problemas.append(f"{rutas.ESTILOS}: {_breve(e, 'estilos')}")
            acciones.append(t("check.fix_styles", path=rutas.ESTILOS))
    if problemas:
        return _chequeo("configuracion", Estado.ERROR, "; ".join(problemas), acciones)
    return _chequeo("configuracion", Estado.OK, t("check.config_ok"))


def _politica_abstencion(motor: dict) -> str | None:
    """Mismo chequeo que hacía doctor: la política existe y acepta los umbrales."""
    from ipsis.aplicacion.registro_base import registrar_componentes_base
    from ipsis.configuracion.perfiles import cargar_perfil_instalacion
    from ipsis.nucleo.registro import RegistroComponentes

    nombre = motor["componentes"]["abstention_policy"]
    try:
        fabrica = registrar_componentes_base(RegistroComponentes()).obtener("abstention_policy", nombre)
        fabrica(umbrales=cargar_perfil_instalacion("light").umbrales_por_defecto)
    except Exception as e:  # noqa: BLE001
        return t("check.policy_unavailable", path=rutas.MOTOR, name=nombre, error=_breve(e))
    return None


def _perfil(ctx: _Contexto) -> ChequeoDoctor:
    from ipsis.aplicacion.proyecto import PerfilInvalido, validar_perfil_instalable
    from ipsis.configuracion.perfiles import perfil_efectivo

    if ctx.dominio is None:
        return _no_evaluado("perfil", rutas.ASISTENTE)
    nombre = ctx.dominio.get("perfil", "light")
    try:
        validar_perfil_instalable(nombre)
    except PerfilInvalido as e:
        return _chequeo("perfil", Estado.ERROR, f"{nombre}: {e}", [_PERFIL_CAMBIAR], perfil=nombre)
    ajustes = (ctx.motor or {}).get("ajustes_perfil")
    try:
        ctx.instalacion = perfil_efectivo(nombre, ajustes, ruta_calibracion=None)
    except Exception as e:  # noqa: BLE001
        return _chequeo("perfil", Estado.ERROR,
                        t("check.invalid_overrides", profile=nombre, path=rutas.MOTOR, error=_breve(e, "perfil")),
                        [t("check.fix_overrides", path=rutas.MOTOR)], perfil=nombre)
    return _chequeo("perfil", Estado.OK, nombre, perfil=nombre)


def _idioma(ctx: _Contexto) -> ChequeoDoctor:
    from ipsis.lenguaje.paquete import IDIOMA_RESPALDO, cargar_paquete, idiomas_disponibles

    if ctx.dominio is None:
        return _no_evaluado("idioma", rutas.ASISTENTE)
    codigo = ctx.dominio.get("idioma", "es")
    try:
        ctx.paquete = cargar_paquete(codigo, proyecto=Path.cwd())
    except Exception as e:  # noqa: BLE001
        return _chequeo("idioma", Estado.ERROR,
                        t("check.language_invalid", code=codigo, path=rutas.IDIOMA, error=_breve(e)),
                        [t("check.fix_language", path=rutas.IDIOMA)], idioma=codigo)
    if ctx.paquete.respaldo:
        return _chequeo("idioma", Estado.AVISO,
                        t("check.language_fallback", code=codigo, available=", ".join(idiomas_disponibles()),
                          fallback=IDIOMA_RESPALDO, path=rutas.IDIOMA), idioma=codigo, respaldo=True)
    return _chequeo("idioma", Estado.OK, f"{codigo} ({ctx.paquete.nombre})", idioma=codigo, respaldo=False)


def _stemmer(ctx: _Contexto) -> ChequeoDoctor:
    if ctx.paquete is None:
        return _no_evaluado("stemmer", t("check.dep_language_pack"))
    nombre = ctx.paquete.stemmer
    if not nombre:
        return _chequeo("stemmer", Estado.OK, t("check.stemmer_none"), stemmer=None)
    import snowballstemmer

    from ipsis.lenguaje.texto import terminos

    disponibles = snowballstemmer.algorithms()
    origen = (rutas.IDIOMA if "stemmer" in _sobrescrituras_idioma()
              else t("check.stemmer_origin_pack", code=ctx.paquete.codigo))
    if nombre not in disponibles:
        return _chequeo("stemmer", Estado.ERROR, t("check.stemmer_unknown", name=nombre, origin=origen),
                        [t("check.fix_stemmer_values", path=rutas.IDIOMA, values=", ".join(sorted(disponibles)))],
                        stemmer=nombre)
    try:
        terminos("documentos de prueba", ctx.paquete)  # la misma conversión que indexación y consulta
    except Exception as e:  # noqa: BLE001
        return _chequeo("stemmer", Estado.ERROR, t("check.stemmer_failed", name=nombre, error=_breve(e)),
                        [t("check.fix_stemmer", path=rutas.IDIOMA)], stemmer=nombre)
    return _chequeo("stemmer", Estado.OK, nombre, stemmer=nombre)


def _sobrescrituras_idioma() -> dict:
    import yaml

    ruta = Path(rutas.IDIOMA)
    try:
        return (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}) if ruta.is_file() else {}
    except Exception:  # noqa: BLE001 -- ya lo reporta el chequeo de idioma
        return {}


def _modelos(ctx: _Contexto) -> ChequeoDoctor:
    from ipsis.aplicacion.modelos import estado_modelos

    if ctx.instalacion is None:
        return _no_evaluado("modelos", t("check.dep_profile"))
    estados = estado_modelos(ctx.instalacion)
    detalles = [t("check.model_available" if e.en_cache else "check.model_missing", role=t(f"models.role_{e.rol}"),
                  model=e.id_hf) for e in estados]
    faltan = [e.id_hf for e in estados if not e.en_cache]
    if faltan:
        return _chequeo("modelos", Estado.ERROR, t("check.models_missing", models=", ".join(faltan)),
                        ["ipsis models download"], detalles, faltantes=faltan)
    return _chequeo("modelos", Estado.OK, t("check.models_ok"), detalles=detalles, faltantes=[])


def _documentos_cargados() -> int:
    from ipsis.ingesta.catalogo import entradas_vigentes

    return len(entradas_vigentes(rutas.CATALOGO))


def _indice(ctx: _Contexto) -> ChequeoDoctor:
    from ipsis.aplicacion.proyecto import estado_indice
    from ipsis.configuracion.carga import config_recuperacion

    if ctx.instalacion is None or ctx.motor is None:
        return _no_evaluado("indice", t("check.dep_config_profile"))
    perfil = ctx.instalacion.perfil
    stemmer = ctx.paquete.stemmer if ctx.paquete is not None else None
    indice = ctx.indice = estado_indice(perfil, stemmer=stemmer)
    if indice.estado == "sin_indice":
        n = _documentos_cargados()
        if n:
            return _chequeo("indice", Estado.ERROR, t("check.index_missing_documents", n=n),
                            ["ipsis index"], estado="sin_indice")
        return _chequeo("indice", Estado.AVISO, t("check.index_missing"),
                        [t("check.load_action"), "ipsis index"], estado="sin_indice")
    if indice.estado == "incompatible":
        if indice.modelo_indice != indice.modelo_requerido:
            motivo = t("check.index_model", built=indice.modelo_indice, profile=perfil,
                       needed=indice.modelo_requerido)
        elif stemmer and indice.stemmer != stemmer:
            motivo = t("check.index_stemmer", built=indice.stemmer, needed=stemmer)
        else:
            motivo = t("check.index_manifest")
        return _chequeo("indice", Estado.ERROR, t("check.index_incompatible", reason=motivo), ["ipsis index"],
                        estado="incompatible")

    fisico = verificar_indice() if ctx.abrir_indice else None
    if fisico is not None and fisico.bloqueante:
        return _chequeo("indice", Estado.ERROR, fisico.mensaje, fisico.acciones, estado="incompatible")
    if _corpus_cambio(indice, config_recuperacion(ctx.motor, perfil=perfil)):
        return _chequeo("indice", Estado.ERROR, t("check.index_corpus_changed"),
                        ["ipsis index"], estado="corpus_cambiado")
    return _chequeo("indice", Estado.OK, t("check.index_ok", model=indice.modelo_indice, n=indice.n_chunks),
                    estado="compatible")


def _corpus_cambio(indice, cfg_rec: dict) -> bool:
    """Compara el corpus actual con el indexado. Si la huella de archivos coincide
    no hace falta parsear; si difiere o falta (manifiesto anterior), se recalcula
    el ``hash_corpus`` exacto, que es lo que decide."""
    from ipsis.ingesta.ingesta import huella_archivos, huella_corpus

    if indice.hash_archivos and huella_archivos(rutas.DOCUMENTOS, cfg_rec) == indice.hash_archivos:
        return False
    return huella_corpus(rutas.DOCUMENTOS, cfg_rec) != indice.hash_corpus


def _calibracion(ctx: _Contexto) -> ChequeoDoctor:
    from ipsis.aplicacion.proyecto import estado_calibracion
    from ipsis.configuracion.calibracion import leer_calibracion

    if ctx.instalacion is None or ctx.indice is None:
        return _no_evaluado("calibracion", t("check.dep_profile_index"))
    try:
        leer_calibracion(rutas.CALIBRACION)
    except Exception as e:  # noqa: BLE001 -- el motor tampoco podría leerla
        return _chequeo("calibracion", Estado.ERROR,
                        t("check.calibration_invalid", path=rutas.CALIBRACION, error=_breve(e, "calibracion")),
                        [t("check.calibration_rewrite"), t("check.calibration_delete", path=rutas.CALIBRACION)],
                        estado="ilegible")
    estado = estado_calibracion(ctx.instalacion, ctx.indice)
    if estado.estado == "sin_calibracion":
        return _chequeo("calibracion", Estado.AVISO, t("check.calibration_none"), estado="sin_calibracion")
    if estado.estado == "vigente":
        return _chequeo("calibracion", Estado.OK, t("check.calibration_current"), estado="vigente")
    if estado.estado == "no_habilitada":
        return _chequeo("calibracion", Estado.AVISO, t("check.calibration_audit", reason=estado.motivo),
                        estado="no_habilitada")
    golden, banco, _ = ctx.golden()
    calibrable = golden == "vigente" and banco.manifiesto.uso != "regresion"
    acciones = ["ipsis calibrate --apply"] if calibrable else [t("check.golden_import"), "ipsis calibrate --apply"]
    return _chequeo("calibracion", Estado.AVISO, t("check.calibration_stale", reason=estado.motivo),
                    acciones, estado="obsoleta")


def _golden(ctx: _Contexto) -> ChequeoDoctor:
    estado, banco, motivo = ctx.golden()
    if estado == "sin_golden":
        return _chequeo("golden", Estado.AVISO, t("check.golden_none"), estado=estado)
    if estado == "desactualizado":
        return _chequeo("golden", Estado.AVISO, t("check.golden_stale", reason=motivo),
                        ["ipsis golden validate", t("check.golden_import")], estado=estado)
    if estado == "ilegible":
        return _chequeo("golden", Estado.AVISO, t("check.golden_unreadable", reason=motivo),
                        [t("check.golden_import")], estado=estado)
    m = banco.manifiesto
    if m.uso == "regresion":
        return _chequeo("golden", Estado.OK, t("check.golden_regression", id=m.dataset_id, n=len(banco.casos)),
                        estado=estado)
    return _chequeo("golden", Estado.OK, t("check.golden_ok", id=m.dataset_id, n=len(banco.casos)), estado=estado)


def _cors(ctx: _Contexto) -> ChequeoDoctor:
    """``cors_origins`` vacío es el valor por defecto (nunca ``"*"`` de fábrica). Solo es
    error si ya hay claves de widget: alguien preparó el widget para un sitio real y el
    navegador bloqueará sus peticiones."""
    if ctx.dominio is None:
        return _no_evaluado("cors", rutas.ASISTENTE)
    origenes = ctx.dominio.get("cors_origenes") or []
    claves = ctx.dominio.get("claves_widget") or []
    if not origenes and claves:
        return _chequeo("cors", Estado.ERROR, t("check.cors_missing"), [t("check.cors_action")])
    if not origenes:
        return _chequeo("cors", Estado.OK, t("check.cors_local"))
    return _chequeo("cors", Estado.OK, t("check.cors_ok", origins=", ".join(origenes)))


def _personalidad(ctx: _Contexto) -> ChequeoDoctor:
    """Tono y avatar. Un ``personality.yaml`` o una plantilla propia inválidos impiden
    arrancar el motor (error); un avatar que falta o no carga deja el ícono (aviso)."""
    from ipsis.aplicacion.personalidad import resumen_personalidad, validar_personalidad

    if ctx.dominio is None:
        return _no_evaluado("personalidad", rutas.ASISTENTE)
    errores, avisos = validar_personalidad()
    if errores:
        return _chequeo("personalidad", Estado.ERROR, "; ".join(errores),
                        [t("check.fix_personality", path=rutas.PERSONALIDAD)])
    resumen = resumen_personalidad()
    mensaje = t("check.personality_ok", tone=resumen.tono, avatar=resumen.avatar.nombre, state=resumen.avatar.estado)
    if avisos:
        from ipsis.aplicacion.personalidad import prefijo_neutralidad

        if resumen.avatar.estado in ("falta", "invalido"):
            accion = t("check.avatar_import")
        elif all(a.startswith(prefijo_neutralidad()) for a in avisos):
            accion = t("check.review_templates", path=rutas.PERSONALIDAD)
        else:
            accion = t("check.avatar_events")
        return _chequeo("personalidad", Estado.AVISO,
                        t("check.personality_warnings", tone=resumen.tono, warnings="; ".join(avisos[:2])), [accion],
                        tono=resumen.tono, avatar=resumen.avatar.estado)
    return _chequeo("personalidad", Estado.OK, mensaje, tono=resumen.tono, avatar=resumen.avatar.estado)


def _modo(ctx: _Contexto) -> ChequeoDoctor:
    """Modo del servicio según las variables de entorno de esta terminal (IPSIS_MODE, IPSIS_ADMIN_TOKEN…)."""
    from ipsis.aplicacion.modo import modo_servicio

    try:
        modo = modo_servicio()
    except ValueError as e:
        return _chequeo("modo", Estado.ERROR, str(e), [t("check.mode_values")])
    if modo.problemas:
        return _chequeo("modo", Estado.ERROR, "; ".join(modo.problemas),
                        [t("check.token_action")], modo=modo.modo)
    if modo.desarrollo:
        return _chequeo("modo", Estado.AVISO, t("check.mode_development"), [t("check.mode_production_action")],
                        modo=modo.modo)
    admin = t("check.with_admin" if modo.admin_activo else "check.without_admin")
    if modo.admin_activo and not modo.proxy_confiable:
        return _chequeo("modo", Estado.AVISO, t("check.mode_no_proxy", admin=admin), [t("check.proxy_action")],
                        modo=modo.modo)
    return _chequeo("modo", Estado.OK, t("check.mode_production", admin=admin), modo=modo.modo)


CHEQUEOS: tuple[tuple[str, Callable[[_Contexto], ChequeoDoctor]], ...] = (
    ("configuracion", _configuracion), ("perfil", _perfil), ("idioma", _idioma), ("stemmer", _stemmer),
    ("modelos", _modelos), ("indice", _indice), ("calibracion", _calibracion), ("golden", _golden), ("cors", _cors),
    ("personalidad", _personalidad), ("modo", _modo),
)


def diagnosticar(*, abrir_indice: bool = True) -> ReporteDoctor:
    """Todos los chequeos, en ``ORDEN``. Lanza ``ProyectoNoEncontrado`` fuera de un proyecto.

    Con ``abrir_indice=False`` el índice se juzga solo por sus manifiestos (sin
    abrir Qdrant): lo usa ``/ready``, porque el servicio ya tiene la colección abierta.
    """
    if not Path(rutas.ASISTENTE).is_file() and not Path(rutas.MOTOR).is_file():
        raise ProyectoNoEncontrado(t("check.no_project"))
    ctx = _Contexto(abrir_indice)
    chequeos = []
    for clave, funcion in CHEQUEOS:
        try:
            chequeos.append(funcion(ctx))
        except Exception as e:  # noqa: BLE001 -- un chequeo roto no detiene a los demás
            chequeos.append(_chequeo(clave, Estado.ERROR, t("check.check_failed", error=_breve(e)),
                                     [t("check.check_failed_action")]))
    perfil = ctx.instalacion.perfil if ctx.instalacion is not None else None
    return ReporteDoctor(tuple(chequeos), perfil)


# Chequeo y estado como los publica /ready.
CLAVE_PUBLICA = {"configuracion": "configuration", "perfil": "profile", "idioma": "language", "stemmer": "stemmer",
                 "modelos": "models", "indice": "index", "calibracion": "calibration", "golden": "golden",
                 "cors": "cors", "personalidad": "personality", "modo": "mode"}
ESTADO_PUBLICO = {Estado.OK: "ok", Estado.AVISO: "warning", Estado.ERROR: "error", Estado.NO_EVALUADO: "not_evaluated"}


def resumen_para_servicio(reporte: ReporteDoctor) -> dict:
    """Lo que ``/ready`` publica: el estado de cada chequeo y, aparte, lo que
    bloquea (con su acción) y lo opcional. Sin ``detalles``: es un endpoint público."""
    def item(c: ChequeoDoctor) -> dict:
        return {"key": CLAVE_PUBLICA[c.clave], "message": c.mensaje, "actions": list(c.acciones)}

    return {
        "ready": reporte.listo,
        "profile": reporte.perfil,
        "checks": {CLAVE_PUBLICA[c.clave]: ESTADO_PUBLICO[c.estado] for c in reporte.chequeos},
        "blocking": [item(c) for c in reporte.errores],
        "warnings": [item(c) for c in reporte.avisos],
    }


def verificar_indice() -> ChequeoDoctor:
    """La colección Qdrant del perfil activo existe y trae sus estadísticas y manifiesto.

    Abre Qdrant (lo usa también ``ipsis serve <carpeta>`` para decidir si reindexar).
    """
    import os

    from ipsis.configuracion.carga import cargar_proyecto, config_recuperacion
    from ipsis.indice.qdrant import crear_cliente_qdrant, nombre_coleccion_versionada

    try:
        cfg = cargar_proyecto()
        cfg_rec = config_recuperacion(cfg)
    except Exception as e:  # noqa: BLE001
        return _chequeo("indice", Estado.ERROR, t("check.config_unreadable", error=_breve(e)), ["ipsis init"])

    backend = cfg["componentes"]["retriever"]
    if backend != "qdrant":
        return _chequeo("indice", Estado.ERROR, t("check.retriever_unknown", name=backend),
                        [t("check.review_retriever", path=rutas.MOTOR)])

    from ipsis.indice.qdrant import modo_del_entorno

    modo = modo_del_entorno() or cfg.get("qdrant", {}).get("modo", "local")
    url_servidor = os.environ.get("QDRANT_URL") or cfg.get("qdrant", {}).get("url_servidor")
    nombre_col = nombre_coleccion_versionada(cfg_rec["coleccion_base"], cfg_rec["modelo"],
                                             cfg_rec["version_coleccion"])
    try:
        cliente = crear_cliente_qdrant(qdrant_path=cfg_rec["qdrant_path"], modo=modo, url_servidor=url_servidor)
        try:
            existe = cliente.collection_exists(nombre_col)
        finally:
            cliente.close()  # libera el candado del modo local
    except Exception as e:  # noqa: BLE001
        if modo == "servidor":
            sugerencia = t("check.qdrant_server")
        elif "already accessed" in str(e):
            # En modo local Qdrant bloquea la carpeta del índice: el servicio
            # corriendo impide abrirla desde otro proceso.
            sugerencia = t("check.qdrant_locked")
        else:
            sugerencia = t("check.qdrant_readable")
        return _chequeo("indice", Estado.ERROR, t("check.qdrant_failed", mode=modo, error=_breve(e)), [sugerencia])

    if not existe:
        return _chequeo("indice", Estado.ERROR, t("check.collection_missing", name=nombre_col, mode=modo),
                        ["ipsis index"])
    from ipsis.indice.manifiesto import ruta_manifiesto
    from ipsis.indice.qdrant import ruta_estadisticas

    if not ruta_estadisticas(nombre_col).is_file() or not ruta_manifiesto(nombre_col).is_file():
        return _chequeo("indice", Estado.ERROR, t("check.collection_old", name=nombre_col), ["ipsis index"])
    return _chequeo("indice", Estado.OK, t("check.collection_ok", name=nombre_col, mode=modo))


__all__ = ["CHEQUEOS", "ChequeoDoctor", "Estado", "ORDEN", "ProyectoNoEncontrado", "ReporteDoctor",
           "diagnosticar", "resumen_para_servicio", "verificar_indice"]
