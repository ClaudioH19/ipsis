"""Diagnóstico del plugin instalado (``rag doctor``).

Cada chequeo es independiente y, si falla, dice **qué comando correr** para
arreglarlo -- es el comando que ahorra soporte a quien adopta el plugin en un
dominio nuevo, así que cada mensaje debe ser accionable, nunca solo "algo
falló". Ningún chequeo descarga nada ni escribe en disco: son de solo
lectura, para que ``rag doctor`` se pueda correr en cualquier momento sin
efectos secundarios.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResultadoChequeo:
    nombre: str
    ok: bool
    mensaje: str
    comando_sugerido: str | None = None


def verificar_config_dominio() -> ResultadoChequeo:
    """``configuracion/asistente.yaml`` es válido y ``configuracion/dominio.yaml``,
    si existe, se puede cargar."""
    from rag.configuracion.carga import cargar_dominio
    from rag.lenguaje.dominio import cargar_perfil

    try:
        cfg = cargar_dominio()
    except Exception as e:  # noqa: BLE001 -- se reporta, no se oculta
        return ResultadoChequeo("configuración de dominio", False, f"error leyendo configuracion/asistente.yaml: {e}",
                                 "rag init")

    try:
        perfil = cargar_perfil()
    except Exception as e:  # noqa: BLE001
        return ResultadoChequeo(
            "configuración de dominio", False,
            f"configuracion/dominio.yaml no se pudo cargar: {e}",
            "revisa la sintaxis de configuracion/dominio.yaml",
        )
    from rag.lenguaje.paquete import idiomas_disponibles

    if cfg.get("idioma", "es") not in idiomas_disponibles():
        return ResultadoChequeo(
            "configuración de dominio", False,
            f"no hay paquete para el idioma {cfg.get('idioma')!r} (disponibles: {idiomas_disponibles()})",
            "rag configurar idioma=es",
        )
    nota_idioma = ""
    return ResultadoChequeo(
        "configuración de dominio", True,
        f"reglas propias={len(perfil.reglas)}, idioma={cfg.get('idioma')!r}, "
        f"asistente={cfg.get('nombre_asistente')!r}{nota_idioma}",
    )


def verificar_config_recuperacion() -> ResultadoChequeo:
    """``configuracion/motor.yaml`` existe y trae la sección ``recuperacion:``
    que leen tanto la ingesta como el servicio."""
    from rag.configuracion.carga import cargar_proyecto, config_recuperacion

    try:
        cfg = cargar_proyecto()
    except FileNotFoundError:
        return ResultadoChequeo("configuración de recuperación", False, "no existe configuracion/motor.yaml",
                                 "rag init")
    try:
        config_recuperacion(cfg)
    except KeyError:
        return ResultadoChequeo(
            "configuración de recuperación", False,
            "configuracion/motor.yaml no trae la sección 'recuperacion:'",
            "revisa configuracion/motor.yaml a mano (no se genera automáticamente, ver README.md)",
        )
    return ResultadoChequeo("configuración de recuperación", True, "configuracion/motor.yaml::recuperacion presente")


def verificar_politica_abstencion() -> ResultadoChequeo:
    """La política configurada existe y acepta las opciones de abstención."""
    from rag.nucleo.registro import RegistroComponentes
    from rag.configuracion.carga import cargar_dominio, cargar_proyecto, config_abstencion
    from rag.configuracion.perfiles import perfil_efectivo
    from rag.aplicacion.registro_base import registrar_componentes_base

    try:
        cfg = cargar_proyecto()
        nombre = cfg["componentes"]["abstention_policy"]
        registro = registrar_componentes_base(RegistroComponentes())
        factory = registro.obtener("abstention_policy", nombre)
        retriever = cfg["componentes"]["retriever"]
        cfg_abs = config_abstencion(cfg, retriever=retriever)
        if cfg_abs is not None:
            perfil = perfil_efectivo(cargar_dominio().get("perfil", "light"), cfg.get("ajustes_perfil"))
            factory(configuracion=cfg_abs, umbrales=perfil.umbrales_por_defecto)
    except Exception as e:  # noqa: BLE001 -- diagnóstico accionable
        return ResultadoChequeo(
            "política de abstención",
            False,
            f"no se pudo resolver componentes.abstention_policy: {e}",
            "revisa componentes.abstention_policy y abstencion en configuracion/motor.yaml",
        )
    return ResultadoChequeo(
        "política de abstención",
        True,
        f"abstention_policy/{nombre} disponible y configurada",
    )


def verificar_modelo_descargado() -> ResultadoChequeo:
    """El modelo denso de ``recuperacion.modelo`` está en la caché de modelos.
    Solo lectura: nunca descarga nada."""
    from rag.configuracion.carga import cargar_proyecto, config_recuperacion
    from rag.modelos.catalogo import obtener
    from rag.modelos.descarga import esta_en_cache, ruta_cache

    try:
        modelo = config_recuperacion(cargar_proyecto())["modelo"]
        spec = obtener(modelo)
    except KeyError as e:
        return ResultadoChequeo("modelo de embeddings", False, str(e), "revisa recuperacion.modelo en configuracion/motor.yaml")
    except Exception as e:  # noqa: BLE001
        return ResultadoChequeo("modelo de embeddings", False, f"no se pudo leer la configuración: {e}", "rag init")
    if not esta_en_cache(spec):
        return ResultadoChequeo("modelo de embeddings", False,
                                 f"{modelo!r} no está en la caché de modelos ({ruta_cache()})",
                                 "rag modelos descargar")
    return ResultadoChequeo("modelo de embeddings", True, f"{modelo!r} está en la caché")


def verificar_indice() -> ResultadoChequeo:
    """El índice Qdrant de producción existe y corresponde al modelo
    configurado (mismo nombre de colección que arma
    ``rag/indice/qdrant.py::nombre_coleccion_versionada``) -- de paso confirma que
    Qdrant responde, porque no se puede comprobar lo primero sin lo segundo."""
    import os

    from rag.configuracion.carga import cargar_proyecto, config_recuperacion
    from rag.indice.qdrant import crear_cliente_qdrant, nombre_coleccion_versionada

    try:
        cfg = cargar_proyecto()
        cfg_rec = config_recuperacion(cfg)
    except Exception as e:  # noqa: BLE001
        return ResultadoChequeo("índice Qdrant", False, f"no se pudo leer la configuración: {e}", "rag init")

    backend = cfg["componentes"]["retriever"]
    if backend != "qdrant":
        return ResultadoChequeo(
            "índice de recuperación",
            False,
            f"retriever desconocido: {backend!r}",
            "revisa componentes.retriever en configuracion/motor.yaml",
        )

    modo = os.environ.get("QDRANT_MODO") or cfg.get("qdrant", {}).get("modo", "local")
    url_servidor = os.environ.get("QDRANT_URL") or cfg.get("qdrant", {}).get("url_servidor")

    try:
        client = crear_cliente_qdrant(qdrant_path=cfg_rec["qdrant_path"], modo=modo, url_servidor=url_servidor)
        nombre_col = nombre_coleccion_versionada(cfg_rec["coleccion_base"], cfg_rec["modelo"],
                                                  cfg_rec["version_coleccion"])
        existe = client.collection_exists(nombre_col)
    except Exception as e:  # noqa: BLE001
        if modo == "servidor":
            sugerencia = "revisa 'docker compose up -d qdrant' y 'curl http://localhost:6333/readyz'"
        elif "already accessed" in str(e):
            # Causa real y frecuente: en modo local Qdrant bloquea la carpeta
            # del índice, así que el servicio corriendo impide abrirla desde
            # otro proceso. Decirlo explícitamente ahorra buscar un problema
            # de permisos que no existe.
            sugerencia = ("detén el servicio ('rag servir') antes de indexar o diagnosticar: en modo "
                          "local Qdrant bloquea la carpeta del índice. Para usar ambos a la vez, "
                          "cambia a modo servidor ('docker compose up -d qdrant' y "
                          "qdrant.modo: \"servidor\" en configuracion/motor.yaml)")
        else:
            sugerencia = "revisa que la carpeta del índice local sea escribible"
        return ResultadoChequeo("índice Qdrant", False, f"Qdrant (modo {modo!r}) no respondió: {e}", sugerencia)

    if not existe:
        return ResultadoChequeo("índice Qdrant", False,
                                 f"la colección {nombre_col!r} no existe todavía (modo {modo!r})", "rag indexar")
    from rag.indice.manifiesto import ruta_manifiesto
    from rag.indice.qdrant import ruta_estadisticas

    if not ruta_estadisticas(nombre_col).is_file() or not ruta_manifiesto(nombre_col).is_file():
        return ResultadoChequeo("índice Qdrant", False,
                                 f"la colección {nombre_col!r} es de una versión anterior (sin estadísticas léxicas)",
                                 "rag indexar")
    return ResultadoChequeo("índice Qdrant", True, f"colección {nombre_col!r} existe (modo {modo!r})")


def verificar_textos_idioma() -> ResultadoChequeo:
    """El paquete de idioma, con las sobrescrituras de ``configuracion/idioma.yaml``,
    es válido: lo necesita cualquier petición (incluida la conversacional)."""
    from rag.configuracion.carga import cargar_dominio
    from rag.lenguaje.paquete import cargar_paquete

    try:
        idioma = cargar_dominio().get("idioma", "es")
        cargar_paquete(idioma, proyecto=Path.cwd())
    except Exception as e:  # noqa: BLE001
        return ResultadoChequeo(
            "textos del idioma", False,
            f"el paquete de idioma o configuracion/idioma.yaml no es válido: {e}",
            "revisa configuracion/idioma.yaml o bórralo para usar los textos por defecto",
        )
    return ResultadoChequeo("textos del idioma", True, f"paquete {idioma!r} válido")


def verificar_estilos() -> ResultadoChequeo:
    """``configuracion/estilos.yaml`` es el unico archivo que define como
    se ve el widget. Su ausencia NO rompe nada -- el widget trae sus
    valores de repuesto y ``/estilos.css`` devuelve una hoja vacia -- asi
    que esto no es una falla: es un aviso de que el asistente se esta
    mostrando con el diseno de fabrica, y donde se cambia."""
    ruta = Path("configuracion/estilos.yaml")
    if not ruta.exists():
        return ResultadoChequeo(
            "estilos del widget", True,
            "no existe configuracion/estilos.yaml -- el widget usa el diseno de fabrica",
            "rag init  # lo crea con todas las claves comentadas; no pisa el resto de tu configuracion",
        )
    try:
        from rag.aplicacion.estilos import cargar_estilos, render_css
        from rag.aplicacion.widget import validar_tema

        tema = cargar_estilos()
        validar_tema(tema)
        render_css(tema=tema)
    except Exception as e:  # YAML mal formado, sobre todo
        return ResultadoChequeo(
            "estilos del widget", False,
            f"configuracion/estilos.yaml no se pudo leer: {e}",
            "revisa la indentacion del YAML; mientras tanto el widget usa el diseno de fabrica",
        )
    return ResultadoChequeo("estilos del widget", True, "configuracion/estilos.yaml presente y valido")


def verificar_cors() -> ResultadoChequeo:
    """``configuracion/asistente.yaml::cors_origenes``: vacía
    por defecto a propósito (nunca ``"*"`` de fábrica, ver
    ``rag/configuracion/carga.py``). Solo se marca como FALLA -- algo accionable,
    no una advertencia genérica -- cuando la lista está vacía Y ya hay
    claves de widget configuradas: es la señal concreta de que alguien
    preparó el widget para un sitio real y se olvidó de abrirle CORS, así
    que el navegador bloqueará sus peticiones aunque la clave sea válida."""
    from rag.configuracion.carga import cargar_dominio

    cfg = cargar_dominio()
    origenes = cfg.get("cors_origenes") or []
    claves = cfg.get("claves_widget") or []
    if not origenes and claves:
        return ResultadoChequeo(
            "CORS", False,
            "cors_origenes está vacío pero hay claves_widget configuradas -- el navegador "
            "bloqueará las peticiones del widget desde tu sitio",
            "rag configurar cors_origenes=https://tu-sitio.cl",
        )
    if not origenes:
        return ResultadoChequeo(
            "CORS", True,
            "cors_origenes vacío (valor por defecto) -- agrega tu(s) origen(es) antes de "
            "embeber el widget en un sitio real ('rag configurar cors_origenes=https://tu-sitio.cl')",
        )
    return ResultadoChequeo("CORS", True, f"orígenes permitidos: {origenes}")


def verificar_golden_set() -> ResultadoChequeo:
    """No es un requisito para operar (a diferencia de los chequeos de
    arriba) -- informativo, para que ``rag evaluar`` no sea una sorpresa."""
    candidatos = ["golden/banco/manifiesto.json"]
    existentes = [c for c in candidatos if Path(c).exists()]
    if not existentes:
        return ResultadoChequeo("golden set", True, "no hay golden set todavía ('rag evaluar' lo dirá y no fallará)")
    return ResultadoChequeo("golden set", True, f"encontrado: {existentes[0]}")


def ejecutar_diagnostico() -> list[ResultadoChequeo]:
    """Todos los chequeos, en el orden en que conviene leerlos: configuración
    antes que índice, índice antes que el modelo (que es el más caro de
    verificar). Nunca lanza -- cada función atrapa sus propios errores."""
    return [
        verificar_config_dominio(),
        verificar_config_recuperacion(),
        verificar_politica_abstencion(),
        verificar_textos_idioma(),
        verificar_estilos(),
        verificar_cors(),
        verificar_indice(),
        verificar_modelo_descargado(),
        verificar_golden_set(),
    ]
