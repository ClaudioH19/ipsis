# Regresión documental general

Para comparar el motor experimental v2 con v1 sobre un proyecto real, consultar
el [avance y los comandos](../../docs/plan/motor-v2-avance.md). El comparador
offline trabaja sobre copias y conserva respuestas completas y trazas; la
selección por defecto del servicio es v2, que entrega fuentes rankeadas para revisar.

El workflow automático `Servicio y contenedor` verifica el arranque de Docker y
la conversación y recuperación por HTTP sobre un proyecto real. Esta evaluación
de respuestas directas conserva su referencia histórica y se ejecuta mediante
el workflow manual `Evaluación documental manual`; comparar esa referencia con
v2 no mide la calidad de su ranking. No se modifica la referencia para ocultar
esa diferencia. Para explorar sin comparación, usa `--no-baseline`.

Para ejecutar la comparación histórica desde la raíz del repositorio:

```bash
python herramientas/evaluacion/general.py --download
```

Ejecuta light y medium sobre 84 preguntas: cuatro temas (RRHH,
compras, mantenimiento y logística), cuatro formatos (Markdown, PDF digital,
DOCX y texto) y tres calidades. Cada calidad contiene los mismos hechos y
preguntas; cambia la estructura, los encabezados, el espaciado y el ruido.
Las unidades, condiciones y actores de las respuestas están congelados.
Los negativos incluyen datos ausentes del mismo tema, premisas falsas,
preguntas ambiguas sin antecedente, saludo y una consulta ajena al corpus.
Cada pregunta empieza sin memoria de otra pregunta.

Sin `--download` exige modelos completos en la caché; nunca descarga
silenciosamente. `IPSIS_MODELS_DIR` cambia la caché y `HF_HUB_OFFLINE=1`
permite verificar sin red. El valor predeterminado es dos hilos ONNX.

```powershell
$env:IPSIS_MODELS_DIR = Join-Path (Get-Location) '.cache/modelos'
$env:HF_HUB_OFFLINE = '1'
.venv/Scripts/python.exe herramientas/evaluacion/general.py
```

Los reportes JSON/Markdown quedan en `.cache/regresion-general/`, con
respuesta completa, tramo QA, señales, evidencia, modelos/revisiones,
perfil efectivo, hashes del corpus y código, hardware y latencia. Se
comprueba que el literal esté en la respuesta publicada y que su evidencia
corresponda al documento y rango esperados; una similitud alta no basta.

La referencia versionada está en
`tests/datos/banco_general/linea_base.json`. El comando devuelve 1 si falla
una ejecución, cambia el banco, pierde un acierto, introduce una respuesta
aceptada incorrecta o pierde una abstención/aclaración/conversación antes
correcta. Una mejora en otra pregunta no compensa esas pérdidas. En el mismo
hardware, falla también si p95 supera el mayor entre el presupuesto del
perfil y el p95 de referencia aumentado un 25 %. En otro hardware conserva
las comprobaciones de contenido y reporta latencia sin compararla con la CPU
de referencia. `--strict` exige cero errores aceptados y el presupuesto
absoluto en todos los bancos elegidos.

La suite normal de pytest ejecuta esta regresión real cuando los modelos
están disponibles (`tests/evaluacion/test_general_regresion.py`, marca
`slow`); en su ausencia se omite explícitamente. Las pruebas de integridad y
del comparador se ejecutan sin modelos. El workflow
`.github/workflows/regresion-general.yml` descarga los modelos y mide los
dos perfiles en las tres calidades en cada push y pull request; sus reportes quedan
como artefacto incluso si hay errores.

## Comparar modelos alternativos

```bash
python herramientas/evaluacion/general.py --profiles medium --variants all --no-baseline --download --output .cache/candidatos
python herramientas/evaluacion/general.py --profiles medium --variants granite,harrier,gemma2 --qualities none --extra-bank tests/datos/banco_consultas/es/manifiesto.json --no-baseline --output .cache/candidatos-consultas
```

Variantes: `granite`, `granite97`, `harrier`, `gemma2`, `horizon-base`,
`horizon-small`, `granite-horizon`; se reportan como `medium+<variante>`.
Proceden del antiguo perfil heavy, retirado porque ninguna superó a medium
(ADR 0003). Cambian un componente, conservando el
lector, los umbrales y la cascada de medium (20/4/2, 600 caracteres, sin
concordancia) para atribuir la diferencia al modelo. La combinada cambia
recuperador y reranker. Las variantes son configuraciones experimentales;
`--no-baseline` mide y reporta errores, pero solo falla por problemas de
ejecución, salvo que se añada `--strict`.

Pueden añadirse varios `--extra-bank` (por ejemplo el universal de es/en/pt).
`--profiles medium --qualities malo` permite una comprobación parcial; la
comprobación general predeterminada mantiene los seis trabajos.

## Revisar una referencia nueva

```bash
python herramientas/evaluacion/general.py --no-baseline --output .cache/revision
# Revisar preguntas, respuestas, evidencias, errores y cambios antes de:
python herramientas/evaluacion/general.py --record-baseline --output .cache/nueva-referencia
```

La referencia registra el comportamiento observado, incluidos errores
conocidos; aprobar una regresión no certifica exactitud perfecta. Nunca se
actualiza automáticamente en CI ni al correr pytest. Para exigir una
referencia sin errores aceptados, añadir `--strict` al guardarla. La
promoción de un modelo requiere además documentos reales del despliegue y
un banco separado del usado para elegirlo.

La referencia vigente (re-grabada el 2026-10-08, tras activar la lectura
semántica en medium) conserva una respuesta incorrecta aceptada de light por
cada calidad (eran tres: la intención de costo y el detector de aclaración las
redujeron) y 10/12 aciertos; medium tiene cero errores y 10/12 aciertos, con
p95 de 0,86–1,40 s en la CPU de referencia (antes 0,63–0,96 s), el costo de la
lectura semántica. El heavy retirado coincidía con medium; sus filas se
quitaron. El modo estricto falla para light. Los estados negativos exactos también se
reportan: una negativa que queda `relacionado` no cuenta como el estado
`sin_respuesta` o `necesita_aclaracion` esperado, aunque no sea una respuesta
directa incorrecta. Ver [resultados y limitaciones](../../docs/methodology/modelos-heavy-2026-10-08/implementacion.md).

`construir_general.py --output DIRECTORIO_NUEVO` construye explícitamente
otro corpus, sin sobrescribir el congelado. No se regeneran las respuestas
esperadas ni sus offsets al evaluar. El banco es de regresión y se rechaza
para calibración. Los PDFs son digitales: este conjunto no certifica OCR,
tablas complejas, archivos dañados ni documentos cuyo texto sea ilegible.

## Investigación de calidad v2

`auditar_v2.py` prueba presupuestos, ausencia de reranking y corrección,
lectura de unidades conocidas y formatos derivados en copias de un índice
estructural. Admite un cross-encoder alternativo disponible en caché. Memoiza
inferencias: sus tiempos globales no son un benchmark de servicio.
Ver [método, resultados y límites](../../docs/methodology/motor-v2-diagnostico.md).

El comparador del consejo se retiró junto con su runtime. El
[informe histórico](../../docs/methodology/consejo-v2.md) conserva las medidas
y ubicación de sus snapshots privados. El enfoque vigente de v2 entrega
[fuentes ordenadas con contexto](../../docs/methodology/fuentes-v2.md).
