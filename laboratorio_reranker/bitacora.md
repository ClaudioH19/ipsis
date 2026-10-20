# Bitácora del laboratorio

Una entrada por observación. Separar **lo visto** de **lo interpretado**. Citar casos por `id` y ejecuciones
por `run_id`; nunca pegar texto de los documentos reales. Registrar también los resultados nulos: un cambio que
no movió el orden también es información.

Plantilla:

```markdown
### OBS-0001: título descriptivo
- Etapa / control:
- Casos y run_id:
- Cambio realizado:
- Resultado observable: (logits, rangos, tokens, gráfica en .cache/…)
- ¿Esperable?: sí / no / incierto
- Explicaciones posibles: (varias, sin elegir todavía)
- Siguiente control:
- Estado: aislada / repetida / descartada / por revisar
```

<!-- Las entradas van debajo, la más reciente al final. -->

### OBS-0001: la exportación a ONNX no altera el modelo
- Etapa / control: 1 / C1 (exportación)
- Casos y run_id: NoMIRACL es `dev`, primeras 30 preguntas (300 pares, 25 truncados a 256 tokens);
  `20261017-154026-c1-cuantizacion-0bca5d`
- Cambio realizado: PyTorch fp32 (`BAAI/bge-reranker-v2-m3@953dc6f`) frente a ONNX fp32
  (`onnx-community/bge-reranker-v2-m3-ONNX@6f5ff65`, `onnx/model.onnx`), mismos ids de token, lote 2.
- Resultado observable: top-1 igual 1,0; Kendall 1,0; 0 pares invertidos; |Δlogit| máximo 0,0000 (redondeo a 5
  decimales); hit@1 0,80 en ambos.
- ¿Esperable?: sí.
- Explicaciones posibles: la conversión es fiel; cualquier diferencia del motor viene de la cuantización o del lote.
- Siguiente control: corrida completa de cuantización y lote sin PyTorch (ahorra ~1 s por par).
- Estado: repetida en 30 preguntas; suficiente para descartar la exportación.

### OBS-0002: el lote cambia los logits del int8 tanto como la cuantización (prueba corta)
- Etapa / control: 1 / C1 (lote)
- Casos y run_id: NoMIRACL es `dev`, 3 preguntas (30 pares); `20261017-152634-c1-cuantizacion-4b05b9`
- Cambio realizado: int8 con lote 1 y lote 10 frente al lote del motor (2).
- Resultado observable: |Δlogit| p50 0,24 (lote 1) y 0,21 (lote 10), frente a 0,21 de int8 contra fp32; 4 % de
  pares invertidos; sin cambios de hit@1.
- ¿Esperable?: sí, por la cuantización dinámica (escala de activaciones por lote).
- Explicaciones posibles: la escala por lote incluye el padding y al vecino; o ruido numérico sin efecto en el orden.
- Siguiente control: las 617 preguntas (corrida en curso).
- Estado: aislada (n = 3), no concluyente.

### OBS-0003: el motor no repite su orden; en esta CPU el presupuesto corta el reranking
- Etapa / control: 0 / determinismo (C0)
- Casos y run_id: banco sintético piloto (48 preguntas, `dev`), dos corridas de `ranking_pasajes.py` con la misma
  configuración (estructural, `medium`, rasgos 5 / 0,6); puntuación fuera del motor
  `20261017-160515-c1-cuantizacion-76ab5c`. Ambas corridas compartieron CPU con la corrida B de C1.
- Cambio realizado: ninguno entre corridas. Después, los mismos 10 candidatos volcados se puntuaron fuera del motor
  con el int8 y sin presupuesto.
