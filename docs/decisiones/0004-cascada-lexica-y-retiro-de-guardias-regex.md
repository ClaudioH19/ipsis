# ADR 0004: cascada con señales léxicas y retiro de las guardias regex

## Contexto

La política anterior (`layered_v1`) decidía por capas con un umbral de
similitud y, para evitar respuestas equivocadas, sumaba **guardias regex por
tipo de pregunta** («¿cuánto?» exige una cifra, «¿cuándo?» una fecha…).
Tenían tres problemas:

- **Atadas al español:** listas de palabras y expresiones en el código.
- **Frágiles:** una pregunta reformulada las esquivaba.
- **Ciegas al «se parece pero no responde»:** ante «¿Cuánto dura la
  garantía?», el pasaje del filtro («se cambia cada 6 meses») tiene una
  cifra, el tema parecido y un score alto.

Además, una lista curada de «palabras generales» arrastraba restos de un
dominio anterior.

## Decisión

- **Una cascada de etapas** (`consulta/etapas/`): conversacional → análisis
  → confianza → filtros → recuperación → reranking → lectura → evidencia →
  política → redacción → verificación. Cada perfil lista las suyas; las baratas van
  primero.
- **Señales léxicas explicables** (`rag/lenguaje/lexico.py`), calculadas con
  un único `terminos()` (stem Snowball del idioma) y el IDF del corpus:
  - `s_oov`: masa IDF de la pregunta ausente del corpus;
  - términos foco: los 2 de mayor IDF que existen en el corpus;
  - `s_foco`: fracción de foco presente en la oración de la respuesta;
  - `s_cov`: cobertura IDF.

  `s_foco = 0` resuelve el caso garantía/filtro sin reglas por idioma.
- **Salida temprana:** si ningún candidato contiene un término foco, no se
  ejecutan reranker ni lector.
- **`cascada_v1`:** reglas en orden (premisa, fuera de dominio, ok,
  relacionado, sin respuesta) en una función pura, `regla_cascada`, que
  comparten producción y calibración.
- **Se borran** las guardias regex, las «palabras generales», la
  tokenización latina `[a-z0-9]+` y el BM25 con vocabulario propio. BM25 pasa
  a ids por hash con el IDF aplicado en Qdrant.
- Todo lo que depende del idioma pasa a paquetes (`rag/recursos/idiomas/`).

## Consecuencias

- La misma lógica funciona en español, inglés y portugués; los demás idiomas
  usan reglas universales.
- Cada decisión deja su regla y sus señales en el diagnóstico y en el
  registro: es auditable y reproducible.
- **Límite conocido:** un sinónimo ausente del documento («cartucho» por
  «filtro») baja `s_foco` y el sistema se abstiene de más. Es el lado seguro
  del error, y `τ_foco` se calibra con la categoría `parafrasis`.
- Falsos `ok` en el banco sintético v1.1.0: 0 en light y en medium. En el
  banco universal quedan trampas «mismo tema» con `s_qa` alto en medium y
  heavy; las controla `τ_ok` calibrado por cliente.

## Estado

Aceptado e implementado (`cascada_v1` es el default; los proyectos con
`layered_v1` migran solos).
