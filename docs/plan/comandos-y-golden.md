# Comandos y golden set

## 1. Ciclo de vida

```text
pip install ─▶ rag init ─▶ rag modelos descargar ─▶ rag cargar ─▶ rag indexar ─▶ rag preguntar
                                                                       │
     ┌─────────────────────────────────────────────────────────────────┘
     ▼
rag golden plantilla ─▶ (el cliente completa golden.csv) ─▶ rag golden importar ─▶ rag evaluar
                                                                                    │
                          rag calibrar --aplicar ◀──────────────────────────────────┘
                                   │
                                   ▼
             rag doctor ─▶ rag servir | rag desplegar preparar ─▶ rag widget exportar
                                   │
                                   ▼
                        rag auditar (si el registro está activo)
```

## 2. Comandos

★ = nuevo. Cada comando es una clase en `rag/cli/comandos/<grupo>.py` que llama
a un caso de uso de `rag/aplicacion/`.

| Grupo | Comando | Qué hace |
|---|---|---|
| proyecto | `rag init [carpeta] --perfil light\|medium\|heavy --idioma <código>` | Crea el proyecto (estructura en [arquitectura.md](arquitectura.md) §1.5). ★ `--perfil` |
| proyecto | ★ `rag perfil mostrar` | Perfil activo, modelos, presupuesto, compatibilidad del índice y de la calibración |
| proyecto | ★ `rag perfil cambiar <perfil>` | Cambia el perfil y avisa si hay que reindexar o recalibrar |
| proyecto | `rag configurar clave=valor` | Edita `asistente.yaml` |
| modelos | ★ `rag modelos listar` | Modelos del perfil: tamaño, licencia, atribución y si están en caché |
| modelos | ★ `rag modelos descargar [--perfil p]` | Descarga a la caché global. Después el servicio corre offline |
| modelos | ★ `rag modelos verificar` | Archivos completos + una inferencia de prueba por modelo |
| modelos | ★ `rag modelos exportar <id_hf> [--int8]` | Desarrollo, extra `[exportar]`: convierte a ONNX y cuantiza |
| corpus | `rag cargar <archivo\|carpeta>` | Copia a `documentos/` y cataloga |
| corpus | `rag indexar [--reindexar]` | Parsea, fragmenta, calcula `EstadisticasLexicas`, codifica e indexa. Escribe el manifiesto |
| consulta | `rag preguntar "<texto>" [--diagnostico]` | Consulta local; con diagnóstico muestra etapas, latencias, señales, términos foco y regla |
| consulta | `rag servir [carpeta] [--reindexar]` | API HTTP + widget |
| golden | ★ `rag golden plantilla [--n 40] [--force]` | Genera `golden/golden.csv` y `golden/LEEME.txt` (§3) |
| golden | ★ `rag golden importar <archivo.csv\|.jsonl\|squad.json>` | Valida, ubica offsets, separa `dev`/`test` y escribe `golden/banco/` |
| golden | ★ `rag golden validar` | Revisa el banco contra el corpus actual |
| golden | ★ `rag golden exportar --formato squad2\|csv` | Exporta el banco |
| evaluacion | `rag evaluar [--split test]` | Métricas con cota de falsos `ok`. Termina con código ≠ 0 si supera el límite |
| evaluacion | ★ `rag calibrar [--alfa 0.05] [--aplicar]` | Umbrales con control de riesgo (§4) |
| evaluacion | `rag benchmark --banco M [--banco M2…] [--perfiles bm25,light,medium,heavy] [--experimentos] [--solo-latencia]` | Compara perfiles con los mismos bancos: seguridad, cobertura, latencia y costo (`golden/reportes/benchmark-perfiles.{json,md}`). Sale ≠ 0 si un perfil excede su presupuesto p95 o, con el golden del cliente, da falsos ok (la guardia de `rag evaluar`) |
| evaluacion | `rag comparar <a.json> <b.json>` | Compara dos reportes |
| operacion | `rag doctor` | Configuración, perfil, modelos, índice, calibración, idioma, golden y CORS |
| operacion | ★ `rag auditar [--desde fecha]` | Verifica que cada evidencia del registro de consultas es literal del corpus vigente y resume estados y reglas |
| operacion | ★ `rag desplegar preparar [--salida dist/]` | Empaqueta configuración, calibración e índice; genera `Dockerfile` y `docker-compose.yml` del perfil desde `rag/recursos/despliegue/` |
| web | `rag widget tema listar\|aplicar\|vista-previa` | Presets visuales |
| web | `rag widget exportar <carpeta>` | `widget.js` + snippet |

