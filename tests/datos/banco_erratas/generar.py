"""Genera el banco de erratas: preguntas existentes con errores de tipeo realistas.

Cada caso conserva la pregunta limpia (``original``) para medir robustez: de lo que el
sistema responde bien en limpio, cuánto sigue respondiendo con erratas. Las trampas
también reciben erratas: una corrección que las vuelva respondibles es un error.

Determinista: la semilla sale del id del caso. Dos conjuntos con el mismo método:

- ``diseno``: desde ``banco_garantias`` (para diseñar la capa de normalización);
- ``validacion``: desde ``banco_validacion`` (se mide una vez antes y otra después).

    python tests/datos/banco_erratas/generar.py   # escribe <conjunto>/<idioma>/casos.yaml
    python tests/datos/banco_erratas/construir.py # deriva banco.jsonl y manifiesto.json
"""
from __future__ import annotations

import hashlib
import random
import shutil
import unicodedata
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ.parent
IDIOMAS = ("es", "en", "pt")
CONJUNTOS = {"diseno": "banco_garantias", "validacion": "banco_validacion"}
CLASES = ("exacta", "parafrasis", "trampa")

# Vecinas en un teclado QWERTY (la ñ junto a la l, como en el teclado español).
VECINAS = {
    "q": "wa", "w": "qes", "e": "wrd", "r": "etf", "t": "ryg", "y": "tuh", "u": "yij", "i": "uok",
    "o": "ipl", "p": "ol", "a": "qsz", "s": "adwx", "d": "sfe", "f": "dgr", "g": "fht", "h": "gjy",
    "j": "hku", "k": "jli", "l": "kop", "z": "asx", "x": "zsc", "c": "xvd", "v": "cbf", "b": "vng",
    "n": "bmh", "m": "nj", "ñ": "lp",
}
# Confusiones por sonido, de la forma correcta a la errada.
FONETICAS = {
    "es": [("ll", "y"), ("y", "ll"), ("v", "b"), ("b", "v"), ("ce", "se"), ("ci", "si"), ("z", "s"),
           ("s", "z"), ("ge", "je"), ("gi", "ji"), ("qu", "k"), ("cc", "c"), ("x", "s")],
    "pt": [("ç", "ss"), ("ç", "s"), ("ss", "s"), ("ch", "x"), ("x", "ch"), ("s", "z"), ("z", "s"),
           ("lh", "li"), ("nh", "ni"), ("ce", "se"), ("qu", "k")],
    "en": [("ie", "ei"), ("ei", "ie"), ("ph", "f"), ("ss", "s"), ("ll", "l"), ("mm", "m"), ("rr", "r"),
           ("ence", "ance"), ("ance", "ence"), ("tion", "sion"), ("ou", "o")],
}
STOP = {"es": {"para", "como", "cada", "cual", "cuál", "cuando", "cuándo", "donde", "dónde", "quien", "quién",
               "hasta", "desde", "entre", "sobre", "tiene", "puedo", "puede", "hace", "cuánto", "cuanto",
               "cuántos", "cuantos", "cuántas", "cuantas", "qué", "que"},
        "en": {"what", "when", "where", "which", "does", "have", "with", "from", "that", "this", "much",
               "many", "long", "after", "into", "your", "their", "there", "they"},
        "pt": {"para", "como", "cada", "qual", "quando", "onde", "quem", "quanto", "quanta", "quantos",
               "quantas", "entre", "sobre", "pode", "posso", "tenho", "depois", "antes"}}


def _rng(caso_id: str) -> random.Random:
    return random.Random(int(hashlib.sha256(caso_id.encode("utf-8")).hexdigest()[:12], 16))


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)
                   or c == "̃" and False)


def _plano(texto: str) -> str:
    salida = []
    for c in unicodedata.normalize("NFD", texto):
        if unicodedata.combining(c):
            continue
        salida.append(c)
    return unicodedata.normalize("NFC", "".join(salida))


