# F2: integración local de sinónimos, 2026-10-06

La integración utiliza WordNet local para ampliar BM25 en es/en/pt cuando
una palabra de contenido no aparece en el corpus, tiene un único sentido
y existe una alternativa inequívoca en ese corpus. La pregunta y el vector
denso originales se conservan para las demás etapas. Los grupos del proyecto
en `domain.yaml::synonyms` tienen prioridad y reconocen frases completas.
El diagnóstico conserva fuente, sentido y POS; la calibración comprueba la
huella de las reglas efectivas y de los archivos léxicos.

Los diccionarios completos y los tesauros permanecen almacenados para
desarrollo. No se descargan durante las consultas ni se convierten sus
millones de formas en grupos de equivalencia. No se cambiaron umbrales.

## Comparación de calidad

Se midieron consultas (60 casos por idioma), universal (30) y conversaciones
(58 turnos), en light/medium × es/en/pt. La base conserva el trabajo previo
de memoria conversacional que ya estaba en el árbol; aísla F2 respecto de
ese estado y no respecto de un commit limpio anterior a F4.

La métrica literal se corrigió **antes de medir la base**: comprueba el
fragmento seleccionado por el lector, cuando existe, en vez de acreditar
un dato que solo aparece en la cita amplia. Los resultados no son
comparables con los conteos históricos que usaban aquella métrica. Los
errores anteriores quedan identificados por caso, sin declararlos aceptables.

| Banco | Perfil | es: correctas / erróneas | en | pt |
|---|---|---|---|---|
| Consultas | light | 14 / 3 | 5 / 1 | 8 / 4 |
| Consultas | medium | 7 / 17 | 4 / 13 | 7 / 8 |
| Universal | light | 8 / 1 | 6 / 0 | 9 / 0 |
| Universal | medium | 2 / 11 | 3 / 9 | 2 / 8 |

Estos conteos coinciden antes y después. La comprobación por identificador
detecta errores nuevos y respuestas correctas perdidas, además de comparar
totales y paráfrasis. Esta entrega comprueba regresiones y funcionamiento
de la expansión; no acredita una mejora general de exactitud ni certifica
el riesgo de producción con estos bancos pequeños.

Conversaciones, también iguales antes y después (herencia correcta / indebida
/ perdida sobre 38 turnos etiquetados; respuestas literales sobre 54):

| Perfil | Idioma | Herencia | Respuestas literales | Directas en los 4 turnos negativos |
|---|---|---|---|---|
| light | es | 36 / 0 / 2 | 34 | 0 |
| light | en | 35 / 0 / 3 | 20 | 0 |
| light | pt | 34 / 0 / 4 | 22 | 0 |
| medium | es | 36 / 0 / 2 | 5 | 0 |
| medium | en | 35 / 0 / 3 | 7 | 0 |
| medium | pt | 34 / 0 / 4 | 8 | 0 |

En las 18 combinaciones no cambió ningún estado, no apareció ningún error
nuevo y no se perdió ninguna respuesta correcta. G2–G4 y G6 pasan respecto
de esta base; G1 y G5 pasan según la validación y las rondas registradas abajo.

### Referencias HTTP anteriores

La primera suite encontró doce diferencias con los archivos históricos de
caracterización. Se capturaron nuevamente las 16 preguntas de ambos perfiles
con el código **anterior a F2** y con el final: contratos iguales, incluyendo
fragmentos y confianza dentro de la tolerancia original de 0,001. Las
referencias se actualizaron desde la captura anterior, conservando las
históricas en `caracterizacion-historica/` y los cambios en
`caracterizacion.json`; no se amplió ninguna tolerancia.

El único cambio de estado histórico es «¿Atienden los domingos?»:
`no_answer` → `related` en ambos perfiles, ya antes de F2. Cambian también
citas/respuestas relacionadas para «agua caliente» y, en medium, el precio;
los demás casos cambian confianza/puntajes. No aparece una respuesta directa
nueva. Esto registra el efecto del trabajo que ya existía en el árbol,
sin atribuirlo a los recursos automáticos ni dar F4 por terminado.

La prueba del panel sufrió además `WinError 5` al reemplazar
`personality.yaml` dentro de OneDrive. La repetición de la suite usa una
carpeta temporal nueva y específica en `%LOCALAPPDATA%/ipsis/`, fuera de
OneDrive, siguiendo la recomendación del `conftest.py`. Se conserva el XML
del primer intento; no se cambió el escritor de configuraciones.

## Latencia y recursos

El primer intento excedió G5. El perfilado identificó trabajo duplicado de
stemming de stopwords; la versión final reutiliza la comprensión de la
pregunta y guarda las stopwords normalizadas por stemmer y lista efectiva.
Las primeras mediciones y el intento descartado se conservan.

Las ejecuciones largas mostraron variación de tiempos incluso en el lector.
`carga-sistema.json` registra una ocupación elevada de RAM durante ellas;
no prueba por sí sola la causa de la variación. La repetición de G5 alterna
ambas versiones, en procesos separados, con los mismos casos y condiciones,
sin ejecutarlas a la vez. Se usa la media de todas las rondas, con igual
número de consultas, y se conserva cada ejecución completa.

