# Banco de garantías

134 preguntas por idioma (es/en/pt) sobre seis documentos nuevos (reglamento de
estacionamiento, manual de impresora, política de vacaciones, protocolo de
emergencias, bases de beca y arriendo de salas), con unos 12 hechos cada uno.
Los nueve documentos del [banco de consultas](../banco_consultas/) quedan como
distractores.

- 98 respondibles: 51 exactas y 47 paráfrasis (formales e informales);
- 20 trampas del mismo tema, cada una junto a su par;
- 6 premisas falsas, 6 fuera de dominio y 4 ambiguas.

**Para qué sirve:** estrechar la cota de riesgo de las respuestas directas
(Clopper-Pearson). Con pocos cientos de respuestas, el 98 % observado solo
garantiza alrededor de 93 %; este banco suma cerca de 300 respondibles. No se
usa para diseñar reglas ni elegir umbrales, y como todo banco sintético no
certifica un cliente: eso lo hace `ipsis calibrate` con su golden.

Fuentes: `<idioma>/casos.yaml`. Derivados: `python tests/datos/banco_garantias/construir.py`.
