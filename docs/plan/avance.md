# Avance del plan V4

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado (explicar en «Hallazgos») · ⚠ espera al usuario.

Punto de partida (2026-10-06): rama `v2/ruta` en `39c7878`, PR #7 abierto
hacia `main`; suite completa 935 pruebas, 2 omitidas.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| F1.1 | ✅ | 2026-10-06 | — | 60 casos por idioma (14/20/16/4/3/3); 3 documentos nuevos por idioma. Capacidad `requisito` normalizada a `condicion`. |
| F1.2 | ✅ | 2026-10-06 | — | 20 conversaciones y 58 turnos por idioma (38 con `hereda`, 54 con respuesta literal, 4 sin respuesta directa); `medir.py`. |
| F1.3 | ✅ | 2026-10-06 | — | 9 pruebas, < 2 s. |
| F1.4 | 🔶 | 2026-10-06 | — | Medición en curso. |
| F1.5 | ✅ | 2026-10-06 | — | evaluation.md (bancos y tamaño de muestra) y CHANGELOG. |
| F1.6 | ⬜ | | | D6: en `v2/ruta`. |
| F1.7 | ⬜ | | | |
| F4.1 | 🔶 | 2026-10-06 | — | Borrador fuera del repo; se aplica después de F1.4. |
| F4.2 | ⬜ | | | |
| F4.3 | ⬜ | | | D5 confirmada. |
| F4.4 | ⬜ | | | |
| F4.5 | ⬜ | | | |
| F4.6 | ⬜ | | | |
| F4.7 | ⬜ | | | |
| F2.1 | ⬜ | | | |
| F2.2 | ⬜ | | | |
| F2.3 | ⬜ | | | |
| F2.4 | ⬜ | | | |
| F2.5 | ⬜ | | | |
| F2.6 | ⬜ | | | |
| F2.7 | ⬜ | | | |
| F2.8 | ⬜ | | | |
| F3.1 | ⬜ | | | |
| F3.2 | ⬜ | | | |
| F3.3 | ⬜ | | | |
| F3.4 | ⬜ | | | |
| F3.5 | ⬜ | | | |
| F5.1 | ⬜ | | | |

## Línea base (F1.4)

Correctas / directas erróneas (banco de consultas, 60 por idioma):

| | es | en | pt |
|---|---|---|---|
| light | | | |
| medium | | | |

Banco de conversaciones (herencia correcta / indebida / perdida; respuestas
correctas; directas indebidas):

| | es | en | pt |
|---|---|---|---|
| light | | | |
| medium | | | |

## Mediciones por tarea

(Se agregan al cerrar cada tarea que cambia el motor: mismas tablas, más la
latencia media de light en el banco universal.)

## Hallazgos

- 2026-10-06: el widget guardaba el `session_id` en `localStorage` pero no
  el historial visible: al recargar, la persona veía el chat vacío y el
  servidor seguía recordando el tema anterior. F4.3 lo corrige.
