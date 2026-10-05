"""``ipsis deploy prepare``: una carpeta lista para copiar a un VPS.

Reúne lo que el servicio necesita en ejecución (configuración con
personalidad, estilos, calibración y avatares importados; documentos; índice)
y genera desde ``ipsis/recursos/despliegue/preparar/`` el ``Dockerfile``, el
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

from ipsis import __version__
from ipsis.configuracion import rutas
from ipsis.recursos.mensajes import t

MARCA = ".ipsis-despliegue"  # identifica una carpeta generada (se puede regenerar con --force)
DOMINIO_EJEMPLO = "asistente.tu-dominio.cl"
IDIOMAS_LEEME = ("es", "en", "pt")
# Dentro de .ipsis solo viaja el índice: registros, snapshots y vistas previas quedan fuera.
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
    return files("ipsis.recursos").joinpath("despliegue", "preparar", nombre).read_text(encoding="utf-8")


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
        raise DespliegueInvalido(t("app.domain_only_name", domain=dominio, example=DOMINIO_EJEMPLO))
    if not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+", dominio):
        raise DespliegueInvalido(t("app.domain_invalid", domain=dominio))
    return dominio


def preparar_despliegue(destino: str = "dist", *, dominio: str | None = None, wheel: str | None = None,
                        forzar: bool = False) -> ResumenDespliegue:
    """Genera la carpeta de despliegue en ``destino`` (relativa al proyecto)."""
    from ipsis.aplicacion.diagnostico import diagnosticar
    from ipsis.aplicacion.modo import modo_servicio
    from ipsis.aplicacion.widget import snippet_widget
    from ipsis.configuracion.carga import cargar_dominio

    if not Path(rutas.ASISTENTE).is_file():
        raise DespliegueInvalido(t("app.deploy_no_project"))
    salida = Path(destino).resolve()
    if salida == Path.cwd().resolve() or Path.cwd().resolve().is_relative_to(salida):
        raise DespliegueInvalido(t("app.deploy_contains_project", target=destino))
    if salida.exists() and any(salida.iterdir()):
        if not (salida / MARCA).is_file():
            raise DespliegueInvalido(t("app.deploy_not_empty", path=salida))
        if not forzar:
            raise DespliegueInvalido(t("app.deploy_exists", path=salida))
        shutil.rmtree(salida)
    if wheel is not None and not (Path(wheel).is_file() and wheel.endswith(".whl")):
        raise DespliegueInvalido(t("app.wheel_invalid", wheel=wheel))
    dominio = _validar_dominio(dominio) if dominio else DOMINIO_EJEMPLO

    datos = cargar_dominio()
    perfil = str(datos.get("perfil") or "medium")
    resumen = ResumenDespliegue(salida, perfil, dominio)
    salida.mkdir(parents=True, exist_ok=True)

    for origen in COPIAR:
        if Path(origen).is_dir():
            shutil.copytree(origen, salida / origen, ignore=shutil.ignore_patterns("*.lock", ".lock"))
    (salida / rutas.REGISTRO_CONSULTAS).parent.mkdir(parents=True, exist_ok=True)

    (salida / "paquete").mkdir()
    if wheel is not None:
        shutil.copy2(wheel, salida / "paquete" / Path(wheel).name)
    # Sin --wheel, la imagen instala desde el repositorio público (rama por defecto).
    paquete = f"ipsis @ git+{modo_servicio(entorno={}).fuente}.git"

    idioma = _idioma_leeme(datos.get("idioma", "es"))
    valores = {
        "perfil": perfil, "dominio": dominio, "nombre": _nombre_servicio(datos.get("nombre_asistente", "")),
        "nombre_asistente": datos.get("nombre_asistente", "ipsis"), "paquete": paquete,
        "snippet": snippet_widget(api=f"https://{dominio}"),
    }
    generados = {
        "Dockerfile": "Dockerfile", "docker-compose.yml": "docker-compose.yml", "Caddyfile": "Caddyfile",
        ".env.ejemplo": f"env.ejemplo.{idioma}", "LEEME_despliegue.md": f"LEEME_despliegue.{idioma}.md",
    }
    for nombre, plantilla in generados.items():
        # Siempre LF: estos archivos se usan en un servidor Linux (un \r final rompería el token de .env).
        (salida / nombre).write_text(_rellenar(_plantilla(plantilla), valores), encoding="utf-8", newline="\n")
    (salida / MARCA).write_text(f"ipsis {__version__}\n", encoding="utf-8")

    resumen.archivos = sorted(p.relative_to(salida).as_posix() for p in salida.rglob("*") if p.is_file())
    if dominio == DOMINIO_EJEMPLO:
        resumen.avisos.append(t("app.deploy_no_domain", example=DOMINIO_EJEMPLO))
    if wheel is None:
        resumen.avisos.append(t("app.deploy_no_wheel"))
    if not Path(rutas.INDICE).is_dir():
        resumen.avisos.append(t("app.deploy_no_index"))
    reporte = diagnosticar(abrir_indice=False)
    for chequeo in reporte.errores:
        acciones = f" ({'; '.join(chequeo.acciones)})" if chequeo.acciones else ""
        resumen.avisos.append(f"{chequeo.nombre}: {chequeo.mensaje}{acciones}")
    return resumen


__all__ = ["DOMINIO_EJEMPLO", "DespliegueInvalido", "MARCA", "ResumenDespliegue", "preparar_despliegue"]