- Resultado observable: hit@1 final de 0,979 en la primera corrida y de 0,938 en la segunda. En la segunda,
  `sint-003i` y `sint-006i` quedan en el rango 3 dentro del motor, pero en el 1 fuera de él. Su reranking duró
  ~1,1 s (los demás, 1,5–2,2 s) y la correcta era la tercera de la cola: el motor puntuó un solo lote de 2 y se
  detuvo. Fuera del motor, en esta máquina, el int8 cuesta ~480 ms por par; la referencia de
  `docs/methodology/precision-ingesta.md` es 85 ms por par con 4 CPU.
- ¿Esperable?: no.
- Explicaciones posibles: (1) `puntuar_progresivo` no inicia un lote que no cabe en `presupuesto_consulta_ms`
  (2 500 ms menos 150); con la CPU cargada o lenta quedan candidatos sin puntuar, y la correcta sin puntuar se
  queda en el orden híbrido. (2) Además, el orden híbrido podría variar entre indexaciones (no verificado).
- Siguiente control: repetir el piloto sin carga en la CPU; verificar que los volcados de ambas corridas coincidan;
  medir el costo por par del int8 sin otra carga.
- Estado: repetida en 2 casos. **Una correcta en el rango 2–3 puede ser un candidato que el reranker nunca puntuó**,
  no un error del modelo. Hay que descartarlo caso por caso (C0) antes de atribuir cualquier error al modelo.

### OBS-0004: el piloto sintético es fácil para bge
- Etapa / control: 0 / línea base del banco sintético
- Casos y run_id: los mismos 48, puntuados fuera del motor (`20261017-160515-c1-cuantizacion-76ab5c`)
- Resultado observable: int8 con lote 2: hit@1 0,979 (47/48). El único error de orden atribuible al modelo es
  `sint-014i` (informal, hermana + brecha léxica: «cuanto rato» frente a «Tiempo máximo continuo»), con la correcta
  en el rango 4. Las preguntas formales y las hermanas que nombran su unidad («práctica 2») se ordenan bien.
- ¿Esperable?: en parte; el banco de pasajes ya estaba saturado.
- Explicaciones posibles: el encabezado de cada unidad nombra la unidad («Título III. Práctica Clínica II») y la
  vista del reranker lo incluye, así que la información que distingue está presente. En los documentos reales, la
  unidad P1/P2 se nombra en un párrafo antes de la tabla o no se nombra.
- Siguiente control: endurecer el banco antes de escalarlo (README § 5.2).
- Estado: aislada.

### OBS-0005: en el banco real, la cuantización int8 no explica los errores de orden
- Etapa / control: 1 / C1 (cuantización y lote)
- Casos y run_id: banco real nuevo (§ 7; 64 preguntas, 61 con la correcta entre los 10 candidatos, 11 pares
  truncados); `20261017-165613-c1-cuantizacion-131f26`. Fuera del motor, sin presupuesto.
- Cambio realizado: int8 con lote 2 (el del motor) frente a fp32 con lote 2, y frente a int8 con lote 1.
- Resultado observable: hit@1 0,787 (int8@2), 0,803 (fp32@2) y 0,754 (int8@1); hit@3 0,951 en las tres.
  Cuantización: top-1 igual 0,934, Kendall 0,929, 2,8 % de pares invertidos, hit@1 0/1 (p = 1,0). Lote 1 frente a
  lote 2: top-1 igual 0,902, hit@1 0/2 (p = 0,5). Por caso, fp32 tiene los mismos errores de orden que int8 en
  `003i`, `004i`, `005f`, `005i`, `012i`, `013f`, `013i`, `030f`, `031f` y `032f`. La cuantización cambia solo
  `018i` (fp32 1, int8 3) y `009i` (fp32 3, int8 2).
- ¿Esperable?: sí.
- Explicaciones posibles: la cuantización y el lote agregan ruido de ±1–2 casos en ambos sentidos, pero los
  errores de orden ya están en el modelo fp32.
- Siguiente control: confirmar con NoMIRACL (617 preguntas, en curso). Seguir con C2–C6 sobre los errores de orden
  de fp32. Los márgenes van de casi empate (`005f/i`: 0,18–0,26) a preferencias claras (`013i`: 5,3; `032f`: 3,2).
