"""Rankings temporales: cursores opacos, ligados a una consulta y una sesión."""
from collections import OrderedDict
from copy import copy, deepcopy
from dataclasses import dataclass, field
from secrets import token_urlsafe
from threading import Lock
from time import monotonic
from ipsis.consulta.errores import ContinuacionInvalida


@dataclass
class _Busqueda:
    pregunta: str
    sesion: str
    creada: float
    ctx: object
    resultados: list
    eventos: list
    tamano: int
    cursores: list[str]
    caracteres: int
    paginas: dict = field(default_factory=dict)
    avanzada: int = 0
    lock: object = field(default_factory=Lock)


class RankingsTemporales:
    """Una instantánea por búsqueda; repetir un cursor devuelve la misma página.

    TTL absoluto de diez minutos y límites de 64 búsquedas / 32M caracteres.
    El límite de caracteres cubre las copias de contexto retenidas, no representa
    el consumo exacto de memoria del intérprete. Un reinicio invalida los cursores.
    """

    def __init__(self, *, ttl=600, capacidad=64, max_caracteres=32_000_000,
                 reloj=monotonic):
        self.ttl, self.capacidad, self.max_caracteres = ttl, capacidad, max_caracteres
        self.reloj = reloj
        self._busquedas = OrderedDict()
        self._cursores = {}
        self._caracteres = 0
        self._lock = Lock()

    def _eliminar(self, clave):
        b = self._busquedas.pop(clave)
        self._caracteres -= b.caracteres
        for cursor in b.cursores:
            self._cursores.pop(cursor, None)

    def _expirar(self):
        ahora = self.reloj()
        for clave, b in list(self._busquedas.items()):
            if ahora - b.creada >= self.ttl:
                self._eliminar(clave)

    def guardar(self, pregunta, sesion, ctx, resultados, eventos, tamano):
        if len(resultados) <= tamano:
            return None
        caracteres = sum(len(t) * 2 for _, t in resultados) + sum(
            len(c.chunk.texto_fuente) + len(c.chunk.texto_embedding) for c in ctx.candidatos)
        if caracteres > self.max_caracteres:
            return None
        cursores = [token_urlsafe(24) for _ in range(tamano, len(resultados), tamano)]
        b = _Busqueda(" ".join(pregunta.split()), sesion, self.reloj(), deepcopy(ctx),
                      deepcopy(resultados), deepcopy(eventos), tamano, cursores, caracteres)
        with self._lock:
            self._expirar()
            while self._busquedas and (len(self._busquedas) >= self.capacidad or
                    self._caracteres + caracteres > self.max_caracteres):
                self._eliminar(next(iter(self._busquedas)))
            clave = token_urlsafe(24)
            self._busquedas[clave] = b
            self._caracteres += caracteres
            for i, cursor in enumerate(cursores):
                self._cursores[cursor] = (clave, i)
        return cursores[0]

    def obtener(self, pregunta, sesion, cursor, preparar=None):
        with self._lock:
            self._expirar()
            ubicacion = self._cursores.get(cursor)
            if ubicacion is None:
                raise ContinuacionInvalida("search expired; submit the question again")
            clave, pagina = ubicacion
            b = self._busquedas[clave]
            if b.sesion != sesion or b.pregunta != " ".join(pregunta.split()):
                raise ContinuacionInvalida("search cursor does not belong to this query/session")
            self._busquedas.move_to_end(clave)
        # Una búsqueda se avanza una vez. Otras búsquedas no esperan su inferencia.
        with b.lock:
            indice = pagina + 1
            if indice in b.paginas:
                return (*deepcopy(b.paginas[indice]), True)
            if indice != b.avanzada + 1:
                raise ContinuacionInvalida("continue from the previous search page")
            offset = indice * b.tamano
            ctx = copy(b.ctx)
            ctx.diagnostico = deepcopy(b.ctx.diagnostico)
            restantes = b.resultados[offset:]
            if preparar is not None:
                restantes = preparar(ctx, restantes)
                # Los rangos publicados son ordinales globales, no logits.
                for i, (c, _) in enumerate(restantes):
                    c.chunk.metadata["rango_resultado"] = offset + i + 1
                b.resultados[offset:] = restantes
            elegidos = restantes[:b.tamano]
            siguiente = b.cursores[pagina + 1] if pagina + 1 < len(b.cursores) else None
            b.ctx = ctx
            b.avanzada = indice
            # La repetición conserva el estado de esta página, no copia todo el corpus.
            pagina_ctx = copy(ctx)
            pagina_ctx.candidatos = [c for c, _ in elegidos]
            pagina_ctx.diagnostico = deepcopy(ctx.diagnostico)
            b.paginas[indice] = (pagina_ctx, elegidos, b.eventos, offset, siguiente)
            return (*deepcopy(b.paginas[indice]), False)

    def limpiar(self):
        with self._lock:
            self._busquedas.clear()
            self._cursores.clear()
            self._caracteres = 0
