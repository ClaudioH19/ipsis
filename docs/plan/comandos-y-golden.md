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

1. Elige secciones **diversas** con MMR sobre vectores TF-IDF, garantizando
   que aparezca cada documento. Escribe una fila por sección con
   `documento`, `fragmento_sugerido` y `terminos_clave` (top TF-IDF).
2. Agrega un 35% de filas `sin_respuesta` cuya nota usa los términos clave de
   una sección: *«Escribe una pregunta sobre «garantía» cuya respuesta NO esté
   en los documentos»*. Así salen preguntas trampa del mismo tema.
3. Agrega 3 filas `conversacional` ya completas en el idioma del proyecto.
4. Escribe `golden/LEEME.txt` con `golden_instrucciones` del paquete de idioma.

### `rag golden importar`

- Ubica `respuesta_literal` en el corpus: primero coincidencia exacta y
  después con espacios colapsados, mapeando de vuelta a los offsets
  originales. Si el texto aparece más de una vez y la fila no indica
  `documento`, avisa.
- Exige al menos 30 filas. Advierte si hay menos de 30% de
  `sin_respuesta` + `premisa_falsa`, porque con menos no se puede medir el
  riesgo (con 0 errores en n casos, la cota al 95% es ≈ 3/n).
- Separa `dev`/`test` 50/50, estratificado por tipo y determinista por hash
  del `id`.
- Guarda el hash del corpus. `golden validar` y `doctor` avisan si el corpus
  cambió.

## 4. Calibración con control de riesgo

1. Ejecuta el perfil sobre `dev` y guarda las señales de cada caso.
2. Para cada `τ_ok` candidato (los valores observados), cuenta los falsos
   `ok` entre los casos aceptados y calcula la **cota superior de
   Clopper-Pearson al 95%**: CDF binomial con `math.comb` + bisección, sin
   scipy.
3. Elige el `τ_ok` más bajo cuya cota sea ≤ α (por defecto 0,05). Si ninguno
   cumple, `τ_ok = 1,01`: el perfil nunca responde `ok`, y el reporte lo dice.
4. Repite para `τ_foco`, `τ_rel`, `τ_dominio` y `τ_oov` con su propio error
   (`relacionado` mostrado ante una pregunta fuera de dominio).
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
umbrales: {oov: 0.58, dominio: 0.27, relacionado: 0.48, foco: 0.5, ok: 0.71}
resultado_test:
  falsos_ok: {observado: 0.0, cota_superior_95: 0.06, n: 48}
  cobertura_ok: 0.62
```

El motor solo usa la calibración si su `procedencia` coincide con el perfil,
los modelos y el índice actuales.