- Estado: repetida en 61 preguntas. **Criterio de C1 no cumplido** (fp32 recupera 1 error de orden, no 2): la
  cuantización no es la causa principal en este banco.

### OBS-0006: el orden final del motor se aparta del orden puro del reranker
- Etapa / control: 0 / C0
- Casos y run_id: el mismo banco; motor completo (`banco-real/ranking/ranking.json`), con la CPU compartida con la
  corrida B de C1.
- Resultado observable: hit@1 final del motor 0,812 y hit@3 0,891. Hay discrepancias en ambos sentidos: `010i`
  queda en el rango 5 dentro del motor y en el 1 fuera; `003i` en el 5 dentro y el 2 fuera; `005f/i`, `012i` y
  `013f/i` en el 1 dentro pero en el 2–3 fuera. El reranking dura 1,1–2,3 s por consulta.
- ¿Esperable?: en parte, por OBS-0003.
- Explicaciones posibles: (1) el presupuesto deja candidatos sin puntuar; eso hunde a una correcta sin puntuar o
  salva a una correcta cuyos competidores no se puntuaron; (2) la deduplicación y la ampliación de resultados del
  motor cambian rangos; (3) hay varias evidencias por caso (artículo y anexo).
- Siguiente control: repetir el motor con la CPU sin carga y dos veces. Registrar `puntuados_esta_pagina` y
  `presupuesto_agotado` por consulta.
- Estado: por revisar. Las cifras del motor de esta corrida no sirven como línea base.

### OBS-0007: NoMIRACL confirma que la cuantización no empeora el orden
- Etapa / control: 1 / C1 (cuantización y lote)
- Casos y run_id: NoMIRACL es `dev`, 617 preguntas, 6 137 pares (778 truncados a 256 tokens);
  `20261017-155039-c1-cuantizacion-5e4b67`
- Cambio realizado: int8 con lote 2 frente a fp32 con lote 2, y frente a int8 con lote 1.
- Resultado observable: hit@1 0,817 (int8@2), 0,809 (fp32@2) y 0,809 (int8@1); hit@3 0,966, 0,963 y 0,963.
  Cuantización: top-1 igual 0,925, Kendall 0,941, 3,0 % de pares invertidos, |Δlogit| p50 0,18 y máximo 1,51;
  hit@1 int8 frente a fp32: 12 ganados y 7 perdidos (p = 0,36). Lote 1 frente a lote 2: 6 ganados y 11 perdidos
  (p = 0,33).
- ¿Esperable?: sí, tras OBS-0005.
- Explicaciones posibles: la cuantización y el lote cambian el primer puesto en el 7–8 % de las preguntas, pero en
  ambos sentidos y sin sesgo: es ruido, no una pérdida sistemática.
- Siguiente control: C0 sin carga en la CPU y, después, C2–C6 sobre los errores de orden de fp32 del banco real.
- Estado: repetida en dos fuentes. **C1 cerrado: la cuantización int8 no es la causa** (criterio no cumplido en el
  banco real; McNemar no significativo en NoMIRACL, y a favor del int8). No se cambia la cuantización.

### OBS-0008: sin carga, el motor sigue sin puntuar todos los candidatos en esta CPU
- Etapa / control: 0 / C0
- Casos y run_id: banco real, dos corridas del motor con la CPU libre (`banco-real/ranking-sincarga-{1,2}`), más la
  puntuación fuera del motor de OBS-0005. CPU: AMD Ryzen 5 7530U (6 núcleos, 12 hilos, portátil), plan «HP
  Optimized».
