# Avance del plan V4

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado (explicar en «Hallazgos») · ⚠ espera al usuario.

Punto de partida (2026-10-06): rama `v2/ruta` en `39c7878`, PR #7 abierto
hacia `main`; suite completa 935 pruebas, 2 omitidas.

La tabla registra la integración inicial del 2026-10-06: «este commit»
se refiere a `b23ad8a`. Las correcciones posteriores y el estado vigente
se registran al final; los resultados iniciales se conservan como referencia.

| Tarea | Estado | Fecha | Commit | Notas |
|---|---|---|---|---|
| F1.1 | ✅ | 2026-10-06 | `c209690` | 60 casos por idioma (14/20/16/4/3/3); 3 documentos nuevos por idioma. Capacidad `requisito` normalizada a `condicion`. |
| F1.2 | ✅ | 2026-10-06 | `c209690` | 20 conversaciones y 58 turnos por idioma (38 con `hereda`, 54 con respuesta literal, 4 sin respuesta directa); `medir.py`. |
| F1.3 | ✅ | 2026-10-06 | `c209690` | 9 pruebas, < 2 s. |
| F1.4 | ✅ | 2026-10-06 | (este commit) | Código en `39c7878`. Tablas abajo. |
| F1.5 | ✅ | 2026-10-06 | `c209690` | evaluation.md (bancos y tamaño de muestra) y CHANGELOG. |
| F1.6 | ✅ | 2026-10-06 | `c209690` + este | D6: en `v2/ruta`. |
| F1.7 | ✅ | 2026-10-06 | (este commit) | `tests/datos/banco_consultas/medir.py`, con `--comparar` e `IPSIS_CODIGO`. |
| F4.1 | ✅ | 2026-10-06 | este commit | Temas, compactación y retoma auditados; herencia 36/35/34 de 38 en ambos perfiles. -007/-015 mejoran en los tres idiomas. Costes literales frente a F1 documentados. |
| F4.2 | ✅ | 2026-10-06 | este commit | Configuración opcional, reloj inyectado, vencimiento exacto y tope; suite completa en verde. |
| F4.3 | ✅ | 2026-10-06 | este commit | ID nuevo por carga de página, panel conserva sesión; widget y guías verificados. |
| F4.4 | ✅ | 2026-10-06 | este commit | Acción y núcleo en diagnóstico/CLI; esquema y diagnóstico verificados. |
| F4.5 | ✅ | 2026-10-06 | este commit | Aislamiento, concurrencia, expiración, compactación y registro posterior a guardias; 1.054 pruebas completas aprobadas, 2 omitidas. |
| F4.6 | ✅ | 2026-10-06 | este commit | Tres bancos × seis combinaciones y dos bases; G1–G6 formales pasan. Cuatro aciertos conversacionales perdidos y cinco nuevas directas sin literal frente a F1 se informan por separado. |
| F4.7 | ✅ | 2026-10-06 | este commit | ADR 0006, arquitectura, guías, README, CHANGELOG y resultados permanentes actualizados. |
| F2.1 | ✅ | 2026-10-06 | este commit | El usuario aprueba las tres fuentes y pide mayor cobertura y conservación local. Versiones, URLs, hashes, licencias y tamaños fijados. |
| F2.2 | ✅ | 2026-10-06 | este commit | Originales comprimidos guardados en `herramientas/sinonimos/datos/fuentes/`; léxicos completos, tablas filtradas y avisos en `ipsis/recursos/sinonimos/`. Reconstrucción offline por defecto. |
| F2.3 | ✅ | 2026-10-06 | este commit | Índice WordNet por idioma/stemmer, sentidos completos y colisiones; expansión solo BM25, vector original reutilizado. G5 pasa en tres rondas alternadas. |
| F2.4 | ✅ | 2026-10-06 | este commit | `domain.yaml::synonyms`, prioridad por término y coincidencia de frases completas; pruebas de OC / orden de compra y reemplazos conflictivos. |
| F2.5 | ✅ | 2026-10-06 | este commit | 25 pruebas del conversor, originales locales y reproducibilidad; wheel/sdist verificados byte a byte en copia limpia. |
| F2.6 | ✅ | 2026-10-06 | este commit | G1–G6: 1.031 pruebas aprobadas, 2 omitidas; tres bancos, 18 combinaciones sin cambios de estado, errores nuevos ni correctas perdidas. Mediciones archivadas. |
| F2.7 | ✅ | 2026-10-06 | este commit | Flujo de actualización y mantenimiento en `herramientas/sinonimos/README.md`. |
| F2.8 | ✅ | 2026-10-06 | este commit | ADR 0007, arquitectura, configuración, metodología, diagnóstico, huella de calibración y resultados de integración documentados. |
| F3.1 | ✅ | 2026-10-06 | este commit | 210 ejemplos independientes: diez por cada una de siete intenciones en es/en/pt. |
| F3.2 | ✅ | 2026-10-06 | este commit | Vectores al arrancar, consulta reutilizada, prioridad de patrones, BM25/modelos no medidos inactivos y diagnóstico de aceptación/rechazo; G5 pasa. |
| F3.3 | ✅ | 2026-10-06 | este commit | Umbrales elegidos en dev: 6 aciertos dev + 2 test, cero errores activos en el banco natural. Errores de intención en bancos secundarios e iteraciones fallidas documentados. |
| F3.4 | ✅ | 2026-10-06 | este commit | Ocho consultas adicionales con intención por perfil; ronda aislada F3 sin cambios de respuesta. Suite completa y G1–G6 en verde; respaldo de cobertura limitada. |
| F3.5 | ✅ | 2026-10-06 | este commit | ADR 0005, metodología, arquitectura, guías, CHANGELOG y evaluación final actualizados. |
| F5.1 | ⚠ | 2026-10-06 | este commit | Resumen y evidencias permanentes preparados. Falta revisión/aprobación del cierre; se conserva docs/plan/. Errores del lector y costes literales no se declaran resueltos. |

