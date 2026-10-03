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
    """``configuracion/asistente.yaml`` existe (o cae a los valores por defecto), su
    ``perfil`` existe en ``dominios/`` y su ``idioma`` tiene recurso en
    ``configuracion/dominios/idiomas/``."""
    from rag.configuracion import cargar_dominio
    from rag.dominio import RUTA_DOMINIOS, _perfiles_disponibles

    try:
        cfg = cargar_dominio()
    except Exception as e:  # noqa: BLE001 -- se reporta, no se oculta
        return ResultadoChequeo("configuración de dominio", False, f"error leyendo configuracion/asistente.yaml: {e}",
                                 "rag init")

    disponibles = _perfiles_disponibles(RUTA_DOMINIOS)
    if cfg["perfil"] not in disponibles:
        return ResultadoChequeo(
            "configuración de dominio", False,
            f"el perfil {cfg['perfil']!r} no existe en {RUTA_DOMINIOS}/ (disponibles: {disponibles or '(ninguno)'})",
            "rag configurar perfil=_generico",
        )
    # El recurso de idioma (configuracion/dominios/idiomas/<idioma>.yaml) es OPCIONAL por
    # diseño: `rag/texto_util.py::cargar_palabras_generales` ya tolera que no
    # exista (el chequeo de grounding léxico queda más permisivo, no roto) --
    # así que su ausencia es informativa, nunca una falla que bloquee
    # 'rag doctor'. Para idioma='es' (el default), 'rag init' ya lo escribe
    # desde una plantilla embebida; para otros idiomas puede no haber un
    # recurso curado todavía, y eso es esperable, no un error.
    recurso_idioma = Path("configuracion/dominios/idiomas") / f"{cfg.get('idioma', 'es')}.yaml"
    nota_idioma = "" if recurso_idioma.exists() else f" (sin recurso de idioma en {recurso_idioma}, opcional)"
    return ResultadoChequeo(
        "configuración de dominio", True,
        f"perfil={cfg['perfil']!r}, idioma={cfg.get('idioma')!r}, "
        f"asistente={cfg.get('nombre_asistente')!r}{nota_idioma}",
    )


def verificar_config_recuperacion() -> ResultadoChequeo:
    """``configuracion/motor.yaml`` existe y trae la sección ``recuperacion:``
    que leen tanto la ingesta como el servicio."""
    from rag.configuracion import cargar_proyecto, config_recuperacion

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
    from rag.configuracion import cargar_proyecto, config_abstencion
    from rag.aplicacion.registro_base import registrar_componentes_base

    try:
        cfg = cargar_proyecto()
        nombre = cfg["componentes"]["abstention_policy"]
        registro = registrar_componentes_base(RegistroComponentes())
        factory = registro.obtener("abstention_policy", nombre)
        retriever = cfg["componentes"]["retriever"]
        cfg_abs = config_abstencion(cfg, retriever=retriever)
        if cfg_abs is not None:
            factory(configuracion=cfg_abs)
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
    """El modelo de embeddings de ``recuperacion.modelo`` está en la caché
    local de HuggingFace -- chequeo de solo lectura, nunca descarga nada."""
    from rag.configuracion import cargar_proyecto, config_recuperacion

    try:
        cfg = cargar_proyecto()
        cfg_rec = config_recuperacion(cfg)
    except Exception as e:  # noqa: BLE001
        return ResultadoChequeo("modelo de embeddings", False, f"no se pudo leer la configuración: {e}", "rag init")

    modelo = cfg_rec["modelo"]
    try:
        from huggingface_hub import scan_cache_dir
        cache = scan_cache_dir()
        repos = {r.repo_id for r in cache.repos}
    except Exception as e:  # noqa: BLE001 -- caché inaccesible no debe tumbar el doctor
        return ResultadoChequeo("modelo de embeddings", False,
                                 f"no se pudo inspeccionar la caché local de HuggingFace: {e}", None)

    if modelo not in repos:
        return ResultadoChequeo(
            "modelo de embeddings", False, f"{modelo!r} no está en la caché local de HuggingFace",
            f'python -c "from sentence_transformers import SentenceTransformer as S; S({modelo!r})"  '
            f"(descarga ~500MB, requiere red la primera vez)",
        )
    return ResultadoChequeo("modelo de embeddings", True, f"{modelo!r} ya está descargado")


def verificar_indice() -> ResultadoChequeo:
    """El índice Qdrant de producción existe y corresponde al modelo
    configurado (mismo nombre de colección que arma
    ``rag/corpus.py::nombre_coleccion_versionada``) -- de paso confirma que
    Qdrant responde, porque no se puede comprobar lo primero sin lo segundo."""
    import os

    from rag.configuracion import cargar_proyecto, config_recuperacion
    from rag.corpus import crear_cliente_qdrant, nombre_coleccion_versionada

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
    return ResultadoChequeo("índice Qdrant", True, f"colección {nombre_col!r} existe (modo {modo!r})")


def verificar_plantillas() -> ResultadoChequeo:
    """``configuracion/textos.yaml`` existe -- lo necesita CUALQUIER petición a
    ``/consultar`` (incluida la detección "conversacional", que corre antes
    que nada más). Sin este archivo el servicio responde 500 en la primera
    pregunta en vez de un diagnóstico claro -- defecto real encontrado
    validando que el servicio pueda responder antes de levantarlo."""
    ruta = Path("configuracion/textos.yaml")
    if not ruta.exists():
        return ResultadoChequeo(
            "plantillas de respuesta", False,
            "no existe configuracion/textos.yaml -- '/consultar' respondería 500 en la primera pregunta",
            "rag init  # lo recrea si se borró por error; no pisa el resto de tu configuración",
        )
    return ResultadoChequeo("plantillas de respuesta", True, "configuracion/textos.yaml presente")


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
        from rag.servicio.estilos import cargar_estilos, render_css
        from rag.temas_widget import validar_tema

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
    ``rag/configuracion.py``). Solo se marca como FALLA -- algo accionable,
    no una advertencia genérica -- cuando la lista está vacía Y ya hay
    claves de widget configuradas: es la señal concreta de que alguien
    preparó el widget para un sitio real y se olvidó de abrirle CORS, así
    que el navegador bloqueará sus peticiones aunque la clave sea válida."""
    from rag.configuracion import cargar_dominio

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
    candidatos = ["data/golden/manifiesto.json"]
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
        verificar_plantillas(),
        verificar_estilos(),
        verificar_cors(),
        verificar_indice(),
        verificar_modelo_descargado(),
        verificar_golden_set(),
    ]