- Cambio realizado: ninguno; se repite el motor y se ubica la correcta en la cola del reranker.
- Resultado observable:
  - los volcados de candidatos de las tres corridas (con carga y sin carga) son idénticos byte a byte: la
    recuperación es determinista;
  - hit@1 final 0,797 en ambas corridas sin carga, pero los casos fallidos cambian (`028i` en una, `012i` en la
    otra); p95 2,8–3,0 s, por encima del presupuesto de 2,5 s;
  - con la correcta en las posiciones 5–7 de la cola, `010i` (rango 1 fuera del motor), `003i` (2), `028i` (1) y
    `018i` (1 en fp32) quedan en el rango 4–5 o fuera de los publicados: el motor puntúa unos 4 candidatos
    (≈ 500 ms por par) y la correcta nunca se evalúa;
  - a la inversa, `005f/i` y `013f/i` salen primeros dentro del motor solo porque sus competidores no se
    puntuaron.
- ¿Esperable?: no en la CPU de referencia (85 ms por par, p95 1,7 s); sí en esta.
- Explicaciones posibles: el costo por par de bge-m3 int8 en esta CPU es ~6 veces el de la referencia, así que el
  presupuesto alcanza para 2–3 lotes de 2.
- Siguiente control: separar los errores en G (presupuesto) y errores del modelo con los 10 candidatos puntuados.
  Seguir C2–C6 solo con estos últimos.
- Estado: repetida. **En hardware de este tipo, parte del problema de «correcta en el rango 2–5» es el
  presupuesto, no el modelo.** Afinar no lo resuelve; lo resuelven el costo por par o el presupuesto.

### OBS-0009: causas de los 15 errores del reranker en el banco real (C2–C6)
- Etapa / control: 1 / C2–C6
- Casos y run_id: banco real, 61 preguntas con la correcta entre los 10 candidatos; int8 con lote 1, sin
  presupuesto; hit@1 0,754 y 15 errores. Controles aplicados a los 15 errores y a 12 aciertos;
  `20261017-193911-c2c5-controles-ca4b1c`. C6 (etiquetas y vistas): revisión de Claude más una búsqueda de cada
  evidencia en el texto exacto que recibe el reranker.
- Resultado observable, por control:
  - **C2, ventana de 512 o 2048 tokens:** no arregla ningún error ni rompe ningún acierto (`032f` sube de 6 a 4);
  - **C3, oráculo:** arregla 6 errores pero **rompe 7 de 12 aciertos**. Una oración suelta pierde el contexto que
    la pregunta necesita (encabezado, práctica), así que **C3 se descarta como control diagnóstico**;
  - **C4, sin la raíz espuria** (cada pasaje empieza con el primer título del documento, «GLOSARIO» o el nombre
    de la institución): sin efecto en nada;
  - **C4, sin la línea «Se distingue por:»** (rasgos distintivos): arregla `014i` y `017i`, empeora `030f`
    (2 → 3) y mejora `018i` (3 → 2); no rompe aciertos;
  - **C5, otro registro:** con la pregunta formal se arreglan 7 informales y `032f`; con la informal se rompen 3
    formales que estaban bien;
  - **C6, vistas:** el 11 % de los candidatos marcados como correctos (11 de 101) no contiene la evidencia en el
    texto que ve el reranker, porque el motor manda la vista del hijo recuperado y no la unidad. En `018i` ningún
    candidato correcto muestra la oración que responde. Al revés, en `005f/i` el candidato que gana contiene
    literalmente la evidencia pero el volcado lo marca como incorrecto: la etiqueta usa los offsets de la unidad,
    no los de la vista.
- Clasificación (primer control que arregla, sin C3):

  | Causa | Casos | n |
  |---|---|---|
  | F etiqueta (el primero también responde) | `005f`, `005i` | 2 |
  | B vista sin la respuesta | `018i` | 1 |
  | C línea de rasgos (también los arregla C5) | `014i`, `017i` | 2 |
  | D formulación (registro informal o redacción) | `002i`, `003i`, `004i`, `009i`, `012i`, `032f` | 6 |
  | E el modelo ve la información y prefiere otro pasaje | `013f`, `013i`, `030f`, `031f` | 4 |

  En E, los ganadores son pasajes del mismo artículo o del mismo tema que comparten más palabras con la pregunta
  sin dar el dato (`013f/i`: la introducción del artículo 14 frente a «semanas 3, 6, 9 y 12»), o casi empates
  (`030f`: margen 0,19).