## Línea base histórica (F1.4)

Esta tabla usaba el literal de la cita amplia. Los conteos medium no son
comparables directamente con la métrica corregida; F1 se reevalúa en la
comparación final abajo.

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

- 2026-10-06 (revisión F2): `equivalentes()` también usa sinónimos para
  validar foco cuando la palabra existe en el corpus. No se debe sumar allí
  todo el diccionario automático bajo la suposición de que la guarda OOV lo
  protege. La propuesta separa recuperación de aceptación.
- 2026-10-06 (revisión de evaluación): el chequeo de acierto actual permite
  encontrar el literal esperado en la evidencia aunque no sea el tramo
  destacado como respuesta. Corregir y medir una nueva línea base antes de
  activar F2. Los bancos `test` de consultas tienen 17 respondibles por
  idioma (51 total); D1 no implica certificación del 5 % en ese split.

- 2026-10-06 (F1.4): con el corpus ampliado aparecen dos falsos ok que el
  banco de 18 casos no tenía: light es-trampa-004 («¿Qué pasa si la unidad
  requirente rechaza los productos recibidos?») y light pt-trampa-003
  («Quem aprova o pagamento… no Financeiro?»). Quedan como línea base.

- 2026-10-06: el widget guardaba el `session_id` en `localStorage` pero no
  el historial visible: al recargar, la persona veía el chat vacío y el
  servidor seguía recordando el tema anterior. F4.3 lo corrige.

## Conversión F2: primera vista previa (histórica)

Herramienta: `herramientas/sinonimos/construir.py`, formato TSV v1 y
conversor v1. Filtros: un sentido por lema, máximo ocho miembros y 2 MiB
por idioma. Se mantienen sentido, POS y tildes, no se generan flexiones.
SHA-256 de descarga y avisos completos en
[`fuentes.json`](../../herramientas/sinonimos/fuentes.json).

| Idioma | Entrada (bytes) | Synsets de entrada | Grupos conservados | Lemas únicos conservados | TSV (bytes) |
|---|---|---|---|---|---|
| es | 5.995.146 | 78.417 | 4.930 | 11.280 | 178.312 |
| en | 11.363.503 (gzip) | 107.519 | 7.162 | 16.519 | 300.006 |
| pt | 2.105.745 | 43.895 | 2.267 | 5.185 | 79.857 |

Total TSV: 558.175 bytes. Los conteos validan conversión y presupuesto;
**no son mediciones de calidad de respuesta**. Cada manifiesto de vista
previa registra también descartes por polisemia, forma y tamaño y el hash
del TSV. Los datos permanecen en `.cache`, fuera de los archivos versionados.