## 3. Golden set en formato estándar

### Decisión

- **BEIR** solo evalúa recuperación (sin respuesta literal ni casos sin respuesta).
- **Ragas** está pensado para RAG generativo, sin offsets.
- **SQuAD 2.0** exige pegar el contexto y calcular offsets a mano.

Por eso el cliente completa un **CSV simple**, el asistente calcula los offsets
y el banco interno (manifiesto + JSONL) conserva el rigor. SQuAD 2.0 se acepta
como entrada y salida para interoperar.

### SQuAD 2.0: qué se conserva

SQuAD 2.0 es formato de **intercambio**; la verdad es el banco interno.
`rag golden exportar --formato squad2` escribe un SQuAD 2.0 estándar:

- `title` es el `doc_id` y `context` es el párrafo del documento que contiene
  la evidencia (sin chunking nuevo).
- `answer_start` es relativo a ese `context`, y se verifica
  `context[answer_start:answer_start + len(text)] == text` antes de escribir.
  Al importar, `context` + `answer_start` ubican la misma ocurrencia aunque el
  texto se repita en el documento.
- `sin_respuesta` → `is_impossible: true`, `answers: []`. Una trampa con `par`
  va en el párrafo de su par (estilo SQuAD 2.0); las demás, en un párrafo con
  `context` vacío (no se inventa contexto).
- `premisa_falsa` y `ambigua` → `is_impossible: true`: el estándar pierde la
  distinción.
- `conversacional` no se exporta (aviso): no es QA extractivo.
- **Extensión opcional `"rag"`** en cada pregunta: `tipo`, `subtipo`, `par` y
  `notas`. Las herramientas estándar la ignoran; un SQuAD externo sin ella se
  importa igual (`is_impossible` → `sin_respuesta`). Con ella, el tipo y el
  par sobreviven a la ida y vuelta.
- `exacta`/`parafrasis` no se exporta: se recalcula al importar con `s_cov`.
- El split no se exporta: se recalcula, determinista por `id`.

**Ida y vuelta** (`importar → exportar squad2 → importar`): el mismo
**contenido QA** (ids, preguntas, respondibilidad, respuesta literal,
evidencia y offsets, categoría y split) y, gracias a la extensión, `subtipo` y
`par`. Se pierden las conversacionales. Por CSV la ida y vuelta da el mismo
banco.

### `golden/golden.csv` (UTF-8 con BOM, para que Excel respete los acentos)

| Columna | Obligatoria | Contenido |
|---|---|---|
| `id` | no | Se genera si falta |
| `pregunta` | sí | Como la escribiría un usuario |
| `tipo` | sí | `respondible`, `sin_respuesta`, `premisa_falsa`, `ambigua`, `conversacional` |
| `respuesta_literal` | si es `respondible` | Texto **copiado tal cual** del documento: el dato mínimo |
| `documento` | no | Para desambiguar si el texto aparece en varios documentos |
| `notas` | no | Libre |
| `subtipo`, `par` | no | `trampa_mismo_tema` y el `id` de la fila respondible del mismo tema (los llena la plantilla) |
| `instrucciones`, `fragmento_sugerido`, `terminos_clave` | no | Ayudas que llena la plantilla; se ignoran al importar |