- ¿Esperable?: en parte; D era la hipótesis principal (foco informal).
- Explicaciones posibles: D y E son sensibilidad del modelo a la redacción y preferencia por el solapamiento
  léxico sobre el dato pedido; B, C y F son de la tubería y de la medición, no del modelo.
- Siguiente control: etapa 2 (oclusión y sondas por capa) sobre D y E.
- Corrección (OBS-0010): `009i` pasa a F. Su competidor contiene la duración de la defensa (anexo 2, paso 10), una
  evidencia que faltaba en el banco. Quedan D = 5 (`002i`, `003i`, `004i`, `012i`, `032f`), E = 4 y F = 3.
- Estado: **puerta 1 superada con muestra chica.** D + E son 10 de 15 (67 %, sobre el mínimo de la mitad), pero
  con n = 15. Aparte del afinado quedan tres arreglos: la vista del hijo (B), la línea de rasgos (C, efecto mixto)
  y la etiqueta del volcado (F).

### OBS-0010: el modelo lee la línea que responde, pero el tema le pesa más que el aspecto preguntado
- Etapa / control: 2 / oclusión
- Casos y run_id: los 10 casos D/E de OBS-0009; int8 con lote 1; `20261017-223216-e2-oclusion-73c745`
- Cambio realizado: quitar una palabra de la pregunta, o una línea de un pasaje, y medir el cambio en
  `s(q, correcto) − s(q, competidor)`.
- Resultado observable:
  - **palabras de la pregunta que favorecen al competidor:** anclas de tema o de entidad («supervisor», «rúbrica»,
    «académico», «nota», «nota final», «bitácora») y el identificador de la unidad («2», «p2», «II»);
  - **palabras que favorecen al correcto:** las que dicen qué se pregunta («cuanto», «pesa», «dura»,
    «intermedio», «12», «difiere», «entrevista»);
  - **líneas:** en 10 de 10 casos, la línea con la evidencia es la que más aporta al pasaje correcto (+3,5 a
    +11,4). El competidor gana con una línea del mismo tema que no trae el dato pedido;
  - en `009i`, esa línea del competidor sí responde: es un error de etiqueta (se corrige en OBS-0009).
- ¿Esperable?: sí; es el sesgo típico de un cross-encoder hacia el solapamiento de tema.
- Explicaciones posibles: el modelo pondera más «este pasaje habla de X» que «este pasaje da el dato Y de X».
  Los negativos de su entrenamiento rara vez eran del mismo tema y de otro aspecto.
- Siguiente control: sondas por capa (¿la diferencia es separable en alguna capa y se pierde al final?).
- Estado: repetida en los 10 casos. Apunta a afinar con **negativos difíciles del mismo tema y otro aspecto**, que
  es justo lo que diseña la etapa 3.

### OBS-0011: ninguna capa separa linealmente los errores de bge; la discriminación se forma en las capas 16–24
- Etapa / control: 2 / sondas por capa
- Casos y run_id: 726 pares (correcto mejor puntuado frente a competidor mejor puntuado): NoMIRACL 617, banco
  real 61, sintético 48. bge (PyTorch fp32) se equivoca en 135: 121 de NoMIRACL, 13 del banco real y 1 del
  sintético. Regresión logística sobre `h(q,c) − h(q,w)` del vector `<s>`, 5 pliegues agrupados por pregunta;
  `20261017-223715-e2-sondas-092796`. Reanálisis con los errores de bge pesando lo mismo que los aciertos (sobre
  los mismos vectores guardados, sin volver a correr el modelo).
