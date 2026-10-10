# Postura proactiva: mediciones (ADR 0008)

Estado: terminado, 2026-10-08. Base: `c3b5f01`. Decisión y regla final en
[ADR 0008](../../../decisions/0008-proactive-posture-and-metadata-similarity.md).

## Banco de alternativas

`tests/datos/banco_alternativas`: catálogo de ferretería e inventario por
idioma, con códigos declarados en `dominio.yaml`, más los documentos del
banco de consultas. 58 casos por idioma en `casos.yaml` (dev/test) y 16 en
`validacion.yaml`. `medir.py` registra todo párrafo elegible con sus señales
y re-decide fuera del motor con la misma regla.

| Archivo | Qué es |
|---|---|
| `registro_1.json` … `registro_4.json` | rondas 1 a 4 (light y medium × es/en/pt), cada una con el código de su ronda |
| `calibracion_1.json` … `calibracion_5.json` | calibraciones sobre las rondas 1, 2, 2, 3 y 3 (criterios descritos en el ADR) |
| `validacion.json` | validación apartada, **una sola corrida** con la regla de la ronda 3 congelada |
| `validacion_2.json` | la misma validación con la regla final (ya no es intacta) |

Resultados con los pesos de envío (`familia` 1, umbral 0,5):

| | precisión light / medium | fuera de dominio con alternativas | vecinos cubiertos |
|---|---|---|---|
| ronda 3, desarrollo | 0,99 / 0,99 | 0 | 39 / 44 |
| ronda 3, validación apartada | **0,87 / 0,85** | 0 | 18 / 18 |
| ronda 4 (final), desarrollo | 1,0 / 1,0 | 0 | 30 / 44 |
| ronda 4 (final), validación | 1,0 / 1,0 | 0 | 12 / 18 |

Los errores de la validación apartada fueron todos de premisas sobre medidas
del núcleo («¿responde en quince días hábiles?» → otro trámite con «N días
hábiles»); los códigos declarados acertaron 24 de 24. La ronda 4 quitó la
familia de las medidas del núcleo.

## Ronda 5: banco ampliado

El banco pasó de 58 a 128 casos por idioma (la validación de la ronda 3 pasó
a desarrollo; se agregaron un catálogo de oficina, una política de despacho
y garantías, premisas sobre medidas y negativos difíciles en dev y test) y
se escribió una validación nueva de 20 por idioma antes de calibrar. Señal
nueva `medida`. Calibración vectorizada sobre 2.187 combinaciones de pesos
(`calibracion_6.json`): `familia` 1 + `terminos` 2, umbral 0,5, tramo válido
0,34–0,66.

| | precisión light / medium | fuera de dominio con alternativas | vecinos cubiertos |
|---|---|---|---|
| ronda 5, desarrollo (`registro_5.json`) | 0,98 / 0,98 | 0 | 129 / 136 |
| ronda 5, validación apartada (`validacion_3.json`, una sola corrida) | **1,0 / 1,0** | 0 | 30 / 32 y 32 / 34 |

Los 4 errores de desarrollo son una misma pregunta en es y pt («¿Puedo
teletrabajar cuatro días por semana?»): sin las palabras de la entidad
queda solo «teletrabajo». Ningún negativo difícil recibió alternativas.

Latencia light con estos pesos (`rend_light_r5.json`, 188 preguntas × 3
rondas): 50,7 / 80,4 ms (media / p95) proactiva contra 49,8 / 81,8 ms
estricta; en las 25 preguntas con alternativas, 59,4 contra 55,5 ms. Banco
de consultas light con estos pesos (`r5_consultas_light.json`): 180 de 180
casos con el mismo estado y regla que la base.

## Bancos existentes

`base_*.json` con el código de `c3b5f01` (worktree, `IPSIS_CODIGO`) y
`despues_*.json` con el código final, light y medium × es/en/pt:

| Banco | casos o turnos | cambios de estado o regla | aciertos / errores |
|---|---|---|---|
| consultas | 360 | 0 | idénticos |
| universal | 180 | 0 | idénticos |
| conversaciones | 348 turnos | 0 (herencia, estado y acierto) | idénticos |

Las latencias de estos archivos no se comparan: las corridas compitieron
por la CPU con otras mediciones.

## Rendimiento (`rendimiento.py`)

En proceso, motor caliente, 118 preguntas en español (banco de alternativas
y banco de consultas) × 3 rondas, postura proactiva y estricta alternadas
pregunta a pregunta (`rend_light.json`, `rend_medium.json`):

| Perfil | proactiva media / p95 | estricta media / p95 | con alternativas (10 preguntas): proactiva / estricta |
|---|---|---|---|
| light | 57,1 / 89,9 ms | 56,1 / 89,0 ms | 83,9 / 70,3 ms |
| medium | 2.793 / 3.018 ms | 2.791 / 3.031 ms | 2.849 / 2.854 ms |

Carga HTTP (`carga_light.json`): `ipsis serve` light, 8 clientes, 240
peticiones por postura, `max_concurrency` 4:

| | 200 | 503 (admisión) | 500 | peticiones/s | p50 / p95 |
|---|---|---|---|---|---|
| proactiva | 238 | 2 | 0 | 9,4 | 825 / 1.043 ms |
| estricta | 240 | 0 | 0 | 9,7 | 773 / 1.049 ms |

La primera corrida de carga dio 16 errores 500 en **ambas** posturas: el
stemmer de snowballstemmer se compartía entre hilos y guarda estado por
palabra (`IndexError` en la selección de oraciones, código anterior a este
cambio). `ipsis/lenguaje/texto.py` usa ahora un stemmer por hilo;
`tests/lenguaje/test_texto_hilos.py` falla 3 de 3 veces con el código base y
pasa con el arreglo. La tabla es la corrida posterior al arreglo.

Medium tarda ~2,8 s por pregunta en esta máquina, también con el código
base; no es efecto de la postura.
