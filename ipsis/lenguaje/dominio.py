"""Perfiles declarativos para extender la extracción sin editar Python.

Las reglas propias de un dominio se declaran en
``configuracion/dominio.yaml`` y son interpretadas por un
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
fechas, plazos, decimales, artículos y numerales (``ipsis/lenguaje/entidades.py``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ipsis.configuracion import rutas


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
    opcional en el YAML del perfil. Las herramientas de evaluación la usan
    para mostrar un texto legible en vez del nombre crudo del tipo; si el
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
        ``ipsis/lenguaje/entidades.py::Entidad`` (import tardío para evitar un
        ciclo: ``reglas_extraccion`` no necesita conocer esta clase)."""
        from ipsis.lenguaje.entidades import Entidad

        crudas: list[tuple[str, str, str, int]] = []
        for regla in self.reglas:
            crudas.extend(regla.extraer(texto))
        crudas.extend(_extraer_organismos(texto, self.organismos))
        return [Entidad(tipo=t, texto=txt, valor_norm=vn, offset=off) for t, txt, vn, off in crudas]

    def tipos_aportados(self) -> set[str]:
        """Nombres de tipo de entidad que este perfil agrega por encima de
        los genéricos del núcleo: el ``tipo`` de cada regla declarada, más
        ``"organismo"`` si el perfil trae una lista cerrada de organismos.
        La usa ``ipsis/lenguaje/entidades.py::tipos_con_regla`` para que ningún
        módulo de evaluación tenga que hardcodear los tipos de UN perfil en particular."""
        tipos = {r.tipo for r in self.reglas}
        if self.organismos:
            tipos.add("organismo")
        return tipos

    def glosas_extra(self) -> dict[str, str]:
        """``{tipo: glosa}`` para las reglas de este perfil que declaran una
        ``glosa`` explícita en su YAML. Un tipo sin ``glosa`` no aparece aquí
        -- el llamador decide el texto de repuesto, genérico y sin depender de este
        dominio."""
        return {r.tipo: r.glosa for r in self.reglas if r.glosa}


def cargar_perfil(ruta: str = rutas.DOMINIO) -> PerfilDominio:
    """Carga las reglas propias del proyecto desde ``configuracion/dominio.yaml``.

    El archivo es opcional: si no existe, devuelve un perfil sin reglas y el
    núcleo extrae solo las entidades generales.
    """
    p = Path(ruta)
    datos = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}
    reglas = []
    for r in datos.get("extractores_regex") or []:
        flags = re.IGNORECASE if r.get("ignorecase", True) else 0
        reglas.append(ReglaEntidad(
            tipo=r["tipo"],
            patron=re.compile(r["patron"], flags),
            valor_norm_tpl=r["valor_norm"],
            transform=r.get("transform", {}),
            glosa=r.get("glosa"),
        ))
    return PerfilDominio(
        nombre=p.stem,
        organismos=list(datos.get("organismos") or []),
        reglas=reglas,
    )
