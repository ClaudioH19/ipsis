"""Redacción de la respuesta con plantillas y conectores fijos.

Nunca genera texto: une fragmentos literales del corpus con conectores y
citas declarados en la configuración del proyecto.
"""
from __future__ import annotations

import zlib
from copy import deepcopy

from rag.consulta.etapas.base import _Etapa

# ==========================================================================
# REDACCION (sección 6.2 — plantillas y conectores fijos, nunca texto libre)
# ==========================================================================
def cargar_plantillas(paquete, dominio: dict | None = None) -> dict:
    """Textos fijos del asistente a partir del paquete de idioma.

    Devuelve conectores, mensajes de abstención y textos conversacionales.
    Con ``dominio`` (``configuracion/asistente.yaml``) sustituye
    ``{nombre_asistente}`` y ``{descripcion_dominio}`` en las respuestas
    conversacionales y aplica las contracciones del idioma (``descripcion_dominio``
    puede empezar con artículo: «de el manual» -> «del manual»).
    """
    mensajes = paquete.mensajes
    datos = {
        "conectores": deepcopy(mensajes.conectores),
        "abstencion": {
            "generico": mensajes.sin_respuesta,
            "premisa_no_encontrada": mensajes.premisa_no_encontrada,
            "zona_gris_intro": mensajes.relacionado_intro,
            "foco_ausente": mensajes.relacionado_foco_ausente,
        },
        "conversacional": paquete.conversacional.model_dump(mode="python"),
    }
    if dominio is None:
        return datos
    variables = {
        "nombre_asistente": dominio.get("nombre_asistente", "el asistente"),
        "descripcion_dominio": dominio.get("descripcion_dominio", "los documentos cargados"),
    }

    def sustituir(texto: str) -> str:
        salida = texto.format(**variables)
        for forma, contraccion in paquete.contracciones.items():
            salida = salida.replace(forma, contraccion)
        return salida

    respuestas = datos["conversacional"].get("respuestas", {})
    for categoria, valor in respuestas.items():
        # Cada categoría puede declarar un texto suelto o varias variantes.
        respuestas[categoria] = sustituir(valor) if isinstance(valor, str) else [sustituir(t) for t in valor]
    return datos


def _cargar_plantillas() -> dict:
    """Textos del idioma activo (o español) para llamadas fuera de ``Motor``.

    Sustituye las variables con ``configuracion/asistente.yaml`` del directorio
    actual, igual que el motor.
    """
    from rag.configuracion.carga import cargar_dominio
    from rag.lenguaje.entidades import idioma_activo
    from rag.lenguaje.paquete import cargar_paquete

    return cargar_plantillas(idioma_activo() or cargar_paquete("es"), cargar_dominio())


def _elegir_variante(opciones: list[str], semilla: str, evitar: set[str] | None = None) -> str:
    """Elige una de varias formulaciones FIJAS de forma determinista.

    Consume: la lista declarada en el paquete de idioma, una cadena
    que sirve de semilla (el ``chunk_id`` del fragmento, o la pregunta) y,
    opcionalmente, las variantes ya usadas en esta misma respuesta. Produce:
    una de las opciones.

    El hash es de la semilla, no aleatorio: la misma pregunta sobre el mismo
    indice devuelve SIEMPRE el mismo texto. Sin eso, la respuesta cambiaria
    entre corridas y ningun test podria fijarla. ``evitar`` solo desplaza la
    eleccion al siguiente candidato, para que una respuesta con tres
    fragmentos no repita la misma frase tres veces."""
    if not opciones:
        return ""
    evitar = evitar or set()
    inicio = zlib.crc32(semilla.encode("utf-8")) % len(opciones)
    for desplazamiento in range(len(opciones)):
        candidato = opciones[(inicio + desplazamiento) % len(opciones)]
        if candidato not in evitar:
            return candidato
    return opciones[inicio]


