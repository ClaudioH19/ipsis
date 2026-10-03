"""CLI pública: ``rag <comando> ...``.

Permite inicializar un proyecto, cargar documentos, indexar y consultar sin
depender del checkout desde el que se instaló la librería.

Regla de diseño de este módulo, no negociable: **cada comando es una función
corta que solo orquesta lo que ya vive en `rag/` y `servicio/`.** Si algo
necesita lógica nueva, esa lógica se escribe en un módulo de `rag/` (ver
`rag/corpus.py::agregar_documentos_al_catalogo`/`ejecutar_ingesta`,
`rag/configuracion/carga.py::actualizar_dominio`, `rag/diagnostico.py`,
`rag/metricas_banco.py::evaluar_backend_activo`), nunca aquí. Los argumentos
se arman con ``argparse`` de la biblioteca estándar -- sin dependencias
nuevas para la CLI, el plugin ya arrastra modelos pesados.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# rag init
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    from rag.configuracion.carga import (
        RUTA_DOMINIO, actualizar_dominio, inicializar_asistente_si_falta,
        inicializar_estilos_si_falta,
        inicializar_plantillas_si_falta, inicializar_proyecto_si_falta,
        slug_coleccion,
    )
    from rag.corpus import CATALOGO_PATH, plantilla_catalogo_vacio
    from rag.lenguaje.dominio import escribir_perfil_generico_si_falta
    from rag.metadata import inicializar_taxonomia_si_falta
    from rag.lenguaje.texto import escribir_idioma_es_si_falta

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
        return sorted(
            p for p in ruta.rglob("*")
            if p.is_file()
            and p.suffix.lower() in EXTENSIONES_SOPORTADAS
            and ".rag-extractivo" not in p.relative_to(ruta).parts
        )
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
    from rag.configuracion.carga import actualizar_dominio

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
    from rag.configuracion.carga import cargar_dominio, cargar_proyecto, config_recuperacion
    from rag.corpus import ejecutar_ingesta
    from rag.lenguaje.dominio import cargar_perfil
    from rag.lenguaje.entidades import configurar_perfil

    try:
        cfg_dominio = cargar_dominio()
        configurar_perfil(cargar_perfil(cfg_dominio["perfil"]))
        cfg = cargar_proyecto()
        cfg_rec = config_recuperacion(cfg)
    except Exception as e:  # noqa: BLE001
        print(f"Error de configuración: {e}")
        print("Corré 'rag doctor' para un diagnóstico completo.")
        return 1

    try:
        resumen = ejecutar_ingesta(
            carpeta_corpus=args.corpus,
            cfg_rec=cfg_rec,
        )
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

def _argumentos_init_automatico() -> argparse.Namespace:
    return argparse.Namespace(
        nombre_asistente=None,
        descripcion_dominio=None,
        idioma=None,
        perfil=None,
        force=False,
    )


def _completar_proyecto_existente() -> None:
    """Añade archivos faltantes usando defaults sin sobrescribir personalizaciones."""
    from rag.configuracion.carga import (
        cargar_dominio,
        inicializar_estilos_si_falta,
        inicializar_plantillas_si_falta,
        inicializar_proyecto_si_falta,
        slug_coleccion,
    )
    from rag.corpus import CATALOGO_PATH, plantilla_catalogo_vacio
    from rag.lenguaje.dominio import escribir_perfil_generico_si_falta
    from rag.metadata import inicializar_taxonomia_si_falta
    from rag.lenguaje.texto import escribir_idioma_es_si_falta

    dominio = cargar_dominio()
    if dominio.get("perfil", "_generico") == "_generico":
        escribir_perfil_generico_si_falta()
    if dominio.get("idioma", "es") == "es":
        escribir_idioma_es_si_falta()
    inicializar_proyecto_si_falta(
        coleccion_base=slug_coleccion(dominio.get("nombre_asistente", "Asistente documental"))
    )
    inicializar_taxonomia_si_falta(
        descripcion_dominio=dominio.get("descripcion_dominio", "los documentos cargados")
    )
    inicializar_plantillas_si_falta()
    inicializar_estilos_si_falta()
    ruta_catalogo = Path(CATALOGO_PATH)
    if not ruta_catalogo.is_file():
        ruta_catalogo.parent.mkdir(parents=True, exist_ok=True)
        ruta_catalogo.write_text(plantilla_catalogo_vacio(), encoding="utf-8")


def _preparar_carpeta_para_servir(carpeta: str, *, reindexar: bool = False) -> Path:
    """Completa un proyecto o crea uno privado junto a una carpeta documental."""
    fuente = Path(carpeta).resolve()
    if not fuente.is_dir():
        raise ValueError(f"no existe la carpeta {fuente}")

    es_proyecto = (
        (fuente / "configuracion" / "asistente.yaml").is_file()
        or (fuente / "documentos" / "catalogo.yaml").is_file()
    )
    if not es_proyecto and not _archivos_de_ruta(fuente):
        raise ValueError(f"no hay documentos compatibles en {fuente}")
    proyecto = fuente if es_proyecto else fuente / ".rag-extractivo"
    proyecto.mkdir(parents=True, exist_ok=True)
    os.chdir(proyecto)

    if not Path("configuracion/asistente.yaml").is_file():
        if cmd_init(_argumentos_init_automatico()) != 0:
            raise RuntimeError("no se pudo inicializar el proyecto automático")
    else:
        _completar_proyecto_existente()

    catalogo = Path("documentos/catalogo.yaml")
    catalogo_antes = catalogo.read_bytes() if catalogo.is_file() else b""
    if not es_proyecto:
        if cmd_cargar(argparse.Namespace(ruta=str(fuente))) != 0:
            raise RuntimeError("no se pudieron cargar los documentos")
    catalogo_despues = catalogo.read_bytes() if catalogo.is_file() else b""

    from rag.diagnostico import verificar_indice

    indice = verificar_indice()
    if reindexar or catalogo_antes != catalogo_despues or not indice.ok:
        print("Preparando el índice antes de iniciar el servicio...")
        if cmd_indexar(argparse.Namespace(corpus="documentos")) != 0:
            raise RuntimeError("no se pudo construir el índice")
    else:
        print("El índice existente está vigente; se reutiliza.")
    return proyecto


def cmd_servir(args: argparse.Namespace) -> int:
    import uvicorn

    anterior = Path.cwd()
    try:
        if args.carpeta:
            proyecto = _preparar_carpeta_para_servir(
                args.carpeta,
                reindexar=args.reindexar,
            )
            print(f"Proyecto activo: {proyecto}")
        print(f"Sirviendo en http://{args.host}:{args.port} (Ctrl+C para detener)...")
        uvicorn.run("rag.servicio.api:app", host=args.host, port=args.port, log_level="info")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"No se pudo preparar el servicio: {exc}")
        return 1
    finally:
        os.chdir(anterior)


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
    from rag.configuracion.carga import guardar_snapshot_configuracion

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

_MANIFIESTO_GOLDEN = "data/golden/manifiesto.json"


def cmd_evaluar(args: argparse.Namespace) -> int:
    import json

    from rag.metricas_banco import evaluar_backend_activo

    ruta = Path(args.banco)
    if not ruta.exists():
        print("No hay golden set en data/golden/ todavía -- no se puede evaluar.")
        print("El formato versionado usa manifiesto.json + golden.jsonl con pregunta, "
              "categoría, split, estado esperado y evidencia literal con offsets.")
        print("Consulta README.md para el formato y las recomendaciones de evaluación.")
        return 0

    print(f"Evaluando el backend activo contra {ruta}...")
    try:
        artefacto = evaluar_backend_activo(str(ruta))
    except Exception as e:  # noqa: BLE001 -- CLI convierte el fallo en mensaje
        print(f"No se pudo evaluar: {e}")
        return 1
    reporte = artefacto.reporte
    print(f"N={reporte.n_casos} Recall@{reporte.k}={reporte.recall_at_k:.3f} "
          f"MRR={reporte.mrr:.3f} exactitud_estado={reporte.exactitud_estado:.3f}")
    print(f"falsos_ok={reporte.tasa_falsos_ok:.3f} "
          f"precision_abstencion={reporte.precision_abstencion:.3f} "
          f"literalidad={reporte.exactitud_literal:.3f} offsets={reporte.exactitud_offsets:.3f}")
    print(f"respuestas_excesivas={reporte.tasa_respuestas_excesivas:.3f} "
          f"latencia_media={reporte.latencia_media_ms:.1f}ms p95={reporte.latencia_p95_ms:.1f}ms")
    if args.salida:
        salida = Path(args.salida)
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(artefacto.model_dump_json(indent=2), encoding="utf-8")
        print(f"Reporte escrito en {salida}")
    veredicto = "CUMPLE" if reporte.guardia_falsos_ok else "BLOQUEADO"
    print(f"Guardia de falsos ok (debe ser 0): {veredicto}")
    return 0 if reporte.guardia_falsos_ok else 1


def cmd_comparar(args: argparse.Namespace) -> int:
    from rag.comparacion import cargar_artefacto, comparar_artefactos

    try:
        informe = comparar_artefactos([cargar_artefacto(ruta) for ruta in args.artefactos])
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo comparar: {e}")
        return 1
    print(f"Dataset {informe.dataset_id}@{informe.dataset_version}, k={informe.k}")
    for fila in informe.filas:
        print(
            f"{fila.backend}: Recall={fila.recall_at_k:.3f} MRR={fila.mrr:.3f} "
            f"falsos_ok={fila.tasa_falsos_ok:.3f} estado={fila.exactitud_estado:.3f} "
            f"latencia_p95={fila.latencia_p95_ms:.1f}ms "
            f"umbral_dev={fila.calibracion_dev.umbral:.5f}"
        )
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(informe.model_dump_json(indent=2), encoding="utf-8")
    print(f"Informe comparativo escrito en {salida}")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from rag.benchmark import ejecutar_benchmark

    try:
        ruta = ejecutar_benchmark(args.banco, args.salida)
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo ejecutar el benchmark: {e}")
        return 1
    print(f"Benchmark reproducible escrito en {ruta}")
    print("El informe no toma decisiones; revísalo antes de cambiar defaults o umbrales.")
    return 0


def cmd_widget_tema_listar(_args: argparse.Namespace) -> int:
    from rag.temas_widget import listar_presets

    for nombre, descripcion in listar_presets().items():
        print(f"{nombre}: {descripcion}")
    return 0


def cmd_widget_tema_aplicar(args: argparse.Namespace) -> int:
    import yaml

    from rag.temas_widget import aplicar_preset

    try:
        aplicar_preset(args.preset, args.ruta)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"No se pudo aplicar el preset: {exc}")
        return 1
    print(f"Preset {args.preset!r} aplicado en {args.ruta}")
    print("Vista activa: inicia el servicio y abre /widget/demo.html")
    return 0


def cmd_widget_tema_vista_previa(args: argparse.Namespace) -> int:
    import yaml

    from rag.temas_widget import generar_vista_previa

    try:
        salida = generar_vista_previa(args.salida, args.ruta)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"No se pudo generar la vista previa: {exc}")
        return 1
    print(f"Vista previa escrita en {salida.resolve()}")
    return 0


def cmd_widget_exportar(args: argparse.Namespace) -> int:
    from rag.exportar_widget import exportar_widget

    try:
        salida = exportar_widget(args.carpeta, api=args.api, posicion=args.posicion)
    except (OSError, ValueError) as exc:
        print(f"No se pudo exportar el widget: {exc}")
        return 1
    print(f"Widget exportado en {salida}")
    print(f"Snippet listo en {salida / 'snippet.html'}")
    return 0


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
    p.add_argument(
        "carpeta",
        nargs="?",
        help="Carpeta de documentos o proyecto existente; se prepara automáticamente.",
    )
    p.add_argument("--host", default="127.0.0.1",
                    help="Dirección donde escucha el servicio (por defecto: '127.0.0.1', solo local; "
                         "usa '0.0.0.0' para aceptar conexiones externas).")
    p.add_argument("--port", type=int, default=8000,
                    help="Puerto donde escucha el servicio (por defecto: 8000).")
    p.add_argument(
        "--reindexar",
        action="store_true",
        help="Reconstruye el índice aunque el catálogo no haya cambiado.",
    )
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
    p.add_argument("--banco", default=_MANIFIESTO_GOLDEN,
                   help="Manifiesto versionado del banco (por defecto: data/golden/manifiesto.json).")
    p.add_argument("--salida", default=None,
                   help="Ruta opcional para guardar el reporte JSON.")
    p.set_defaults(func=cmd_evaluar)

    p = sub.add_parser("comparar", help="Compara artefactos producidos por 'rag evaluar'.")
    p.add_argument("artefactos", nargs="+", help="Dos o más reportes JSON comparables.")
    p.add_argument("--salida", default="reportes/comparacion.json",
                   help="Ruta del informe consolidado.")
    p.set_defaults(func=cmd_comparar)

    p = sub.add_parser("benchmark", help="Compara Qdrant vectorial e híbrido.")
    p.add_argument("--banco", required=True, help="Manifiesto versionado a evaluar.")
    p.add_argument("--salida", default="reportes/benchmark",
                   help="Directorio para artefactos e informe comparativo.")
    p.set_defaults(func=cmd_benchmark)

    p_widget = sub.add_parser("widget", help="Configura y exporta el widget embebible.")
    sub_widget = p_widget.add_subparsers(
        dest="widget_comando", required=True, help="Operación sobre el widget.",
    )
    p_tema = sub_widget.add_parser("tema", help="Administra presets visuales.")
    sub_tema = p_tema.add_subparsers(
        dest="tema_comando", required=True, help="Operación sobre el tema visual.",
    )
    p_listar = sub_tema.add_parser("listar", help="Muestra los presets disponibles.")
    p_listar.set_defaults(func=cmd_widget_tema_listar)
    p_aplicar = sub_tema.add_parser("aplicar", help="Aplica un preset a estilos.yaml.")
    p_aplicar.add_argument("preset", help="Nombre del preset visual.")
    p_aplicar.add_argument(
        "--ruta", default="configuracion/estilos.yaml",
        help="Archivo de estilos a modificar.",
    )
    p_aplicar.set_defaults(func=cmd_widget_tema_aplicar)
    p_preview = sub_tema.add_parser(
        "vista-previa", help="Genera un mockup HTML sin iniciar la API.",
    )
    p_preview.add_argument(
        "--ruta", default="configuracion/estilos.yaml",
        help="Archivo de estilos que se desea previsualizar.",
    )
    p_preview.add_argument(
        "--salida", default=".cache/widget-vista-previa.html",
        help="Archivo HTML de salida.",
    )
    p_preview.set_defaults(func=cmd_widget_tema_vista_previa)
    p_exportar = sub_widget.add_parser(
        "exportar", help="Copia widget.js y genera un snippet de integración.",
    )
    p_exportar.add_argument("carpeta", help="Directorio donde escribir los archivos.")
    p_exportar.add_argument(
        "--api", default="http://127.0.0.1:8000",
        help="URL pública de la API que consultará el widget.",
    )
    p_exportar.add_argument(
        "--posicion", choices=["abajo-derecha", "abajo-izquierda"],
        default="abajo-derecha", help="Esquina donde se mostrará el botón.",
    )
    p_exportar.set_defaults(func=cmd_widget_exportar)

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
