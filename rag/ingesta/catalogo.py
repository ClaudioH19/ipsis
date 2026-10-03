"""Catálogo de documentos del proyecto (``documentos/catalogo.yaml``)."""
from __future__ import annotations

from rag.configuracion import rutas

import json
import pathlib
import hashlib
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


from rag.ingesta.parsear import parsear_documento, DocumentoParseado, EXTENSIONES_SOPORTADAS


CATALOGO_PATH = rutas.CATALOGO


def cargar_catalogo(ruta: str = CATALOGO_PATH) -> list[dict]:
    """Catálogo de documentos, leído de ``documentos/catalogo.yaml``.

    Vive en configuración y no en código porque es lo primero que cambia al
    adoptar un dominio nuevo: agregar un documento debe ser agregar una
    entrada al YAML, no editar Python.
    """
    import yaml
    datos = yaml.safe_load(pathlib.Path(ruta).read_text(encoding="utf-8")) or {}
    # `datos["documentos"]` puede ser `None` si el catálogo se creó vacío
    # (`rag init`, o `_append_entrada_catalogo` antes de la primera entrada:
    # "documentos:\n" sin items parsea a `None`, no a `[]`) -- se normaliza
    # aquí, una sola vez, en vez de que cada llamador tenga que acordarse.
    return datos.get("documentos") or []


# ---------------------------------------------------------------------------
# `rag cargar` (Etapa Plugin, Tarea A): copia un documento al corpus y lo
# registra en `documentos/catalogo.yaml`. La lógica vive aquí (no en la CLI) por
# la regla del encargo: "si un comando necesita lógica nueva, esa lógica se
# escribe en rag/, nunca en la CLI".
# ---------------------------------------------------------------------------

def _slug(nombre: str) -> str:
    """Slug determinista y legible: sin acentos, minúsculas, solo
    ``[a-z0-9-]``. Nunca vacío (cae a "documento")."""
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    return base or "documento"


def generar_doc_id(nombre_archivo: str, ids_existentes: set[str], hash_contenido: str) -> str:
    """``doc_id`` estable y legible: el slug del nombre de archivo (sin
    extensión); si ya existe un ``doc_id`` igual (otro documento con nombre
    parecido), se distingue con un sufijo corto del hash de CONTENIDO -- no
    un número de serie ciego, para que dos cargas del mismo archivo en
    momentos distintos sigan produciendo el mismo id si el contenido no
    cambió (ver `rag/ingesta/catalogo.py::agregar_documentos_al_catalogo`, que además
    detecta ese caso ANTES de llegar aquí y no duplica la entrada)."""
    base = _slug(Path(nombre_archivo).stem)
    if base not in ids_existentes:
        return base
    candidato = f"{base}-{hash_contenido[:6]}"
    contador = 2
    original = candidato
    while candidato in ids_existentes:
        candidato = f"{original}-{contador}"
        contador += 1
    return candidato


def inferir_titulo(doc: DocumentoParseado, nombre_archivo: str) -> str:
    """El primer encabezado del documento (bloque ``tipo_contenido ==
    "titulo"``); si no hay ninguno, el comienzo del primer bloque narrativo,
    recortado; si el documento no tiene ni un bloque, el nombre de archivo
    humanizado. Nunca inventa un título: siempre es texto que ya existe en
    el documento, o el nombre que el propio usuario le puso al archivo."""
    primero_titulo = next((b.texto for b in doc.bloques if b.tipo_contenido == "titulo"), None)
    if primero_titulo:
        return primero_titulo

    primero_narrativo = next((b.texto for b in doc.bloques if b.tipo_contenido == "narrativo"), None)
    if primero_narrativo:
        texto = primero_narrativo.strip()
        return texto[:80].rstrip() + ("..." if len(texto) > 80 else "")

    base = Path(nombre_archivo).stem
    return re.sub(r"[-_]+", " ", base).strip().title() or Path(nombre_archivo).name


def _yaml_valor(valor) -> str:
    """Serializa un valor escalar como YAML de flujo válido, en una línea --
    usa el mismo truco que ``rag/paquete_revision_externa.py::_json_una_linea``:
    un JSON válido de un escalar simple ES YAML de flujo válido, así que no
    hace falta razonar sobre el "quoting" de PyYAML a mano para un `dump`
    parcial (que además perdería los comentarios del resto del archivo)."""
    return json.dumps(valor, ensure_ascii=False)


def plantilla_catalogo_vacio() -> str:
    """Contenido inicial de ``documentos/catalogo.yaml`` sin documentos -- la usa
    tanto ``rag init`` (para que el archivo exista desde el principio, con
    un mensaje claro en vez de un ``FileNotFoundError``) como
    ``_append_entrada_catalogo`` (si `rag cargar` es lo primero que se
    corre). Nota: ``documentos:`` sin items parsea a ``None`` con
    ``yaml.safe_load``, no a una lista vacía -- ``cargar_catalogo`` ya lo
    normaliza."""
    return (
        "# Catálogo de documentos del corpus.\n"
        "# Agregado con 'rag cargar <archivo|carpeta>' -- no se edita a mano salvo\n"
        "# para corregir 'doc_titulo', 'version' o 'vigente' de una entrada existente.\n"
        "documentos:\n"
    )


