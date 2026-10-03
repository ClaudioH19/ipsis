"""Lo que el servicio necesita para sostener un frontend externo:
autenticación de widget por clave pública y límite de
peticiones. CORS se configura directamente con ``CORSMiddleware`` de FastAPI
en ``rag/servicio/api.py`` (no necesita lógica propia); este módulo cubre las
otras dos piezas, ambas deterministas y sin dependencias nuevas.

Ninguna de las dos reemplaza una autenticación real de usuario final: están
pensadas para un widget que corre en el navegador de un visitante anónimo,
no para proteger datos privados por usuario.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Autenticación de widget: una clave PÚBLICA por sitio, enviada en una
# cabecera HTTP. Deliberadamente NO es un secreto -- el widget se sirve al
# navegador de cualquier visitante, que puede leer la clave con solo abrir
# las herramientas de desarrollador. Su función es distinguir integradores
# (qué sitio hace cada petición) y poder revocar el acceso de uno sin tocar
# a los demás, no impedir que alguien la copie. Si hiciera falta algo más
# fuerte, el paso siguiente (fuera de esta tanda) es que el sitio anfitrión
# firme un token de sesión corto desde SU backend, que sí puede guardar un
# secreto.
# ---------------------------------------------------------------------------
NOMBRE_CABECERA_CLAVE_WIDGET = "X-Rag-Widget-Key"


def verificar_clave_widget(clave_recibida: str | None, claves_validas: list[str]) -> None:
    """Lanza ``HTTPException(401)`` si hay claves configuradas y
    ``clave_recibida`` no es ninguna de ellas.

    Comportamiento por defecto, EXPLÍCITO (no accidental): si
    ``claves_validas`` está vacía (``configuracion/asistente.yaml::claves_widget`` sin
    configurar, el valor de fábrica de ``rag init``), no se exige ninguna
    clave -- cualquier petición pasa, con o sin cabecera. Es la opción que
    deja al widget funcionando de inmediato para quien recién adopta el
    plugin; un despliegue que quiera distinguir integradores agrega al menos
    una clave (``rag configurar claves_widget=clave-sitio-a,clave-sitio-b``)
    y desde ese momento toda petición sin una clave de esa lista se
    rechaza."""
    if not claves_validas:
        return
    if clave_recibida not in claves_validas:
        raise HTTPException(status_code=401, detail="clave de widget inválida o ausente "
                             f"(cabecera {NOMBRE_CABECERA_CLAVE_WIDGET!r})")


# ---------------------------------------------------------------------------
# Límite de peticiones: *token bucket* clásico, EN MEMORIA DEL PROCESO, por
# identificador (clave de widget + IP del cliente).
#
# Documentado sin ambigüedad porque es una limitación real, no un detalle
# menor: con varios procesos (varios workers de uvicorn/gunicorn, o varias
# réplicas del contenedor) cada uno lleva su propia cuenta -- N procesos
# permiten hasta N veces la tasa configurada en total. Un límite COMPARTIDO
# de verdad exigiría un almacén externo (Redis, típicamente), que este
# proyecto no usa (ver pyproject.toml / restricción de "sin dependencias
# nuevas"). Para el caso de uso previsto -- un solo proceso uvicorn detrás de
# un único despliegue pequeño -- es exacto; para escalar horizontalmente hay
# que reemplazar este limitador, no solo subir la cifra.
# ---------------------------------------------------------------------------
@dataclass
class _Bucket:
    tokens: float
    ultima_actualizacion: float


class LimitadorPeticiones:
    """``capacidad`` es el máximo de peticiones en ráfaga; ``tasa_por_segundo``
    es cuántos tokens se recargan por segundo (p.ej. 0.333 ≈ 1 cada 3s).
    Cada identificador nuevo arranca con el bucket lleno menos la petición
    que lo crea, para que la primera petición de un integrador nunca se
    rechace por sí sola."""

    def __init__(self, capacidad: float, tasa_por_segundo: float):
        if capacidad <= 0 or tasa_por_segundo <= 0:
            raise ValueError("capacidad y tasa_por_segundo deben ser positivos")
        self.capacidad = float(capacidad)
        self.tasa_por_segundo = float(tasa_por_segundo)
        self._buckets: dict[str, _Bucket] = {}
        self._candado = threading.Lock()

    def permitir(self, identificador: str) -> bool:
        """``True`` si la petición se admite (consume un token); ``False``
        si el identificador ya agotó su bucket. Reloj monotónico
        (``time.monotonic``), no afectado por ajustes del reloj del sistema."""
        ahora = time.monotonic()
        with self._candado:
            bucket = self._buckets.get(identificador)
            if bucket is None:
                self._buckets[identificador] = _Bucket(tokens=self.capacidad - 1, ultima_actualizacion=ahora)
                return True
            transcurrido = max(0.0, ahora - bucket.ultima_actualizacion)
            bucket.tokens = min(self.capacidad, bucket.tokens + transcurrido * self.tasa_por_segundo)
            bucket.ultima_actualizacion = ahora
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True
            return False

    def reiniciar(self) -> None:
        """Solo para tests: vacía todos los buckets."""
        with self._candado:
            self._buckets.clear()


def identificador_limitador(clave_widget: str | None, ip: str | None) -> str:
    """Identificador estable para el token bucket: clave de widget (o
    ``"sin-clave"`` si no se envió ninguna) + IP del cliente -- así dos
    integradores sin clave configurada todavía no comparten un único bucket
    global, y un integrador CON clave queda aislado de los demás aunque
    compartan salida NAT."""
    return f"{clave_widget or 'sin-clave'}:{ip or 'desconocida'}"
