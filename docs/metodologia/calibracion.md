# Calibración con control de riesgo

## 1. Propósito

Elegir los umbrales de la [política](politica.md) para un proyecto concreto
de modo que, con 95% de confianza, la tasa de respuestas `ok` incorrectas sea
≤ α (por defecto 5%), maximizando la cobertura directa.

## 2. Alcance y no-alcance

- **Alcance:** seleccionar umbrales escalares entre valores observados de
  señales ya calculadas sobre el golden del cliente.
- **No-alcance:** entrenar, aprender pesos, cambiar modelos o tocar índices.
  El producto no hace fine-tuning de ningún tipo.

## 3. Entradas y salidas versionadas

- **Entrada:** banco `golden/banco/` (casos con `split` dev/test y evidencia
  literal) y las observaciones de una evaluación del perfil activo, con sus
  señales.
- **Salida:** `configuracion/calibracion.yaml` (versión 1) con estado,
  `alfa`, `confianza`, umbrales, resultado por split y **procedencia**
  (perfil, modelos, `hash_corpus` del índice, banco y su hash).

## 4. Algoritmo y desempates

1. Evalúa el perfil sobre el golden y guarda las señales de cada caso.
2. Rechaza el banco universal (`uso: regresion`): sirve para regresión, no
   para calibrar a un cliente.
3. **Solo `dev` elige.** Candidatos: los valores observados en `dev` más el
   del perfil (`τ_ok` sobre `s_qa`, o `s_ret` sin lector; `τ_foco` sobre
   `s_foco`; `τ_oov_ok` sobre `s_oov` + ε).
4. Búsqueda conjunta de (`τ_foco`, `τ_oov_ok`) × `τ_ok`: para cada par ordena
   los casos y barre `τ_ok` acumulando `n` (aceptadas) y `x` (falsos ok más
   directas sin respuesta literal). Una combinación es segura si la cota
   superior de Clopper-Pearson de `x/n` es ≤ α.
5. De las seguras gana la de mayor cobertura directa; en empate, la más
   cercana al perfil y luego la más estricta.
6. Re-decide sin modelos con `regla_cascada`, la misma función de producción.
7. `τ_oov_dominio`, `τ_dominio`, `τ_relacionado` y `τ_cov` quedan en el valor
   del perfil: no cambian el riesgo de una respuesta aceptada.
8. Verifica la combinación en `dev` con la política completa y la reporta en
   `test` aparte (`cumple`, `excede` o `muestra_insuficiente`). **`test`
   nunca elige.**

**Tamaño de muestra.** Con 0 errores, la cota al 95% es `1 − 0,05^(1/n)`:

| n aceptadas | 20 | 30 | 40 | 58 | **59** | 100 |
|---|---|---|---|---|---|---|
| cota | 13,9% | 9,5% | 7,2% | 5,03% | **4,95%** | 2,95% |

Certificar α = 5% exige **al menos 59 respuestas aceptadas sin error** en el
split donde se mide (más si hay errores). Tres resultados posibles:

| Estado | Significa | Salida de `ipsis calibrar` |
|---|---|---|
| `CALIBRADO` | Hay muestra y una combinación cumple α | 0; con `--aplicar` el motor la usa |
| `MUESTRA_INSUFICIENTE` | Los resultados pueden ser buenos, pero n no alcanza | 0; mantiene los umbrales del perfil e informa cuántas aceptadas faltan |
| `SIN_UMBRAL_SEGURO` | Hay muestra y ninguna combinación cumple α | 1; mantiene los del perfil |

## 5. Supuestos

El golden representa las preguntas reales: ≥ 30% sin respuesta o con premisa
falsa, y pares mínimos «mismo tema, dato ausente» curados por una persona.

## 6. Invariantes

- El motor aplica la calibración solo si está en estado `calibrado` **y** su
  procedencia coincide con el perfil, los modelos y el `hash_corpus` del índice
  abierto. Si algo cambió, la ignora y `ipsis doctor` lo dice.
- `calibracion.yaml` se escribe en cualquier estado, para auditoría.

## 7. Parámetros y defaults

`ipsis calibrar [--alfa 0.05] [--aplicar]`; confianza 0,95. Umbrales
calibrables: `ok`, `oov_ok` y `foco`.

## 8. Complejidad y recursos

Una evaluación del golden con modelos más una búsqueda en memoria
(polinómica en los valores observados; segundos).

## 9. Fallos y fallback

Sin índice: «ipsis indexar». Corpus cambiado desde que se importó el golden:
«ipsis golden validar». En los estados que no certifican, el perfil sigue con
sus umbrales: el producto funciona, sin afirmar el 5%.

## 10. Seguridad y privacidad

El golden y el reporte quedan en el proyecto; nada sale de la máquina.

## 11. Pruebas técnicas

`tests/evaluacion/test_calibracion.py` (los tres estados, empates,
procedencia) y las pruebas de CLI de `ipsis calibrar` con un motor falso.

## 12. Limitaciones

- Con bancos chicos el split 50/50 estratificado puede dejar categorías
  internas desbalanceadas.
- La garantía es estadística sobre la distribución del golden: preguntas muy
  distintas a las del golden no quedan cubiertas.

## 13. Referencias y procedencia

- Clopper y Pearson, *The use of confidence or fiducial limits illustrated in
  the case of the binomial* (1934).
- Angelopoulos et al., *Learn then Test: Calibrating Predictive Algorithms to
  Achieve Risk Control* (2021).

## 14. Estado

Estable. Ningún proyecto queda calibrado por defecto.
