# Banco multimedia (español, sintético)

Mide cuándo el carril multimedia debe mostrar una ficha de audio o video y cuándo no
([ADR 0011](../../../../docs/decisions/0011-media-records-in-a-separate-lane.md)). **Es sintético**: las fichas y las
preguntas las escribió el mismo asistente que construye el carril, sobre los documentos de
`../../banco_terminos/validacion/es/corpus/`, así que sus cifras son optimistas. No sustituye a fichas y preguntas
reales; si se aportan, se miden aparte y quedan fuera del repositorio.

- `fichas/`: 20 fichas (`media/*.yaml` de un proyecto), 14 videos y 6 audios; 10 con de 2 a 3 capítulos. Los enlaces
  son de `example.org`: no se abre ningún archivo ni enlace.
- `casos.jsonl`: 90 preguntas, una por línea.

| Tipo | Cantidad | Qué debe pasar |
|---|---|---|
| `ficha` | 30 | se muestra la ficha `media_id` (y, si `capitulo_segundos` no es `null`, ese capítulo) |
| `mismo_tema` | 30 | no se muestra ninguna ficha: el tema está en un documento (`documento`) pero ninguna ficha responde la pregunta |
| `fuera` | 30 | no se muestra ninguna ficha: la pregunta es ajena al dominio |

Campos de cada caso: `id`, `pregunta`, `tipo`, `informal` (10 en total: escritas sin tildes, con abreviaturas o en
tono coloquial), `particion` y, según el tipo, `media_id` y `capitulo_segundos` o `documento`.

**Particiones:** `dev` (54) y `test` (36), fijadas por el orden del `id` (tipos intercalados: cada tres casos hay uno de cada
tipo). Los umbrales se eligen mirando solo `dev`; `test` se informa.

**Casos difíciles a propósito:** los `mismo_tema` comparten palabras con una ficha del mismo asunto (por ejemplo, «¿a qué
hora abre la biblioteca los sábados?» frente a la ficha de préstamos) y son la parte más exigente.

Medición: `herramientas/evaluacion/carril_multimedia.py`.
