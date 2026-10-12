"""Errores de ciclo de vida compartidos por los motores documentales."""


class MotorNoListo(RuntimeError):
    pass


class MotorSaturado(RuntimeError):
    pass


class ContinuacionInvalida(ValueError):
    """Una búsqueda expiró o el cursor no pertenece a su consulta/sesión."""
