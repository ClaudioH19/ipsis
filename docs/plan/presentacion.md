# Plan de presentación: que la segunda fuente correcta se lea como comprensión

Abierto el 2026-10-16. Tareas para ejecutar una por sesión:
[presentacion-tareas.md](presentacion-tareas.md). Estado:
[presentacion-avance.md](presentacion-avance.md).

## Problema

V2 publica tres fuentes porque la correcta no siempre es la primera. En los
documentos reales (banco adversarial de 56 preguntas, `medium`, estructural,
ver [precision-ingesta-avance.md](precision-ingesta-avance.md)) hit@1 es 0,893
y hit@3 0,946: en unas 5 de cada 100 preguntas la fuente correcta es la
segunda o la tercera. Muchos de esos fallos son **pares de secciones
hermanas** (P1/P2: misma estructura, otra columna u otro artículo).

Hoy el mensaje del asistente es el mismo en todos los casos («{count} para
revisar…», `ipsis/recursos/voz/es.yaml`, `messages.results`), y el widget lo
elige solo por cantidad (`ipsis/servicio/estaticos/widget.js`, cerca de la
línea 1762). Si la persona lee la primera tarjeta como «la respuesta», una
segunda tarjeta correcta parece un error del asistente.

## Idea

No cambiar **qué** se publica, sino **cómo se presenta**. El motor describe
la forma de la página con una señal determinista (`result_shape`), y el
widget elige plantillas y disposición según esa forma:

| Forma | Cuándo (medible) | Mensaje (plantilla) | Disposición |
|---|---|---|---|
| `clear` | La primera fuente se separa del resto por más que un umbral medido | «Esto dice *{top_doc}*:» | Primera tarjeta destacada; el resto bajo «También aparece en» |
| `variants` | Las primeras fuentes son variantes de la misma sección (mismo documento y sección padre, o alcances distintos) | «Depende de tu caso:» | Tarjetas encabezadas por su alcance (P1 / P2), con atajos |
| `documents` | Las primeras fuentes vienen de documentos distintos y están cerca | «Lo encontré en {n_docs} documentos:» | Agrupadas por documento |
| `neutral` | Ninguna de las anteriores, o la función apagada | Plantillas actuales | Como hoy |

Y dos caminos de corrección:

- **Abrir el contexto de la fuente 2 o 3:** el asistente responde «Esto es de
  *{doc}*, {scope}», sin afirmar que sea la respuesta correcta.
- **«No es esto»:** pide la página siguiente (la continuación que ya existe),
  con «Entonces quizás buscabas…».

Todo texto nuevo es una plantilla de interfaz. Los valores que se insertan
(`doc_title`, `scope`, conteos) son campos literales que la API ya publica.
No hay generación de texto ([ADR 0001](../decisions/0001-non-generative-answers.md)).

## Por qué primero se mide

`clear` es la única forma que insinúa «esta es»: solo se puede activar si
existe un umbral de separación con el que la primera fuente casi nunca se
equivoca. Si la medición no lo encuentra, `clear` queda apagada y el
producto usa `variants`, `documents` y `neutral`. Así sigue siendo honesto
sin perder fluidez.

## Fases

| Fase | Contenido | Cambia la conducta por defecto |
|---|---|---|
| P0 | Medición: relación entre separación de puntajes, forma y acierto del primer resultado | No |
| P1 | Señal `result_shape` en el motor y la API (apagada por defecto) | No |
| P2 | Plantillas y disposición del widget por forma | No (solo con la señal encendida) |
| P3 | Caminos de corrección: contexto abierto y «No es esto» | Sí, ⚠ con aprobación |
| P4 | Activación por defecto, ADR y documentación | Sí, ⚠ con aprobación |
| P5 | Opcional: registro anónimo del rango abierto, para medir con personas reales | No (opt-in) |

## Límites

- No cambia el ranking, el número de resultados ni las ventanas publicadas.
- `light` no tiene reranker: su puntaje es de recuperación y su escala es
  otra. La forma `clear` se mide y se decide por perfil; en `light` puede
  quedar desactivada.
- La forma describe la página, no la verdad: «Esto dice *X*» afirma la
  procedencia del texto, no que el texto responda.