- Resultado observable:

  | Capa | 1 | 4 | 8 | 12 | 16 | 20 | 24 |
  |---|---|---|---|---|---|---|---|
  | Acierto de la sonda (todas) | 0,53 | 0,55 | 0,58 | 0,60 | 0,67 | 0,78 | 0,79 |
  | Acierto en los aciertos de bge | 0,54 | 0,56 | 0,58 | 0,63 | 0,72 | 0,88 | 0,87 |
  | **Rescate** de los errores de bge (peso igual) | 0,51 | 0,51 | 0,56 | 0,46 | 0,44 | 0,38 | 0,44 |
  | D/E del banco real ordenados bien (de 9) | 7 | 6 | 9 | 7 | 7 | 5 | 4 |

  Sin el reponderado, el rescate es de 0,44–0,58 hasta la capa 11 y de 0,33–0,41 desde la 17. La capa 0
  (embeddings) da 0 por construcción: el `<s>` es idéntico en ambos pares.
- ¿Esperable?: en parte.
- Explicaciones posibles:
  - la distinción entre correcto y competidor se construye en la mitad superior (capas 12–24, sobre todo 16–24);
  - para los pares que bge ordena mal, ninguna capa contiene una dirección lineal que los ordene bien. El máximo
    (0,56 en la capa 8, ±0,04) no se distingue del azar, y en las capas finales el rescate cae bajo el azar: la
    representación tardía codifica activamente la preferencia equivocada;
  - el 9/9 de la capa 8 en los D/E reales es llamativo pero no concluyente (n = 9, siete capas probadas, sonda
    casi al azar en general).
  - Límite del método: una sonda lineal no detecta información codificada de forma no lineal.
- Siguiente control: puerta 2 (abajo); etapa 3.
- Estado: repetida en tres fuentes. Según la tabla prefijada del README, el patrón es «nunca hay separación»: **no
  basta recalibrar la cabeza**. Hay que cambiar las representaciones donde se forma la decisión.

### Puerta 2: qué capas se afinan
- **Principal:** capas 12–24 y la cabeza. Es donde se forma la discriminación (OBS-0011). Cuesta menos en CPU y en
  memoria, y arriesga menos olvido que tocar las capas bajas.
- **Variante de comparación:** afinado completo con lr 1e-5.
- **Descartado:** solo la cabeza. Las capas finales codifican la preferencia equivocada; recalibrar la salida no
  la corrige.
- **Datos:** la oclusión (OBS-0010) dice qué enseñar. Negativos del **mismo tema y otro aspecto**, y preguntas con
  **anclas de entidad** («supervisor», «P2», «bitácora») que aparecen en el competidor más que en el correcto, más
  paráfrasis informales.

### Congelamiento de la prueba sintética (2026-10-18)
- `sintetico_prueba.yaml`: 4 documentos (transporte, evaluación de asignaturas, salud estudiantil, ayudantías), 26
  objetivos y 52 preguntas. Lo escribió Claude después del banco de entrenamiento, con dominios distintos.
- SHA-256 con finales LF: `49e6237f67c1efe6c74443edc0007e2d8a82f599ce4611c6b3697ded44aee9b5`. Huella canónica,
  que no depende de CRLF/LF al clonar en Windows: blob de git `569b71843933d7a16521feb32929baef7fd70502`
  (comprobar con `git hash-object laboratorio_reranker/sintetico_prueba.yaml`).
- **No se ha medido.** Se mide una sola vez en la etapa 4, con el modelo base y con la copia afinada. Si el hash
  cambia, la prueba deja de valer.
- Límite conocido: con 52 preguntas y un bge que acierta casi todo en lo sintético, esta prueba difícilmente reúne
  los 15 errores de orden de § 5. La prueba principal será NoMIRACL `test`; el banco real queda como confirmación.

