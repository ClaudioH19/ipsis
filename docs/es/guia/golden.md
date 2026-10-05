# Tu golden set

El golden set es el banco de preguntas reales del cliente con el que se mide
y calibra el asistente. Vive en la carpeta `golden/` de cada proyecto y nunca
se mezcla con el banco sintético de las pruebas (`tests/datos/banco/`).

El banco versionado queda en `golden/bank/` (`manifest.json` más los casos
en JSONL). Se arma a partir de un CSV simple que completa una persona. Con 30 a 60 preguntas revisadas
por una persona conocedora del corpus sirve para ajustar y comparar perfiles
(para certificar un riesgo hace falta más: ver «Calibrar»). Debe cubrir las seis
categorías internas (exacta, paráfrasis, sin respuesta, premisa falsa,
ambigua, conversacional) y separar casos `dev` y `test` antes de calibrar.

## Paso a paso

```bash
ipsis golden template            # golden/golden.csv con preguntas sugeridas desde tus documentos
# completa el CSV en Excel, LibreOffice o un editor
ipsis golden import golden/golden.csv
ipsis golden validate              # ¿sigue coincidiendo con el corpus?
ipsis evaluate                     # cobertura, falsos «ok» y latencia del perfil
ipsis calibrate                    # ver «Calibrar»
```

1. **Plantilla.** `ipsis golden template [--n N]` elige secciones diversas de
   tus documentos (TF-IDF y MMR, sin modelos) y escribe filas con
   `instructions`, `suggested_passage` y `key_terms` para ayudarte. Un
   ~35% son trampas: preguntas del **mismo tema** cuyo dato no está. No pisa
   un `golden.csv` existente sin `--force`. Junto al CSV queda un `README.txt`
   en el idioma del proyecto.
2. **Completar.** Columnas:

   | Columna | Contenido |
   |---|---|
   | `question` | Como la escribiría un usuario real |
   | `type` | `answerable`, `no_answer`, `false_premise`, `ambiguous` o `conversational` |
   | `literal_answer` | Solo si es respondible: el dato mínimo, copiado tal cual del documento |
   | `document` | El documento donde está (nombre o id) |
   | `subtype`, `pair` | `same_topic_trap` y el `id` de la respondible del mismo tema |
   | `id`, `notes` | Opcionales |

   Las columnas de ayuda se ignoran al importar. Los CSV anteriores a ipsis
   0.9, con columnas en español (`pregunta`, `tipo`, `respuesta_literal`…) y
   tipos en español (`respondible`, `sin_respuesta`…), se siguen importando.
3. **Importar.** `ipsis golden import` acepta el CSV (coma o punto y coma,
   con o sin BOM), un `.jsonl` o un SQuAD 2.0. Ubica cada respuesta literal en
   el documento y guarda sus offsets; clasifica las respondibles en exactas o
   paráfrasis. Si hay errores, los lista todos con su fila y no escribe nada.
   Avisa si hay menos de 30 filas o menos de un 30% sin respuesta.
4. **Exportar.** `ipsis golden export --format squad2|csv` para usarlo en
   otras herramientas.

## Reglas de curación

- `dev` puede usarse para ajustar umbrales; `test` permanece cerrado hasta la
  comparación final.
- La separación dev/test se hace al importar. Es 50/50 dentro de cada estrato:
  - categoría interna (exacta, paráfrasis, sin respuesta…);
  - más el subtipo (trampa del mismo tema).

  Así, con bancos chicos, las exactas no quedan todas de un lado. Es
  determinista: reimportar el mismo archivo da la misma separación.
- Toda pregunta respondible incluye respuesta literal y evidencia con offsets.
- Las preguntas usadas para descubrir o corregir un defecto no deben ser la
  única medición de ese comportamiento.
- No se copian documentos institucionales sensibles al repositorio; el
  manifiesto identifica y hashea el corpus evaluado localmente.

## Calibrar

```text
ipsis calibrate [--alpha 0.05] [--apply]
```

Requiere el índice (`ipsis index`) y el golden importado
(`ipsis golden import`). Corre el perfil sobre el golden y **elige umbrales
escalares** (`ok`, `oov_ok`, `focus`) usando solo `dev`. Busca la combinación
que más responde directo cuya cota superior de riesgo (Clopper-Pearson al 95%)
es ≤ `--alpha`; `test` solo verifica. No entrena ni modifica modelos.
Entre combinaciones con la misma cobertura, prefiere:

1. la de menos errores;
2. la más cercana a los umbrales del perfil;
3. recién después, la más estricta.

Si `dev` no distingue dos valores de un umbral, ese umbral no se mueve.

| Resultado | Qué significa | Salida |
|---|---|---|
| `CALIBRADO` | Hay muestra y una combinación cumple α | 0 |
| `MUESTRA_INSUFICIENTE` | Todavía no se puede certificar α: no hay suficientes respuestas directas sin error en `dev` (con 0 errores, 59 para α = 0,05). **No** significa que el perfil sea inseguro | 0 |
| `SIN_UMBRAL_SEGURO` | Hay muestra, pero ninguna combinación cumple α | 1 |

- Sin `--apply`, solo informa y no escribe nada.
- Con `--apply`, escribe `config/calibration.yaml` en cualquier
  estado, para auditoría. El motor **solo** usa sus umbrales si el estado es
  `calibrated` y su procedencia coincide con el proyecto: perfil, modelos y
  `corpus_hash` del índice. Si cambia el corpus o el perfil, la calibración se
  ignora y vuelven los umbrales del perfil.
- Si el corpus cambió desde que se importó el golden, primero
  `ipsis golden validate` y, si corresponde, vuelve a importar.
- El banco universal de las pruebas (`tests/datos/banco_universal/`) es de
  regresión y no se puede usar para calibrar.
