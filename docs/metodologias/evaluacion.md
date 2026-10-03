# Banco de evaluación

## Propósito

Separar la calidad esperada del comportamiento actual del sistema. La
caracterización detecta cambios; el banco normativo permite afirmar si esos
cambios son mejoras o regresiones.

## Formato versionado

Cada banco tiene un `manifiesto.json` y un archivo JSONL de casos. El esquema
vigente es `1`, validado por `rag.evaluacion.banco`.

El manifiesto identifica:

- ID, versión, tipo (`sintetico` o `manual`) y estado del dataset;
- archivo de casos;
- archivos del corpus y su SHA-256 conjunto;
- categorías obligatorias.

Cada caso declara:

- `id`, `dataset_version`, `split`, `categoria` y `pregunta`;
- `estado_esperado` y `respondible`;
- para preguntas respondibles, `respuesta_literal` y una o más evidencias con
  `doc_id`, texto y offsets exactos;
- notas opcionales que expliquen casos adversariales.

## Categorías

- `exacta`: usa términos cercanos al documento.
- `parafrasis`: expresa el mismo hecho con vocabulario diferente.
- `sin_respuesta`: el corpus no contiene el dato o está fuera del dominio.
- `premisa_falsa`: la pregunta presupone una entidad o valor inexistente.
- `ambigua`: falta información para elegir una respuesta única.
- `conversacional`: saludo, agradecimiento u otra interacción no documental.

## Separación de datos

`dev` puede utilizarse para calibrar. `test` permanece cerrado hasta comparar
configuraciones. Cada categoría del conjunto sintético tiene casos en ambos
splits para impedir que los únicos ejemplos medidos sean los usados al ajustar.

Los datos se mantienen en dos ubicaciones distintas:

- `tests/evaluacion/sintetico/`: corpus ficticio, reproducible y versionado;
- `data/golden/`: futuro conjunto manual de 30–50 preguntas de un corpus real.

El conjunto manual no se rellena automáticamente. Requiere revisión humana y
no debe incorporar documentos sensibles al repositorio.

## Estado

El formato y el banco sintético `aqualis_sintetico@1.0.0` están activos. Su
línea base comparativa está resumida en `CHANGELOG.md`.

## Métricas de C.2

`rag evaluar --banco <manifiesto> [--salida reporte.json]` ejecuta el backend
activo sin reindexar y calcula:

- Recall@k y MRR sobre la evidencia esperada;
- tasa de falsos `ok`, que bloquea el comando si es mayor que cero;
- precisión de abstención y distribución de estados;
- exactitud del estado esperado, de la respuesta literal y de los offsets;
- proporción de respuestas sobre el límite de longitud;
- latencia media, p95 y promedio por etapa del diagnóstico;
- los indicadores principales desglosados por backend y categoría.

Un falso `ok` es una pregunta marcada no respondible que termina en
`respuesta_directa` o `respuesta_parcial`. Esta guardia tiene prioridad sobre
Recall: recuperar más evidencia no compensa afirmar algo que el corpus no
respalda.

## Comparación y calibración de C.3

Para producir los tres artefactos y la tabla comparable desde un solo comando:

```bash
rag benchmark \
  --banco tests/evaluacion/sintetico/manifiesto.json \
  --salida reportes/aqualis_sintetico_v1
```

El benchmark inicializa un proyecto temporal, carga el corpus declarado una
vez y ejecuta Qdrant denso y Qdrant híbrido. Cada JSON conserva:

- hash del banco completo, versión e identidad del dataset;
- snapshot y hash de la configuración efectiva;
- manifiesto o identidad del índice;
- versión de la señal de confianza y calibración calculada solo con `dev`;
- reporte agregado y observaciones por caso.

`test` nunca participa en la selección del umbral. La calibración es una
recomendación registrada, no modifica automáticamente `motor.yaml`. Para
comparar artefactos existentes sin repetir consultas:

```bash
rag comparar \
  reportes/aqualis_sintetico_v1/qdrant_vectorial.json \
  reportes/aqualis_sintetico_v1/qdrant_hibrida.json \
  --salida reportes/aqualis_sintetico_v1/comparacion.json
```

El comparador exige igual hash, versión y `k`, y no admite backends repetidos.
El informe deja explícitamente vacía la lista `decisiones`: un banco sintético
pequeño permite detectar defectos y verificar el proceso, no escoger por sí
solo el backend predeterminado ni publicar umbrales.