### OBS-0012: conjunto de afinado (etapa 3)
- Archivos: `.cache/laboratorio-reranker/afinado/grupos-entrenamiento.jsonl` (SHA-256 `94aaf752…b6eca4`) y
  `grupos-desarrollo.jsonl` (`dc9be08b…b019f`). Grupos de 1 positivo y 7 negativos (formato FlagEmbedding),
  semilla 13.
- Composición del entrenamiento (1 716 grupos):
  - **SQAC** `train`, 1 200 grupos (CC BY-SA 4.0). Cada contexto se parte en tramos de 2 oraciones con el título;
    los negativos son primero tramos hermanos del mismo texto (media 2,4 por grupo) y después vecinos por TF-IDF
    de otros artículos. Ningún negativo contiene la respuesta. En AnCora se omite el «título», que es un nombre de
    archivo;
  - **MIRACL** es `train` (sentence-transformers, Apache-2.0), 400 grupos: la negativa juzgada más positivos de
    otras preguntas. Revisión manual de 20: ninguno claramente erróneo, unos 4 flojos y otro malo visto antes
    («colonias»). Se bajó de 800 a 400 por ese ruido, porque sus negativas son casi todas de otro tema y porque
    bge ya lo vio;
  - **sintético propio**, 116 grupos (58 de 68 preguntas, duplicadas): vistas reales del motor, positivos solo si
    la vista contiene la evidencia y negativos solo si no la contiene. El motor da hit@1 0,853 en este banco: es
    más difícil que el piloto.
- Registro: 1 170 formales, 490 informalizados por reglas (el 28 % de los públicos) y 56 informales escritos a
  mano.
- Desarrollo: 200 grupos de SQAC `dev`. El seguimiento útil será la puntuación fuera de línea de los volcados
  (piloto `dev`, banco real como descubrimiento y NoMIRACL `dev`).
- Fugas comprobadas: ninguna pregunta de entrenamiento coincide con la prueba sintética, el banco real ni
  NoMIRACL dev/test (se excluyeron 2 714 preguntas normalizadas de NoMIRACL). El banco real **no entra al
  entrenamiento**: los documentos del cliente no llegan al modelo.
- Pasajes: 58 palabras de mediana y 157 en el p95, así que entran holgados en los 256 tokens.
- Estado: listo para la etapa 4, pendiente de revisión del usuario.

### OBS-0013: herramienta de afinado y exportación verificada (sin entrenar todavía)
- Etapa / control: 4 / preparación
- Entrenamiento (`afinar.py entrenar --pasos-prueba 2`, CPU):
  - 152 M parámetros entrenables (capas 12–23 y cabeza);
  - la ruta mixta (congelado en fp16, entrenable en fp32), que es la de la GTX 1650 de 4 GB, corre sin errores de
    tipos y da la misma pérdida que fp32 (0,0327 tras 2 pasos);
  - `original_intacto: true`: el SHA-256 de `model.safetensors` en la caché no cambia;
  - **en CPU fp32: 32 s por grupo, ~15 h por época** en el Ryzen 5 7530U. Se entrenará en la GPU.
- Exportación (`afinar.py exportar` sobre una copia **sin entrenar**):
  - un solo `model.onnx_data` (fp32, 2,27 GB) y un `model_int8.onnx` de 570,7 MB, igual en tamaño al de
    onnx-community; el motor lo carga (`local:<carpeta>`);
  - paridad con el int8 oficial en 8 preguntas reales: top-1 igual 8/8, |Δlogit| p50 0,18 y máximo 0,66, del
    mismo orden que el ruido de cuantización de C1. No es idéntico bit a bit, porque el grafo exportado difiere;
  - por eso la comparación de la etapa 4 será **base re-exportado con la misma receta**
    (`.cache/laboratorio-reranker/base-reexportado/onnx/`) frente a la **copia afinada exportada igual**: la
    diferencia solo puede venir del entrenamiento.
- Se necesitó liberar el modelo de PyTorch antes de cuantizar: la matriz de embeddings exige ~1 GB contiguo y el
  portátil tenía 5,6 GB libres.
