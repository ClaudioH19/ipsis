# Capa léxica: BM25, TF-IDF y señales

## 1. Propósito

Dar señales baratas, deterministas y explicables para tres cosas: recuperar
(BM25 en la búsqueda híbrida), detectar el «se parece pero no responde» y
ahorrar latencia con salidas tempranas que evitan ejecutar modelos.

## 2. Alcance y no-alcance

- **Alcance:** convertir texto en términos, estadísticas del corpus, vector
  BM25, TF-IDF y las señales `s_oov`, foco, `s_foco`, `s_cov` y `s_lex`.
- **No-alcance:** entender paráfrasis; eso lo compensan el
  [reranker](reranker.md) y el [lector](lector.md) en medium y heavy.

## 3. Entradas y salidas versionadas

- `terminos(texto, paquete)`: el **único** camino de texto a términos, igual
  al indexar y al consultar.
- `.ipsis/indice/estadisticas.json`: `n_chunks`, `largo_medio`, `df[término]` y
  `superficie[término]` (la forma original más frecuente, para mostrarla).
  JSON legible, con el hash del corpus.

## 4. Algoritmo y desempates

`terminos()`: tokenizar Unicode (`\w+`) → casefold → quitar tildes (solo
escritura latina) → stem Snowball del idioma, si el paquete define uno.

- **IDF:** `ln(1 + (N − df + 0,5) / (df + 0,5))`.
- **BM25 en Qdrant sin vocabulario:** id de término = `zlib.crc32`; el
  documento lleva `tf·(k1+1) / (tf + k1·(1 − b + b·largo/largo_medio))` y la
  consulta, 1 por término; el IDF lo aplica Qdrant (`modifier: idf`).

| Señal | Definición | Qué detecta |
|---|---|---|
| `s_oov` | masa IDF de los términos de la pregunta ausentes del corpus / masa total (un término desconocido recibe el IDF máximo) | pregunta fuera de dominio |
| foco | los 2 términos de la pregunta con mayor IDF que existen en el corpus | «de qué se habla» |
| `s_foco` | fracción de términos foco presentes en la oración de la respuesta (1 si no hay foco) | el tramo correcto en el lugar equivocado: «6 meses» del filtro ante una pregunta por la garantía da `s_foco = 0` |
| `s_cov` | masa IDF de la pregunta presente en la oración / masa total | cobertura general |
| `s_lex` | BM25(pregunta, oración) / BM25 ideal de la pregunta | elige la oración ancla en light |

**Salida temprana:** si ningún candidato contiene un término foco, no se
ejecutan reranker ni lector; la política decide entre `relacionado` y
`sin_respuesta` con lo que hay.

Otros usos de TF-IDF: palabras clave de cada fragmento, `ipsis golden
plantilla` (MMR sobre secciones para proponer preguntas diversas) y la
clasificación `exacta`/`parafrasis` al importar el golden (`s_cov ≥ 0,6`).

## 5. Supuestos

El IDF basta para restar peso a las palabras frecuentes: no hay listas de
stopwords obligatorias (las del paquete son opcionales).

## 6. Invariantes

- Un solo `terminos()`; lo que se indexa y lo que se consulta coinciden y
  cualquier puntaje se puede reproducir.
- Todas las señales son funciones puras en `ipsis/lenguaje/lexico.py`, con
  resultado en [0, 1].

## 7. Parámetros y defaults

`k1 = 1,2`, `b = 0,75`, `max_terminos_foco = 2`, `salida_temprana_sin_foco:
true` (perfil, sección `lexico` y `cascada`).

## 8. Complejidad y recursos

Menos de 5 ms por consulta; las estadísticas ocupan unos KB por documento.

## 9. Fallos y fallback

- Idioma sin stemmer: términos sin stem.
- Estadísticas faltantes o de otro corpus: `ipsis doctor` pide `ipsis indexar`.

## 10. Seguridad y privacidad

Sin E/S en las señales; las estadísticas solo contienen términos y conteos.

## 11. Pruebas técnicas

`tests/lenguaje/test_lexico.py`, `tests/lenguaje/test_texto.py` y los bancos
de evaluación (trampas «mismo tema, dato ausente»).

## 12. Limitaciones

- **Sinónimos:** si el usuario dice «cartucho» y el documento «filtro»,
  `s_foco` cae y el sistema se abstiene de más. Es el lado seguro del error;
  `τ_foco` se calibra con la categoría `parafrasis` del golden.
- `acuerdo` (top-1 denso en el top-3 de BM25 y viceversa) se midió y se
  descartó como señal de la política: sin efecto en el banco universal y
  +4,6 ms de p95. La función se conserva para el experimento del benchmark.
- El chunking por cohesión léxica (`texttiling_v1`) se probó y se descartó:
  mismos estados que cortar por sección y más falsos `ok` que el chunker
  actual.

## 13. Referencias y procedencia

- Robertson y Zaragoza, *The Probabilistic Relevance Framework: BM25 and
  Beyond* (2009).
- [snowballstemmer](https://pypi.org/project/snowballstemmer/) (BSD-3-Clause).
- Carbonell y Goldstein, *MMR* (SIGIR 1998).

## 14. Estado

Estable. `τ_foco` y `τ_oov_ok` se calibran por proyecto.