Validación: 21 pruebas del conversor en verde, incluyendo dos construcciones
offline de las fuentes reales y comparación byte a byte; `all --check`
reproduce los tres TSV. Una descarga nueva con el conversor produce los
mismos 13 archivos (TSV, manifiestos y avisos) que la caché original.
Suite rápida: **868 pasan, 2 omitidas, 105 deseleccionadas**, con
`PYTHONUTF8=1` heredado por subprocesos (155 s). La primera ejecución sin
esa variable falló en la prueba de portabilidad del PDF escaneado por leer
Windows-1252 como UTF-8; su repetición con UTF-8 pasó, sin modificar esa
prueba. Esta vista previa inicial se sustituyó por la incorporación ampliada
de la sección siguiente.

## Incorporación F2: fuentes locales y cobertura ampliada

2026-10-06: el usuario aprueba las fuentes y pide conservar la descarga
para seguir trabajando después. Conversor v2: offline por defecto;
`--download` solo para actualizar explícitamente una fuente. Los originales
completos comprimidos, avisos y hashes están en
`herramientas/sinonimos/datos/fuentes/` (13.438.364 bytes). No dependen de `.cache`.

Se guarda un léxico maestro sin filtros por idioma (con expresiones y todos
los sentidos) y una tabla filtrada con hasta tres sentidos, conservados en
grupos independientes. Máximo ocho miembros; nunca se mezclan acepciones.

| Idioma | Lemas/expresiones del maestro | Palabras de la tabla filtrada | Grupos filtrados | Maestro (bytes) | Filtrado (bytes) |
|---|---|---|---|---|---|
| es | 90.899 | 24.289 | 11.737 | 2.658.348 | 441.157 |
| en | 128.009 | 31.671 | 15.214 | 3.969.199 | 643.532 |
| pt | 54.071 | 11.405 | 5.612 | 1.418.291 | 200.752 |

Las tablas están en `ipsis/recursos/sinonimos/`, junto con manifiestos y
`FUENTES.md`. La tabla filtrada suma 67.365 palabras por idioma agregado,
frente a 32.984 de la vista previa inicial. El maestro suma 272.979 formas
escritas/expresiones. Son conteos de datos, **no resultados de calidad de respuesta**.

Validación de la incorporación WordNet anterior: 36 pruebas (25 del conversor más documentación,
arquitectura y recursos), incluyendo reconstrucción desde originales
versionables sin caché ni red.
`verificar_paquetes.py` compara 16 recursos byte a byte en wheel/sdist y
comprueba también todos los originales en el sdist. La construcción usa
una copia limpia: se detectaron restos de un paquete antiguo `rag` en el
`build/` compartido y no se utilizaron para la verificación definitiva.
También pasa `all --check` en esa copia limpia, sin `.cache`, usando los
originales y la configuración que contiene el repositorio.

Al terminar la incorporación WordNet, F2.3/F2.4/F2.6 estaban pendientes:
los archivos estaban incorporados y empaquetados. La integración y su
evaluación posterior se registran al final de este documento.

## Ampliación posterior: tesauros e inventario de vocabulario

2026-10-06: ante la solicitud de más vocabulario, conversor v3 y cuatro
complementos MyThes de LibreOffice, commit
`32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4`. Originales y avisos guardados
en `herramientas/sinonimos/datos/tesauros/` (10.236.338 bytes de fuentes y
avisos, más manifiesto). No hay descarga durante la reconstrucción.

| Idioma | Inventario anterior | Inventario combinado | Formas incorporadas | Palabras alfabéticas minúsculas incorporadas |
|---|---|---|---|---|
| es | 90.899 | 96.633 | 5.734 | 4.985 |
| en | 128.009 | 193.124 | 65.115 | 14.171 |
| pt | 54.071 | 94.108 | 40.037 | 38.159 |

Total: **383.865 formas/expresiones**, **110.886** nuevas (40,6%). No se
inflan los recuentos sumando coincidencias de fuentes: se deduplica por
escritura exacta e idioma. Expresiones y variantes de mayúsculas permanecen
identificables; las palabras sueltas minúsculas nuevas suman 57.315.

Nuevos `*.thesaurus.tsv`: filas dirigidas, fuentes, sentidos, etiquetas y
anotaciones originales. Nuevos `*.vocabulary.tsv`: índice de escritura y
fuentes. Las relaciones marcadas como genéricas, similares, relacionadas
o antónimas no se transforman en sinónimos. Los filtros y los hashes de
las tablas WordNet existentes se conservan.