| `tipo` | Categoría interna | Estado esperado |
|---|---|---|
| `respondible` | `exacta` si `s_cov(pregunta, evidencia) ≥ 0,6`; si no, `parafrasis` | `respuesta_directa` |
| `sin_respuesta` | `sin_respuesta` | `sin_respuesta` |
| `premisa_falsa` | `premisa_falsa` | `sin_respuesta` |
| `ambigua` | `ambigua` | `relacionado` o `sin_respuesta` (un `ok` cuenta como falso `ok`) |
| `conversacional` | `conversacional` | `conversacional` |

### `rag golden plantilla`

1. Elige secciones **diversas** con MMR sobre vectores TF-IDF (con IDF
   calculado sobre las secciones, no sobre los chunks), garantizando que
   aparezca cada documento. Escribe una fila por sección con
   `documento`, `fragmento_sugerido` y `terminos_clave` (top TF-IDF).
2. Agrega un 35% de filas trampa en **pares mínimos**. Junto a la fila
   respondible de una sección va una fila `sin_respuesta` con
   `subtipo: trampa_mismo_tema` y una nota que usa sus términos clave: *«Escribe
   otra pregunta sobre «garantía» cuya respuesta NO esté en los documentos (p.
   ej. qué incluye, quién la autoriza)»*. Es la clase de error más importante:
   la misma entidad, el mismo pasaje tentador y otra relación pedida («¿Cuándo
   vence la garantía?» frente a «¿Qué incluye la garantía?»). Los negativos
   ajenos al corpus aportan poco. `subtipo` es metadata de evaluación, no un
   tipo público nuevo. La plantilla trae los `id` (`r001` y su trampa `t001`,
   con `par = r001`). Si el cliente completa la trampa pero no su par,
   `importar` avisa y la mide sin par.
3. Agrega 3 filas `conversacional` ya completas en el idioma del proyecto.
4. Escribe `golden/LEEME.txt` con `golden_instrucciones` del paquete de idioma.

### `rag golden importar`

- Ubica `respuesta_literal` en el corpus: primero coincidencia exacta y
  después con espacios colapsados, mapeando de vuelta a los offsets
  originales. Si el texto aparece más de una vez y la fila no indica
  `documento`, avisa.
- Con menos de 30 filas importa igual y avisa que solo sirve de prueba rápida
  (la falta de muestra no es un error), y advierte si hay menos de 30% de
  `sin_respuesta` + `premisa_falsa`. **Con ese tamaño el golden sirve de ajuste
  práctico**: detecta errores evidentes, compara perfiles y explora umbrales,
  pero **no certifica** un riesgo de 5% (ver §4.1). `importar` informa cuántos
  casos haría falta para certificar.
- Separa `dev`/`test` 50/50, estratificado por tipo y determinista por hash
  del `id`.
- Guarda el hash del corpus. `golden validar` y `doctor` avisan si el corpus
  cambió.

## 4. Calibración con control de riesgo

La calibración **solo selecciona umbrales escalares** entre los valores
observados de señales ya calculadas:

- no entrena, no aprende pesos ni cambia modelos;
- no toca índices;
- conserva la procedencia (hashes de banco, corpus y modelos).

Sin calibración, el perfil usa sus umbrales conservadores.

### 4.1 Tamaño de muestra: tres resultados posibles

Con 0 falsos `ok` entre n respuestas aceptadas, la cota superior unilateral
de Clopper-Pearson al 95% es `1 − 0,05^(1/n)`:

| n aceptadas | 20 | 30 | 40 | 50 | 58 | **59** | 100 |
|---|---|---|---|---|---|---|---|
| cota (0 errores) | 13,9% | 9,5% | 7,2% | 5,82% | 5,03% | **4,95%** | 2,95% |

Para certificar α = 0,05 con 95% de confianza hacen falta **al menos 59
respuestas aceptadas sin error** en el split donde se mide (más si hay
errores). Un golden de 30-40 filas separado 50/50 no puede lograrlo, aunque
no tenga ningún error. Por eso `rag calibrar` distingue tres resultados:

