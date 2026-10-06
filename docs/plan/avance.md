# Avance del plan V4

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado (explicar en «Hallazgos») · ⚠ espera al usuario.

Punto de partida (2026-10-06): rama `v2/ruta` en `39c7878`, PR #7 abierto
hacia `main`; suite completa 935 pruebas, 2 omitidas.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| F1.1 | ✅ | 2026-10-06 | `c209690` | 60 casos por idioma (14/20/16/4/3/3); 3 documentos nuevos por idioma. Capacidad `requisito` normalizada a `condicion`. |
| F1.2 | ✅ | 2026-10-06 | `c209690` | 20 conversaciones y 58 turnos por idioma (38 con `hereda`, 54 con respuesta literal, 4 sin respuesta directa); `medir.py`. |
| F1.3 | ✅ | 2026-10-06 | `c209690` | 9 pruebas, < 2 s. |
| F1.4 | ✅ | 2026-10-06 | (este commit) | Código en `39c7878`. Tablas abajo. |
| F1.5 | ✅ | 2026-10-06 | `c209690` | evaluation.md (bancos y tamaño de muestra) y CHANGELOG. |
| F1.6 | ✅ | 2026-10-06 | `c209690` + este | D6: en `v2/ruta`. |
| F1.7 | ✅ | 2026-10-06 | (este commit) | `tests/datos/banco_consultas/medir.py`, con `--comparar` e `IPSIS_CODIGO`. |
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
| light | 14 / 3 | 5 / 1 | 8 / 4 |
| medium | 25 / 0 | 16 / 1 | 15 / 0 |

Directas erróneas: light es-parafrasis-002, es-trampa-004, es-exacta-003;
light en-exacta-014; light pt-parafrasis-005, pt-trampa-003, pt-exacta-003,
pt-exacta-014; medium en-ambigua-002.

Latencia media del banco de consultas (ms): light 142 / 129 / 142, medium
3.101 / 2.804 / 3.357 (es / en / pt; con 9 documentos por idioma).

Banco de conversaciones (herencia correcta / indebida / perdida; respuestas
correctas; directas indebidas), sobre 38 turnos con `hereda`, 54 con
respuesta y 4 sin respuesta directa por idioma:

| | es | en | pt |
|---|---|---|---|
| light | 26 / 0 / 12; 29; 0 | 25 / 0 / 13; 19; 0 | 21 / 0 / 17; 20; 0 |
| medium | 29 / 0 / 9; 38; 0 | 26 / 0 / 12; 34; 0 | 21 / 0 / 17; 31; 0 |

Lectura: hoy nunca hereda donde no debe (0 indebidas), pero pierde entre 9 y
17 seguimientos por idioma: lo que F4 debe subir sin crear herencias
indebidas.

## Mediciones por tarea

(Se agregan al cerrar cada tarea que cambia el motor: mismas tablas, más la
latencia media de light en el banco universal.)

## Hallazgos

- 2026-10-06 (F1.4): con el corpus ampliado aparecen dos falsos ok que el
  banco de 18 casos no tenía: light es-trampa-004 («¿Qué pasa si la unidad
  requirente rechaza los productos recibidos?») y light pt-trampa-003
  («Quem aprova o pagamento… no Financeiro?»). Quedan como línea base.

- 2026-10-06: el widget guardaba el `session_id` en `localStorage` pero no
  el historial visible: al recargar, la persona veía el chat vacío y el
  servidor seguía recordando el tema anterior. F4.3 lo corrige.