Validación ampliada: **49 pruebas** del conversor, documentación, arquitectura
y recursos. Incluyen las codificaciones UTF-8/ISO8859-1, datos malformados,
relaciones no equivalentes, deduplicación/procedencia, suplemento corrupto,
presupuesto, detección de salidas alteradas y reconstrucción offline.
Wheel/sdist contienen **29 recursos léxicos**; el sdist conserva también
los originales y sus avisos, incluidos los complementos. La verificación
reconstruye en una copia limpia sin caché ni descargas.

Esta ampliación preparó vocabulario para trabajo posterior. F2.3/F2.4/F2.6
estaban pendientes en ese momento; no se atribuyen mejoras de respuesta
a estos conteos. La integración posterior se registra al final.

## Diccionarios completos en los tres idiomas

2026-10-06: ampliación solicitada para es/en/pt, conversor v4. Se descargaron
los tres gzip completos de Wiktionary/Kaikki (extracción 2026-10-03 del dump
enwiktionary 2026-09-02): **675.305.401 bytes**. Están guardados sin pérdida
en `herramientas/sinonimos/datos/diccionarios/`, divididos en partes de hasta
24 MiB. `diccionarios.json` fija hashes de cada parte y del gzip completo,
fecha, URL, metadatos HTTP, atribución y avisos.

| Idioma | Inventario anterior | Inventario ampliado | Formas clasificadas como lemas del diccionario | Registros explícitos de sinonimia |
|---|---|---|---|---|
| es | 96.633 | 1.325.362 | 108.026 | 56.585 |
| en | 193.124 | 1.740.739 | 758.100 | 725.169 |
| pt | 94.108 | 569.099 | 73.068 | 62.643 |

Total **3.635.200** formas únicas contadas por idioma; **3.251.335**
incorporaciones. Los tipos distinguen lemas, flexiones, variantes,
sinonimia explícita y pertenencia al inventario anterior. Expresiones y
nombres propios siguen identificables. Las clases pueden solaparse; la
clasificación como lema es del extractor, no una certificación normativa.
Los registros de sinonimia retienen dirección, sentido y calificadores;
no equivalen a pares únicos ni a grupos de equivalencia.

Los derivados comprimidos están en `ipsis/recursos/sinonimos/diccionarios/`:
vocabulario tipado, registros de flexión, relaciones explícitas de sinonimia
y vistas de entradas léxicas. Se conservan proyecciones verificadas para
reconstruir más rápido, además de los originales completos. No hace falta
`.cache` ni descargar nada de nuevo. `--raw-dictionaries` permite auditar
directamente desde los originales. Las tablas WordNet filtradas mantienen
sus hashes y no se fusionan con estas formas o relaciones.

Validación final: **58 pruebas rápidas** del conversor, diccionarios,
documentación, arquitectura y recursos. Comprobación de igualdad byte a
byte entre los derivados obtenidos del original y de la proyección.
Wheel/sdist verificados con **91 recursos**; los originales y las
proyecciones locales están incluidos en el sdist. También pasa la
reconstrucción `all --check` en una copia limpia sin `.cache` ni red.
`git diff --check` pasa. Los paquetes de prueba pesan aproximadamente
214 MB (wheel) y 1.058 MB (sdist); los recursos locales suman 264.459.554 bytes.

Al finalizar esa preparación, F2.3/F2.4/F2.6 estaban pendientes. Los conteos
no se presentan como mejoras de respuestas. La integración posterior se
registra abajo.

## Integración F2 en el motor

2026-10-06: carga local conservadora de WordNet en es/en/pt. Solo amplía
BM25 para términos OOV inequívocos; conserva pregunta/vector originales
para las demás etapas. Los grupos de `domain.yaml::synonyms` tienen
prioridad y reconocen frases completas. La calibración incluye la huella
efectiva de reglas y datos; las anteriores sin esa huella se invalidan.
No se modificaron umbrales ni se descargaron fuentes durante la integración.

Resultados, fuentes de comparación, capturas HTTP, XML y rondas de
rendimiento en [mediciones/f2](../methodology/mediciones/f2/README.md). Los conteos de
vocabulario almacenado permanecen separados de la calidad de respuesta.

