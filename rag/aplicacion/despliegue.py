"""``rag desplegar preparar``: una carpeta lista para copiar a un VPS.

Reúne lo que el servicio necesita en ejecución (configuración con
personalidad, estilos, calibración y avatares importados; documentos; índice)
y genera desde ``rag/recursos/despliegue/preparar/`` el ``Dockerfile``, el
``docker-compose.yml`` con un Caddy opcional (perfil ``https``), el
``Caddyfile``, un ``.env.ejemplo`` y ``LEEME_despliegue.md`` en el idioma del
proyecto. Nunca copia secretos ni los registros de consultas.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

from rag import __version__
from rag.configuracion import rutas

MARCA = ".rag-despliegue"  # identifica una carpeta generada (se puede regenerar con --forzar)
DOMINIO_EJEMPLO = "asistente.tu-dominio.cl"
IDIOMAS_LEEME = ("es", "en", "pt")
# Dentro de .rag solo viaja el índice: registros, snapshots y vistas previas quedan fuera.
COPIAR = (rutas.CONFIGURACION, rutas.DOCUMENTOS, rutas.INDICE)


class DespliegueInvalido(ValueError):
    """No se puede preparar el despliegue; el mensaje dice qué hacer."""


@dataclass
class ResumenDespliegue:
    destino: Path
    perfil: str
    dominio: str
    archivos: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _plantilla(nombre: str) -> str:
    return files("rag.recursos").joinpath("despliegue", "preparar", nombre).read_text(encoding="utf-8")


def _rellenar(texto: str, valores: dict[str, str]) -> str:
    for clave, valor in valores.items():
        texto = texto.replace("{{" + clave + "}}", valor)
    return texto


def _nombre_servicio(nombre: str) -> str:
    """Nombre válido para la imagen de Docker a partir del nombre del asistente."""
    limpio = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")
    return limpio[:40] or "asistente"


def _idioma_leeme(idioma: str) -> str:
    base = (idioma or "").lower().split("-")[0]
    return base if base in IDIOMAS_LEEME else "en"


def _validar_dominio(dominio: str) -> str:
    dominio = dominio.strip().lower()
    if dominio.startswith(("http://", "https://")) or "/" in dominio:
        raise DespliegueInvalido(f"--dominio {dominio!r}: escribe solo el nombre, p. ej. {DOMINIO_EJEMPLO}")
    if not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+", dominio):
        raise DespliegueInvalido(f"--dominio {dominio!r} no es un nombre de dominio válido")
    return dominio


def preparar_despliegue(destino: str = "dist", *, dominio: str | None = None, wheel: str | None = None,
                        forzar: bool = False) -> ResumenDespliegue:
    """Genera la carpeta de despliegue en ``destino`` (relativa al proyecto)."""
    from rag.aplicacion.diagnostico import diagnosticar
    from rag.aplicacion.modo import modo_servicio
    from rag.aplicacion.widget import snippet_widget
    from rag.configuracion.carga import cargar_dominio

    if not Path(rutas.ASISTENTE).is_file():
        raise DespliegueInvalido("no hay un proyecto en esta carpeta: ejecuta 'rag init' primero")
    salida = Path(destino).resolve()
    if salida == Path.cwd().resolve() or Path.cwd().resolve().is_relative_to(salida):
        raise DespliegueInvalido(f"{destino!r} contiene al proyecto: elige otra carpeta, p. ej. dist")
    if salida.exists() and any(salida.iterdir()):
        if not (salida / MARCA).is_file():
            raise DespliegueInvalido(f"{salida} no está vacía y no la generó 'rag desplegar preparar': "
                                     "elige otra carpeta")
        if not forzar:
            raise DespliegueInvalido(f"{salida} ya existe: usa --forzar para regenerarla")
        shutil.rmtree(salida)
    if wheel is not None and not (Path(wheel).is_file() and wheel.endswith(".whl")):
        raise DespliegueInvalido(f"--wheel {wheel!r} no es un archivo .whl")
    dominio = _validar_dominio(dominio) if dominio else DOMINIO_EJEMPLO

    datos = cargar_dominio()
    perfil = str(datos.get("perfil") or "medium")
    resumen = ResumenDespliegue(salida, perfil, dominio)
    salida.mkdir(parents=True, exist_ok=True)

    for origen in COPIAR:
        if Path(origen).is_dir():
            shutil.copytree(origen, salida / origen, ignore=shutil.ignore_patterns("*.lock", ".lock"))
    (salida / rutas.INTERNO / "registros").mkdir(parents=True, exist_ok=True)

    (salida / "paquete").mkdir()
    if wheel is not None:
        shutil.copy2(wheel, salida / "paquete" / Path(wheel).name)
    # Sin --wheel, la imagen instala desde el repositorio público (rama por defecto).
    paquete = f"rag-extractivo @ git+{modo_servicio(entorno={}).fuente}.git"

    idioma = _idioma_leeme(datos.get("idioma", "es"))
    valores = {
        "perfil": perfil, "dominio": dominio, "nombre": _nombre_servicio(datos.get("nombre_asistente", "")),
        "nombre_asistente": datos.get("nombre_asistente", "rag-extractivo"), "paquete": paquete,
        "snippet": snippet_widget(api=f"https://{dominio}"),
    }
    generados = {
        "Dockerfile": "Dockerfile", "docker-compose.yml": "docker-compose.yml", "Caddyfile": "Caddyfile",
        ".env.ejemplo": f"env.ejemplo.{idioma}", "LEEME_despliegue.md": f"LEEME_despliegue.{idioma}.md",
    }
    for nombre, plantilla in generados.items():
        (salida / nombre).write_text(_rellenar(_plantilla(plantilla), valores), encoding="utf-8")
    (salida / MARCA).write_text(f"rag-extractivo {__version__}\n", encoding="utf-8")

    resumen.archivos = sorted(p.relative_to(salida).as_posix() for p in salida.rglob("*") if p.is_file())
    if dominio == DOMINIO_EJEMPLO:
        resumen.avisos.append(f"sin --dominio: el Caddyfile usa {DOMINIO_EJEMPLO}; vuelve a preparar con "
                              "--dominio tu-dominio")
    if wheel is None:
        resumen.avisos.append("sin --wheel: la imagen instalará la versión actual del repositorio público; "
                              "para fijar esta versión, construye el wheel (python -m pip wheel . --no-deps) "
                              "y pásalo con --wheel")
    if not Path(rutas.INDICE).is_dir():
        resumen.avisos.append("no hay índice: ejecuta 'rag indexar' y vuelve a preparar")
    reporte = diagnosticar(abrir_indice=False)
    for chequeo in reporte.errores:
        acciones = f" ({'; '.join(chequeo.acciones)})" if chequeo.acciones else ""
        resumen.avisos.append(f"{chequeo.nombre}: {chequeo.mensaje}{acciones}")
    return resumen


__all__ = ["DOMINIO_EJEMPLO", "DespliegueInvalido", "MARCA", "ResumenDespliegue", "preparar_despliegue"]
