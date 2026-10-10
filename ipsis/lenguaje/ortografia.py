"""Normalización de erratas contra el vocabulario del corpus.

Un usuario apurado escribe «pasword», «covran», «abreel» o «estacio namiento». Sin
corregir, esa palabra no existe en el corpus: no la encuentra BM25, no puede ser foco y
suma a ``s_oov``, que bloquea el ``ok`` aunque la evidencia sea la correcta.

Sigue las ideas de SymSpell (índice de borrados simétrico) y de su modo «compound»
(unir y separar palabras), siempre contra el corpus del proyecto: corrige hacia
palabras de los documentos, nunca hacia otras. La corrección es conservadora y
auditable (el diagnóstico la muestra):

- nunca una palabra que se reconoce: stopwords, genéricas, palabras del corpus, de los
  grupos de sinónimos del paquete («compu») o del léxico del idioma (WordNet).
  «feriados» u «orina» son palabras reales que el corpus no trae, y corregirlas
  convertiría una pregunta sin respuesta en un falso ``ok``. Sin léxico (paquete de
  respaldo), no se corrige nada;
- nunca un nombre propio ni una sigla: una mayúscula fuera del inicio («Atacama»,
  «Copa», «HDMI») se deja como está;
- edición: distancia 1 (2 desde 8 letras, con transposiciones) a una forma del corpus,
  desde 4 letras, y una sola candidata a esa distancia: ante un empate no se elige. Si
  ninguna forma está tan cerca, se comparan raíces («covran» → «covr», a una letra de
  «cobr»: el corpus dice «cobra», no «cobran»), con la misma primera letra y sin que la
  forma del corpus quede lejos de lo escrito;
- separar: «abreel» → «abre el» cuando una parte es una palabra funcional y la otra
  está en el corpus (o las dos son formas exactas del corpus);
- unir: «estacio namiento» → «estacionamiento» cuando la unión está en el corpus y
  alguna parte no es una palabra;
- contexto (si el índice lo trae): pares de palabras de contenido vecinas del corpus,
  como presencia y no como frecuencia (un título o un pie de página repetido no pesa
  más). Una palabra ausente del corpus se cambia por una forma a distancia 1 si ese
  par existe junto a su vecina y el par original no: «paring permit» → «parking
  permit». Una palabra real exige el par con las dos vecinas; una inexistente, con
  una. Al indexar, una autoprueba con erratas sobre oraciones del propio corpus lo
  deja apagado si no recupera nada o se equivoca demasiado.

Las tildes ya se ignoran al comparar términos («contrasena» = «contraseña»): eso no es
una errata y no pasa por aquí.
"""
from __future__ import annotations

import functools
import re
from importlib.resources import files
from types import SimpleNamespace

from ipsis.lenguaje.texto import terminos

LARGO_MINIMO = 4
MUESTRA_AUTOPRUEBA = 300
_PALABRA = re.compile(r"[^\W\d_]+")


@functools.lru_cache(maxsize=16)
def raices_lexico(codigo: str, stemmer: str | None) -> frozenset[str]:
    """Raíces de todos los lemas de una palabra del léxico maestro del idioma."""
    recurso = files("ipsis.recursos").joinpath("sinonimos", f"{codigo}.lexicon.tsv")
    if not recurso.is_file():
        return frozenset()
    paquete = SimpleNamespace(stemmer=stemmer)
    formas = {f for linea in recurso.read_text(encoding="utf-8").splitlines()
              if linea and not linea.startswith("#") for f in linea.split("\t")[2:] if f.isalpha()}
    return frozenset(r for f in formas for r in terminos(f, paquete))


def distancia(a: str, b: str, tope: int) -> int:
    """Damerau-Levenshtein restringida (transposiciones adyacentes); ``tope + 1``
    en cuanto la distancia supera ``tope``."""
    if abs(len(a) - len(b)) > tope:
        return tope + 1
    previa2: list[int] = []
    previa = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        fila = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            costo = a[i - 1] != b[j - 1]
            fila[j] = min(previa[j] + 1, fila[j - 1] + 1, previa[j - 1] + costo)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                fila[j] = min(fila[j], previa2[j - 2] + 1)
        if min(fila) > tope:
            return tope + 1
        previa2, previa = previa, fila
    return previa[-1]