- **G1:** suite completa: 1.031 aprobadas, 2 omitidas (947,53 s). El primer
  intento detectó referencias HTTP anteriores al trabajo ya existente;
  la captura previa a F2 y la final coinciden en los 32 contratos. Se
  actualizaron las referencias desde la previa, con la tolerancia original.
  El bloqueo transitorio de un YAML en OneDrive se evitó usando temporales
  fuera de la carpeta sincronizada.
- **G2–G4 y G6:** universal, consultas y conversaciones en las seis
  combinaciones cada uno: ningún estado cambiado, error nuevo, correcta
  perdida ni herencia indebida nueva. Las paráfrasis mantienen sus resultados.
- **G5:** tres rondas alternadas, 90 consultas por idioma y versión:
  medias antes → después es 77,3 → 45,5 ms; en 41,2 → 40,7 ms;
  pt 50,9 → 46,1 ms. Todos cumplen el límite +10 %. Las mediciones
  originales tomadas en momentos separados y sus incumplimientos también
  se conservan; los tiempos variaron bastante, sin atribuir toda la
  diferencia al código ni prometer estas latencias en otros equipos.
- **Arranque/RSS del índice léxico:** es 1,56 s / +9,87 MiB; en 2,03 s /
  +13,13 MiB; pt 1,04 s / +6,88 MiB. Medidos en procesos separados,
  incluyendo inicialización del stemmer; no son el RSS del servicio completo.
  El índice se conserva en caché. Los diccionarios completos no se cargan
  en consultas.

La evaluación comprueba el tramo elegido por el lector, no un literal
presente solo en su cita amplia. Esta corrección revela tramos incompletos
anteriores en medium; sus casos siguen registrados y no se declaran
aceptables para producción. F2 no empeora esta base y no acredita por sí
solo una mejora general de exactitud. F3 y el cierre general de V4 siguen
pendientes; el trabajo previo de F4 se conserva.

## Final F4/F3 y preparación de F5

G1–G6 formales pasan. Suite final: **1.054 aprobadas, 2 omitidas**
(21 min 53 s); 62 pruebas específicas de separación aprobadas.
La comparación F1 corrige solo la métrica, no su motor. El fallo G3
inicial se conserva y se corrige separando `genericas_memoria` del foco.

[Informe permanente](../methodology/v4-results.md),
[evidencias y reproducción](../methodology/mediciones/v4/README.md),
[validación por criterio](../methodology/mediciones/v4/validacion.json).

Pasar G4 no implica ausencia de errores en turnos positivos: hay cuatro
pérdidas literales conversacionales frente a F1 y cinco nuevas directas
sin el literal elegido por el lector; dos seleccionan a quien firma
cuando se pregunta quién redacta. La similitud también infiere etiquetas
incorrectas en bancos secundarios, sin alterar sus respuestas en esta
medición. Se mantienen como limitaciones y requieren revisión del cierre.

## Consultas: correctas / directas erróneas, F1 → final

| Perfil | es | en | pt |
|---|---|---|---|
| light | 14 / 3 → 14 / 3 | 5 / 1 → 5 / 1 | 8 / 4 → 8 / 4 |
| medium | 8 / 17 → 8 / 17 | 4 / 13 → 4 / 13 | 7 / 8 → 7 / 8 |

## Universal: correctas / directas erróneas, F1 → final

| Perfil | es | en | pt |
|---|---|---|---|
| light | 8 / 1 → 8 / 1 | 6 / 0 → 6 / 0 | 9 / 0 → 9 / 0 |
| medium | 2 / 11 → 2 / 11 | 3 / 9 → 3 / 9 | 2 / 8 → 2 / 8 |

## Conversaciones: herencias correctas; respuestas literales correctas, F1 → final

| Perfil | es | en | pt |
|---|---|---|---|
| light | 26 → 36; 29 → 34 | 25 → 35; 19 → 20 | 21 → 34; 20 → 22 |
| medium | 29 → 36; 6 → 5 | 26 → 35; 8 → 7 | 21 → 34; 8 → 8 |

38 turnos etiquetados para herencia, 54 para respuesta literal y 4 negativos por idioma. Herencias indebidas y directas negativas: **0 → 0 en las seis combinaciones**.

## Latencia universal light (ms), tres pares alternados

| Base | Idioma | Antes | Final | Cambio | G5 |
|---|---|---|---|---|---|
| inicio | es | 30.8 | 30.8 | +0.1% | pasa |
| inicio | en | 23.7 | 25.2 | +6.3% | pasa |
| inicio | pt | 29.1 | 30.5 | +4.7% | pasa |
| f1 | es | 40.6 | 29.0 | -28.5% | pasa |
| f1 | en | 29.9 | 24.2 | -19.1% | pasa |
| f1 | pt | 34.7 | 30.7 | -11.3% | pasa |

