"""API HTTP del asistente documental.

Implementa ``/consultar`` de punta a punta con el pipeline de
``rag/servicio/pipeline.py``: detección conversacional determinista (Etapa C),
recuperación real (``rag/indice.py``, la misma que usan las evaluaciones),
abstención en DOS CAPAS con recuperación dirigida contra el corpus completo
(Fase 3, Etapa C), selección de las oraciones más pertinentes de cada
fragmento con orden GLOBAL entre fragmentos (Etapa C,
``rag/seleccion_fragmento.py``), plan único "extractivo" (o el estado propio
"relacionado") con conectores fijos (Fase 4) y guardia de fidelidad real.

No se implementa aquí ningún llamado a LLM en línea (restricción dura del
proyecto) ni en este módulo ni en ninguno de los que importa.

**Pensado para servir un frontend externo:** toda respuesta trae un
``respuesta`` de texto LISTO PARA
MOSTRAR (nunca ``null``), y cada fragmento citado trae lo necesario para
mostrarlo (``doc_titulo``, ``seccion``, ``texto``, offsets).

**Ajustes al contrato de esta etapa (documentados, no silenciosos):**
- ``Fragmento`` gana ``offset_inicio``/``offset_fin``.
- ``RespuestaConsulta.estado`` gana ``"relacionado"`` (Etapa C, punto 2: no
  es una abstención ni una afirmación -- muestra fragmentos pertinentes
  enmarcados) y ``"conversacional"`` (Etapa C, punto 4: saludos/charla
  trivial, texto fijo, nunca toca Qdrant).
- ``RespuestaConsulta.plan`` gana ``"extractivo"``, ``"zona_gris"``,
  ``"sin_respuesta"`` y ``"conversacional"``.
- ``RespuestaConsulta.respuesta`` NUNCA es ``null``.
- ``Confianza.acuerdo_bm25`` pasa a opcional (``None``).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from rag.configuracion import (
    cargar_proyecto, cargar_dominio, config_recuperacion, config_abstencion, config_servicio,
    config_redaccion, config_seguridad,
)
from rag.corpus import (
    crear_cliente_qdrant, cargar_vocabulario_bm25, cargar_inventario_entidades,
    cargar_estadisticas_lexico_dominio,
    nombre_coleccion_versionada,
)
from rag.dominio import cargar_perfil
from rag.indice import ColeccionQdrant, buscar, codificar_pregunta, construir_filtro_entidad
from rag.reglas_extraccion import extraer_entidades, configurar_perfil
from rag.seleccion_fragmento import recortar_payload_a_texto_pertinente, ordenar_por_pertinencia_global
from rag.texto_util import cargar_palabras_generales
from rag.servicio.pipeline import (
    ConfiguracionAdmision, ControlAdmision,
    SenalesAbstencion, verificar_premisa, separar_entidades_ausentes, decidir_capas_abstencion,
    elegir_plan, redactar, redactar_zona_gris, construir_mensaje_abstencion,
    verificar_fidelidad,
    detectar_conversacional, respuesta_conversacional,
    tiene_grounding_dominio,
)
from rag.servicio.seguridad import (
    NOMBRE_CABECERA_CLAVE_WIDGET, LimitadorPeticiones, identificador_limitador, verificar_clave_widget,
)

app = FastAPI(title="rag-extractivo", version="0.6.0")

_DIR_ESTATICOS = Path(__file__).resolve().parent / "estaticos"


# ---------------------------------------------------------------------------
# Estado del proceso: modelos, cliente Qdrant y control de admisión se
# cargan UNA SOLA VEZ al arrancar (sección 7 del molde: "warm-up: 1
# inferencia por modelo al arrancar"), nunca por petición.
# ---------------------------------------------------------------------------
class _EstadoServicio:
    listo: bool = False
    error_arranque: Optional[str] = None
    col: Optional[ColeccionQdrant] = None
    n_chunks: int = 0
    inventario_entidades: set = frozenset()
    estadisticas_lexico: Optional[dict] = None
    palabras_generales: frozenset = frozenset()
    cfg: Optional[dict] = None
    cfg_dominio: Optional[dict] = None
    cfg_rec: Optional[dict] = None
    cfg_abs: Optional[dict] = None
    cfg_red: Optional[dict] = None
    control_admision: Optional[ControlAdmision] = None
    # Seguridad (Etapa Plugin, Tarea A): leídas a nivel de IMPORTACIÓN del
    # módulo, igual que CORS más abajo -- así funcionan aunque el resto del
    # arranque (conectar Qdrant) falle. ``claves_widget`` y ``limitador`` NO
    # dependen de que el índice exista.
    claves_widget: list = []
    limitador: Optional[LimitadorPeticiones] = None


estado = _EstadoServicio()

# CORS (Etapa Plugin, Tarea A/C): orígenes permitidos para que un widget de
# chat embebido en OTRO sitio pueda llamar a este servicio -- configurable
# por dominio en ``configuracion/asistente.yaml::cors_origenes`` (``rag configurar
# cors_origenes=https://mi-sitio.cl``), nunca fijado en código. Se lee en
# tiempo de IMPORTACIÓN del módulo (antes del evento ``startup``) porque
# FastAPI exige que el middleware se registre antes de que la app reciba
# tráfico; si ``configuracion/asistente.yaml`` no existe todavía, cae al valor por
# defecto VACÍO (``rag/configuracion.py::cargar_dominio``) -- nunca ``["*"]``,
# ver la justificación de seguridad en ese módulo.
_cfg_dominio_arranque = cargar_dominio()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cfg_dominio_arranque.get("cors_origenes", []),
    allow_methods=["*"],
    allow_headers=["*", NOMBRE_CABECERA_CLAVE_WIDGET],
)

# Autenticación de widget + límite de peticiones (Etapa Plugin, Tarea A):
# igual criterio que CORS arriba -- se leen a nivel de importación, con
# valores por defecto tolerantes (``config_seguridad`` no exige que
# ``configuracion/motor.yaml`` exista todavía), para que ambos mecanismos
# funcionen incluso en un despliegue a medio inicializar.
estado.claves_widget = _cfg_dominio_arranque.get("claves_widget", [])
_cfg_limite = config_seguridad()["limite_peticiones"]
estado.limitador = LimitadorPeticiones(
    capacidad=_cfg_limite["capacidad"], tasa_por_segundo=_cfg_limite["tasa_por_segundo"],
)


def _verificar_seguridad(
    peticion: Request,
    x_rag_widget_key: Optional[str] = Header(default=None, alias=NOMBRE_CABECERA_CLAVE_WIDGET),
) -> None:
    """Dependencia de FastAPI (``Depends``): se resuelve ANTES de que el
    cuerpo de la ruta se ejecute, así que una clave inválida o un límite de
    peticiones agotado se rechazan sin gastar ni una consulta a Qdrant --
    ni siquiera requieren que el servicio esté "listo" (``estado.listo``),
    a propósito: la autenticación y el límite de peticiones son una capa de
    borde, independiente de si el índice terminó de cargar."""
    verificar_clave_widget(x_rag_widget_key, estado.claves_widget)
    ip_cliente = peticion.client.host if peticion.client else None
    identificador = identificador_limitador(x_rag_widget_key, ip_cliente)
    if estado.limitador is not None and not estado.limitador.permitir(identificador):
        raise HTTPException(
            status_code=429,
            detail="límite de peticiones excedido, reintenta en unos segundos",
            headers={"Retry-After": "3"},
        )


class Filtros(BaseModel):
    version: Optional[str] = None
    documento: Optional[str] = None


class PeticionConsulta(BaseModel):
    pregunta: str
    id_sesion: str
    filtros: Filtros = Filtros()
    deadline_ms: int = 1500


class Fragmento(BaseModel):
    chunk_id: str
    doc_titulo: str
    seccion: str
    version: str
    pagina: Optional[int] = None
    offset_inicio: int
    offset_fin: int
    texto: str
    score: float


class Confianza(BaseModel):
    top1: float
    margen: float
    # E4 completo (acuerdo BM25/vectorial) no se calcula en la versión
    # mínima de abstención de esta etapa -- ver rag/servicio/pipeline.py.
    acuerdo_bm25: Optional[bool] = None


class RespuestaConsulta(BaseModel):
    estado: Literal["ok", "relacionado", "conversacional", "sin_respuesta", "degradado", "saturado"]
    nivel_servicio: Literal["normal", "media", "alta"]
    respuesta: Optional[str]  # en la práctica NUNCA null (ver docstring del módulo)
    plan: Optional[Literal["definicion", "procedimiento", "requisito", "dato_puntual",
                            "comparacion", "excepcion", "extractivo", "zona_gris",
                            "sin_respuesta", "conversacional"]]
    fragmentos: list[Fragmento]
    confianza: Confianza
    latencia_ms: int


def _construir_indice_para_servicio(cfg_rec: dict, cfg_qdrant: dict) -> tuple[ColeccionQdrant, set, dict]:
    """Conecta con la colección Qdrant YA INDEXADA por ``rag indexar``
    (misma sección ``recuperacion:``) y carga el vocabulario BM25, el
    inventario de entidades y las estadísticas léxicas de dominio que ese
    mismo paso persistió como artefactos
    (``rag.corpus.cargar_vocabulario_bm25``/``cargar_inventario_entidades``/
    ``cargar_estadisticas_lexico_dominio``).

    **El servicio NO toca ``documentos/`` en ningún momento** (Etapa B): el
    payload de cada chunk (texto, offsets, sección, doc_titulo...) tampoco
    hace falta reconstruirlo: Qdrant ya lo devuelve con cada resultado de
    búsqueda (``rag/indice.py::buscar``, ``with_payload=True`` por defecto).
    """
    modo = os.environ.get("QDRANT_MODO") or cfg_qdrant.get("modo")
    url_servidor = os.environ.get("QDRANT_URL") or cfg_qdrant.get("url_servidor")
    client = crear_cliente_qdrant(qdrant_path=cfg_rec["qdrant_path"], modo=modo, url_servidor=url_servidor)

    nombre_col = nombre_coleccion_versionada(cfg_rec["coleccion_base"], cfg_rec["modelo"],
                                              cfg_rec["version_coleccion"])
    if not client.collection_exists(nombre_col):
        raise RuntimeError(
            f"la colección Qdrant {nombre_col!r} no existe todavía. Corré "
            f"'rag indexar' primero (lee la misma configuracion/motor.yaml::recuperacion "
            f"que este servicio)."
        )

    vocab = cargar_vocabulario_bm25(nombre_col)
    inventario = cargar_inventario_entidades(nombre_col)
    estadisticas_lexico = cargar_estadisticas_lexico_dominio(nombre_col)

    from sentence_transformers import SentenceTransformer
    modelo = SentenceTransformer(cfg_rec["modelo"], device="cpu")

    col = ColeccionQdrant(client=client, modelo_st=modelo, vocab=vocab, nombre=nombre_col,
                           qdrant_path=cfg_rec["qdrant_path"])
    return col, inventario, estadisticas_lexico


@app.on_event("startup")
def cargar_todo() -> None:
    try:
        cfg = cargar_proyecto()
        cfg_dominio = cargar_dominio()
        cfg_rec = config_recuperacion(cfg)
        cfg_abs = config_abstencion(cfg)
        cfg_srv = config_servicio(cfg)
        cfg_red = config_redaccion(cfg)

        # Perfil de dominio (Etapa Plugin, Tarea C): las entidades
        # específicas del dominio activo (saberes, organismos, prácticas...
        # ver configuracion/dominios/<perfil>/perfil.yaml) se registran UNA VEZ para todo
        # el proceso -- rag/reglas_extraccion.py::extraer_entidades las usa
        # desde entonces sin que este módulo tenga que pasarlas en cada
        # llamada.
        perfil = cargar_perfil(cfg_dominio["perfil"])
        configurar_perfil(perfil)
        palabras_generales = cargar_palabras_generales(cfg_dominio.get("idioma", "es"))

        col, inventario, estadisticas_lexico = _construir_indice_para_servicio(cfg_rec, cfg.get("qdrant", {}))

        # warm-up (sección 7): una inferencia real antes de aceptar tráfico,
        # para que la primera petición de un usuario no pague el costo de
        # cargar los kernels de PyTorch/ONNX en frío. También sirve para
        # conocer n_chunks reales del índice (para /ready) sin mantener una
        # lista de payloads aparte.
        codificar_pregunta(col, "calentamiento del modelo", cfg_rec.get("prefijo_query", ""))
        conteo = col.client.count(collection_name=col.nombre, exact=True)

        estado.col = col
        estado.n_chunks = conteo.count
        estado.inventario_entidades = inventario
        estado.estadisticas_lexico = estadisticas_lexico
        estado.palabras_generales = palabras_generales
        estado.cfg = cfg
        estado.cfg_dominio = cfg_dominio
        estado.cfg_rec = cfg_rec
        estado.cfg_abs = cfg_abs
        estado.cfg_red = cfg_red
        estado.control_admision = ControlAdmision(
            ConfiguracionAdmision(concurrencia_maxima=cfg_srv["concurrencia_maxima"])
        )
        estado.listo = True
        estado.error_arranque = None
    except Exception as e:  # noqa: BLE001 -- se reporta en /ready, no se oculta
        estado.listo = False
        estado.error_arranque = f"{type(e).__name__}: {e}"


@app.get("/health")
def health():
    """Vivo: el proceso responde. No implica que los modelos estén cargados."""
    return {"estado": "vivo"}


@app.get("/ready")
def ready():
    """Listo: índice Qdrant conectado, modelo cargado y calentado, control de
    admisión inicializado. Si algo falló al arrancar, devuelve 503 con el
    motivo (nunca oculta el error)."""
    if not estado.listo:
        raise HTTPException(
            status_code=503,
            detail=f"no listo: {estado.error_arranque or 'modelos/índice todavía no cargados'}",
        )
    return {
        "estado": "listo",
        "coleccion": estado.col.nombre,
        "n_chunks": estado.n_chunks,
        "n_entidades_inventario": len(estado.inventario_entidades),
        "abstencion_calibrada": estado.cfg_abs is not None,
        "concurrencia_maxima": estado.control_admision.config.concurrencia_maxima,
    }


class ConfigWidget(BaseModel):
    nombre_asistente: str
    descripcion_dominio: str
    saludo: str


@app.get("/config", response_model=ConfigWidget)
def configuracion_widget():
    """Textos definidos en el SERVIDOR para que el widget (``/widget.js``)
    no tenga que traer ningún texto propio del dominio -- así adoptar un
    dominio nuevo (``rag configurar nombre_asistente=... descripcion-
    dominio=...``) no obliga a editar JavaScript. Lee ``configuracion/asistente.yaml``
    (identidad) y ``configuracion/textos.yaml`` (el saludo fijo de la categoría
    conversacional "saludo", ya con las variables de dominio sustituidas --
    reusa ``rag/servicio/pipeline.py::respuesta_conversacional``, la MISMA
    función que responde un "hola" real, para no mantener el texto en dos
    lugares). No requiere que el índice esté listo (``estado.listo``): es
    metadata de presentación, no depende de Qdrant."""
    cfg_dominio = cargar_dominio()
    return ConfigWidget(
        nombre_asistente=cfg_dominio.get("nombre_asistente", "Asistente documental"),
        descripcion_dominio=cfg_dominio.get("descripcion_dominio", "los documentos cargados"),
        saludo=respuesta_conversacional("saludo"),
    )


@app.get("/widget.js")
def widget_js():
    """El widget embebible (Etapa Plugin, Tarea B): un único archivo
    JavaScript, servido por este mismo proceso -- así una sola línea
    (``<script src=".../widget.js" data-api="...">``) basta para integrarlo,
    sin publicar el archivo aparte ni versionarlo contra el backend."""
    return FileResponse(_DIR_ESTATICOS / "widget.js", media_type="application/javascript; charset=utf-8")


@app.get("/estilos.css")
def estilos_css():
    """Tema del despliegue, traducido desde ``configuracion/estilos.yaml``.

    El widget trae sus propios valores de repuesto dentro del Shadow DOM y
    enlaza esta hoja DESPUES, asi que aqui solo viaja lo que el despliegue
    quiso cambiar: una clave borrada del YAML vuelve sola al valor de
    fabrica y el widget nunca queda sin estilos, ni siquiera si este
    endpoint falla.

    Se lee del disco en cada peticion a proposito: editar el YAML y
    recargar la pagina basta para ver el cambio, sin reiniciar el
    servicio. Es un archivo pequeno y no esta en el camino de ninguna
    consulta."""
    from rag.servicio.estilos import render_css

    return Response(content=render_css(), media_type="text/css; charset=utf-8")


@app.get("/widget/demo.html")
def widget_demo():
    """Página de demostración que simula un sitio anfitrión con el widget
    embebido, para poder verlo sin montar nada propio."""
    return FileResponse(_DIR_ESTATICOS / "demo.html", media_type="text/html; charset=utf-8")


def _respuesta_abstencion(motivo: str, confianza: Confianza, latencia_ms: int,
                           entidad_texto: Optional[str] = None) -> RespuestaConsulta:
    """Toda abstención devuelve texto LISTO PARA MOSTRAR (nunca ``null``,
    ver docstring del módulo) y ``plan="sin_respuesta"`` (nunca ``None``,
    así un frontend externo no tiene que tratar "no hay plan" como un
    estado especial distinto de "no hay respuesta")."""
    return RespuestaConsulta(
        estado="sin_respuesta", nivel_servicio="normal",
        respuesta=construir_mensaje_abstencion(motivo, entidad_texto),
        plan="sin_respuesta", fragmentos=[], confianza=confianza, latencia_ms=latencia_ms,
    )


def _fragmentos_respuesta(payloads: list[dict], scores: list[float]) -> list[Fragmento]:
    return [
        Fragmento(
            chunk_id=p["chunk_id"], doc_titulo=p["doc_titulo"],
            seccion=" > ".join(p.get("seccion_path") or []) or "(sin sección)",
            version=p["version"], pagina=None,
            offset_inicio=p["offset_inicio"], offset_fin=p["offset_fin"],
            texto=p["texto"], score=scores[i],
        )
        for i, p in enumerate(payloads)
    ]


@app.post("/consultar", response_model=RespuestaConsulta, dependencies=[Depends(_verificar_seguridad)])
def consultar(peticion: PeticionConsulta):
    """Flujo real (sección 2.1 del molde, Etapa C):

      -1. Seguridad de borde (``_verificar_seguridad``, Etapa Plugin, Tarea
          A): clave de widget válida (si hay alguna configurada) y límite de
          peticiones -- se resuelve ANTES que todo lo de abajo, como
          dependencia de FastAPI, y no gasta ninguna consulta a Qdrant.
      0. Conversacional (``rag/servicio/pipeline.py::detectar_conversacional``):
         saludos/charla trivial se resuelven con texto fijo ANTES de tocar
         Qdrant.
      1. Control de admisión: 503 inmediato si está saturado.
      2. Señal de abstención (score denso del mejor fragmento, consulta
         vectorial-solo) + capa (a): ¿la pregunta pertenece al dominio del
         corpus? Si no, se abstiene sin gastar una recuperación híbrida.
      3. Recuperación híbrida real (``rag/indice.py``, reusa el mismo vector).
      4. Capa (b): chequeo de premisa determinista. Si una entidad de la
         pregunta no aparece en los fragmentos recuperados, se intenta una
         RECUPERACIÓN DIRIGIDA a los chunks del corpus completo que sí la
         contienen (``rag/corpus.py::cargar_inventario_entidades`` +
         ``rag/indice.py::construir_filtro_entidad``) antes de decidir
         abstenerse -- distingue "no está en el top-k" de "no existe en el
         corpus".
      5. Zona gris (entre las dos capas de score, premisa ya respaldada):
         según ``configuracion/motor.yaml::abstencion.zona_gris.modo``, estado
         propio ``"relacionado"`` (default) o abstención.
      6. Selección de las oraciones más pertinentes de cada fragmento +
         orden GLOBAL entre fragmentos (``rag/seleccion_fragmento.py``) +
         plan "extractivo"/"relacionado" + conectores fijos + guardia de
         fidelidad. Si la guardia falla, se abstiene.
    """
    # Conversacional: se resuelve ANTES de admisión/Qdrant -- es gratis
    # (regex) y no tiene sentido contarlo contra la concurrencia del
    # servicio ni calentar el modelo para un saludo.
    t0 = time.perf_counter()
    categoria_conv = detectar_conversacional(peticion.pregunta)
    if categoria_conv is not None:
        return RespuestaConsulta(
            estado="conversacional", nivel_servicio="normal",
            respuesta=respuesta_conversacional(categoria_conv, peticion.pregunta),
            plan="conversacional", fragmentos=[],
            confianza=Confianza(top1=0.0, margen=0.0, acuerdo_bm25=None),
            latencia_ms=int((time.perf_counter() - t0) * 1000),
        )

    if not estado.listo:
        raise HTTPException(status_code=503, detail="servicio no listo, ver /ready")

    if not estado.control_admision.intentar_admitir():
        raise HTTPException(
            status_code=503,
            detail="servicio saturado (límite de concurrencia alcanzado), reintente en un momento",
            headers={"Retry-After": "1"},
        )

    try:
        cfg_rec = estado.cfg_rec
        cfg_red = estado.cfg_red
        col = estado.col
        pregunta = peticion.pregunta
        prefijo_query = cfg_rec.get("prefijo_query", "")

        def latencia_ms() -> int:
            return int((time.perf_counter() - t0) * 1000)

        # Una sola codificación de la pregunta, reusada en TODAS las
        # consultas de esta petición (señal + recuperación real +
        # recuperación dirigida) -- rag/indice.py::codificar_pregunta.
        vq = codificar_pregunta(col, pregunta, prefijo_query)

        limit_senal = max(cfg_rec["top_k"], 2)
        res_denso = buscar(col, pregunta, modo="vectorial", limit=limit_senal, vector_precomputado=vq)
        s1 = res_denso.scores[0] if res_denso.scores else 0.0
        s2 = res_denso.scores[1] if len(res_denso.scores) > 1 else 0.0
        senales = SenalesAbstencion(score_top1=s1, margen_top1_top2=s1 - s2)
        confianza = Confianza(top1=s1, margen=senales.margen_top1_top2, acuerdo_bm25=None)

        if estado.cfg_abs is None:
            # sin calibración -> falla seguro: se abstiene siempre (nunca
            # responde con un umbral inventado).
            return _respuesta_abstencion("generico", confianza, latencia_ms())

        umbral_fuera_dominio = estado.cfg_abs["capa_a_fuera_dominio"]["umbral"]
        umbral_confianza_alta = estado.cfg_abs["confianza_alta"]["umbral"]
        zona_gris_modo = estado.cfg_abs.get("zona_gris", {}).get("modo", "relacionado")
        df_fraccion_max = estado.cfg_abs["capa_a_fuera_dominio"]["grounding_lexico"]["df_fraccion_max"]

        # Capa (a): fuera de dominio -- se resuelve ANTES de gastar una
        # recuperación híbrida real (no tiene sentido recuperar fragmentos
        # del corpus para una pregunta ajena a él). EXCEPCIÓN
        # (Etapa C, punto 1, refinada en la Etapa D: el grounding léxico
        # ahora exige términos ESPECÍFICOS del dominio -- ver
        # rag/servicio/pipeline.py::tiene_grounding_lexico -- no cualquier
        # palabra que aparezca una vez en el corpus): si la pregunta tiene
        # "grounding" determinista con el corpus -- una entidad cerrada que
        # existe en él, o una palabra de contenido específica del corpus
        # (con o sin tildes), no se rechaza solo por un score denso marginal.
        grounding_dominio = tiene_grounding_dominio(pregunta, estado.inventario_entidades,
                                                     estado.estadisticas_lexico, df_fraccion_max,
                                                     estado.palabras_generales)
        if s1 < umbral_fuera_dominio and not grounding_dominio:
            return _respuesta_abstencion("fuera_dominio", confianza, latencia_ms())

        # Recuperación de PRODUCCIÓN (config: modo híbrido), reusa el mismo
        # vector. El payload de cada punto ya viene en la respuesta de
        # Qdrant (rag/indice.py::buscar) -- no se reconstruye desde ningún
        # lado externo.
        res_hib = buscar(col, pregunta, modo=cfg_rec["modo"], limit=cfg_rec["top_k"], vector_precomputado=vq)
        payloads_top = list(res_hib.payloads)
        scores_top = list(res_hib.scores)

        if not payloads_top:
            return _respuesta_abstencion("sin_fragmentos", confianza, latencia_ms())

        # Capa (b): premisa determinista, con recuperación DIRIGIDA contra
        # el corpus completo (Etapa C, punto 1) para las entidades que sí
        # existen en el corpus pero no llegaron al top-k.
        resultado_premisa = verificar_premisa(pregunta, payloads_top)
        if resultado_premisa.entidades_ausentes:
            en_corpus, _genuinamente_ausentes = separar_entidades_ausentes(
                resultado_premisa.entidades_ausentes, estado.inventario_entidades,
            )
            if en_corpus:
                # Tope a la recuperación dirigida (Etapa D, punto 3): una
                # pregunta con muchas entidades ausentes del top-k no debe
                # poder inflar la respuesta sin límite -- configurable,
                # ver configuracion/motor.yaml::abstencion.capa_b_premisa.max_fragmentos_adicionales.
                max_adicionales = estado.cfg_abs["capa_b_premisa"].get("max_fragmentos_adicionales", 2)
                chunk_ids_vistos = {p["chunk_id"] for p in payloads_top}
                agregados = 0
                for entidad in en_corpus:
                    if agregados >= max_adicionales:
                        break
                    filtro = construir_filtro_entidad(entidad["valor_norm"])
                    res_dirigida = buscar(col, pregunta, modo=cfg_rec["modo"], limit=1,
                                           vector_precomputado=vq, query_filter=filtro)
                    for i, p in enumerate(res_dirigida.payloads):
                        if p["chunk_id"] not in chunk_ids_vistos and agregados < max_adicionales:
                            payloads_top.append(p)
                            scores_top.append(res_dirigida.scores[i])
                            chunk_ids_vistos.add(p["chunk_id"])
                            agregados += 1
                # Re-verifica con el conjunto fusionado -- las entidades que
                # sí estaban en el corpus deberían quedar respaldadas ahora;
                # las genuinamente ausentes del corpus (o las que no cupieron
                # bajo el tope) siguen bloqueando.
                resultado_premisa = verificar_premisa(pregunta, payloads_top)

        decision = decidir_capas_abstencion(
            senales, umbral_fuera_dominio, umbral_confianza_alta, resultado_premisa,
            zona_gris_modo=zona_gris_modo, grounding_dominio=grounding_dominio,
        )
        if decision.resultado == "abstiene":
            return _respuesta_abstencion(
                "premisa" if decision.motivo == "premisa" else "generico",
                confianza, latencia_ms(), entidad_texto=decision.entidad_texto,
            )

        # Selección de las oraciones más pertinentes de cada fragmento
        # (Etapa B, punto 2) + orden GLOBAL entre fragmentos, con la oración
        # que contiene una entidad LITERAL de la pregunta siempre primero
        # (Etapa D, punto 2 -- antes el score de similitud, ciego a
        # entidades cortas como "3,9", podía anteponer una mención lateral)
        # -- nunca reescribe, solo recorta y reordena bloques ya literales.
        entidades_pregunta = extraer_entidades(pregunta)
        payloads_recortados = [
            recortar_payload_a_texto_pertinente(
                p, pregunta, cfg_red["longitud_maxima_fragmento_chars"],
                metodo=cfg_red["metodo_seleccion"], modelo_st=col.modelo_st, prefijo_query=prefijo_query,
                entidades_pregunta=entidades_pregunta,
            )
            for p in payloads_top
        ]
        payloads_recortados, scores_top = ordenar_por_pertinencia_global(payloads_recortados, scores_top)

        if decision.resultado == "relacionado":
            respuesta_texto = redactar_zona_gris(payloads_recortados)
            plan_resp: str = "zona_gris"
            estado_resp: str = "relacionado"
        else:
            plan = elegir_plan(pregunta, payloads_recortados)
            respuesta_texto = redactar(plan, payloads_recortados)
            plan_resp = "extractivo"
            estado_resp = "ok"

        resultado_guardia = verificar_fidelidad(respuesta_texto, payloads_recortados)
        if not resultado_guardia.fiel:
            # sección 6.3: si falla la guardia, no se muestra -- se abstiene.
            return _respuesta_abstencion("guardia", confianza, latencia_ms())

        fragmentos_resp = _fragmentos_respuesta(payloads_recortados, scores_top)

        return RespuestaConsulta(
            estado=estado_resp, nivel_servicio="normal", respuesta=respuesta_texto,
            plan=plan_resp, fragmentos=fragmentos_resp, confianza=confianza,
            latencia_ms=latencia_ms(),
        )
    finally:
        estado.control_admision.liberar()