def borrados(palabra: str, tope: int) -> set[str]:
    """La palabra y todas sus variantes con hasta ``tope`` letras quitadas (SymSpell)."""
    variantes, frontera = {palabra}, {palabra}
    for _ in range(tope):
        frontera = {v[:i] + v[i + 1:] for v in frontera for i in range(len(v))}
        variantes |= frontera
    return variantes


def _indice(claves, tope: int) -> dict[str, tuple[str, ...]]:
    salida: dict[str, set[str]] = {}
    for clave in claves:
        for v in borrados(clave, tope):
            salida.setdefault(v, set()).add(clave)
    return {v: tuple(cs) for v, cs in salida.items()}


class Corrector:
    """Índices de un corpus y un paquete; se construye una vez por motor."""

    def __init__(self, paquete, estadisticas, pares: frozenset[tuple[str, str]] | None = None) -> None:
        from ipsis.lenguaje.consultas import _grupos_por_raiz, plano, terminos_genericos

        self.paquete, self.plano = paquete, plano
        self.df = getattr(estadisticas, "df", {}) or {}
        superficie = getattr(estadisticas, "superficie", {}) or {}
        # Raíz del corpus → su forma más frecuente (plana, para comparar), y esa forma → raíz.
        # La corrección devuelve la forma con tildes del corpus: «viático», no «viatico».
        self.superficie = {r: f for r, f in superficie.items() if self.df.get(r, 0) > 0 and f.isalpha()}
        self.formas = {r: plano(f) for r, f in self.superficie.items()}
        self.por_forma = {f: r for r, f in self.formas.items() if len(f) >= LARGO_MINIMO}
        self.lexico = raices_lexico(paquete.codigo.split("-")[0], paquete.stemmer)
        self.stop = {plano(s) for s in paquete.stopwords}
        self.genericos = terminos_genericos(paquete)
        self.de_grupos = set(_grupos_por_raiz(paquete))
        self.idx_formas = _indice(self.por_forma, 2)
        self.idx_raices = _indice([r for r in self.formas if len(r) >= 4], 1)
        if pares is None and getattr(estadisticas, "contexto_erratas", False):
            pares = frozenset(tuple(p.split(" ", 1)) for p in getattr(estadisticas, "pares", ()))
        self.pares = pares or frozenset()

    def _raiz(self, palabra: str) -> str | None:
        rs = terminos(palabra, self.paquete)
        return rs[0] if len(rs) == 1 else None

    def _en_corpus(self, palabra: str) -> bool:
        r = self._raiz(palabra)
        return r is not None and self.df.get(r, 0) > 0

    def _conocida(self, palabra: str) -> bool:
        if palabra in self.stop:
            return True
        r = self._raiz(palabra)
        return r is not None and (self.df.get(r, 0) > 0 or r in self.lexico or r in self.genericos
                                  or r in self.de_grupos)

    def _exacta(self, palabra: str) -> bool:
        """Forma tal cual del corpus, no una raíz recortada («cobr»)."""
        return palabra in self.por_forma

    def _editar(self, palabra: str) -> str | None:
        """Raíz del corpus a la que corregir, o ``None`` si no hay una sola."""
        largo = len(palabra)
        if largo < LARGO_MINIMO:
            return None
        tope = 1 if largo < 8 else 2
        candidatas: dict[str, float] = {}
        for v in borrados(palabra, tope):
            for forma in self.idx_formas.get(v, ()):
                d = distancia(palabra, forma, tope)
                if d <= tope:
                    r = self.por_forma[forma]
                    candidatas[r] = min(candidatas.get(r, 9.0), d)
        raiz = self._raiz(palabra)
        if not candidatas and raiz and len(raiz) >= 4:
            for v in borrados(raiz, 1):
                for r in self.idx_raices.get(v, ()):
                    # Misma primera letra y la forma del corpus no muy lejos de lo escrito:
                    # «covran» → «cobra», nunca «muere» → «fuera» ni «prepara» → «precos».
                    if r[0] != raiz[0] or distancia(palabra, self.formas[r], tope + 1) > tope + 1:
                        continue
                    if distancia(raiz, r, 1) <= 1:
                        candidatas[r] = min(candidatas.get(r, 9.0), 1.5)
        if not candidatas:
            return None
        mejor = min(candidatas.values())
        ganadoras = [r for r, d in candidatas.items() if d == mejor]
        return ganadoras[0] if len(ganadoras) == 1 else None

    def _separar(self, palabra: str) -> str | None:
        opciones = []
        for corte in range(1, len(palabra)):
            a, b = palabra[:corte], palabra[corte:]
            if a in self.stop or b in self.stop:
                # Una palabra funcional pegada: «abre|el», «garantia|de», «warranty|if».
                funcional, otra = (a, b) if a in self.stop else (b, a)
                valida = (self._exacta(otra) if len(funcional) == 1
                          else len(otra) >= 3 and self._en_corpus(otra))
            else:
                valida = self._exacta(a) and self._exacta(b)
            if valida:
                opciones.append(f"{a} {b}")
        return opciones[0] if len(opciones) == 1 else None

    def correcciones(self, pregunta: str) -> dict[str, str]:
        salida: dict[str, str] = {}
        palabras = _PALABRA.findall(pregunta)
        planas = [self.plano(p).lower() for p in palabras]
        propias = {i for i, p in enumerate(palabras)
                   if (i > 0 and p[:1].isupper()) or (len(p) > 1 and p.isupper())}
        unidas: set[int] = set()
        for i in range(len(palabras) - 1):
            if {i, i + 1} & propias:
                continue
            junta = planas[i] + planas[i + 1]
            if (len(junta) >= 6 and self._en_corpus(junta)
                    and not (self._conocida(planas[i]) and self._conocida(planas[i + 1]))):
                salida[f"{palabras[i]} {palabras[i + 1]}"] = junta
                unidas |= {i, i + 1}
        for i, (palabra, plana) in enumerate(zip(palabras, planas)):
            if i in unidas or i in propias or self._conocida(plana):
                continue
            separada = self._separar(plana) if len(plana) >= 5 else None
            if separada:
                salida[palabra] = separada
                continue
            raiz = self._editar(plana)
            if raiz:
                salida[palabra] = self.superficie[raiz]
        if self.pares:
            self._con_contexto(palabras, planas, propias, salida)
        return salida

    def _vecinas(self, planas: list[str], i: int) -> tuple[str | None, str | None]:
        """Raíces de contenido inmediatamente a la izquierda y a la derecha."""
        izq = next((self._raiz(p) for p in reversed(planas[:i]) if p not in self.stop), None)
        der = next((self._raiz(p) for p in planas[i + 1:] if p not in self.stop), None)
        return izq, der

    def _apoyo(self, raiz: str, izq: str | None, der: str | None, ambos: bool = False) -> bool:
        a = izq is not None and (izq, raiz) in self.pares
        b = der is not None and (raiz, der) in self.pares
        return (a and b) if ambos else (a or b)

    def _con_contexto(self, palabras, planas, propias, salida: dict[str, str]) -> None:
        tocadas = {w for clave in salida for w in clave.split()}
        for i, (palabra, plana) in enumerate(zip(palabras, planas)):
            if palabra in tocadas or i in propias or len(plana) < LARGO_MINIMO or plana in self.stop:
                continue
            raiz = self._raiz(plana)
            if raiz is None or self.df.get(raiz, 0) > 0 or raiz in self.genericos or raiz in self.de_grupos:
                continue  # está en el corpus o la resuelve otra regla
            izq, der = self._vecinas(planas, i)
            if self._apoyo(raiz, izq, der):
                continue  # el par original ya existe: no hay nada que corregir
            real = raiz in self.lexico
            candidatas = {self.por_forma[f] for v in borrados(plana, 1) for f in self.idx_formas.get(v, ())
                          if distancia(plana, f, 1) <= 1}
            apoyadas = [r for r in candidatas if r != raiz and self._apoyo(r, izq, der, ambos=real)]
            if len(apoyadas) == 1:
                salida[palabra] = self.superficie[apoyadas[0]]