def _append_entrada_catalogo(ruta_catalogo: str, entrada: dict) -> None:
    """Agrega una entrada al FINAL de ``documentos/catalogo.yaml`` sin volver a
    serializar el archivo completo -- es lo que garantiza que los
    comentarios existentes (y las entradas ya escritas a mano) queden
    intactos, letra por letra, en vez de depender de que un dumper YAML los
    preserve (PyYAML con `yaml.safe_load`/`safe_dump` los descarta
    siempre)."""
    ruta = Path(ruta_catalogo)
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(plantilla_catalogo_vacio(), encoding="utf-8")

    texto_actual = ruta.read_text(encoding="utf-8")
    if not texto_actual.endswith("\n"):
        texto_actual += "\n"

    bloque = (
        f"\n  - archivo: {_yaml_valor(entrada['archivo'])}\n"
        f"    doc_id: {entrada['doc_id']}\n"
        f"    doc_titulo: {_yaml_valor(entrada['doc_titulo'])}\n"
        f"    version: {_yaml_valor(str(entrada['version']))}\n"
        f"    vigente: {'true' if entrada['vigente'] else 'false'}\n"
        f"    hash_contenido: {entrada['hash_contenido']}\n"
    )
    ruta.write_text(texto_actual + bloque, encoding="utf-8")


@dataclass
class DocumentoCargado:
    archivo: str
    doc_id: str
    doc_titulo: str
    version: str
    vigente: bool
    hash_contenido: str
    ya_existia: bool = False
    advertencias: list[str] = field(default_factory=list)


def agregar_documentos_al_catalogo(rutas: list[str], carpeta_corpus: str = "documentos",
                                    ruta_catalogo: str = CATALOGO_PATH) -> list[DocumentoCargado]:
    """Copia cada archivo de ``rutas`` a ``carpeta_corpus`` (si no está ya
    ahí) y agrega una entrada nueva a ``documentos/catalogo.yaml`` -- salvo que su
    HASH de contenido ya esté registrado (misma carga repetida: se avisa y
    no se duplica). Devuelve un resumen por documento, incluidas las
    advertencias del parser (p.ej. "sin estructura de secciones") para que
    el llamador (la CLI) las muestre."""
    Path(carpeta_corpus).mkdir(parents=True, exist_ok=True)

    catalogo_actual = cargar_catalogo(ruta_catalogo) if Path(ruta_catalogo).exists() else []
    ids_existentes = {e["doc_id"] for e in catalogo_actual}
    hashes_existentes = {e["hash_contenido"]: e["doc_id"] for e in catalogo_actual if e.get("hash_contenido")}

    resultado: list[DocumentoCargado] = []
    for ruta_str in rutas:
        ruta_origen = Path(ruta_str)
        if not ruta_origen.is_file():
            raise FileNotFoundError(f"no existe el archivo {ruta_origen}")
        ext = ruta_origen.suffix.lower()
        if ext not in EXTENSIONES_SOPORTADAS:
            raise ValueError(
                f"{ruta_origen}: formato {ext!r} no soportado (soportados: {sorted(EXTENSIONES_SOPORTADAS)})"
            )

        contenido = ruta_origen.read_bytes()
        hash_contenido = hashlib.sha256(contenido).hexdigest()

        if hash_contenido in hashes_existentes:
            resultado.append(DocumentoCargado(
                archivo=ruta_origen.name, doc_id=hashes_existentes[hash_contenido],
                doc_titulo="(ya estaba en el catálogo, mismo contenido)", version="-", vigente=True,
                hash_contenido=hash_contenido, ya_existia=True,
            ))
            continue

        doc_id = generar_doc_id(ruta_origen.name, ids_existentes, hash_contenido)

        # Parsea desde el ORIGEN, antes de copiar nada: si el documento se
        # rechaza (p.ej. un PDF escaneado, DocumentoEscaneadoError), no debe
        # quedar un archivo huérfano en documentos/ sin entrada en el
        # catálogo -- defecto real encontrado reproduciendo 'rag cargar' con
        # un PDF escaneado en un directorio externo al repo.
        doc_parseado = parsear_documento(str(ruta_origen), doc_id=doc_id, doc_titulo="(pendiente)", version="1")
        titulo = inferir_titulo(doc_parseado, ruta_origen.name)

        destino = Path(carpeta_corpus) / ruta_origen.name
        if destino.is_file() and hashlib.sha256(destino.read_bytes()).hexdigest() != hash_contenido:
            destino = destino.with_name(
                f"{destino.stem}-{hash_contenido[:6]}{destino.suffix}"
            )
        if destino.resolve() != ruta_origen.resolve():
            shutil.copy2(ruta_origen, destino)
        ids_existentes.add(doc_id)

        entrada = {
            "archivo": destino.name, "doc_id": doc_id, "doc_titulo": titulo,
            "version": "1", "vigente": True, "hash_contenido": hash_contenido,
        }
        _append_entrada_catalogo(ruta_catalogo, entrada)
        catalogo_actual.append(entrada)
        hashes_existentes[hash_contenido] = doc_id

        resultado.append(DocumentoCargado(
            archivo=entrada["archivo"], doc_id=doc_id, doc_titulo=titulo, version="1",
            vigente=True, hash_contenido=hash_contenido, advertencias=list(doc_parseado.advertencias),
        ))
    return resultado