def _errata(palabra: str, idioma: str, rng: random.Random) -> tuple[str, str]:
    """Una errata de un tipo al azar que cambie la palabra; ``(nueva, tipo)``."""
    tipos = ["omision", "duplicacion", "transposicion", "vecina", "fonetica", "fonetica"]
    rng.shuffle(tipos)
    for tipo in tipos:
        p = palabra
        interior = range(1, len(p) - 1)
        if tipo == "omision" and len(p) >= 5:
            i = rng.choice(list(interior))
            nueva = p[:i] + p[i + 1:]
        elif tipo == "duplicacion":
            i = rng.choice(list(interior))
            nueva = p[:i] + p[i] + p[i:]
        elif tipo == "transposicion" and len(p) >= 5:
            i = rng.choice(list(range(1, len(p) - 2)))
            nueva = p[:i] + p[i + 1] + p[i] + p[i + 2:]
        elif tipo == "vecina":
            posibles = [i for i in interior if p[i].lower() in VECINAS]
            if not posibles:
                continue
            i = rng.choice(posibles)
            nueva = p[:i] + rng.choice(VECINAS[p[i].lower()]) + p[i + 1:]
        elif tipo == "fonetica":
            reglas = [(a, b) for a, b in FONETICAS[idioma] if a in p.lower()]
            if not reglas:
                continue
            a, b = rng.choice(reglas)
            i = p.lower().index(a)
            nueva = p[:i] + b + p[i + len(a):]
        else:
            continue
        if nueva != palabra:
            return nueva, tipo
    return palabra, ""


def errar(pregunta: str, idioma: str, caso_id: str) -> tuple[str, list[str]]:
    """La pregunta con 1 o 2 erratas en palabras de contenido; a veces sin tildes ni
    signos (como se escribe apurado), a veces con dos palabras pegadas o una separada."""
    rng = _rng(caso_id)
    palabras = pregunta.split(" ")
    candidatas = [i for i, w in enumerate(palabras)
                  if len(w.strip("¿?¡!,.;:")) >= 4 and w.strip("¿?¡!,.;:").isalpha()
                  and w.strip("¿?¡!,.;:").lower() not in STOP[idioma] and not w[:1].isupper()]
    tipos: list[str] = []
    if not candidatas:
        return pregunta, tipos
    extra = rng.random()
    if extra < 0.12 and len(candidatas) >= 1:
        i = rng.choice(candidatas)
        if i + 1 < len(palabras):  # dos palabras pegadas: «ordende compra»
            palabras[i] = palabras[i].rstrip(",.;:") + palabras[i + 1]
            del palabras[i + 1]
            tipos.append("pegadas")
    elif extra < 0.20:
        largas = [i for i in candidatas if len(palabras[i].strip("¿?¡!,.;:")) >= 8]
        if largas:  # una palabra separada: «capa citación»
            i = rng.choice(largas)
            w = palabras[i]
            corte = rng.randint(3, len(w.strip("¿?¡!,.;:")) - 3)
            palabras[i] = w[:corte] + " " + w[corte:]
            tipos.append("separada")
    if not tipos:
        n = 2 if len(candidatas) >= 3 and rng.random() < 0.4 else 1
        for i in rng.sample(candidatas, n):
            w = palabras[i]
            nucleo = w.strip("¿?¡!,.;:")
            nueva, tipo = _errata(nucleo, idioma, rng)
            if tipo:
                palabras[i] = w.replace(nucleo, nueva)
                tipos.append(tipo)
    salida = " ".join(palabras)
    if rng.random() < 0.5:  # apurado: sin tildes, minúsculas, sin signos de apertura
        salida = _plano(salida).lower().replace("¿", "").replace("¡", "")
    return salida, tipos


def generar() -> None:
    for conjunto, fuente in CONJUNTOS.items():
        for idioma in IDIOMAS:
            origen = DATOS / fuente / idioma
            destino = RAIZ / conjunto / idioma
            (destino / "corpus").mkdir(parents=True, exist_ok=True)
            for archivo in (origen / "corpus").glob("*.md"):
                shutil.copyfile(archivo, destino / "corpus" / archivo.name)
            casos = yaml.safe_load((origen / "casos.yaml").read_text(encoding="utf-8"))
            salida = []
            for caso in casos:
                if caso["id"].split("-")[1] not in CLASES:
                    continue
                nueva, tipos = errar(caso["pregunta"], idioma, f"{conjunto}:{caso['id']}")
                if not tipos:
                    continue
                if "par" in caso and caso["par"] not in {c["id"] for c in salida}:
                    continue  # la trampa necesita a su par en el banco
                salida.append({**caso, "pregunta": nueva, "original": caso["pregunta"], "erratas": tipos})
            cabecera = (f"# Banco de erratas ({conjunto}), generado por generar.py desde {fuente}. "
                        "No editar a mano.\n")
            (destino / "casos.yaml").write_text(
                cabecera + yaml.safe_dump(salida, allow_unicode=True, sort_keys=False, width=200),
                encoding="utf-8", newline="\n")


if __name__ == "__main__":
    generar()