def pares_de_contexto(textos, paquete) -> list[str]:
    """Pares «raíz raíz» de palabras de contenido vecinas, línea por línea, sin repetir:
    cuenta la presencia, no la frecuencia, para que un título o un pie de página que se
    repite no gane importancia."""
    from ipsis.lenguaje.consultas import plano

    stop = {plano(s) for s in getattr(paquete, "stopwords", ())}
    pares: set[str] = set()
    for texto in textos:
        for linea in texto.splitlines():
            raices = [r for w in _PALABRA.findall(plano(linea).lower()) if w not in stop
                      for r in terminos(w, paquete)[:1]]
            pares.update(f"{a} {b}" for a, b in zip(raices, raices[1:]))
    return sorted(pares)


def _errata_de_prueba(palabra: str, n: int) -> str:
    """Una omisión o una transposición interior, alternadas: determinista."""
    i = 1 + n % (len(palabra) - 2)
    if n % 2:
        return palabra[:i] + palabra[i + 1:]
    return palabra[:i] + palabra[i + 1] + palabra[i] + palabra[i + 2:]


def autoprueba_contexto(textos, paquete, estadisticas, pares: list[str]) -> bool:
    """¿Sirve el contexto en este corpus? Una errata por oración del propio corpus,
    corregida con y sin contexto. Se activa si recupera al menos una palabra más y se
    equivoca a lo sumo una vez por cada cuatro aciertos. No detecta el riesgo de cambiar
    una palabra real que el corpus no trae (eso lo cuida la regla de las dos vecinas):
    solo decide si el corpus tiene pares suficientes para que valga la pena."""
    if not pares or not raices_lexico(paquete.codigo.split("-")[0], paquete.stemmer):
        return False
    conjunto = frozenset(tuple(p.split(" ", 1)) for p in pares)
    base = Corrector(paquete, estadisticas, pares=frozenset())
    con = Corrector(paquete, estadisticas, pares=conjunto)
    aciertos = errores = probadas = 0
    vistas: set[str] = set()
    for texto in textos:
        for linea in texto.splitlines():
            palabras = _PALABRA.findall(linea)
            if len(palabras) < 5 or linea in vistas:
                continue
            vistas.add(linea)
            elegibles = [p for p in palabras if len(p) >= 6 and p.islower() and base._en_corpus(base.plano(p))]
            if not elegibles:
                continue
            palabra = elegibles[probadas % len(elegibles)]
            errada = _errata_de_prueba(palabra, probadas)
            pregunta = re.sub(rf"(?<!\w){re.escape(palabra)}(?!\w)", errada, linea, count=1)
            sin = base.correcciones(pregunta).get(errada)
            con_ctx = con.correcciones(pregunta).get(errada)
            if con_ctx and con_ctx != sin:
                if base._raiz(base.plano(con_ctx)) == base._raiz(base.plano(palabra)):
                    aciertos += 1
                else:
                    errores += 1
            probadas += 1
            if probadas >= MUESTRA_AUTOPRUEBA:
                return aciertos > 0 and errores * 4 <= aciertos
    return aciertos > 0 and errores * 4 <= aciertos


