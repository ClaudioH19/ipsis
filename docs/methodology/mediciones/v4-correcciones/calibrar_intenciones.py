"""Repite la búsqueda dev con la nueva condición de compatibilidad, sin usar test."""
from pathlib import Path

ANTERIOR = Path(__file__).resolve().parent.parent / "v4/calibrar_intenciones.py"
# Conserva el mismo grid, ejemplos, etiquetas y desempate de V4. La única
# condición adicional es la compatibilidad declarada antes de esta medición.
codigo = ANTERIOR.read_text(encoding="utf-8")
cambios = {
    "RespaldoIntenciones, tiene_tema": "RespaldoIntenciones, tiene_tema, compatible_con_respaldo",
    '"con_tema": tiene_tema(preparada, paquete, estadisticas),':
        '"con_tema": tiene_tema(preparada, paquete, estadisticas), "compatible": compatible_con_respaldo(caso["pregunta"], paquete, p.candidato),',
    'if f["similitud"] > tau and f["margen"] > delta':
        'if f["compatible"] and f["similitud"] > tau and f["margen"] > delta',
    'if f["con_tema"] and f["candidato"] in habilitadas':
        'if f["con_tema"] and f["compatible"] and f["candidato"] in habilitadas',
}
for antes, despues in cambios.items():
    assert antes in codigo, antes
    codigo = codigo.replace(antes, despues)
exec(compile(codigo, str(ANTERIOR), "exec"), {"__file__": __file__, "__name__": "__main__"})