def _fragmentos_para_el_texto(fragmentos: list[dict], cfg: dict) -> list[dict]:
    """Decide QUE fragmentos entran en la prosa de la respuesta.

    Consume: los fragmentos recuperados (ya ordenados por pertinencia) y la
    seccion ``redaccion:`` de ``configuracion/motor.yaml``. Produce: el
    subconjunto que se concatena en el texto.

    Antes se concatenaban los ``top_k`` completos, siempre. Con top_k=3 eso
    producia respuestas de tres bloques donde el tercero solia ser de otra
    seccion del documento y no venia al caso -- mas texto, menos precision.
    Ahora un fragmento posterior al primero entra solo si su score alcanza
    una fraccion del score del primero, y con un tope duro de cuantos
    caben.

    IMPORTANTE: esto acorta la PROSA, no esconde evidencia. El campo
    ``fragmentos`` de la respuesta HTTP sigue trayendo todos los
    recuperados, con su texto literal y sus offsets, que es lo que el widget
    despliega como citas. Nada de lo recuperado deja de estar disponible.

    Ambos valores son decisiones de diseno NO MEDIDAS (no hay golden set en
    el repositorio con el que medirlas); por eso son configurables y estan
    documentadas como tales en ``configuracion/motor.yaml``."""
    if not fragmentos:
        return []
    tope = int(cfg.get("max_fragmentos_en_respuesta", 0) or 0)
    minimo_relativo = float(cfg.get("score_relativo_minimo", 0.0) or 0.0)
    primero = fragmentos[0]
    salida = [primero]
    referencia = float(primero.get("score") or 0.0)
    for frag in fragmentos[1:]:
        if tope and len(salida) >= tope:
            break
        if referencia > 0 and minimo_relativo > 0:
            if float(frag.get("score") or 0.0) < referencia * minimo_relativo:
                continue
        salida.append(frag)
    return salida


def _formatear_cita(frag: dict, estilo: str) -> str:
    """Cita que va DENTRO del texto de la respuesta.

    ``completa`` trae documento y ruta de seccion; ``breve``, solo el
    documento; ``ninguna`` no pone nada en el texto. En los tres casos la
    cita exacta -- documento, seccion y offsets -- sigue viajando en el
    campo estructurado ``fragmentos`` de la respuesta HTTP: esto decide
    cuanto se repite dentro de la prosa, no si se cita."""
    if estilo == "ninguna":
        return ""
    if estilo == "breve":
        return f"(Fuente: {frag['doc_titulo']})"
    seccion = " > ".join(frag.get("seccion_path") or []) or "(sin seccion)"
    return f"(Fuente: {frag['doc_titulo']}, seccion: {seccion})"


def _ensamblar_fragmentos_con_citas(
    fragmentos: list[dict],
    con_apertura: bool = True,
    *,
    plantillas: dict | None = None,
    cfg_redaccion: dict | None = None,
) -> str:
    """Concatena el texto LITERAL de cada fragmento (nunca lo reescribe) con
    su cita y, entre fragmentos, un conector FIJO de
    los ``mensajes`` del paquete de idioma -- la unica "redaccion" permitida.

    La CATEGORIA del conector la decide metadata determinista calculada en
    la ingesta (``tiene_excepcion``/``tiene_condicion``), nunca un modelo;
    la VARIANTE dentro de la categoria sale de ``_elegir_variante``. Los
    conectores cierran en dos puntos a proposito: el texto que sigue es una
    cita literal que empieza donde el documento empiece, y un conector
    subordinante ("Siempre que,") producia frases rotas.

    Compartida por ``redactar`` (estado ``ok``) y ``redactar_zona_gris``
    (estado ``relacionado``)."""
    from rag.configuracion.carga import config_redaccion

    plantillas = plantillas or _cargar_plantillas()
    conectores = plantillas["conectores"]
    cfg = cfg_redaccion or config_redaccion()
    estilo_cita = str(cfg.get("cita_en_texto", "completa"))

    elegidos = _fragmentos_para_el_texto(fragmentos, cfg)
    usadas: set[str] = set()
    partes: list[str] = []

    if con_apertura and cfg.get("incluir_apertura", False) and conectores.get("apertura"):
        semilla = str(elegidos[0].get("chunk_id", "")) if elegidos else ""
        apertura = _elegir_variante(list(conectores["apertura"]), semilla)
        if apertura:
            partes.append(apertura)
            usadas.add(apertura)

    for i, frag in enumerate(elegidos):
        texto = frag["texto"].strip()
        cita = _formatear_cita(frag, estilo_cita)
        cuerpo = f"{texto} {cita}." if cita else texto
        if i == 0:
            partes.append(cuerpo)
            continue
        if frag.get("tiene_excepcion"):
            categoria = "excepcion"
        elif frag.get("tiene_condicion"):
            categoria = "condicion"
        else:
            categoria = "complemento"
        opciones = list(conectores.get(categoria) or [])
        conector = _elegir_variante(opciones, str(frag.get("chunk_id", i)), usadas)
        if conector:
            usadas.add(conector)
            partes.append(f"{conector} {cuerpo}")
        else:
            partes.append(cuerpo)
    return " ".join(partes)


