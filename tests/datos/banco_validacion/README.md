# Banco de validación

99 preguntas por idioma (es/en/pt) sobre seis documentos nuevos (política de
equipos, reglamento de casino, manual de proyector, reglamento de capacitación,
seguro de salud y reglamento de gimnasio). Los nueve documentos del
[banco de consultas](../banco_consultas/) quedan como distractores.

- 67 respondibles: 44 exactas y 23 paráfrasis (formales e informales);
- 20 trampas del mismo tema, cada una junto a su par (calificadores ausentes:
  «celular» por «notebook», «cena» por «almuerzo», «pilates» por «yoga»…);
- 4 premisas falsas, 4 fuera de dominio y 4 ambiguas.

**Para qué sirve:** banco retenido. Se escribió antes de las correcciones de
2026-10-09 (exclusión de la línea de presentación y modificador adyacente) y
no se miró para diseñarlas; se mide una vez antes y otra después. Si una
corrección futura se diseña mirando sus fallos, deja de ser retenido y hace
falta otro. Como todo banco sintético, no certifica un cliente.

Medido (medium, agregados): antes 146 correctas y 9 errores en 155 directas
(94,2 %, garantía ≥ 90,1 %); después 146 y 4 en 150 (97,3 %, ≥ 94,0 %).

Fuentes: `<idioma>/casos.yaml`. Derivados: `python tests/datos/banco_validacion/construir.py`.
