# Correcciones posteriores a V4

Estado: validación terminada, 2026-10-08. La referencia inmediata es el commit `b23ad8a`;
se compara también con F1 (`39c7878`) usando la misma métrica literal
corregida. Las rondas anteriores permanecen en [V4](../v4/README.md).

Se revisan cuatro pérdidas de respuestas literales y cinco nuevas directas
incorrectas/incompletas de la memoria inicial. Una pérdida coincide con una
nueva directa incorrecta: son ocho turnos diferentes. También se verifica
el respaldo de intención en importes y preguntas por actores.

Los ocho turnos vuelven a ser correctos. Frente a ambas referencias,
los tres bancos mantienen todos sus aciertos y no añaden respuestas
directas erróneas. Las conversaciones correctas de medium pasan de
5/7/8 en es/en/pt a 11/12/11 (sobre 54 por idioma); light pasa de
34/20/22 a 34/21/24. La herencia queda en 36/35/34 de 38, sin herencia
indebida ni directas en los cuatro turnos negativos por idioma.
Las consultas independientes conservan sus errores anteriores; estas
mejoras no acreditan exactitud general del lector.

La suite completa termina con **1.072 aprobadas, 2 omitidas, cero fallos y
cero errores** en 907,23 s (15 min 7 s). También comprueba la reconstrucción
de los datos originales sin red. Los [26 criterios de validación](validacion.json)
pasan, incluida la igualdad del código medido con el actual y las
comparaciones por caso frente a ambas bases. F5.1 sigue pendiente de
revisión y aprobación del usuario; se conserva el plan hasta ese cierre.

- [Tablas contra F1 y V4 inicial](tablas.md).
- [Comparación por caso](vigente-comparacion.json) y
  [caracterización de cambios de estado o acierto](caracterizacion.md).
- [Procedencia de la ronda vigente](procedencia-vigente.json): solo
  cambia la rama de preguntas de seguimiento entre `final` y `elipsis`.
  Los bancos independientes tienen una sesión nueva por caso y se
  conservan de `final`; las conversaciones se vuelven a medir con `elipsis`.
- [Aceptación efectiva de intenciones](respaldo-intenciones.md), con
  [cada aceptación y rechazo por incompatibilidad](respaldo-intenciones.json).
  Las confusiones de importe extranjero con fin y transportadora con
  procedimiento quedan rechazadas; las ocho aceptaciones del banco natural
  se conservan por perfil. Los bancos secundarios no tienen etiquetas
  exhaustivas independientes: se inspeccionan sus aceptaciones, sin
  tratarlos como una estimación estadística de errores de intención.

Cambios generales:

- Los términos de apertura fuera del núcleo se conservan una vez y las
  formas heredadas mantienen su orden original; el IDF elige qué guardar.
- Los patrones y la similitud usan la relación del turno actual. El lector
  recibe el turno actual cuando expresa una relación reconocida o varios
  términos propios; un calificativo aislado («¿y en verano?») conserva la
  interpretación para saber qué modifica. El contexto heredado recupera el tema.
- Preguntas por actores aíslan la oración pertinente del pasaje. Los tramos
  QA de seguimientos completan unidades, límites/referencias de cantidades
  o la cláusula de acción del actor seleccionado, con offsets literales.
  No se cambia un actor/cifra seleccionado por otro. El tramo original
  permanece en el diagnóstico; no se acredita una respuesta por un dato
  distinto encontrado en la cita amplia.
- La compatibilidad de fin/procedimiento se declara en cada idioma y es
  necesaria además del coseno/margen. Los umbrales publicados se conservan.
  En seguimientos puede codificarse la pregunta actual además de la
  interpretada; ambos vectores se memoizan.
- La versión de comportamiento léxico es v5; recalibrar los proyectos
  que tenían una calibración anterior.