def redactar(
    fragmentos: list[dict],
    *,
    plantillas: dict | None = None,
    cfg_redaccion: dict | None = None,
) -> str:
    """Respuesta normal (estado ``ok``): fragmentos literales + citas +
    conectores fijos, sin ningún encabezado adicional."""
    return _ensamblar_fragmentos_con_citas(
        fragmentos,
        plantillas=plantillas,
        cfg_redaccion=cfg_redaccion,
    )


def redactar_zona_gris(
    fragmentos: list[dict],
    *,
    plantillas: dict | None = None,
    cfg_redaccion: dict | None = None,
    termino_ausente: str | None = None,
) -> str:
    """Estado propio ``"relacionado"`` (Etapa C, punto 2 del encargo del
    coordinador -- ACTIVO por defecto desde esta etapa): cuando la pregunta
    pasa las dos capas de abstención pero el score denso es "intermedio"
    (ni claramente fuera de dominio ni un match fuerte), en vez de
    abstenerse se muestran los fragmentos más pertinentes enmarcados con un
    conector fijo que dice explícitamente que NO es una respuesta directa
    -- con citas literales y el encuadre explícito, mostrar texto
    relacionado no es una afirmación directa.
    Sigue siendo texto literal + cita; el único agregado es la frase de
    encabezado fija (``mensajes.relacionado_intro`` del paquete de idioma).
    Configurable: ``configuracion/motor.yaml::abstencion.zona_gris.modo`` en
    {"relacionado" (default), "abstenerse"} -- dominios de costo de error
    ALTO pueden volver a "abstenerse" por configuración, sin tocar código."""
    plantillas = plantillas or _cargar_plantillas()
    # Si falta el término de foco, el mensaje lo nombra («No encontré información sobre «X»»).
    if termino_ausente:
        intro = plantillas["abstencion"]["foco_ausente"].format(termino=termino_ausente)
    else:
        intro = plantillas["abstencion"]["zona_gris_intro"]
    # Sin apertura: este estado ya trae su propio encabezado fijo, y apilar
    # los dos producia "No encontre una respuesta directa. Esto es lo que
    # dicen los documentos sobre el tema: Encontre esto en el documento:".
    return f"{intro} {_ensamblar_fragmentos_con_citas(fragmentos, con_apertura=False, plantillas=plantillas, cfg_redaccion=cfg_redaccion)}"


def construir_mensaje_abstencion(
    motivo: str,
    entidad_texto: str | None = None,
    plantillas: dict | None = None,
) -> str:
    """Mensaje de abstención SIEMPRE listo para mostrar a un usuario final
    (nunca ``null`` en la respuesta HTTP: el servicio puede servir a un
    frontend externo -- plugin/widget de chat -- que necesita un string,
    no un estado vacío que interpretar). ``motivo`` en
    {"fuera_dominio", "premisa", "guardia", "sin_fragmentos"}; solo
    "premisa" usa ``entidad_texto`` (copiado LITERAL de la pregunta del
    usuario, nunca inventado)."""
    textos = (plantillas or _cargar_plantillas())["abstencion"]
    if motivo == "premisa" and entidad_texto:
        return textos["premisa_no_encontrada"].format(entidad=entidad_texto)
    return textos["generico"]


class EtapaRedaccion(_Etapa):
    """Arma el texto con plantillas: respuesta directa o pasajes relacionados."""

    nombre = "redaccion"

    def ejecutar(self, ctx) -> None:
        from rag.consulta.etapas.verificacion import verificar_respaldo_dato_solicitado
        from rag.nucleo.esquemas import AssistantState

        m = self.motor
        if ctx.decision.resultado == "relacionado":
            termino = ctx.decision.entidad_texto if ctx.decision.motivo == "foco_ausente" else None
            ctx.texto = redactar_zona_gris(ctx.payloads, plantillas=m.plantillas,
                                           cfg_redaccion=m.configuracion_redaccion, termino_ausente=termino)
            ctx.estado = AssistantState.RELACIONADO
            ctx.plan = "zona_gris"
            return
        respaldo = verificar_respaldo_dato_solicitado(ctx.pregunta, ctx.payloads)
        if not respaldo.fiel:
            ctx.diagnostico["advertencias"].extend(respaldo.motivos)
            ctx.resultado = m._abstener("guardia", ctx.confianza, ctx.latencia_ms(), diagnostico=ctx.diagnostico)
            return
        ctx.texto = redactar(ctx.payloads, plantillas=m.plantillas, cfg_redaccion=m.configuracion_redaccion)
        ctx.estado = AssistantState.RESPUESTA_DIRECTA
        ctx.plan = "extractivo"
