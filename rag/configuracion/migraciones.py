"""Migración de la estructura de archivos de un proyecto a la versión vigente.

``rag.configuracion.esquemas`` migra el contenido de cada YAML en memoria; este
módulo mueve y fusiona archivos en disco. Es idempotente: sobre un proyecto ya
migrado no hace nada. Devuelve la lista de cambios para mostrarla al usuario.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from rag.configuracion import rutas


def _leer_yaml(ruta: Path) -> dict:
    return (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}) if ruta.is_file() else {}


def _escribir_yaml(ruta: Path, datos: dict, encabezado: str = "") -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(encabezado + yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _encabezado(ruta: Path) -> str:
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True) if ruta.is_file() else []
    fin = 0
    for linea in lineas:
        if linea.strip() == "" or linea.lstrip().startswith("#"):
            fin += 1
        else:
            break
    return "".join(lineas[:fin])


def _mover(origen: Path, destino: Path, cambios: list[str], raiz: Path) -> None:
    if not origen.exists():
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origen.is_dir():
        destino.mkdir(parents=True, exist_ok=True)
        for hijo in origen.iterdir():
            objetivo = destino / hijo.name
            if not objetivo.exists():
                shutil.move(str(hijo), str(objetivo))
        if not any(origen.iterdir()):
            origen.rmdir()
    elif not destino.exists():
        shutil.move(str(origen), str(destino))
    cambios.append(f"{origen.relative_to(raiz).as_posix()} -> {destino.relative_to(raiz).as_posix()}")


def _migrar_dominio(raiz: Path, perfil: str, cambios: list[str]) -> None:
    destino = raiz / rutas.DOMINIO
    carpeta_perfiles = raiz / rutas.CONFIGURACION / "dominios"
    viejo_perfil = carpeta_perfiles / perfil / "perfil.yaml"
    viejo_categorias = raiz / rutas.CONFIGURACION / "categorias.yaml"
    if destino.exists() or not (viejo_perfil.exists() or viejo_categorias.exists()):
        return
    datos = _leer_yaml(viejo_perfil)
    for clave in ("nombre_asistente", "descripcion_dominio", "idioma"):
        datos.pop(clave, None)  # la identidad vive en asistente.yaml
    if viejo_categorias.exists():
        datos["taxonomia"] = _leer_yaml(viejo_categorias)
    _escribir_yaml(destino, datos, "# Reglas y taxonomía del dominio (migrado desde perfil.yaml y categorias.yaml).\n")
    cambios.append(f"{rutas.DOMINIO} creado desde dominios/{perfil}/perfil.yaml y categorias.yaml")
    if viejo_perfil.exists():
        shutil.rmtree(viejo_perfil.parent)
    if viejo_categorias.exists():
        viejo_categorias.unlink()
    otros = [p.name for p in carpeta_perfiles.iterdir() if p.is_dir() and p.name != "idiomas"] if carpeta_perfiles.exists() else []
    if otros:
        cambios.append(f"[!] perfiles de dominio no usados que quedaron sin migrar: {otros}")


def migrar_proyecto(raiz: str | Path = ".") -> list[str]:
    """Lleva un proyecto v2 a la estructura v3. Devuelve los cambios hechos."""
    raiz = Path(raiz).resolve()
    cambios: list[str] = []
    asistente = raiz / rutas.ASISTENTE
    if not asistente.is_file():
        return cambios
    datos = _leer_yaml(asistente)
    if int(datos.get("config_version", 0)) < 3:
        perfil = datos.pop("perfil", "_generico") or "_generico"
        _migrar_dominio(raiz, perfil, cambios)
        datos["config_version"] = 3
        _escribir_yaml(asistente, datos, _encabezado(asistente))
        cambios.append(f"{rutas.ASISTENTE}: config_version 3 (sin la clave 'perfil')")

    motor = raiz / rutas.MOTOR
    datos_motor = _leer_yaml(motor)
    if datos_motor and int(datos_motor.get("config_version", 0)) < 3:
        recuperacion = datos_motor.get("recuperacion") or {}
        if recuperacion.get("qdrant_path") == ".cache/qdrant_local":
            recuperacion["qdrant_path"] = rutas.QDRANT
        datos_motor["config_version"] = 3
        _escribir_yaml(motor, datos_motor, _encabezado(motor))
        cambios.append(f"{rutas.MOTOR}: config_version 3")

    _mover(raiz / ".cache" / "qdrant_local", raiz / rutas.QDRANT, cambios, raiz)
    _mover(raiz / ".cache" / "vocab_bm25", raiz / rutas.INDICE, cambios, raiz)
    _mover(raiz / "data" / "golden", raiz / rutas.GOLDEN_BANCO, cambios, raiz)
    for vacio in (raiz / ".cache", raiz / "data"):
        if vacio.is_dir() and not any(vacio.iterdir()):
            vacio.rmdir()
    return cambios


__all__ = ["migrar_proyecto"]