`intento-*` conserva sondeos anteriores, incluido el recorte excesivo de
todas las preguntas de seguimiento que empeoró respuestas numéricas. El
recorte final se limita a preguntas por actores. `correccion-1-*` usa el
primer filtro portugués que omitía el pronombre explícito «eu»; no representa
el código final. La prueba y la medición dev detectaron ese rechazo y el
filtro corregido acepta «o que eu faço». Esas dos rondas y la primera suite
se detuvieron antes de terminar al reforzar una condición adicional del
actor: su acción debe seguir inmediatamente al tramo seleccionado. Sus
logs y capturas son evidencia parcial; no se presentan como bancos completos.
`final-*` congela el código con esa condición. Su banco de conversaciones
recuperó los ocho objetivos, pero detectó tres efectos nuevos al quitar
contexto a preguntas elípticas: es-conv-002:4, es-conv-011:2 y pt-conv-011:2.
`elipsis-*` incorpora la conservación del contexto para calificativos
aislados y vuelve a medir las seis combinaciones de conversaciones.

Una suite posterior alcanzó seis fallos de caracterización y se
detuvo después de revisar sus diferencias: puntajes de dos premisas falsas,
el score de una cita correcta y una evidencia relacionada diferente para
un precio que el corpus no informa. Los estados no cambiaron. Se regeneran
los archivos esperados después de esa revisión, conservando la tolerancia;
`referencias-http.json` documenta cada diferencia y la repetición específica
pasó sus 36 pruebas. No se presenta la corrida detenida como una suite verde.

`calibrar_intenciones.py` reutiliza el grid dev anterior con compatibilidad
como condición adicional, conservando ejemplos y etiquetas. Test se reporta
por separado y no determina los valores. Como ya se observó en el desarrollo,
no es un conjunto estadístico intacto. Se mantienen los umbrales anteriores
(es 0,850; en 0,870; pt 0,895; margen estricto > 0) aunque el nuevo mínimo
dev español sea 0,845: no se aumenta cobertura reduciendo el umbral.

`ejecutar.py <ronda> conversaciones,consultas,universal` guarda un ZIP del
código, conserva recursos grandes con enlaces locales inalterados y mide
las seis combinaciones por banco. `comparar.py <ronda>` compara los
resultados por caso con ambas referencias y registra pérdidas, ganancias,
nuevos errores y los ocho objetivos. `sondear.py` guarda el diagnóstico
completo de conversaciones elegidas para inspeccionar lectores y guardias.

Toda la evaluación utiliza modelos locales, sin descargas y con dos hilos
ONNX. La [suite completa definitiva](pruebas-vigentes.xml) registra nueve
avisos de dependencias/Qdrant y de decodificación del subproceso de la
prueba CP1252. Esa prueba pasa, pero no se declaran resueltos sus avisos.

La latencia se mide en tres pares alternados, 90 consultas light por
idioma y versión contra cada referencia, sin la suite en paralelo.
[V4 inicial](pareadas-v4/resumen.json) y [F1](pareadas-f1/resumen.json)
cumplen G5 en los tres idiomas, conservando cada ronda y calidad idéntica
por caso. Frente a V4, es cambia −9,0 %, en +3,2 % y pt +1,8 %; frente
a F1, −37,9 %, −19,4 % y −33,7 %. Son medias locales bajo carga variable;
no se atribuye toda la diferencia al código ni se prometen otros equipos.

Para reproducir, reconstruir los árboles de código como describe
[V4](../v4/README.md), conservando recursos locales y extrayendo los ZIP
correspondientes (`vigente-code.zip`, `../v4/corregido-code.zip` y
`../v4/f1-evaluacion-code.zip`). Los archivos `*-codigo.json` registran
los hashes y las rutas de los árboles de esta corrida.

```powershell
$env:PYTHONUTF8 = '1'
$env:IPSIS_ONNX_THREADS = '2'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.venv/Scripts/python.exe docs/methodology/mediciones/v4-correcciones/ejecutar.py repeticion conversaciones,consultas,universal
.venv/Scripts/python.exe tests/datos/banco_universal/medir_latencia.py .cache/v4-continuacion/corregido .cache/v4-correcciones/elipsis .cache/repeticion-latencia 3
.venv/Scripts/python.exe -m pytest -q --basetemp "$env:LOCALAPPDATA/ipsis/pytest-v4-repeticion" --junitxml .cache/pruebas-v4-repeticion.xml
```

Los nombres de nuevas rondas y directorios deben ser distintos para
conservar estas evidencias. `consolidar.py` verifica la diferencia exacta
de código antes de reutilizar bancos independientes; `comparar.py vigente`,
`documentar.py` y `auditar_intenciones.py` regeneran los informes. La
validación final de criterios y procedencia corresponde a `validar.py`.
