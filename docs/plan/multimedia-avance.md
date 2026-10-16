# Avance del plan multimedia

Plan: [multimedia.md](multimedia.md). Tareas: [multimedia-tareas.md](multimedia-tareas.md).

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado · ⚠ espera al usuario.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| M0.1 | ✅ | 2026-10-16 | (ver git log) | `ipsis/ingesta/fichas.py`: lee y valida `media/*.yaml`; 82 pruebas; 21 mensajes en EN/ES. Ver «M0.1» abajo. |
| M0.2 | ⬜ | | | ⚠ ¿fichas y preguntas reales? |
| M1 | ⬜ | | | ⚠ si cambia `hash_corpus` sin `media/` |
| M2.1 | ⬜ | | | |
| M2.2 | ⬜ | | | ⚠ objetivo de fichas mostradas sin corresponder |
| M3 | ⬜ | | | |
| M4.1 | ⬜ | | | ⚠ tipos, tamaño y control de acceso |
| M4.2 | ⬜ | | | |
| M5 | ⬜ | | | ⚠ activación por defecto |

## M0.1: esquema y validación de la ficha

- **Módulo:** `ipsis/ingesta/fichas.py` (`Ficha`, `Capitulo`, `LecturaFichas`, `validar_ficha`, `leer_fichas`,
  `a_segundos`). Solo lee y valida: no indexa, no sirve archivos y no abre el audio o el video. Rutas nuevas en
  `ipsis/configuracion/rutas.py`: `MEDIA = "media"` y `MEDIA_ARCHIVOS = "media/files"`. `ipsis init` no crea la carpeta todavía.
- **Desviación de la tarea (motivo):** se pidió un modelo pydantic; se usaron *dataclasses* con validación manual. Una prueba
  existente (`tests/cli/test_mensajes.py`) exige que cada clave de mensaje exista en inglés y español y se use en el código,
  y los errores de pydantic salen en inglés. Así cada error sale del catálogo (`media.*`, 21 claves, 1114 por idioma) en el
  idioma de la interfaz.
- **Reglas que valida** (todas con prueba): `id` = nombre del archivo, solo `[a-z0-9]` con guiones; claves desconocidas
  rechazadas; `title`, `kind` (`video`/`audio`) y `description` obligatorios; exactamente uno de `url` (solo `https://`) o
  `file`; `file` solo dentro de `files/`, sin `..`, sin ruta absoluta ni `\`; `keywords`, `language`, `version`, `active`,
  `duration` y `chapters` con su forma; capítulos con `at` estrictamente creciente y anterior a `duration`; `transcript`
  rechazado con un mensaje que dice que aún no se admite. Se informan **todos** los errores de una ficha, en orden estable.
- `leer_fichas()` además exige que el `file` exista; un archivo inválido no impide leer los demás, sus errores quedan por
  `id`; el orden es por `id` y no depende del orden de creación; solo se leen `*.yaml` (no `.yml`); sin carpeta no hay
  fichas ni errores.
- **Hallazgo de YAML que afecta a quien escriba fichas:** `14:32` sin comillas se lee como el **entero 872** (PyYAML lo trata
  como base 60), mientras que `06:45` queda como texto. Como ese entero ya son los segundos, `a_segundos` acepta ambas
  formas; la guía de M5 debe decir igualmente que se pongan entre comillas.
- **Comprobación de que las pruebas no son vacías:** se rompieron a propósito tres reglas (aceptar `http://`, aceptar
  capítulos repetidos, aceptar `file` fuera de `files/`) y las pruebas fallaron en las tres, en el caso exacto.
- Suite rápida: **1683 aprobadas, 0 fallidas, 2 omitidas** (77 s).
