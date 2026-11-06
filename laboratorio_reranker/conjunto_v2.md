# Conjunto v2: datos compartidos por los experimentos 1 y 2

Estado: **diseño (2026-11-06), sin construir.** Reemplaza al conjunto de la etapa 3 (OBS-0012) para los dos
experimentos de la rama `lab061126`:

- **Exp. 1**: afinado de bge-reranker-v2-m3 con LoRA u otro método eficiente en parámetros.
- **Exp. 2**: edición directa de pesos por GPT-6 Astra («weight-space programming», Takehi et al., MIT CSAIL,
  2026-11-02), con salidas por capa sobre una fracción del conjunto de práctica.

Los dos usan **las mismas particiones, los mismos grupos y la misma prueba congelada**, y se evalúan con el mismo
código antes y después.

## 1. Por qué un conjunto nuevo

El afinado de la etapa 4 con el conjunto v1 no dio una mejora estadísticamente significativa (corrida en GPU del
usuario). El conjunto v1 tenía límites que explican, al menos en parte, ese resultado:

| Límite del v1 | Dato | Efecto |
|---|---|---|
| Pocas negativas difíciles | MIRACL entró en la versión `es-triplet`: **1** negativa juzgada por pregunta, completada con positivos de otras preguntas (fáciles) | Se usaba 1 de las 5,3 negativas juzgadas por persona que MIRACL tiene por pregunta |
| Hermanas escasas | SQAC: 2,4 tramos hermanos por grupo en promedio; el resto, vecinos TF-IDF de otros artículos | Pocos ejemplos del error que importa: mismo tema, otro aspecto (OBS-0010) |
| Tamaño | 1 716 grupos; se usaron 1 200 de unas 15 000 preguntas de SQAC | Poca señal para mover las capas 12–24 |
| Negativas no minadas con bge | TF-IDF elige negativas que bge ya ordena bien | Los gradientes se gastan en casos resueltos |
| Registro informal | Solo reglas ortográficas (tildes, «q», «xq») | La brecha léxica (D, OBS-0009) casi no está |
| Dominio | Wikipedia y noticias | Los documentos reales son normativa con artículos, anexos y tablas hermanas |
| Prueba sintética | 52 preguntas, saturada para bge | Potencia ≈ 0 (§ 6) |

## 2. Inventario de fuentes (verificado el 2026-11-06)

Solo entran al **entrenamiento** las fuentes con licencia compatible con publicar el modelo. Las CC BY-SA quedan
con la advertencia del README § 5.1. Las no comerciales solo sirven para evaluación interna.

