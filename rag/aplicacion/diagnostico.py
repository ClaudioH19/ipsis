"""Diagnóstico del proyecto (``rag doctor``).

Responde: ¿puede este proyecto funcionar ahora y, si no, qué comando hay que
ejecutar? Compone las reglas que ya existen (perfil e índice de P11.2, caché
de modelos de P11.3, banco golden, paquete de idioma) sin reimplementarlas.

Es de solo lectura y barato: no usa la red, no carga ONNX, no descarga, no
indexa, no calibra ni escribe nada. Para probar la inferencia de los modelos
está ``rag modelos verificar``.

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

from rag.configuracion import rutas


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
    """No hay ``configuracion/asistente.yaml`` ni ``configuracion/motor.yaml``."""


ORDEN = ("configuracion", "perfil", "idioma", "stemmer", "modelos", "indice", "calibracion", "golden", "cors")
NOMBRES = {
    "configuracion": "Configuración", "perfil": "Perfil", "idioma": "Idioma", "stemmer": "Stemmer",
    "modelos": "Modelos", "indice": "Índice", "calibracion": "Calibración", "golden": "Golden", "cors": "CORS",
}
_PERFIL_CAMBIAR = "rag perfil cambiar light|medium|heavy"
_GOLDEN_IMPORTAR = "rag golden importar <archivo>"


def _chequeo(clave: str, nivel: Estado, mensaje: str, acciones=(), detalles=(), **datos) -> ChequeoDoctor:
    return ChequeoDoctor(clave, NOMBRES[clave], nivel, mensaje, tuple(acciones), tuple(detalles), datos)


def _no_evaluado(clave: str, depende: str) -> ChequeoDoctor:
    return _chequeo(clave, Estado.NO_EVALUADO, f"no se evaluó: depende de {depende}")


def _breve(error: Exception) -> str:
    """Error de YAML/Pydantic resumido en campo y problema."""
    errores = getattr(error, "errors", None)
    if callable(errores):
        try:
            return "; ".join(f"{'.'.join(map(str, e['loc'])) or '(raíz)'}: {e['msg']}" for e in errores()[:3])
        except Exception:  # noqa: BLE001
            pass
    texto = str(error).strip()
    return texto.splitlines()[0] if texto else type(error).__name__


class _Contexto:
    """Lo que leen varios chequeos; ``None`` si no se pudo leer."""

    def __init__(self) -> None:
        self.dominio: dict | None = None
        self.motor: dict | None = None
        self.instalacion = None  # perfil efectivo (base + ajustes_perfil), sin calibración
        self.paquete = None
        self.indice = None  # EstadoIndice
        self._golden: tuple | None = None

    def golden(self) -> tuple[str, object | None, str | None]:
        """(estado, banco, motivo) del banco importado, leído una vez."""
        if self._golden is None:
            from rag.evaluacion.banco import cargar_banco

            manifiesto = Path(rutas.GOLDEN_MANIFIESTO)
            if not manifiesto.is_file():
                self._golden = ("sin_golden", None, None)
            else:
                try:
                    self._golden = ("vigente", cargar_banco(manifiesto), None)
                except FileNotFoundError as e:
                    self._golden = ("desactualizado", None,
                                    f"falta un documento del banco en el corpus ({Path(e.filename or '').name})")
                except ValueError as e:
                    if "hash del corpus" in str(e):
                        self._golden = ("desactualizado", None, "el corpus cambió desde que se importó")
                    else:
                        self._golden = ("ilegible", None, _breve(e))
                except Exception as e:  # noqa: BLE001
                    self._golden = ("ilegible", None, _breve(e))
        return self._golden


# --- chequeos ---------------------------------------------------------------------------
def _configuracion(ctx: _Contexto) -> ChequeoDoctor:
    from rag.configuracion.carga import cargar_dominio, cargar_proyecto, config_recuperacion

    problemas: list[str] = []
    acciones: list[str] = []
    try:
        ctx.dominio = cargar_dominio()
    except Exception as e:  # noqa: BLE001
        problemas.append(f"{rutas.ASISTENTE}: {_breve(e)}")
        acciones.append(f"corrige {rutas.ASISTENTE} (o 'rag init --force' para reiniciarlo)")
    if not Path(rutas.MOTOR).is_file():
        problemas.append(f"no existe {rutas.MOTOR}")
        acciones.append("rag init --force (crea motor.yaml; reinicia asistente.yaml con valores por defecto)")
    else:
        try:
            motor = cargar_proyecto()
            config_recuperacion(motor, perfil="light")  # la sección recuperacion: existe
            ctx.motor = motor
        except Exception as e:  # noqa: BLE001
            problemas.append(f"{rutas.MOTOR}: {_breve(e)}")
            acciones.append(f"corrige {rutas.MOTOR}")
    try:
        from rag.lenguaje.dominio import cargar_perfil

        cargar_perfil()
    except Exception as e:  # noqa: BLE001
        problemas.append(f"{rutas.DOMINIO}: {_breve(e)}")
        acciones.append(f"corrige {rutas.DOMINIO} (es opcional: también puedes borrarlo)")
    if ctx.motor is not None:
        problema = _politica_abstencion(ctx.motor)
        if problema:
            problemas.append(problema)
            acciones.append(f"corrige componentes.abstention_policy en {rutas.MOTOR}")
    if Path(rutas.ESTILOS).is_file():
        try:
            from rag.aplicacion.estilos import cargar_estilos, render_css
            from rag.aplicacion.widget import validar_tema

            tema = cargar_estilos()
            validar_tema(tema)
            render_css(tema=tema)
        except Exception as e:  # noqa: BLE001
            problemas.append(f"{rutas.ESTILOS}: {_breve(e)}")
            acciones.append(f"corrige {rutas.ESTILOS} (mientras tanto el widget usa el diseño de fábrica)")
    if problemas:
        return _chequeo("configuracion", Estado.ERROR, "; ".join(problemas), acciones)
    return _chequeo("configuracion", Estado.OK, "asistente.yaml y motor.yaml válidos")


def _politica_abstencion(motor: dict) -> str | None:
    """Mismo chequeo que hacía doctor: la política existe y acepta los umbrales."""
    from rag.aplicacion.registro_base import registrar_componentes_base
    from rag.configuracion.perfiles import cargar_perfil_instalacion
    from rag.nucleo.registro import RegistroComponentes

    nombre = motor["componentes"]["abstention_policy"]
    try:
        fabrica = registrar_componentes_base(RegistroComponentes()).obtener("abstention_policy", nombre)
        fabrica(umbrales=cargar_perfil_instalacion("light").umbrales_por_defecto)
    except Exception as e:  # noqa: BLE001
        return f"{rutas.MOTOR}: política de abstención {nombre!r} no disponible: {_breve(e)}"
    return None


def _perfil(ctx: _Contexto) -> ChequeoDoctor:
    from rag.aplicacion.proyecto import PerfilInvalido, validar_perfil_instalable
    from rag.configuracion.perfiles import perfil_efectivo

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
                        f"{nombre}: los ajustes_perfil de {rutas.MOTOR} no son válidos: {_breve(e)}",
                        [f"corrige ajustes_perfil en {rutas.MOTOR}"], perfil=nombre)
    return _chequeo("perfil", Estado.OK, nombre, perfil=nombre)


def _idioma(ctx: _Contexto) -> ChequeoDoctor:
    from rag.lenguaje.paquete import cargar_paquete, idiomas_disponibles

    if ctx.dominio is None:
        return _no_evaluado("idioma", rutas.ASISTENTE)
    codigo = ctx.dominio.get("idioma", "es")
    disponibles = idiomas_disponibles()
    if codigo not in disponibles:
        # El plan prevé un respaldo (reglas universales y textos en inglés), pero
        # el código no lo implementa: con este idioma el motor no arranca.
        return _chequeo("idioma", Estado.ERROR,
                        f"{codigo}: no hay paquete de idioma (disponibles: {', '.join(disponibles)}); "
                        "el motor no puede arrancar sin uno",
                        [f"rag configurar idioma=<{'|'.join(disponibles)}>"], idioma=codigo)
    try:
        ctx.paquete = cargar_paquete(codigo, proyecto=Path.cwd())
    except Exception as e:  # noqa: BLE001
        return _chequeo("idioma", Estado.ERROR,
                        f"{codigo}: el paquete con las sobrescrituras de {rutas.IDIOMA} no es válido: {_breve(e)}",
                        [f"corrige {rutas.IDIOMA} o bórralo para usar los textos del paquete"], idioma=codigo)
    return _chequeo("idioma", Estado.OK, f"{codigo} ({ctx.paquete.nombre})", idioma=codigo)


def _stemmer(ctx: _Contexto) -> ChequeoDoctor:
    if ctx.paquete is None:
        return _no_evaluado("stemmer", "el paquete de idioma")
    nombre = ctx.paquete.stemmer
    if not nombre:
        return _chequeo("stemmer", Estado.OK, "no configurado para este idioma (términos sin stem)", stemmer=None)
    import snowballstemmer

    from rag.lenguaje.texto import terminos

    disponibles = snowballstemmer.algorithms()
    origen = rutas.IDIOMA if "stemmer" in _sobrescrituras_idioma() else f"el paquete {ctx.paquete.codigo}"
    if nombre not in disponibles:
        return _chequeo("stemmer", Estado.ERROR,
                        f"{nombre!r} no existe en snowballstemmer (declarado en {origen})",
                        [f"corrige 'stemmer' en {rutas.IDIOMA} (valores válidos: {', '.join(sorted(disponibles))})"],
                        stemmer=nombre)
    try:
        terminos("documentos de prueba", ctx.paquete)  # la misma conversión que indexación y consulta
    except Exception as e:  # noqa: BLE001
        return _chequeo("stemmer", Estado.ERROR, f"{nombre}: no se pudo instanciar: {_breve(e)}",
                        [f"corrige 'stemmer' en {rutas.IDIOMA}"], stemmer=nombre)
    return _chequeo("stemmer", Estado.OK, nombre, stemmer=nombre)


def _sobrescrituras_idioma() -> dict:
    import yaml

    ruta = Path(rutas.IDIOMA)
    try:
        return (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}) if ruta.is_file() else {}
    except Exception:  # noqa: BLE001 -- ya lo reporta el chequeo de idioma
        return {}


def _modelos(ctx: _Contexto) -> ChequeoDoctor:
    from rag.aplicacion.modelos import estado_modelos

    if ctx.instalacion is None:
        return _no_evaluado("modelos", "el perfil")
    estados = estado_modelos(ctx.instalacion)
    detalles = [f"{e.rol}: {e.id_hf} -- {'disponible' if e.en_cache else 'falta'}" for e in estados]
    faltan = [e.id_hf for e in estados if not e.en_cache]
    if faltan:
        return _chequeo("modelos", Estado.ERROR, f"faltan en la caché: {', '.join(faltan)}",
                        ["rag modelos descargar"], detalles, faltantes=faltan)
    return _chequeo("modelos", Estado.OK,
                    "en la caché (no se cargaron; para probar la inferencia: rag modelos verificar)",
                    detalles=detalles, faltantes=[])


def _documentos_cargados() -> int:
    from rag.ingesta.catalogo import cargar_catalogo

    return len(cargar_catalogo(rutas.CATALOGO)) if Path(rutas.CATALOGO).is_file() else 0


def _indice(ctx: _Contexto) -> ChequeoDoctor:
    from rag.aplicacion.proyecto import estado_indice
    from rag.configuracion.carga import config_recuperacion

    if ctx.instalacion is None or ctx.motor is None:
        return _no_evaluado("indice", "la configuración y el perfil")
    perfil = ctx.instalacion.perfil
    stemmer = ctx.paquete.stemmer if ctx.paquete is not None else None
    indice = ctx.indice = estado_indice(perfil, stemmer=stemmer)
    if indice.estado == "sin_indice":
        n = _documentos_cargados()
        if n:
            return _chequeo("indice", Estado.ERROR,
                            f"todavía no existe y hay {n} documento(s) cargado(s) sin indexar",
                            ["rag indexar"], estado="sin_indice")
        return _chequeo("indice", Estado.AVISO, "todavía no existe (no hay documentos cargados)",
                        ["rag cargar <archivo|carpeta>", "rag indexar"], estado="sin_indice")
    if indice.estado == "incompatible":
        if indice.modelo_indice != indice.modelo_requerido:
            motivo = f"se construyó con {indice.modelo_indice} y el perfil {perfil} necesita {indice.modelo_requerido}"
        elif stemmer and indice.stemmer != stemmer:
            motivo = f"se construyó con el stemmer {indice.stemmer!r} y el idioma usa {stemmer!r}"
        else:
            motivo = "su manifiesto (versión de payload o dimensión) no corresponde a esta versión"
        return _chequeo("indice", Estado.ERROR, f"incompatible: {motivo}", ["rag indexar"], estado="incompatible")

    fisico = verificar_indice()
    if fisico.bloqueante:
        return _chequeo("indice", Estado.ERROR, fisico.mensaje, fisico.acciones, estado="incompatible")
    from rag.ingesta.ingesta import huella_corpus

    actual = huella_corpus(rutas.DOCUMENTOS, config_recuperacion(ctx.motor, perfil=perfil))
    if actual != indice.hash_corpus:
        return _chequeo("indice", Estado.ERROR, "los documentos cambiaron desde la última indexación",
                        ["rag indexar"], estado="corpus_cambiado")
    return _chequeo("indice", Estado.OK,
                    f"compatible ({indice.modelo_indice}, {indice.n_chunks} fragmentos, corpus sin cambios)",
                    estado="compatible")


def _calibracion(ctx: _Contexto) -> ChequeoDoctor:
    from rag.aplicacion.proyecto import estado_calibracion
    from rag.configuracion.calibracion import leer_calibracion

    if ctx.instalacion is None or ctx.indice is None:
        return _no_evaluado("calibracion", "el perfil y el índice")
    try:
        leer_calibracion(rutas.CALIBRACION)
    except Exception as e:  # noqa: BLE001 -- el motor tampoco podría leerla
        return _chequeo("calibracion", Estado.ERROR,
                        f"{rutas.CALIBRACION} no es válido ({_breve(e)}); el motor no puede arrancar",
                        ["rag calibrar --aplicar (la reescribe)", f"o borra {rutas.CALIBRACION}"], estado="ilegible")
    estado = estado_calibracion(ctx.instalacion, ctx.indice)
    if estado.estado == "sin_calibracion":
        return _chequeo("calibracion", Estado.AVISO, "no hay (opcional); se usan los umbrales del perfil",
                        estado="sin_calibracion")
    if estado.estado == "vigente":
        return _chequeo("calibracion", Estado.OK, "vigente: sus umbrales están activos", estado="vigente")
    if estado.estado == "no_habilitada":
        return _chequeo("calibracion", Estado.AVISO,
                        f"guardada solo para auditoría ({estado.motivo})", estado="no_habilitada")
    golden, banco, _ = ctx.golden()
    calibrable = golden == "vigente" and banco.manifiesto.uso != "regresion"
    acciones = ["rag calibrar --aplicar"] if calibrable else [_GOLDEN_IMPORTAR, "rag calibrar --aplicar"]
    return _chequeo("calibracion", Estado.AVISO,
                    f"obsoleta ({estado.motivo}); rigen los umbrales del perfil y el archivo se conserva",
                    acciones, estado="obsoleta")


def _golden(ctx: _Contexto) -> ChequeoDoctor:
    estado, banco, motivo = ctx.golden()
    if estado == "sin_golden":
        return _chequeo("golden", Estado.AVISO, "no hay (opcional)", estado=estado)
    if estado == "desactualizado":
        return _chequeo("golden", Estado.AVISO,
                        f"{motivo}: no lo uses para evaluar ni calibrar hasta actualizarlo",
                        ["rag golden validar", _GOLDEN_IMPORTAR], estado=estado)
    if estado == "ilegible":
        return _chequeo("golden", Estado.AVISO,
                        f"el banco importado no se puede leer ({motivo}); evaluar y calibrar quedan bloqueados",
                        [_GOLDEN_IMPORTAR], estado=estado)
    m = banco.manifiesto
    if m.uso == "regresion":
        return _chequeo("golden", Estado.OK,
                        f"banco de regresión {m.dataset_id} ({len(banco.casos)} casos): sirve para evaluar, "
                        "no para calibrar", estado=estado)
    return _chequeo("golden", Estado.OK, f"{m.dataset_id} ({len(banco.casos)} casos), vigente con el corpus actual",
                    estado=estado)


def _cors(ctx: _Contexto) -> ChequeoDoctor:
    """``cors_origenes`` vacío es el valor por defecto (nunca ``"*"`` de fábrica). Solo es
    error si ya hay claves de widget: alguien preparó el widget para un sitio real y el
    navegador bloqueará sus peticiones."""
    if ctx.dominio is None:
        return _no_evaluado("cors", rutas.ASISTENTE)
    origenes = ctx.dominio.get("cors_origenes") or []
    claves = ctx.dominio.get("claves_widget") or []
    if not origenes and claves:
        return _chequeo("cors", Estado.ERROR,
                        "cors_origenes está vacío pero hay claves_widget configuradas: el navegador "
                        "bloqueará las peticiones del widget desde tu sitio",
                        ["rag configurar cors_origenes=https://tu-sitio.cl"])
    if not origenes:
        return _chequeo("cors", Estado.OK, "sin orígenes (uso local); agrégalos antes de embeber el widget")
    return _chequeo("cors", Estado.OK, f"orígenes permitidos: {', '.join(origenes)}")


CHEQUEOS: tuple[tuple[str, Callable[[_Contexto], ChequeoDoctor]], ...] = (
    ("configuracion", _configuracion), ("perfil", _perfil), ("idioma", _idioma), ("stemmer", _stemmer),
    ("modelos", _modelos), ("indice", _indice), ("calibracion", _calibracion), ("golden", _golden), ("cors", _cors),
)


def diagnosticar() -> ReporteDoctor:
    """Todos los chequeos, en ``ORDEN``. Lanza ``ProyectoNoEncontrado`` fuera de un proyecto."""
    if not Path(rutas.ASISTENTE).is_file() and not Path(rutas.MOTOR).is_file():
        raise ProyectoNoEncontrado("no se encontró un proyecto RAG en esta carpeta")
    ctx = _Contexto()
    chequeos = []
    for clave, funcion in CHEQUEOS:
        try:
            chequeos.append(funcion(ctx))
        except Exception as e:  # noqa: BLE001 -- un chequeo roto no detiene a los demás
            chequeos.append(_chequeo(clave, Estado.ERROR, f"el chequeo falló: {_breve(e)}",
                                     ["revisa los archivos de configuracion/ y vuelve a ejecutar 'rag doctor'"]))
    perfil = ctx.instalacion.perfil if ctx.instalacion is not None else None
    return ReporteDoctor(tuple(chequeos), perfil)


def verificar_indice() -> ChequeoDoctor:
    """La colección Qdrant del perfil activo existe y trae sus estadísticas y manifiesto.

    Abre Qdrant (lo usa también ``rag servir <carpeta>`` para decidir si reindexar).
    """
    import os

    from rag.configuracion.carga import cargar_proyecto, config_recuperacion
    from rag.indice.qdrant import crear_cliente_qdrant, nombre_coleccion_versionada

    try:
        cfg = cargar_proyecto()
        cfg_rec = config_recuperacion(cfg)
    except Exception as e:  # noqa: BLE001
        return _chequeo("indice", Estado.ERROR, f"no se pudo leer la configuración: {_breve(e)}", ["rag init"])

    backend = cfg["componentes"]["retriever"]
    if backend != "qdrant":
        return _chequeo("indice", Estado.ERROR, f"retriever desconocido: {backend!r}",
                        [f"revisa componentes.retriever en {rutas.MOTOR}"])

    modo = os.environ.get("QDRANT_MODO") or cfg.get("qdrant", {}).get("modo", "local")
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
            sugerencia = "revisa 'docker compose up -d qdrant' y 'curl http://localhost:6333/readyz'"
        elif "already accessed" in str(e):
            # En modo local Qdrant bloquea la carpeta del índice: el servicio
            # corriendo impide abrirla desde otro proceso.
            sugerencia = ("detén el servicio ('rag servir') antes de diagnosticar: en modo local Qdrant "
                          "bloquea la carpeta del índice (o usa qdrant.modo: \"servidor\")")
        else:
            sugerencia = "revisa que la carpeta del índice local sea legible"
        return _chequeo("indice", Estado.ERROR, f"Qdrant (modo {modo!r}) no respondió: {_breve(e)}", [sugerencia])

    if not existe:
        return _chequeo("indice", Estado.ERROR, f"la colección {nombre_col!r} no existe (modo {modo!r})",
                        ["rag indexar"])
    from rag.indice.manifiesto import ruta_manifiesto
    from rag.indice.qdrant import ruta_estadisticas

    if not ruta_estadisticas(nombre_col).is_file() or not ruta_manifiesto(nombre_col).is_file():
        return _chequeo("indice", Estado.ERROR,
                        f"la colección {nombre_col!r} es de una versión anterior (sin estadísticas léxicas)",
                        ["rag indexar"])
    return _chequeo("indice", Estado.OK, f"colección {nombre_col!r} existe (modo {modo!r})")


__all__ = ["CHEQUEOS", "ChequeoDoctor", "Estado", "ORDEN", "ProyectoNoEncontrado", "ReporteDoctor",
           "diagnosticar", "verificar_indice"]
