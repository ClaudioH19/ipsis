"""WordNet local: expansión de recuperación, separada de la validación del foco."""
from __future__ import annotations

import functools
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from importlib.resources import files
from types import SimpleNamespace

from ipsis.lenguaje.texto import terminos


@dataclass(frozen=True)
class GrupoLexico:
    fuente: str
    sentido: str
    pos: str
    formas: tuple[str, ...]
    raices: tuple[str, ...]


@functools.lru_cache(maxsize=16)
def indice_automatico(codigo: str, stemmer: str | None) -> dict[str, tuple[GrupoLexico, ...]]:
    """Una lectura por idioma/stemmer. Nunca abre los diccionarios de desarrollo."""
    recurso = files("ipsis.recursos").joinpath("sinonimos", f"{codigo}.tsv")
    if not recurso.is_file():
        return {}
    paquete = SimpleNamespace(stemmer=stemmer)
    # Un sentido descartado por tamaño sigue haciendo ambiguo al lema.
    # El léxico maestro se lee solo para contar pertenencias, nunca para expandir.
    maestro = files("ipsis.recursos").joinpath("sinonimos", f"{codigo}.lexicon.tsv")
    sentidos: Counter[str] = Counter()
    for linea in maestro.read_text(encoding="utf-8").splitlines():
        if linea and not linea.startswith("#"):
            sentidos.update(f for f in linea.split("\t")[2:] if f.isalpha() and f.islower())
    salida: dict[str, list[GrupoLexico]] = {}
    bloqueadas = set()
    fuente = ""
    for linea in recurso.read_text(encoding="utf-8").splitlines():
        if linea.startswith("# source\t"):
            fuente = linea.split("\t")[1]
        if not linea or linea.startswith("#"):
            continue
        sentido, pos, *formas = linea.split("\t")
        rs = tuple(terminos(f, paquete)[0] for f in formas)
        bloqueadas.update(r for f, r in zip(formas, rs) if sentidos[f] != 1)
        pares = [(f, r) for f, r in zip(formas, rs) if sentidos[f] == 1]
        if len(pares) < 2:
            continue
        formas, rs = zip(*pares)
        grupo = GrupoLexico(fuente, sentido, pos, tuple(formas), rs)
        for raiz in set(rs):
            salida.setdefault(raiz, []).append(grupo)
    return {r: tuple(gs) for r, gs in salida.items() if r not in bloqueadas}


def expansion_automatica(pregunta: str, paquete, estadisticas) -> tuple[dict[str, list[str]], list[dict]]:
    """Solo OOV, sin relación ni correcciones manuales, y un único sentido por raíz.

    Una colisión del stemmer entre sentidos bloquea la expansión. No se unen
    grupos, ni se usan formas morfológicas como equivalencias semánticas.
    """
    from ipsis.lenguaje.consultas import (
        comprender, plano, terminos_de_contenido, terminos_genericos, _grupos_por_raiz,
    )

    if paquete is None or getattr(paquete, "respaldo", False):
        return {}, []
    df = getattr(estadisticas, "df", None)
    if df is None:
        return {}, []
    indice = indice_automatico(paquete.codigo.split("-")[0], paquete.stemmer)
    relacion = comprender(pregunta, paquete).terminos_relacion
    # La conversación ya calculó estos términos. Reutilizar su caché evita
    # repetir stemming y respeta las frases ya resueltas por el proyecto.
    contenido = set(terminos_de_contenido(pregunta, paquete, estadisticas)) - relacion - terminos_genericos(paquete)
    manuales = _grupos_por_raiz(paquete)
    propios = {r for g in getattr(paquete, "sinonimos_dominio", ()) for f in g
               if len(plano(f).split()) == 1 for r in terminos(f, paquete)}
    salida, detalles = {}, []
    for palabra in plano(pregunta).split():
        rs = terminos(palabra, paquete)
        if len(rs) != 1:
            continue
        raiz = rs[0]
        grupos = indice.get(raiz, ())
        if df.get(raiz, 0) or raiz not in contenido or raiz in manuales or raiz in propios or len(grupos) != 1:
            continue
        grupo = grupos[0]
        presentes = [f for f, r in zip(grupo.formas, grupo.raices)
                     if df.get(r, 0) and len(indice.get(r, ())) == 1]
        if presentes:
            salida[palabra] = presentes
            detalles.append({"palabra": palabra, "fuente": grupo.fuente, "sentido": grupo.sentido,
                             "pos": grupo.pos, "formas": presentes})
    return salida, detalles


def expansion_dominio(pregunta: str, paquete, estadisticas) -> dict[str, list[str]]:
    """Coincidencia de frase completa: «orden de compra» no equivale a «orden»."""
    from ipsis.lenguaje.consultas import comprender, plano

    df = getattr(estadisticas, "df", {})
    relacion = comprender(pregunta, paquete).terminos_relacion
    texto = plano(pregunta)
    stop = set(getattr(paquete, "stopwords", ()))
    salida = {}
    for grupo in getattr(paquete, "sinonimos_dominio", ()):
        formas = [(plano(f), tuple(r for p in plano(f).split() if p not in stop for r in terminos(p, paquete)))
                  for f in grupo]
        for forma, rs in formas:
            if (not rs or relacion.intersection(rs) or any(df.get(r, 0) for r in rs)
                    or not re.search(rf"(?<!\w){re.escape(forma)}(?!\w)", texto)):
                continue
            presentes = [f for f, otras in formas if otras and all(df.get(r, 0) for r in otras)]
            if presentes:
                salida[forma] = presentes
    return salida


def huella_lexica(paquete) -> str:
    """Versión de comportamiento + reglas efectivas + bytes del TSV activo."""
    datos = paquete.model_dump(exclude={"nombre", "mensajes", "interfaz", "contracciones",
                                       "golden_instrucciones", "plantillas_legado"})
    # La primera intención coincidente gana: ordenar las claves al serializar
    # no debe ocultar un cambio de esa prioridad.
    datos["orden_intenciones"] = list(paquete.intenciones)
    h = hashlib.sha256(b"ipsis-lexical-runtime-v6\n")
    h.update(json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    if not paquete.respaldo:
        for sufijo in (".tsv", ".lexicon.tsv"):
            recurso = files("ipsis.recursos").joinpath("sinonimos", f"{paquete.codigo.split('-')[0]}{sufijo}")
            if recurso.is_file():
                h.update(recurso.read_bytes())
    return "sha256:" + h.hexdigest()