| Estado | Significa | Qué hace |
|---|---|---|
| `CALIBRADO` | Hay muestra suficiente y un umbral cumple α | Escribe los umbrales (con `--aplicar`) |
| `MUESTRA_INSUFICIENTE` | Los resultados pueden ser buenos, pero n no permite certificar α | Mantiene los umbrales del perfil, reporta la exploración como **no certificada** e informa cuántas observaciones aceptadas faltan (`n_minimo(errores, α, confianza)`) |
| `SIN_UMBRAL_SEGURO` | Hay muestra suficiente, pero ningún umbral cumple α | Mantiene los umbrales del perfil y lo reporta |

`MUESTRA_INSUFICIENTE` **no** significa que el perfil sea inseguro, ni hace
fallar el producto. Ejemplo:

```text
Calibración no certificable todavía.
Aceptadas sin falso ok: 37
Mínimo con 0 errores para α=0,05 al 95%: 59
Faltan al menos 22 observaciones aceptadas.
Se mantienen los umbrales del perfil.
```

### 4.2 Algoritmo

Implementado en `rag/evaluacion/calibracion.py::calibrar` (P10.2):

1. Ejecuta el perfil sobre el golden y guarda las señales de cada caso
   (`ObservacionEvaluacion.senales`, tal como decidió la política).
2. `exigir_calibrable`: el banco universal (`uso: regresion`) se rechaza.
3. **Solo `dev` elige.** Los candidatos son los valores observados en `dev`
   más el del perfil:
   - `τ_ok`: `s_qa`, o `s_ret` sin lector;
   - `τ_foco`: `s_foco`;
   - `τ_oov_ok`: `s_oov` + ε, porque se compara con «<».
4. Búsqueda **conjunta** de (`τ_foco`, `τ_oov_ok`) × `τ_ok`:
   - Para cada par, ordena los casos elegibles por su puntaje y barre `τ_ok`
     acumulando `n` (respuestas aceptadas) y `x` (falsos ok + directas sin
     respuesta literal).
   - Una combinación es segura si la cota superior de Clopper-Pearson de
     `x/n` es ≤ α.
   - De las seguras, elige la de **mayor cobertura directa**. En empate, la
     más estricta.
   - Sin modelos: re-decide con `regla_cascada`, la misma función que en
     producción.
5. `τ_oov_dominio`, `τ_dominio`, `τ_relacionado` y `τ_cov` quedan en el valor
   del perfil: no cambian el riesgo de una respuesta aceptada. Se reportan el
   recall de fuera de dominio y de premisa falsa.
6. La combinación final se **verifica con la política completa** en `dev` y
   luego se reporta en `test`, aparte (`cumple`, `excede` o
   `muestra_insuficiente`). `test` nunca elige.
7. Estado según §4.1:
   - `CALIBRADO` si hay una combinación segura.
   - `MUESTRA_INSUFICIENTE` si ni la combinación más permisiva llega a
     `n_minimo(0, α)` respuestas. Informa cuántas respuestas sin error hay y
     cuántas faltan.
   - Si no, `SIN_UMBRAL_SEGURO`.
   - En los dos últimos casos se mantienen los umbrales del perfil y no se
     fuerza `τ_ok = 1,01`.
8. `escribir_calibracion` escribe `configuracion/calibracion.yaml` en
   cualquier estado (para auditoría):

```yaml
version: 1
estado: calibrado          # o muestra_insuficiente / sin_umbral_seguro
alfa: 0.05
confianza: 0.95
procedencia:
  perfil: medium
  modelos: {denso: …, reranker: …, lector: …}
  hash_corpus: "sha256:…"   # del manifiesto del índice
  banco: golden@1.0.0
  hash_banco: "…"
umbrales: {oov_dominio: 0.6, oov_ok: 0.75, dominio: 0.33, relacionado: 0.33, foco: 0.5, ok: 0.71, cov: 0.6}
resultado: {mensaje: …, dev: …, test: …, verificacion_test: cumple}
```

El motor solo aplica la calibración si está en estado `calibrado` y su
`procedencia` coincide con el perfil, los modelos y el `hash_corpus` del
índice abierto. Si algo cambió, la ignora y usa los umbrales del perfil.
