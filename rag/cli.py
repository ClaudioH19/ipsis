"""CLI pública: ``rag <comando> ...``.

Permite inicializar un proyecto, cargar documentos, indexar y consultar sin
depender del checkout desde el que se instaló la librería.

Regla de diseño de este módulo, no negociable: **cada comando es una función
corta que solo orquesta lo que ya vive en `rag/` y `servicio/`.** Si algo
necesita lógica nueva, esa lógica se escribe en un módulo de `rag/` (ver
`rag/corpus.py::agregar_documentos_al_catalogo`/`ejecutar_ingesta`,
`rag/configuracion.py::actualizar_dominio`, `rag/diagnostico.py`,
`rag/evaluacion.py::evaluar_indice_produccion`), nunca aquí. Los argumentos
se arman con ``argparse`` de la biblioteca estándar -- sin dependencias
nuevas para la CLI, el plugin ya arrastra modelos pesados.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# rag init
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    from rag.configuracion import (
        RUTA_DOMINIO, actualizar_dominio, inicializar_asistente_si_falta,
        inicializar_estilos_si_falta,
        inicializar_plantillas_si_falta, inicializar_proyecto_si_falta,
        slug_coleccion,
    )
    from rag.corpus import CATALOGO_PATH, plantilla_catalogo_vacio
    from rag.dominio import escribir_perfil_generico_si_falta
    from rag.metadata import inicializar_taxonomia_si_falta
    from rag.texto_util import escribir_idioma_es_si_falta

    ruta_dominio = Path(RUTA_DOMINIO)
    if ruta_dominio.exists() and not args.force:
        print(f"Ya existe {RUTA_DOMINIO} -- usa 'rag configurar clave=valor' para modificarlo, "
              f"o 'rag init --force' para reiniciarlo desde los valores por defecto.")
        return 1
    if ruta_dominio.exists():
        ruta_dominio.unlink()  # --force: parte de los valores por defecto, no fusiona con lo viejo

    idioma = args.idioma or "es"
    perfil = args.perfil or "_generico"

    # Un directorio de trabajo VACÍO
    # (el caso de uso real de un plugin, fuera de una copia de este repo) no
    # trae 'configuracion/dominios/_generico/perfil.yaml' ni 'configuracion/dominios/idiomas/es.yaml' --
    # 'rag init' debe ESCRIBIRLOS (desde plantillas embebidas en Python, no
    # leerlos del árbol del proyecto) para poder validar el perfil/idioma por
    # defecto, en vez de asumir que ya están ahí. Se escriben ANTES de
    # 'actualizar_dominio' porque esa función valida que existan.
    if perfil == "_generico":
        escribir_perfil_generico_si_falta()
    if idioma == "es":
        escribir_idioma_es_si_falta()

    inicializar_asistente_si_falta()

    pares = {
        "nombre_asistente": args.nombre_asistente or "Asistente documental",
        "descripcion_dominio": args.descripcion_dominio or "los documentos cargados",
        "idioma": idioma,
        "perfil": perfil,
    }
    try:
        nuevo = actualizar_dominio(pares)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    Path("documentos").mkdir(parents=True, exist_ok=True)
    ruta_catalogo = Path(CATALOGO_PATH)
    if not ruta_catalogo.exists():
        ruta_catalogo.parent.mkdir(parents=True, exist_ok=True)
        ruta_catalogo.write_text(plantilla_catalogo_vacio(), encoding="utf-8")

    creo_proyecto = inicializar_proyecto_si_falta(
        coleccion_base=slug_coleccion(nuevo["nombre_asistente"])
    )
    creo_taxonomia = inicializar_taxonomia_si_falta(descripcion_dominio=nuevo["descripcion_dominio"])
    inicializar_plantillas_si_falta()  # configuracion/textos.yaml: genérico, no necesita mensaje aparte
    if inicializar_estilos_si_falta():
        print("configuracion/estilos.yaml creado: ahí se cambia TODO el diseño del widget "
              "(colores, tipografía, formas, sombras y animaciones), sin tocar código.")

    print(f"Dominio inicializado en {RUTA_DOMINIO}:")
    print(f"  nombre_asistente = {nuevo['nombre_asistente']!r}")
    print(f"  descripcion_dominio = {nuevo['descripcion_dominio']!r}")
    print(f"  idioma = {nuevo['idioma']!r}, perfil = {nuevo['perfil']!r}")
    print(f"Corpus vacío listo en documentos/ (catálogo en {CATALOGO_PATH}).")
    if creo_proyecto:
        print("configuracion/motor.yaml creado con umbrales genéricos de partida. "
              "La calibración se realiza al final, después de estabilizar la infraestructura.")
    else:
        print("configuracion/motor.yaml ya existía -- no se tocó.")
    if creo_taxonomia:
        print("configuracion/categorias.yaml creado con una plantilla genérica mínima "
              "(agrégale categorías propias de tu dominio cuando puedas).")
    else:
        print("configuracion/categorias.yaml ya existía -- no se tocó.")
    print("Siguiente paso: 'rag cargar <archivo|carpeta>', después 'rag indexar'.")
    return 0


# ---------------------------------------------------------------------------
# rag cargar
# ---------------------------------------------------------------------------

def _archivos_de_ruta(ruta: Path) -> list[Path]:
    from rag.parsear import EXTENSIONES_SOPORTADAS
    if ruta.is_file():
        return [ruta]
    if ruta.is_dir():
        return sorted(p for p in ruta.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONES_SOPORTADAS)
    raise FileNotFoundError(f"no existe {ruta}")


def cmd_cargar(args: argparse.Namespace) -> int:
    from rag.corpus import agregar_documentos_al_catalogo

    try:
        archivos = _archivos_de_ruta(Path(args.ruta))
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    if not archivos:
        print(f"No se encontró ningún archivo soportado en {args.ruta!r} "
              f"(soportados: .docx, .pdf, .md, .markdown, .txt).")
        return 1

    try:
        resultado = agregar_documentos_al_catalogo([str(a) for a in archivos])
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    for d in resultado:
        if d.ya_existia:
            print(f"  = {d.archivo}: ya estaba cargado como doc_id={d.doc_id!r} (mismo contenido, se omite)")
            continue
        print(f"  + {d.archivo}: doc_id={d.doc_id!r}, título={d.doc_titulo!r}")
        for a in d.advertencias:
            print(f"      [!] {a}")
    n_nuevos = sum(1 for d in resultado if not d.ya_existia)
    print(f"{n_nuevos} documento(s) nuevo(s) agregado(s) al catálogo (documentos/catalogo.yaml).")
    print("Siguiente paso: 'rag indexar'.")
    return 0


# ---------------------------------------------------------------------------
# rag configurar
# ---------------------------------------------------------------------------

def cmd_configurar(args: argparse.Namespace) -> int:
    from rag.configuracion import actualizar_dominio

    pares: dict[str, str] = {}
    for par in args.pares:
        if "=" not in par:
            print(f"Error: {par!r} no tiene la forma 'clave=valor'.")
            return 1
        clave, _, valor = par.partition("=")
        pares[clave.strip()] = valor.strip()

    try:
        nuevo = actualizar_dominio(pares)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    print("configuracion/asistente.yaml actualizado:")
    for clave in pares:
        print(f"  {clave} = {nuevo[clave]!r}")
    return 0


# ---------------------------------------------------------------------------
# rag indexar
# ---------------------------------------------------------------------------

def cmd_indexar(args: argparse.Namespace) -> int:
    from rag.configuracion import cargar_dominio, config_recuperacion
    from rag.corpus import ejecutar_ingesta
    from rag.dominio import cargar_perfil
    from rag.reglas_extraccion import configurar_perfil

    try:
        cfg_dominio = cargar_dominio()
        configurar_perfil(cargar_perfil(cfg_dominio["perfil"]))
        cfg_rec = config_recuperacion()
    except Exception as e:  # noqa: BLE001
        print(f"Error de configuración: {e}")
        print("Corré 'rag doctor' para un diagnóstico completo.")
        return 1

    try:
        resumen = ejecutar_ingesta(carpeta_corpus=args.corpus, cfg_rec=cfg_rec)
    except Exception as e:  # noqa: BLE001 -- se reporta con contexto, no se oculta
        print(f"Error indexando: {e}")
        return 1

    print(f"Documentos parseados: {resumen.n_documentos}")
    for d in resumen.documentos:
        print(f"  - {d.doc_id}: {d.n_bloques} bloques, {d.n_caracteres} caracteres")
    print(f"Chunks generados: {resumen.n_chunks}")
    if resumen.errores_validacion:
        print(f"Errores de validación de ingesta: {len(resumen.errores_validacion)}")
        for e in resumen.errores_validacion[:20]:
            print(f"  ! {e}")
    for a in resumen.advertencias:
        print(f"  [!] {a}")
    print(f"Indexado en la colección {resumen.nombre_coleccion!r}: "
          f"vocabulario BM25 ({resumen.n_vocab_bm25} términos), "
          f"inventario de entidades ({resumen.n_entidades_inventario} valores), "
          f"estadísticas léxicas ({resumen.n_terminos_lexico} términos).")
    print(f"Tiempo total: {resumen.tiempo_seg:.1f}s")
    print("Siguiente paso: 'rag servir' (o 'rag preguntar \"...\"' si ya está sirviendo).")
    return 0


# ---------------------------------------------------------------------------
# rag servir
# ---------------------------------------------------------------------------

def cmd_servir(args: argparse.Namespace) -> int:
    import uvicorn
    print(f"Sirviendo en http://{args.host}:{args.port} (Ctrl+C para detener)...")
    uvicorn.run("rag.servicio.api:app", host=args.host, port=args.port, log_level="info")
    return 0


# ---------------------------------------------------------------------------
# rag preguntar
# ---------------------------------------------------------------------------

_ETIQUETA_ESTADO = {
    "ok": "[OK]",
    "relacionado": "[RELACIONADO -- no es una respuesta directa]",
    "sin_respuesta": "[SIN RESPUESTA]",
    "conversacional": "[CONVERSACIONAL]",
    "degradado": "[DEGRADADO]",
    "saturado": "[SATURADO]",
}


def cmd_preguntar(args: argparse.Namespace) -> int:
    import httpx

    url = f"{args.url.rstrip('/')}/consultar"
    try:
        resp = httpx.post(
            url, json={"pregunta": args.pregunta, "id_sesion": "rag-cli"}, timeout=args.timeout,
        )
    except httpx.ConnectError:
        print(f"No se pudo conectar a {url}. ¿Está el servicio arriba? Corré 'rag servir' primero.")
        return 1
    except httpx.TimeoutException:
        print(f"El servicio no respondió en {args.timeout}s.")
        return 1

    if resp.status_code != 200:
        print(f"El servicio respondió {resp.status_code}: {resp.text}")
        return 1

    datos = resp.json()
    estado = datos.get("estado", "?")
    print(_ETIQUETA_ESTADO.get(estado, f"[{estado.upper()}]"))
    print(datos.get("respuesta", ""))
    fragmentos = datos.get("fragmentos") or []
    if fragmentos:
        print("\nCitas:")
        for f in fragmentos:
            print(f"  - {f['doc_titulo']} > {f['seccion']} "
                  f"(offsets {f['offset_inicio']}-{f['offset_fin']}, score={f['score']:.3f})")
    return 0


# ---------------------------------------------------------------------------
# rag doctor
# ---------------------------------------------------------------------------

def cmd_doctor(_args: argparse.Namespace) -> int:
    from rag.diagnostico import ejecutar_diagnostico

    resultados = ejecutar_diagnostico()
    hay_fallas = False
    for r in resultados:
        marca = "OK  " if r.ok else "FALLA"
        print(f"[{marca}] {r.nombre}: {r.mensaje}")
        if not r.ok:
            hay_fallas = True
            if r.comando_sugerido:
                print(f"        -> corré: {r.comando_sugerido}")
    print()
    print("Todo listo." if not hay_fallas else "Hay puntos por resolver (ver '-> corré:' arriba).")
    return 1 if hay_fallas else 0


def cmd_snapshot_config(args: argparse.Namespace) -> int:
    from rag.configuracion import guardar_snapshot_configuracion

    try:
        ruta = guardar_snapshot_configuracion(args.salida)
    except Exception as e:  # noqa: BLE001 -- CLI debe dar un error accionable
        print(f"Error generando snapshot de configuración: {e}")
        return 1
    print(f"Snapshot de configuración efectiva escrito en {ruta}")
    return 0


# ---------------------------------------------------------------------------
# rag evaluar
# ---------------------------------------------------------------------------

_CANDIDATOS_GOLDEN = ["data/golden/golden.jsonl"]


def cmd_evaluar(_args: argparse.Namespace) -> int:
    from rag.evaluacion import evaluar_indice_produccion

    ruta = next((c for c in _CANDIDATOS_GOLDEN if Path(c).exists()), None)
    if ruta is None:
        print("No hay golden set en data/golden/ todavía -- no se puede evaluar.")
        print("Un golden set es un .jsonl con una pregunta por linea: 'pregunta', "
              "'respondible', 'evidencia' (texto literal del documento) y 'hechos_clave'.")
        print("Consulta README.md para el formato y las recomendaciones de evaluación.")
        return 0

    print(f"Evaluando el índice de producción contra {ruta} (split dev, respondibles)...")
    try:
        r = evaluar_indice_produccion(ruta)
    except RuntimeError as e:
        print(f"No se pudo evaluar: {e}")
        return 1

    print(f"N={r.n_items}  Recall@3={r.recall_at_3:.3f} [IC95% {r.ic_lo:.2f},{r.ic_hi:.2f}]  "
          f"cobertura_hechos={r.cobertura_hechos:.3f}")
    veredicto = "CUMPLE" if r.cumple else "NO CUMPLE"
    print(f"Criterio (configuracion/motor.yaml::criterios_aceptacion): "
          f"Recall@3 >= {r.recall_at_3_min_requerido} -> {veredicto}")
    print("Nota: esta es una comprobación rápida sobre la configuración activa; no reindexa el corpus.")
    return 0 if r.cumple else 1


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def _construir_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="rag", description="Chatbot RAG extractivo sobre tus documentos.")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("init", help="Crea la configuración de un dominio nuevo.")
    p.add_argument("--nombre-asistente", dest="nombre_asistente", default=None,
                    help="Nombre visible del asistente (por defecto: 'Asistente documental').")
    p.add_argument("--descripcion-dominio", dest="descripcion_dominio", default=None,
                    help="Descripción corta del dominio, p.ej. 'el manual de mi equipo' "
                         "(por defecto: 'los documentos cargados').")
    p.add_argument("--idioma", default=None,
                    help="Idioma de las palabras de alta frecuencia general (por defecto: 'es').")
    p.add_argument("--perfil", default=None,
                    help="Perfil de configuracion/dominios/<perfil>/perfil.yaml a usar (por defecto: '_generico', "
                         "sin reglas de extracción propias).")
    p.add_argument("--force", action="store_true", help="Reinicia configuracion/asistente.yaml si ya existe.")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("cargar", help="Copia un archivo o carpeta al corpus y lo cataloga.")
    p.add_argument("ruta", help="Archivo o carpeta con .docx/.pdf/.md/.txt")
    p.set_defaults(func=cmd_cargar)

    p = sub.add_parser("configurar", help="Modifica configuracion/asistente.yaml (clave=valor).")
    p.add_argument("pares", nargs="+",
                    help="Uno o más pares clave=valor, p.ej. nombre_asistente='Mi asistente' "
                         "cors_origenes=https://mi-sitio.cl (varias claves separadas por espacio, "
                         "varios valores de una lista separados por coma dentro del mismo valor).")
    p.set_defaults(func=cmd_configurar)

    p = sub.add_parser("indexar", help="Parsea, fragmenta, vectoriza y persiste el índice.")
    p.add_argument("--corpus", default="documentos",
                    help="Carpeta con los documentos a indexar (por defecto: 'documentos').")
    p.set_defaults(func=cmd_indexar)

    p = sub.add_parser("servir", help="Levanta la API del servicio.")
    p.add_argument("--host", default="127.0.0.1",
                    help="Dirección donde escucha el servicio (por defecto: '127.0.0.1', solo local; "
                         "usa '0.0.0.0' para aceptar conexiones externas).")
    p.add_argument("--port", type=int, default=8000,
                    help="Puerto donde escucha el servicio (por defecto: 8000).")
    p.set_defaults(func=cmd_servir)

    p = sub.add_parser("preguntar", help="Consulta el servicio desde la terminal.")
    p.add_argument("pregunta", help="La pregunta a enviar (entre comillas si tiene espacios).")
    p.add_argument("--url", default="http://127.0.0.1:8000",
                    help="Base del servicio a consultar (por defecto: 'http://127.0.0.1:8000').")
    p.add_argument("--timeout", type=float, default=30.0,
                    help="Segundos de espera máxima por una respuesta antes de fallar (por defecto: 30).")
    p.set_defaults(func=cmd_preguntar)

    p = sub.add_parser("doctor", help="Diagnóstico: configuración, índice, modelos, Qdrant.")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser(
        "snapshot-config",
        help="Escribe la configuración efectiva con defaults resueltos.",
    )
    p.add_argument(
        "--salida",
        default=".cache/configuracion-efectiva.yaml",
        help="Ruta del snapshot (por defecto: .cache/configuracion-efectiva.yaml).",
    )
    p.set_defaults(func=cmd_snapshot_config)

    p = sub.add_parser("evaluar", help="Corre una evaluación rápida si hay golden set.")
    p.set_defaults(func=cmd_evaluar)

    return ap


def _asegurar_salida_no_crashea() -> None:
    """La consola de
    Windows suele usar cp1252 (o cp437), que no puede codificar caracteres
    fuera de esa página -- un solo símbolo decorativo en un `print()`
    (encontrado con '⚠' en una advertencia de `rag cargar`) bastaba para
    matar el comando con un `UnicodeEncodeError` sin capturar, justo en la
    ruta que más importa mostrarle al usuario. Esto es la red de seguridad:
    ningún carácter que la consola no pueda pintar debe volver a tumbar un
    comando (se reemplaza por el caracter de repuesto de `errors="replace"`,
    un defecto cosmético, nunca un traceback). Además, en `rag/cli.py` ya no
    se usan glifos decorativos en la salida (se cambiaron a marcadores ASCII
    como `[!]`) -- esto es un respaldo, no la primera línea de defensa."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass  # streams sin `reconfigure` (p.ej. redirigidos a algo atípico): se deja tal cual


def main(argv: list[str] | None = None) -> int:
    _asegurar_salida_no_crashea()
    parser = _construir_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