# id(estadísticas), id(paquete) → (estadísticas, paquete, corrector).
_CORRECTORES: dict[tuple[int, int], tuple[object, object, Corrector]] = {}


def correcciones(pregunta: str, paquete, estadisticas) -> dict[str, str]:
    """Texto de la pregunta → su corrección (vacío si ninguna). La clave puede ser dos
    palabras («estacio namiento») y el valor, dos palabras («abre el»)."""
    if paquete is None or getattr(paquete, "respaldo", False) or not getattr(estadisticas, "df", None):
        return {}
    if not raices_lexico(paquete.codigo.split("-")[0], paquete.stemmer):
        return {}
    clave = (id(estadisticas), id(paquete))
    guardado = _CORRECTORES.get(clave)
    if guardado is None or guardado[0] is not estadisticas or guardado[1] is not paquete:
        _CORRECTORES.clear()  # un índice por motor: no se acumulan vocabularios viejos
        guardado = (estadisticas, paquete, Corrector(paquete, estadisticas))
        _CORRECTORES[clave] = guardado
    return guardado[2].correcciones(pregunta)


def corregir(pregunta: str, cambios: dict[str, str]) -> str:
    """La pregunta con cada corrección aplicada (palabras completas, sin tocar el resto)."""
    for original, forma in cambios.items():
        pregunta = re.sub(rf"(?<!\w){re.escape(original)}(?!\w)", forma, pregunta)
    return pregunta


__all__ = ["Corrector", "autoprueba_contexto", "borrados", "correcciones", "corregir", "distancia",
           "pares_de_contexto", "raices_lexico"]
