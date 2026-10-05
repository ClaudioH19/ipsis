# Política `cascada_v1`

## 1. Propósito

Decidir el estado de cada respuesta (`ok`, `relacionado` o `sin_respuesta`)
con todas las señales de la cascada, de modo que un `ok` sea siempre texto
literal que responde la pregunta, y abstenerse cuando no lo es.

## 2. Alcance y no-alcance

- **Alcance:** aplicar las reglas en orden y dejar la regla que decidió y
  todas las señales en el diagnóstico.
- **No-alcance:** recuperar, leer o redactar. La política no conoce Qdrant ni
  los modelos.

## 3. Entradas y salidas versionadas

- **Entrada:** `SenalesPolitica` (`s_ret`, `s_oov`, `s_foco`, `s_cov`, `s_rr`,
  `s_qa`; `None` si la etapa no corrió) y los umbrales efectivos.
- **Salida:** `DecisionAbstencion` (resultado, motivo, regla y señal de
  dominio usada). La regla viaja en el diagnóstico (`ipsis ask
  --diagnostics`) y en el registro de consultas.

## 4. Algoritmo y desempates

Reglas en orden; la primera que se cumple decide (`regla_cascada`, una
función pura):

1. **`premisa`:** la pregunta pide una entidad cerrada (fecha, monto,
   artículo) que no está en los candidatos ni en el corpus → `sin_respuesta`.
2. **`fuera_dominio`:** `s_oov ≥ τ_oov_dominio` y dominio < `τ_dominio` →
   `sin_respuesta`. Dominio = `max(s_ret, s_rr)` (ver [reranker](reranker.md)).
3. **`ok_lector` / `ok_lexico`:** `s_foco ≥ τ_foco` y `s_oov < τ_oov_ok` y:
   - con lector: `s_qa ≥ τ_ok`;
   - sin lector (light): `s_ret ≥ τ_ok` y `s_cov ≥ τ_cov`.
4. **`relacionado`:** dominio ≥ `τ_relacionado`. Si falló el foco, el mensaje
   nombra el término ausente («No encontré información específica sobre
   «garantía»…»).
5. **`sin_respuesta`** en cualquier otro caso.

En heavy, la **concordancia** baja un `ok` a `relacionado` si dos tramos
confiables se contradicen.

**La decisión manda sobre el lector.** En `relacionado` no hay
`respuesta_exacta` y los pasajes van bajo un encabezado de «no es una
respuesta directa». En `ok`, la oración que responde va primero.

Después de la política, la verificación comprueba que cada evidencia sea
`corpus[inicio:fin]` y que las entidades de la respuesta estén en la fuente.

## 5. Supuestos

Las señales están en [0, 1] y son comparables entre consultas del mismo
perfil (por eso `s_ret` se normaliza desde el piso del modelo denso).

## 6. Invariantes

- Producción y [calibración](calibracion.md) usan la **misma** `regla_cascada`:
  no pueden divergir.
- Un `ok` siempre trae evidencia literal y verificada.
- Re-decidir las señales guardadas con los umbrales del perfil reproduce cada
  estado (prueba de no regresión sobre 180 casos del banco universal).

## 7. Parámetros y defaults

Umbrales por defecto del perfil (conservadores, sin calibrar):

| Umbral | light | medium / heavy |
|---|---|---|
| `oov_dominio`, `oov_ok` | 0,6 | 0,6 |
| `dominio`, `relacionado` | 0,33 | 0,33 |
| `foco` | 0,5 | 0,5 |
| `ok` | 0,5 (sobre `s_ret`) | 0,8 (sobre `s_qa`) |
| `cov` | 0,6 | 0,6 (no se usa con lector) |

Orden de aplicación: perfil ← `engine.yaml::ajustes_perfil` ←
`calibration.yaml` (solo si su procedencia coincide).

## 8. Complejidad y recursos

Constante; menos de 1 ms.

## 9. Fallos y fallback

Un umbral faltante impide construir el motor, con un mensaje que nombra los
umbrales. Sin calibración vigente se usan los del perfil y `ipsis doctor` lo
advierte.

## 10. Seguridad y privacidad

No usa datos fuera de la consulta.

## 11. Pruebas técnicas

`tests/consulta/test_cascada.py`, el banco sintético v1.1.0 (27 casos, 56%
no respondibles) y el banco universal (90 casos en es, en y pt).

## 12. Limitaciones

Benchmark del banco universal (regresión, **no certifica**; defaults sin
calibrar; CPU local):

| Perfil | Cobertura directa | Falsos ok | p95 | Presupuesto |
|---|---|---|---|---|
| light | 22/45 | 1/45 | 85 ms | 150 ms |
| medium | 32/45 | 3/45 | 815 ms | 1.000 ms |
| heavy | 31/45 | 2/45 | 2.130 ms | 4.000 ms |

Fuera de dominio y premisa falsa se rechazan al 100% en todos los perfiles.
Las trampas «mismo tema, dato ausente» son el riesgo residual; las controla
`τ_ok` calibrado.

## 13. Referencias y procedencia

Diseño propio; reemplaza la política por capas anterior y las guardias
regex por tipo de pregunta (ver [ADR 0004](../decisiones/0004-cascada-lexica-y-retiro-de-guardias-regex.md)).

## 14. Estado

Estable; umbrales pendientes de calibración por proyecto.
