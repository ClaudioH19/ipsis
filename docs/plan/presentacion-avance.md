# Avance del plan de presentación

Plan: [presentacion.md](presentacion.md). Tareas: [presentacion-tareas.md](presentacion-tareas.md).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado · ⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| P0.1 | ✅ | 2026-10-16 | (ver git log) | `--volcar-publicados` en `ranking_pasajes.py` (un JSONL por perfil, sin texto de pasajes ni de la pregunta); 5 pruebas nuevas. Ver «P0.1» abajo. |
| P0.2 | ⬜ | | | ⚠ ruta del banco real; ⚠ precisión objetivo de `clear` |
| P1.1 | ⬜ | | | ⚠ plantilla de `engine.yaml` y `config_version` |
| P1.2 | ⬜ | | | |
| P2.1 | ⬜ | | | |
| P2.2 | ⬜ | | | |
| P3.1 | ⬜ | | | ⚠ confirmar caminos de corrección |
| P3.2 | ⬜ | | | |
| P4 | ⬜ | | | ⚠ activación por defecto |
| P5 | ⬜ | | | Opcional; solo a pedido |

## P0.1: volcar las fuentes publicadas

- `herramientas/evaluacion/ranking_pasajes.py`: opción `--volcar-publicados RUTA` y clase `GrabadorPublicados`. Escribe un
  JSONL **por perfil** (`RUTA-light.jsonl`, `RUTA-medium.jsonl`; el volcado de candidatos existente sí se pisa entre
  perfiles). Una fila por pregunta: `id`, `split`, `perfil`, `rango_final` y, por cada fuente publicada, `rango`,
  `chunk_id`, `doc_id`, `seccion_path`, `score`, `tipo_puntaje`, `alcance`, `rasgos` y `correcto`. **No escribe el texto de
  los pasajes ni el de la pregunta**: el banco real es privado y para el análisis bastan los IDs. `correcto` usa los offsets
  del fragmento recuperado, igual que `rango_final`, y no los de la ventana ampliada.
- Pruebas (`tests/evaluacion/test_ranking_pasajes.py`, de 8 a 13): orden, puntaje y `correcto`; ausencia de texto y de
  pregunta en el archivo; resultado sin contrato HTTP; sin grabador no se registra nada; un archivo por perfil.
- **Aceptación comprobada** con una corrida real: `banco_pasajes/es`, perfil `light`, partición `todas`: 116 filas con 5
  fuentes cada una; hit@1 final 1,000 (híbrido 0,931). El archivo vive fuera del repositorio.

### Lo que esa corrida ya dice para P0.2

- En `light` el `score` publicado es de recuperación y está **normalizado respecto a la primera fuente** (vale 1,0 en 104
  de 116 primeras y los segundos van de 0,34 a 0,67), así que el margen entre las dos primeras sí informa y está acotado a
  [0, 1]. En `medium` será un logit del reranker, de otra escala: el umbral se mide por perfil, como ya estaba previsto.
- En el banco sintético ninguna fuente publicada tiene `alcance` (580 de 580 vacías): sus documentos no tienen tablas con un
  párrafo previo ni líneas enfatizadas que lo originen. La forma `variants` debe apoyarse en la sección padre
  (`seccion_path[:-1]`), no solo en `alcance`; la regla por alcance solo se podrá probar con el banco real.
- Con 116 de 116 primeros correctos en `light`, el banco sintético casi no tiene errores que estudiar: el análisis útil
  necesita el banco real (⚠ P0.2).

### Fallos previos que aparecieron al correr `tests/evaluacion` completo

Con los modelos de `medium` descargados, 5 pruebas `slow` + `modelos` fallan **también sin los cambios de P0.1**
(comprobado sobre `bd6c24e`): `test_banco_universal.py::test_falsos_ok_no_superan_la_linea_base[es|en|pt-light]`,
`test_general_regresion.py::test_regresion_documental_real[light]` y
`test_tono_no_cambia_estados.py::test_otro_tono_no_cambia_estados_reglas_ni_literalidad`. Son pruebas del motor v1
(exigen `senales` y aciertos de «respuesta directa»); desde que v2 es el predeterminado ya no producen eso. En CI sin
modelos se omiten, por eso no se veían. No se tocaron (fuera del alcance).
