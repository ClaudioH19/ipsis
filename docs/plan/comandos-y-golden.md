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
| golden | ★ `rag golden plantilla [--n 40]` | Genera `golden/golden.csv` y `golden/LEEME.txt` (§3) |
| golden | ★ `rag golden importar <archivo.csv\|.jsonl\|squad.json>` | Valida, ubica offsets, separa `dev`/`test` y escribe `golden/banco/` |
| golden | ★ `rag golden validar` | Revisa el banco contra el corpus actual |
| golden | ★ `rag golden exportar --formato squad2\|csv` | Exporta el banco |
| evaluacion | `rag evaluar [--split test]` | Métricas con cota de falsos `ok`. Termina con código ≠ 0 si supera el límite |
| evaluacion | ★ `rag calibrar [--alfa 0.05] [--aplicar]` | Umbrales con control de riesgo (§4) |
| evaluacion | `rag benchmark [--perfiles bm25,light,medium,heavy] [--solo-latencia]` | Compara perfiles con el mismo banco y frente a su presupuesto |
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

### `golden/golden.csv` (UTF-8 con BOM, para que Excel respete los acentos)

| Columna | Obligatoria | Contenido |
|---|---|---|
| `id` | no | Se genera si falta |
| `pregunta` | sí | Como la escribiría un usuario |
| `tipo` | sí | `respondible`, `sin_respuesta`, `premisa_falsa`, `ambigua`, `conversacional` |
| `respuesta_literal` | si es `respondible` | Texto **copiado tal cual** del documento: el dato mínimo |
| `documento` | no | Para desambiguar si el texto aparece en varios documentos |
| `notas` | no | Libre |
| `fragmento_sugerido`, `terminos_clave` | no | Ayudas que llena la plantilla; se ignoran al importar |

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
- Exige al menos 30 filas para importar, y advierte si hay menos de 30% de
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

1. Ejecuta el perfil sobre `dev` y guarda las señales de cada caso.
2. Para cada `τ_ok` candidato (los valores observados), cuenta los falsos
   `ok` entre los casos aceptados y calcula la **cota superior de
   Clopper-Pearson al 95%**: CDF binomial con `math.comb` + bisección, sin
   scipy.
3. Elige el `τ_ok` más bajo cuya cota sea ≤ α (por defecto 0,05). Si ninguno
   cumple, `τ_ok = 1,01`: el perfil nunca responde `ok`, y el reporte lo dice.
4. Repite para `τ_foco`, `τ_rel`, `τ_dominio`, `τ_oov_dominio` y `τ_oov_ok`
   con su propio error (`relacionado` mostrado ante una pregunta fuera de
   dominio). Los dos usos de `s_oov` se separan:
   - `s_oov` alto con recuperación baja suele indicar fuera de dominio;
   - `s_oov` alto con recuperación y QA fuertes puede ser una paráfrasis
     legítima o «mismo tema, otra relación».

   Se mide si separar `τ_oov_ok` mejora la cobertura de paráfrasis sin
   introducir falsos `ok`.
5. Verifica en `test`.
6. Con `--aplicar` escribe `configuracion/calibracion.yaml`:

```yaml
version: 1
perfil: medium
fecha: 2026-11-02T10:00:00Z
procedencia:
  banco: golden@1.0.0
  hash_banco: "…"
  hash_corpus: "…"
  manifiesto_indice: "…"
  modelos: {denso: …, reranker: …, lector: …}
alfa: 0.05
estado: CALIBRADO      # o MUESTRA_INSUFICIENTE / SIN_UMBRAL_SEGURO
umbrales: {oov_dominio: 0.58, oov_ok: 0.6, dominio: 0.27, relacionado: 0.48, foco: 0.5, ok: 0.71}
resultado_test:
  falsos_ok: {observado: 0.0, cota_superior_95: 0.045, n: 66}
  cobertura_ok: 0.62
```

El motor solo usa la calibración si su `procedencia` coincide con el perfil,
los modelos y el índice actuales.
