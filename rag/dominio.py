"""Perfiles declarativos para extender la extracción sin editar Python.

Las reglas propias de un dominio se declaran en
``configuracion/dominios/<nombre>/perfil.yaml`` y son interpretadas por un
motor genérico:

- ``extractores_regex``: cada regla es un patrón regex con grupos
  nombrados (``(?P<nombre>...)``) y una plantilla ``valor_norm`` que los
  referencia. Los segmentos entre corchetes ``[...]`` son OPCIONALES: se
  omiten completos si algún grupo que citan no matcheó -- así
  ``"semana_{n1}[_{conector}_{n2}]"`` da ``"semana_4"`` sin rango o
  ``"semana_7_a_10"`` con uno, sin necesitar dos reglas separadas.
  ``transform`` aplica una función determinista a un grupo antes de
  formatear (por ahora: ``romano_a_num``, para números romanos I-IV).
- ``organismos``: lista cerrada de nombres/siglas (igual criterio que la
  lista original: coincidencia exacta, normalizada a minúsculas con
  espacios por guion bajo).

El núcleo sigue extrayendo, sin depender de ningún perfil, las entidades
GENÉRICAS de un documento normativo/técnico cualquiera: números, porcentajes,
fechas, plazos, notas, artículos y numerales (``rag/reglas_extraccion.py``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

RUTA_DOMINIOS = "configuracion/dominios"
PERFIL_GENERICO = "_generico"

_ROMANOS_A_NUM = {"I": 1, "II": 2, "III": 3, "IV": 4}

_TRANSFORMS = {
    "romano_a_num": lambda v: (str(_ROMANOS_A_NUM.get(v, v)) if v is not None else v),
    "minusculas": lambda v: (v.lower() if v is not None else v),
    "sin_espacios": lambda v: (v.replace(" ", "_") if v is not None else v),
}

_RE_OPCIONAL = re.compile(r"\[([^\[\]]*)\]")
_RE_NOMBRE_GRUPO = re.compile(r"\{(\w+)\}")


def _renderizar_valor_norm(plantilla: str, grupos: dict[str, str | None]) -> str:
    """Formatea ``valor_norm`` a partir de los grupos capturados, quitando
    los segmentos ``[...]`` opcionales cuyo(s) grupo(s) no matchearon."""

    def _sub_opcional(m: re.Match) -> str:
        segmento = m.group(1)
        nombres = _RE_NOMBRE_GRUPO.findall(segmento)
        if any(grupos.get(n) is None for n in nombres):
            return ""
        return segmento.format(**grupos)

    sin_opcionales = _RE_OPCIONAL.sub(_sub_opcional, plantilla)
    return sin_opcionales.format(**{k: (v if v is not None else "") for k, v in grupos.items()})


@dataclass
class ReglaEntidad:
    tipo: str
    patron: re.Pattern
    valor_norm_tpl: str
    transform: dict[str, str] = field(default_factory=dict)
    glosa: str | None = None
    """Descripción legible del tipo (p.ej. "saber o competencia evaluada"),
    opcional en el YAML del perfil. La usa
    ``rag/paquete_revision_externa.py::tipos_hecho_legible`` para mostrarle al
    revisor externo un texto legible en vez del nombre crudo del tipo; si el
    perfil no la declara, el llamador usa un texto de repuesto genérico."""

    def extraer(self, texto: str) -> list[tuple[str, str, str, int]]:
        """Devuelve tuplas ``(tipo, texto_matcheado, valor_norm, offset)``."""
        salida = []
        for m in self.patron.finditer(texto):
            grupos_crudos = m.groupdict()
            grupos: dict[str, str | None] = {}
            for nombre, valor in grupos_crudos.items():
                fn = _TRANSFORMS.get(self.transform.get(nombre, ""))
                grupos[nombre] = fn(valor) if fn else valor
            valor_norm = _renderizar_valor_norm(self.valor_norm_tpl, grupos)
            salida.append((self.tipo, m.group(0), valor_norm, m.start(0)))
        return salida


def _extraer_organismos(texto: str, organismos: list[str]) -> list[tuple[str, str, str, int]]:
    if not organismos:
        return []
    patron = re.compile(
        r"\b(" + "|".join(re.escape(o) for o in sorted(organismos, key=len, reverse=True)) + r")\b"
    )
    salida = []
    for m in patron.finditer(texto):
        norm = m.group(0).lower().replace(" ", "_")
        salida.append(("organismo", m.group(0), norm, m.start(0)))
    return salida


@dataclass
class PerfilDominio:
    nombre: str
    nombre_asistente: str = "el asistente"
    descripcion_dominio: str = "los documentos cargados"
    idioma: str = "es"
    organismos: list[str] = field(default_factory=list)
    reglas: list[ReglaEntidad] = field(default_factory=list)

    def extraer_entidades_extra(self, texto: str) -> list:
        """Entidades específicas de este dominio, en el mismo formato que
        ``rag/reglas_extraccion.py::Entidad`` (import tardío para evitar un
        ciclo: ``reglas_extraccion`` no necesita conocer esta clase)."""
        from rag.reglas_extraccion import Entidad

        crudas: list[tuple[str, str, str, int]] = []
        for regla in self.reglas:
            crudas.extend(regla.extraer(texto))
        crudas.extend(_extraer_organismos(texto, self.organismos))
        return [Entidad(tipo=t, texto=txt, valor_norm=vn, offset=off) for t, txt, vn, off in crudas]

    def tipos_aportados(self) -> set[str]:
        """Nombres de tipo de entidad que este perfil agrega por encima de
        los genéricos del núcleo: el ``tipo`` de cada regla declarada, más
        ``"organismo"`` si el perfil trae una lista cerrada de organismos.
        La usa ``rag/reglas_extraccion.py::tipos_con_regla`` (Etapa Plugin,
        Tarea 2a) para que ningún módulo de evaluación tenga que hardcodear
        los tipos de UN perfil en particular."""
        tipos = {r.tipo for r in self.reglas}
        if self.organismos:
            tipos.add("organismo")
        return tipos

    def glosas_extra(self) -> dict[str, str]:
        """``{tipo: glosa}`` para las reglas de este perfil que declaran una
        ``glosa`` explícita en su YAML. Un tipo sin ``glosa`` no aparece aquí
        -- el llamador (``rag/paquete_revision_externa.py::tipos_hecho_legible``)
        decide el texto de repuesto, genérico y sin depender de este
        dominio."""
        return {r.tipo: r.glosa for r in self.reglas if r.glosa}


def _perfiles_disponibles(base: str) -> list[str]:
    ruta = Path(base)
    if not ruta.exists():
        return []
    return sorted(p.name for p in ruta.iterdir() if p.is_dir() and (p / "perfil.yaml").exists())


def cargar_perfil(nombre: str, base: str = RUTA_DOMINIOS) -> PerfilDominio:
    """Carga ``<base>/<nombre>/perfil.yaml``. Falla fuerte y explícito si no
    existe -- mismo criterio que ``rag/corpus.py::cargar_vocabulario_bm25``:
    nunca se inventa un perfil vacío en silencio cuando se pidió uno con
    nombre."""
    ruta = Path(base) / nombre / "perfil.yaml"
    if not ruta.exists():
        disponibles = _perfiles_disponibles(base)
        raise FileNotFoundError(
            f"no existe el perfil de dominio {nombre!r} en {ruta!r}. "
            f"Perfiles disponibles: {disponibles or '(ninguno)'}"
        )
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    reglas = []
    for r in datos.get("extractores_regex", []):
        flags = re.IGNORECASE if r.get("ignorecase", True) else 0
        reglas.append(ReglaEntidad(
            tipo=r["tipo"],
            patron=re.compile(r["patron"], flags),
            valor_norm_tpl=r["valor_norm"],
            transform=r.get("transform", {}),
            glosa=r.get("glosa"),
        ))
    return PerfilDominio(
        nombre=nombre,
        nombre_asistente=datos.get("nombre_asistente", nombre),
        descripcion_dominio=datos.get("descripcion_dominio", "los documentos cargados"),
        idioma=datos.get("idioma", "es"),
        organismos=list(datos.get("organismos", [])),
        reglas=reglas,
    )


def cargar_perfil_generico(base: str = RUTA_DOMINIOS) -> PerfilDominio:
    """Perfil sin reglas propias (``configuracion/dominios/_generico/``): usado por
    ``rag init`` como punto de partida para un dominio nuevo -- el núcleo ya
    extrae las entidades genéricas sin necesitar ninguna regla adicional."""
    return cargar_perfil(PERFIL_GENERICO, base)


# ---------------------------------------------------------------------------
# Semilla EMBEBIDA para `rag init` (corrección tras revisión independiente,
# Etapa Plugin): un directorio de trabajo VACÍO no tiene
# `configuracion/dominios/_generico/perfil.yaml` -- antes, `rag init` (vía
# `rag/configuracion.py::actualizar_dominio`) asumía que ya existía para
# poder validar el perfil por defecto, lo que en la práctica solo
# funcionaba DENTRO de una copia de este repo. El contenido es idéntico al
# de `configuracion/dominios/_generico/perfil.yaml` de este proyecto (que sigue existiendo
# tal cual, usado por las pruebas de este mismo repo) -- pero
# embebido en Python, no leído del árbol del proyecto en tiempo de
# ejecución, para que `rag init` funcione en cualquier directorio.
# ---------------------------------------------------------------------------
def escribir_perfil_generico_si_falta(base: str = RUTA_DOMINIOS) -> bool:
    """Escribe el perfil global incluido en el paquete si todavía no existe."""
    from rag.recursos import leer_plantilla

    ruta = Path(base) / PERFIL_GENERICO / "perfil.yaml"
    if ruta.exists():
        return False
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(leer_plantilla("dominios/_generico/perfil.yaml"), encoding="utf-8")
    return True
