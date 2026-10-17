# Fichas de audio y video

ipsis puede señalar un audio o un video que corresponde a la pregunta, **sin transcribirlo ni analizarlo**. Escribes una ficha
breve (un archivo YAML) por audio o video; ipsis busca la ficha cuyo texto coincide con la pregunta y la muestra en una tarjeta
aparte, **después** de las fuentes de documentos. No se genera nada: la tarjeta muestra el texto de la propia ficha
([ADR 0011](../../decisions/0011-media-records-in-a-separate-lane.md)).

## Una ficha

Un archivo por audio o video en `media/` (junto a `documents/`), con el nombre de su id (`media/induccion.yaml`):

```yaml
title: Inducción a la plataforma de matrícula    # obligatorio
kind: video                                      # obligatorio: video | audio
url: https://example.org/induccion               # obligatorio: un enlace http(s)
description: Cómo ingresar, inscribir asignaturas y revisar el horario.   # obligatorio
keywords: [matrícula, horario]                   # opcional
language: es                                     # opcional
version: "2026-03"                               # opcional; se muestra junto al título
duration: "14:32"                                # opcional: MM:SS u HH:MM:SS (entre comillas)
active: true                                     # opcional: false la deja fuera del índice
chapters:                                        # opcional
  - at: "01:10"
    title: Ingresar con la clave única
  - at: "06:45"
    title: Inscribir asignaturas
    description: Elegir secciones y confirmar.
```

- El texto de la ficha es lo que se busca: escribe el título, la descripción y los títulos de capítulo como la gente pregunta.
- Un **capítulo** permite que la tarjeta diga «Desde 6:45» y, en YouTube y Vimeo, abra el enlace en ese minuto. Se muestra lo que
  más se acerca a la pregunta: el video si es sobre todo el video, un capítulo si es sobre él.
- `transcript` se rechaza: ipsis no lee ni transcribe el contenido.
- `file:` (un archivo bajo `media/files/`) lo acepta el formato pero **todavía no se sirve ni se muestra**: usa `url`. ipsis no
  publica tus archivos, lo que los mantiene privados ([ADR 0011](../../decisions/0011-media-records-in-a-separate-lane.md)).

## Indexación

`ipsis index` (y `ipsis sync`, que detecta fichas cambiadas) indexa las fichas en su propia colección, aparte de los documentos, e
imprime las inválidas con lo que falla (`[!] media/induccion.yaml: …`). El índice de documentos es el mismo con o sin `media/`.

## Encenderlo y el umbral

```yaml
# config/engine.yaml
media:
  enabled: true      # encendido por defecto; sin carpeta media/ no hace nada
  min_score: 0.874   # bajo este coseno denso no se muestra nada; null no muestra nada en absoluto
  max_results: 1     # fichas por página (1 a 5)
  budget_ms: 150     # el carril se omite si a la consulta le queda menos tiempo
```

Una ficha se muestra solo si su coseno alcanza `min_score`; sin él **no se muestra nada**. El valor por defecto se midió en un
banco sintético (`tests/datos/banco_multimedia/es/`, 90 preguntas, 20 fichas) con `intfloat/multilingual-e5-small`: **0 fichas
mostradas sin corresponder en dev (36 preguntas) y 1 de 24 en test**, y la ficha correcta se mostró en el 78 % (dev) y el 92 %
(test) de las preguntas que tienen una. Las preguntas las escribió el mismo asistente que escribió las fichas, así que las cifras
son optimistas; mide las tuyas:

```bash
python herramientas/evaluacion/carril_multimedia.py --banco <tu banco> --salida /tmp/mm/carril
```

El informe está en [`docs/methodology/mediciones/multimedia/carril.md`](../../methodology/mediciones/multimedia/carril.md). Si la
tarjeta aparece cuando no debe, sube `min_score`; si nunca aparece, bájalo un poco y vuelve a medir.

## Qué muestra el widget

Tras las fuentes y «Mostrar más resultados», un bloque aparte: «También hay un video sobre esto», con tipo, duración, versión,
título, capítulo y minuto, la descripción de la ficha («Según la descripción del video») y un botón «Abrir el video» que abre el
enlace en otra pestaña. No hay reproductor incrustado. Nunca cambia las fuentes de documentos ni su orden, y aparece solo en la
primera página. La API lo devuelve como `media` ([guía del widget](web.md)).
