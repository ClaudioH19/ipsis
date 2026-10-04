"""Control de admisión: límite duro de consultas concurrentes.

Sin cola ni degradación escalonada: al superar el límite, la API responde
503 de inmediato. El límite se configura en ``servicio.concurrencia_maxima``.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum

# ==========================================================================
# ADMISION (sección 7, alcance recortado — ver docstring del módulo)
# ==========================================================================
class NivelServicio(str, Enum):
    NORMAL = "normal"
    MEDIA = "media"     # FASE 5 completa — no implementado en esta etapa
    ALTA = "alta"        # FASE 5 completa — no implementado en esta etapa
    SATURADO = "saturado"


@dataclass
class ConfiguracionAdmision:
    concurrencia_maxima: int


class ControlAdmision:
    """Límite duro de peticiones concurrentes, sin cola de espera: una
    petición que no cabe se rechaza de inmediato (503), en vez de esperar y
    acumular latencia — coherente con el principio fijo de
    ``configuracion/motor.yaml``: "ante carga, el sistema degrada en escalones y
    rechaza con 503 antes que acumular latencia". Solo hay dos niveles:
    normal y saturado.

    Pensado para poder testearse sin concurrencia real: ``intentar_admitir``
    y ``liberar`` son las dos operaciones atómicas que el test puede invocar
    directamente para forzar el estado "saturado" de forma determinista.
    """

    def __init__(self, config: ConfiguracionAdmision):
        self.config = config
        self._lock = threading.Lock()
        self._en_curso = 0

    def intentar_admitir(self) -> bool:
        """True si se admite (reserva un cupo); False si está saturado."""
        with self._lock:
            if self._en_curso >= self.config.concurrencia_maxima:
                return False
            self._en_curso += 1
            return True

    def liberar(self) -> None:
        with self._lock:
            self._en_curso = max(0, self._en_curso - 1)

    def nivel_actual(self) -> NivelServicio:
        with self._lock:
            if self._en_curso >= self.config.concurrencia_maxima:
                return NivelServicio.SATURADO
            return NivelServicio.NORMAL

    @property
    def en_curso(self) -> int:
        with self._lock:
            return self._en_curso
