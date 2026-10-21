# Banco de pasajes

Banco sintético en español, inglés y portugués (ver [precision-ingesta.md](../../../docs/methodology/precision-ingesta.md))
para medir el **orden de los pasajes**, no solo el de los documentos. A
diferencia de los demás bancos, aquí cada documento tiene muchos fragmentos
(más de 6 con `CH-F256`) y la respuesta compite con pasajes muy parecidos.

- 6 documentos principales de 2 200–2 500 palabras (reembolsos, garantía de equipos,
  permisos, compras, laboratorios y viajes), cada uno con 6 secciones «hermanas» de
  más de 300 palabras: mismo tema, distinto actor, producto o cifra.
- 4 documentos «gemelos» (reglamento de biblioteca y de titulación de las facultades
  de Ciencias e Ingeniería): mismo texto, distintas cifras.
- 116 preguntas respondibles: 42 `segunda` (la respuesta está en la segunda mitad de
  una sección larga), 52 `hermana` (solo se distingue por el actor o la facultad) y
  22 `parafrasis` informales. Más 15 `trampa` del mismo tema con dato ausente.
- Partición 60/40 (`dev`/`test`) fijada por posición dentro de cada clase; la
  trampa va en la partición de su par. **Los ajustes se hacen mirando solo `dev`.**

Las evidencias son la oración que contiene la respuesta, con offsets exactos.

Las fuentes (`es/corpus/*.md`, `es/casos.yaml`) las produce
`generar_fuentes.py` de forma determinista; los derivados (`banco.jsonl`,
`manifiesto.json`) los produce `construir.py`:

    python tests/datos/banco_pasajes/generar_fuentes.py
    python tests/datos/banco_pasajes/construir.py

`tests/evaluacion/test_banco_pasajes.py` falla si los derivados no coinciden.
No sirve para certificar un cliente ni para elegir umbrales de abstención; solo
para comparar configuraciones de ingesta entre sí.

## Tres idiomas

`es/`, `en/` y `pt/` tienen los mismos 10 documentos, hechos, cifras y casos (131 por idioma), redactados en
cada idioma por separado: el contenido está en `contenido_<idioma>.py` y `generar_fuentes.py` los combina.
Cada hecho trae una pregunta formal (`q`) y otra informal (`p`), escrita como en un chat («how long do they
take to give me…», «quanto demoram pra me dar…»). Sirve para comparar modelos por idioma con las mismas
preguntas; las cifras no son comparables entre idiomas, porque la redacción cambia.

    python tests/datos/banco_pasajes/generar_fuentes.py es en pt
    python tests/datos/banco_pasajes/construir.py
    python herramientas/evaluacion/ranking_pasajes.py tests/datos/banco_pasajes/en/manifiesto.json --idioma en ...