La suite completa final aprobó **1.031 pruebas**, con **2 omitidas**, en
947,53 s. G1–G6 pasan respecto del árbol anterior a F2. Los avisos de
dependencias y de decodificación cp1252 de una prueba de portabilidad
permanecen en el XML; no se presentan como problemas resueltos por F2.

| Idioma | Media antes (ms) | Media final (ms) | G5: ≤ antes +10 % |
|---|---|---|---|
| es | 77,3 | 45,5 | Sí |
| en | 41,2 | 40,7 | Sí |
| pt | 50,9 | 46,1 | Sí |

Tres rondas, 90 consultas por idioma y versión. La variación por ronda es
visible en `pareadas/resumen.json`; no se deduce de ellas una aceleración
general ni una garantía de latencia. `comparacion.json::g5` conserva el
**incumplimiento** de las mediciones largas tomadas en momentos separados;
la verificación repetida y alternada de G5 está en `pareadas/resumen.json`.
No se sustituyeron ni descartaron aquellos resultados.

| Idioma | Raíces / grupos indexados | Carga fría (s) | Incremento RSS (MiB) |
|---|---|---|---|
| es | 8.708 / 4.704 | 1,56 | 9,87 |
| en | 11.827 / 6.599 | 2,03 | 13,13 |
| pt | 3.900 / 2.157 | 1,04 | 6,88 |

Un proceso nuevo por idioma, después de cargar el paquete de idioma y
antes/después de construir el índice; incluye inicialización del stemmer.
No es el RSS del servidor con sus modelos. Los 10.000 accesos calientes
por idioma devuelven el mismo índice (menos de 0,001 ms por acceso).

## Evidencia y reproducción

- `antes-*.json` y `despues-*.json`: resultados completos por caso, media/p95.
- `comparacion.json`: nuevas directas erróneas, correctas perdidas, cambios
  de estado y herencias indebidas por combinación.
- `intento-1/`: primera versión, antes de corregir el coste duplicado.
- `pareadas/`: rondas alternadas y resumen de G5.
- `coste.json`: arranque del índice léxico y RSS en un proceso por idioma.
- `metadata.json`: huellas del código y de los recursos, alcance y métrica.
- `validacion.json`: comprobación conjunta de G1–G6, sin reemplazar el G5
  fallido de las mediciones originales.
- `pruebas.xml`: resultado completo de pytest.
- `pruebas-intento-1.xml`: fallos originales de referencias y OneDrive.
- `antes-caracterizacion.json`, `despues-caracterizacion.json`,
  `caracterizacion.json`: contratos HTTP y diferencias históricas.
- `baseline-code.zip`, `final-code.zip`: los archivos `.py`/`.yaml` de ambos
  árboles medidos, para conservar también el código final al continuar V4.

La base es una instantánea del árbol de trabajo, no un commit publicado.
Para reconstruir cada árbol, crear una carpeta nueva, copiar `ipsis/` de esta versión
excluyendo `.py`, `.yaml` y `__pycache__`, y extraer allí `baseline-code.zip`.
Para el árbol final, extraer en su carpeta nueva `final-code.zip` en su lugar.
Así se reutilizan los recursos inalterados sin introducir módulos nuevos en
el código anterior. Los hashes se calculan sobre rutas relativas y bytes de
todos los `.py`/`.yaml` de `ipsis/`; los seis TSV tienen hashes separados.
Los modelos deben estar en la caché local y se utiliza el mismo intérprete;
sus identificadores de snapshot se conservan en `metadata.json`.

```powershell
$env:PYTHONUTF8 = '1'
$env:TEMP = "$PWD/.cache/plan-v4/tmp"
$env:TMP = $env:TEMP
$env:IPSIS_CODIGO = "$PWD/.cache/plan-v4/base"
.venv/Scripts/python.exe tests/datos/banco_consultas/medir.py antes-consultas.json light,medium es,en,pt
.venv/Scripts/python.exe tests/datos/banco_consultas/medir.py antes-universal.json light,medium es,en,pt banco_universal
```

Para conversaciones se usa `banco_consultas/medir.py::_importar_codigo` antes
de ejecutar `banco_conversaciones/medir.py`, tal como hace el ejecutor
archivado. Los ejecutores archivados registran la organización original
en `.cache/plan-v4/`; copiarlos allí antes de ejecutarlos. Repetir con
`IPSIS_CODIGO` apuntando a la versión final.
Para G5:

```powershell
.venv/Scripts/python.exe tests/datos/banco_universal/medir_latencia.py .cache/plan-v4/base . .cache/plan-v4/pareadas 3
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp .cache/pytest-f2 --junitxml .cache/pruebas-f2.xml
```

`metadata.json` distingue el código al iniciar la repetición final del
código final: se completó la cobertura de la huella de calibración durante
el primer banco. Sus proyectos no tienen calibración, por lo que esa
completitud de procedencia no cambia sus decisiones; los siguientes bancos
y la suite utilizan el código final. Las rondas alternadas registran las
huellas exactas de ambas versiones.

F3 y el cierre general del plan V4 siguen pendientes. Esta entrega documenta
la integración F2 y conserva las demás modificaciones del árbol.