## Respaldo efectivo de intención

| Banco | Perfil | Idioma | Intentos | Aceptadas |
|---|---|---|---|---|
| consultas | light | es | 30 | 4 |
| consultas | light | en | 28 | 2 |
| consultas | light | pt | 31 | 2 |
| consultas | medium | es | 30 | 4 |
| consultas | medium | en | 28 | 2 |
| consultas | medium | pt | 31 | 2 |
| universal | light | es | 21 | 4 |
| universal | light | en | 20 | 0 |
| universal | light | pt | 21 | 1 |
| universal | medium | es | 21 | 4 |
| universal | medium | en | 20 | 0 |
| universal | medium | pt | 21 | 1 |
| conversaciones | light | es | 42 | 17 |
| conversaciones | light | en | 42 | 2 |
| conversaciones | light | pt | 40 | 1 |
| conversaciones | medium | es | 42 | 17 |
| conversaciones | medium | en | 42 | 2 |
| conversaciones | medium | pt | 40 | 1 |

## Correcciones posteriores, 2026-10-07–08

Validación terminada: **1.072 pruebas aprobadas, 2 omitidas**, cero fallos
y errores (15 min 7 s). Pasan los 26 criterios finales, incluida la
comparación de todos los turnos positivos frente a F1 y V4 inicial.
[Informe y reproducción](../methodology/mediciones/v4-correcciones/README.md).

Los ocho turnos que reunían cuatro pérdidas literales y cinco nuevas
directas incorrectas vuelven a ser correctos. Frente a F1 y V4 inicial,
ningún acierto se pierde y no aparecen nuevas directas erróneas en los
tres bancos. El núcleo conserva una vez los términos iniciales adicionales
y el orden de las formas; la intención usa el turno actual. El lector
conserva contexto para calificativos aislados y distingue el actor de la
acción que se pregunta ahora. La terminación literal del tramo conserva
su puntaje bruto y registra offsets literales; el tramo original queda en
el diagnóstico. No selecciona otro actor ni otra cifra.

| Perfil | es: F1 / V4 inicial / vigente | en | pt |
|---|---|---|---|
| light | 29 / 34 / 34 | 19 / 20 / 21 | 20 / 22 / 24 |
| medium | 6 / 5 / 11 | 8 / 7 / 12 | 8 / 8 / 11 |

Respuestas literales correctas sobre 54 por idioma. Herencia: 36/35/34
sobre 38 en ambos perfiles; cero herencias indebidas y directas negativas.
Los bancos independientes mantienen sus aciertos y errores anteriores;
la corrección no resuelve todos los errores del lector de medium.

Latencia light: tres pares alternados y 90 consultas por idioma/versión
contra cada referencia, sin ejecutar la suite en paralelo. G5 pasa en las
seis comparaciones:

| Referencia | Idioma | Antes → vigente (ms) | Cambio |
|---|---|---|---|
| V4 inicial | es | 34,2 → 31,1 | −9,0 % |
| V4 inicial | en | 25,3 → 26,1 | +3,2 % |
| V4 inicial | pt | 29,6 → 30,2 | +1,8 % |
| F1 | es | 52,0 → 32,3 | −37,9 % |
| F1 | en | 35,6 → 28,7 | −19,4 % |
| F1 | pt | 45,0 → 29,8 | −33,7 % |

La variación entre rondas se conserva; estas medias no son una promesa
de rendimiento ni atribuyen toda la diferencia al código.

El respaldo conserva ocho aceptaciones correctas por perfil en el banco
natural (seis dev y dos test), con los umbrales anteriores. Los patrones
de compatibilidad rechazan las confusiones observadas de importe con fin
y transportadora con procedimiento. Los casos de test ya se observaron
durante el desarrollo, por lo que no se presentan como una validación
estadística intacta. Las aceptaciones de los bancos secundarios se
inspeccionan y conservan, sin etiquetas exhaustivas independientes.

**F5.1 sigue pendiente de revisión y aprobación del usuario.** Se conserva
`docs/plan/` hasta ese cierre. Las pérdidas específicas de la integración
inicial están corregidas; los demás errores del lector quedan documentados.