| Fuente | Licencia | Tamaño (es) | Juicio de «responde» | Uso propuesto |
|---|---|---|---|---|
| [MIRACL](https://huggingface.co/datasets/miracl/miracl) `train`, juicios completos (`sentence-transformers/miracl` `es-triplet-all`) | Apache-2.0 | 2 162 preguntas, 10,0 juicios/pregunta: 4,6 positivos y **5,3 negativos juzgados por nativos** | humano | entrenamiento (núcleo) |
| [NoMIRACL](https://huggingface.co/datasets/miracl/nomiracl) `test` `relevant` | Apache-2.0 (textos CC BY-SA) | **1 515 preguntas**, 9,9 juicios/pregunta | humano | **prueba principal congelada** |
| NoMIRACL `dev` `relevant` | ídem | 648 preguntas (son exactamente las de MIRACL `dev`) | humano | desarrollo |
| [SQAC](https://huggingface.co/datasets/PlanTL-GOB-ES/SQAC) | CC BY-SA 4.0 | ≈ 18 800 preguntas extractivas | tramo de respuesta | entrenamiento (todas, no 1 200) y desarrollo |
| [MLQA](https://github.com/facebookresearch/MLQA) es | CC BY-SA 3.0 | ≈ 5 750 preguntas (dev 500, test 5 253) | tramo de respuesta | entrenamiento o segunda prueba pública |
| [XQuAD](https://huggingface.co/datasets/google/xquad) es | CC BY-SA 4.0 | 1 190 preguntas, 240 contextos | tramo de respuesta | prueba (traducción profesional, independiente de SQAC) |
| [ALIA legal-administrativo CQA](https://huggingface.co/datasets/SINAI/ALIA-es-legal-administrative-cqa) (BOJA) | CC BY-SA 4.0 | 9 776 preguntas sobre 6 474 documentos; 700 documentos con ≥ 3 fragmentos (3 196 preguntas) | **ninguno**: pregunta y respuesta generadas por GPT-OSS-20B; respuesta abstractiva | **dominio normativo**: entrenamiento y prueba de dominio, con re-fragmentación y juez (§ 4, D4) |
| Sintético propio (Claude) | propio | 68 + 52 preguntas hoy | evidencia con offsets | ampliar a los fallos del banco real (§ 4, D5) |
| [Horizon multilingual-rerank-distill](https://huggingface.co/datasets/Horizon-Labs/multilingual-rerank-distill) | ODC-BY | 732 k filas en 47 idiomas; 16 candidatos por pregunta con puntaje de Qwen3-Reranker-4B | puntaje de un modelo maestro | **opcional**: etiquetas blandas para destilación (variante del exp. 1) |
| [MessIRve](https://huggingface.co/datasets/spanish-ir/messirve) | **CC BY-NC 4.0** | ~700 k consultas reales | fragmento destacado de Google | solo evaluación interna del registro coloquial; nunca entrenamiento |
| [SQuAD-es](https://github.com/ccasimiro88/TranslateAlignRetrieve) v1.1 | CC BY 4.0 | ≈ 87 k (traducción automática) | tramo realineado | reserva; ruido de traducción |

Notas:

- BGE-M3 se entrenó con MIRACL `train`. Las cifras absolutas sobre MIRACL saldrán optimistas, pero el afinado
  se compara contra el mismo modelo base. La prueba principal (NoMIRACL `test`) no comparte ids con MIRACL `train`
  ni con `dev` (comprobado).
- Los pasajes de ALIA tienen 452 palabras de mediana (≈ 630 tokens): **no caben en la ventana de 256** del motor.
  Hay que re-fragmentarlos desde el corpus base ([ALIA-es-legal-administrative](https://huggingface.co/datasets/SINAI/ALIA-es-legal-administrative),
  CC BY-SA 4.0) y ubicar la evidencia de cada pregunta dentro de un fragmento.
- No encontré un conjunto público en español con negativas etiquetadas explícitamente como «mismo tema, otro
  aspecto». Esas se fabrican con hermanas de documento y se verifican (D4).

## 3. Esquema de un grupo

Una línea JSONL por pregunta. Es el formato de FlagEmbedding ampliado: `afinar.py` lee `query`, `pos` y `neg`, y
el resto de los campos sirve para estratificar y auditar.

```json
{"id": "miracl-es-123", "fuente": "miracl", "licencia": "Apache-2.0", "particion": "entrenamiento",
 "documento": "wiki:Ley_de_Moore", "registro": "formal|informal_reglas|informal_claude",
 "query": "...", "pos": ["..."], "neg": ["...", "..."],
 "neg_tipo": ["hermana", "juzgada", "minada_bge", "minada_densa", "otro_documento"],
 "verificacion": {"pos": "humano|tramo|juez", "neg": ["humano", "tramo", "juez", "..."]},
 "base": {"rango_pos_fp32": 3, "margen_fp32": -0.42, "rango_pos_int8": 2, "dificil": true},
 "tokens": {"pos": 141, "neg_max": 233, "truncado": false}}
```

`base` se calcula **una vez**, con bge sin tocar (fp32 y el int8 del motor, lote 2, 256 tokens): define la
dificultad de cada grupo y es la línea base del «antes».

## 4. Fases de construcción

Cada fase escribe su salida en `.cache/laboratorio-reranker/conjunto-v2/<fase>/` con `resumen.json` (conteos y
SHA-256). Es determinista con semilla fija y versiones fijadas.

| Fase | Qué hace | Puerta |
|---|---|---|
| **D0 Recolección** | Descarga con revisión fijada: MIRACL `es-triplet-all`, NoMIRACL, SQAC, MLQA, XQuAD, ALIA (CQA y corpus base). Registra licencia y revisión de cada fuente | Todas las fuentes con licencia anotada |
| **D1 Pasajes** | Normaliza a pasajes ≤ 256 tokens con el tokenizador del motor. Título y sección como primera línea, igual que la vista del motor. Re-fragmenta ALIA por artículo o apartado | ≤ 2 % de positivos truncados que pierdan la evidencia |
| **D2 Candidatos** | Por pregunta junta: juicios humanos (MIRACL), hermanas del mismo documento o artículo, BM25 y el denso del motor (e5-small) sobre el corpus de su fuente. Unos 30 candidatos | Cobertura: el positivo está entre los candidatos |
| **D3 Puntuación base** | bge fp32 y int8 sobre todos los pares. Rango del positivo, margen y negativas que lo superan | — |
| **D4 Falsos negativos** | Descarta las negativas que también responden: tramo de respuesta (extractivas); umbral relativo al positivo (se descarta la negativa con puntaje ≥ 95 % del positivo, *TopK-PercPos* de [NV-Retriever](https://arxiv.org/abs/2407.15831)) salvo que la verifique un juez; juez para las negativas que bge pone sobre el positivo y para los positivos de ALIA | Auditoría manual de 100 grupos al azar: ≤ 5 % de etiquetas erróneas |
| **D5 Registro** | Informalización por reglas (como el v1) y **paráfrasis con brecha léxica escritas por Claude** para una muestra estratificada (objetivo: ≥ 1 000 preguntas), con anclas de entidad y aspecto (OBS-0010) | Revisión de 50 paráfrasis: mantienen la intención |
| **D6 Particiones** | Por **documento o artículo**, nunca por pregunta, y por fuente (§ 5). Se excluyen de entrenamiento y práctica las preguntas normalizadas de toda prueba | Fugas = 0 (pregunta normalizada, pasaje exacto y documento) |
| **D7 Congelamiento y línea base** | Hash de cada partición y métricas del modelo base en todas ellas (§ 7). La prueba se congela **antes** de entrenar o editar | Hashes en la bitácora |

**Composición objetivo del entrenamiento** (a ajustar con los conteos de D3): unos 8 000 a 12 000 grupos con 7
negativas cada uno.

- Al menos el 40 % de los grupos debe ser **difícil** (bge no pone el positivo primero, o gana por un margen menor
  que 1).
- Al menos 3 negativas por grupo deben ser **hermanas** o **juzgadas**.
- El resto son grupos fáciles, que sirven como retención para no olvidar lo que ya funciona.

**El juez de D4.** Lo ideal es un modelo abierto, local o en la GPU (p. ej. Qwen3-Reranker-4B o un LLM de 7–14 B),
más una muestra revisada por Claude o por persona. Hay que confirmar los términos de uso antes de entrenar con
salidas de un modelo de OpenAI. El juez solo **descarta** pares dudosos: nunca crea positivos que entren a la
prueba principal.

## 5. Particiones

| Partición | Contenido | Exp. 1 | Exp. 2 (Astra) |
|---|---|---|---|
| `entrenamiento` | MIRACL `train`, SQAC `train`, MLQA, ALIA (documentos de entrenamiento), sintético de entrenamiento | entrena | **práctica**: lee pares y textos, y recibe las salidas por capa de una fracción fija (p. ej. 10 %, sorteada una vez y versionada) |
| `desarrollo` | NoMIRACL `dev` (= MIRACL `dev`), SQAC `dev`, ALIA (documentos de desarrollo), piloto sintético | elección de hiperparámetros y parada | presupuesto de pasadas: es lo único que Astra puede evaluar |
| `prueba` (congelada) | **NoMIRACL `test` `relevant`** (1 515, principal), XQuAD-es, ALIA (documentos de prueba), `sintetico_prueba.yaml` | se mide una sola vez | Astra no la ve nunca |
| `retención` | `banco_pasajes` `test`, `general.py`, una muestra fácil de `desarrollo` | olvido | olvido |
| `descubrimiento` (privado) | banco real del cliente | confirmación final | **no sale de la máquina**: nada del cliente va a OpenAI |

## 6. Potencia: por qué la prueba v1 no podía dar significativo

Potencia del McNemar exacto (α = 0,05), simulada con tasas de casos ganados y perdidos por el afinado:

| n de la prueba | gana 3 %, pierde 1,5 % | gana 5 %, pierde 3 % | gana 4 %, pierde 1 % |
|---|---|---|---|
| 52 (sintética v1) | 0,01 | 0,01 | 0,02 |
| 300 | 0,17 | 0,15 | 0,57 |
| 648 (NoMIRACL `dev`) | 0,39 | 0,38 | 0,94 |
| **1 515 (NoMIRACL `test`)** | **0,79** | **0,75** | **1,00** |
| 3 000 | 0,97 | 0,97 | 1,00 |

Una mejora neta de 1,5 puntos de hit@1 necesita una prueba del orden de 1 500 preguntas para detectarse con
potencia ≈ 0,8. Por eso la prueba principal pasa a NoMIRACL `test`, y XQuAD, ALIA y la sintética se reportan
aparte como pruebas secundarias. Para el criterio de éxito del README § 4 se fija **una sola** prueba primaria; si
se usan varias, se corrige por comparaciones múltiples (Holm).

## 7. Evaluación antes y después (común a los dos experimentos)

El mismo script mide el modelo base y cada candidato en **todas** las particiones, con el int8 exportado igual
para los dos (OBS-0013: base re-exportado frente a modelo modificado):

- hit@1, hit@3 y MRR@10, por fuente, por registro (formal o informal) y por tipo de negativa (hermana, juzgada…);
- ganados y perdidos con McNemar exacto contra el base;
- en `entrenamiento` y en la práctica de Astra: el ajuste conseguido;
- en `desarrollo` y `prueba`: la generalización; en `retención`: el olvido;
- el C1 sobre el modelo modificado (que la mejora sobreviva al int8) y el p95 de latencia.

## 8. Orden de los experimentos sobre este conjunto

1. **D0–D7**: construir y congelar el conjunto v2 y medir la línea base.
2. **Exp. 1**:
   1. repetir el afinado del v1 (capas 12–24) con el conjunto v2, para separar el efecto de los datos del efecto
      del método;
   2. LoRA en todas las capas, fusionado antes de exportar (misma arquitectura y mismo costo);
   3. opcional: destilación con etiquetas blandas (Horizon).

   La elección se hace en `desarrollo`.
3. **Exp. 2**:
   1. construir el harness (kernel en CPU con los pesos, herramienta de pasadas con presupuesto, `save_edit` con
      restricciones, sin gradientes, explicación obligatoria);
   2. entregar la práctica con las salidas por capa;
   3. hacer corridas con presupuestos de 10, 25 y 50 pasadas, con al menos 2 corridas por presupuesto;
   4. como línea base sin Astra, hacer a mano la ablación de una dirección contrastiva de «solapamiento de tema»
      (al estilo de Heretic).
4. **Medición única de la prueba congelada** para todos los candidatos finales de los dos experimentos, a la vez.
