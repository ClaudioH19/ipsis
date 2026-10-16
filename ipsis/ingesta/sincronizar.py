"""Sincroniza el catálogo (``documents/catalog.yaml``) con lo que hay en la carpeta ``documents/``.

El catálogo es la fuente de verdad del índice; si la carpeta cambia por fuera (se borra, se renombra o se agrega un
archivo) el catálogo queda desfasado y el índice falla o sirve documentos que ya no están. ``planificar`` compara
ambos y clasifica cada archivo; ``aplicar`` actualiza el catálogo editando solo las líneas necesarias.

- **nuevo**: archivo sin entrada vigente -> se agrega (título y ``doc_id`` como en ``ipsis load``);
- **renombrado**: una entrada cuyo archivo falta y un archivo nuevo con el mismo contenido -> se conserva la entrada
  (mismo ``doc_id``, título y versión) y solo cambia el nombre de archivo;
- **modificado**: mismo nombre, otro contenido -> se actualiza el hash de la entrada;
- **retirado**: la entrada apunta a un archivo que ya no existe -> ``active: false`` (reversible: el archivo vuelve y se
  reactiva);
- **reactivado**: un archivo cuyo contenido es el de una entrada retirada -> se vuelve a activar.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from ipsis.configuracion import rutas
from ipsis.ingesta.catalogo import (
    CATALOGO_PATH, actualizar_entrada_catalogo, agregar_documentos_al_catalogo, cargar_catalogo)
from ipsis.ingesta.parsear import EXTENSIONES_SOPORTADAS


@dataclass
class PlanSincronizacion:
    nuevos: list[Path] = field(default_factory=list)
    renombrados: list[tuple[dict, Path]] = field(default_factory=list)   # (entrada, archivo nuevo)
    modificados: list[tuple[dict, str]] = field(default_factory=list)    # (entrada, hash nuevo)
    retirados: list[dict] = field(default_factory=list)
    reactivados: list[tuple[dict, Path]] = field(default_factory=list)
    sin_cambios: int = 0
    ignorados: list[Path] = field(default_factory=list)                  # en subcarpetas: el catálogo guarda solo nombres

    @property
    def hay_cambios(self) -> bool:
        return bool(self.nuevos or self.renombrados or self.modificados or self.retirados or self.reactivados)


@dataclass
class ResultadoSincronizacion:
    plan: PlanSincronizacion
    agregados: list = field(default_factory=list)       # DocumentoCargado de los nuevos (con sus avisos y rechazos)


def _hash(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def planificar(carpeta: str = rutas.DOCUMENTOS, ruta_catalogo: str = CATALOGO_PATH) -> PlanSincronizacion:
    raiz = Path(carpeta)
    catalogo = cargar_catalogo(ruta_catalogo) if Path(ruta_catalogo).is_file() else []
    plan = PlanSincronizacion()
    en_carpeta: dict[str, Path] = {}
    for p in sorted(raiz.rglob("*")) if raiz.is_dir() else []:
        if not p.is_file() or p.suffix.lower() not in EXTENSIONES_SOPORTADAS:
            continue
        if p.parent == raiz:
            en_carpeta[p.name] = p
        else:
            plan.ignorados.append(p)
    hashes = {nombre: _hash(p) for nombre, p in en_carpeta.items()}

    vigentes = [e for e in catalogo if e.get("vigente", True) is not False]
    retiradas = [e for e in catalogo if e.get("vigente", True) is False]
    registrados = {e["archivo"] for e in vigentes}
    sin_entrada = {n for n in en_carpeta if n not in registrados}
    faltantes: list[dict] = []
    for e in vigentes:
        nombre = e["archivo"]
        if nombre not in en_carpeta:
            faltantes.append(e)
        elif e.get("hash_contenido") and hashes[nombre] != e["hash_contenido"]:
            plan.modificados.append((e, hashes[nombre]))
        else:
            plan.sin_cambios += 1

    # Renombres: un archivo nuevo con el contenido de una entrada que ya no tiene su archivo.
    por_hash_nuevo: dict[str, list[str]] = {}
    for n in sorted(sin_entrada):
        por_hash_nuevo.setdefault(hashes[n], []).append(n)
    for e in faltantes:
        candidatos = por_hash_nuevo.get(e.get("hash_contenido"), [])
        if candidatos:
            nuevo = candidatos.pop(0)
            sin_entrada.discard(nuevo)
            plan.renombrados.append((e, en_carpeta[nuevo]))
        else:
            plan.retirados.append(e)

    # Lo que queda sin entrada: vuelve una retirada (mismo contenido) o es un documento nuevo.
    por_hash_retirada = {e.get("hash_contenido"): e for e in retiradas if e.get("hash_contenido")}
    vigentes_por_hash = {e.get("hash_contenido") for e in vigentes}
    for n in sorted(sin_entrada):
        if hashes[n] in por_hash_retirada and hashes[n] not in vigentes_por_hash:
            plan.reactivados.append((por_hash_retirada.pop(hashes[n]), en_carpeta[n]))
        else:
            plan.nuevos.append(en_carpeta[n])
    return plan


def aplicar(plan: PlanSincronizacion, carpeta: str = rutas.DOCUMENTOS,
            ruta_catalogo: str = CATALOGO_PATH) -> ResultadoSincronizacion:
    for entrada, nuevo in plan.renombrados:
        actualizar_entrada_catalogo(ruta_catalogo, entrada["doc_id"], archivo=nuevo.name)
    for entrada, hash_nuevo in plan.modificados:
        actualizar_entrada_catalogo(ruta_catalogo, entrada["doc_id"], hash_contenido=hash_nuevo)
    for entrada in plan.retirados:
        actualizar_entrada_catalogo(ruta_catalogo, entrada["doc_id"], vigente=False)
    for entrada, archivo in plan.reactivados:
        actualizar_entrada_catalogo(ruta_catalogo, entrada["doc_id"], archivo=archivo.name, vigente=True)
    agregados = (agregar_documentos_al_catalogo([str(p) for p in plan.nuevos], carpeta, ruta_catalogo)
                 if plan.nuevos else [])
    return ResultadoSincronizacion(plan=plan, agregados=agregados)


__all__ = ["PlanSincronizacion", "ResultadoSincronizacion", "aplicar", "planificar"]
