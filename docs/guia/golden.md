# Golden set del cliente

El golden set es el banco de preguntas reales del cliente con el que se mide
y calibra el asistente. Vive en la carpeta `golden/` de cada proyecto y nunca
se mezcla con el banco sintético de las pruebas (`tests/datos/banco/`).

El banco versionado queda en `golden/banco/` (`manifiesto.json` más los casos
en JSONL) con el esquema de `rag.evaluacion.banco`. Los comandos
`rag golden plantilla` e `rag golden importar` (plan V3, fase P9) generan y
cargan ese banco a partir de un CSV simple. Con 30 a 60 preguntas revisadas
por una persona conocedora del corpus sirve para ajustar y comparar perfiles
(para certificar un riesgo hace falta más: ver «Calibrar»). Debe cubrir las seis
categorías (`exacta`, `parafrasis`, `sin_respuesta`, `premisa_falsa`,
`ambigua`, `conversacional`) y separar casos `dev` y `test` antes de calibrar.

Reglas de curación:

- `dev` puede usarse para ajustar umbrales; `test` permanece cerrado hasta la
  comparación final.
- Toda pregunta respondible incluye respuesta literal y evidencia con offsets.
- Las preguntas usadas para descubrir o corregir un defecto no deben ser la
  única medición de ese comportamiento.
- No se copian documentos institucionales sensibles al repositorio; el
  manifiesto identifica y hashea el corpus evaluado localmente.

## Calibrar

```text
rag calibrar [--alfa 0.05] [--aplicar]
```

Requiere el índice (`rag indexar`) y el golden importado
(`rag golden importar`). Corre el perfil sobre el golden y **elige umbrales
escalares** (`ok`, `oov_ok`, `foco`) usando solo `dev`. Busca la combinación
que más responde directo cuya cota superior de riesgo (Clopper-Pearson al 95%)
es ≤ `--alfa`; `test` solo verifica. No entrena ni modifica modelos.

| Resultado | Qué significa | Salida |
|---|---|---|
| `CALIBRADO` | Hay muestra y una combinación cumple α | 0 |
| `MUESTRA_INSUFICIENTE` | Todavía no se puede certificar α: no hay suficientes respuestas directas sin error en `dev` (con 0 errores, 59 para α = 0,05). **No** significa que el perfil sea inseguro | 0 |
| `SIN_UMBRAL_SEGURO` | Hay muestra, pero ninguna combinación cumple α | 1 |

- Sin `--aplicar`, solo informa y no escribe nada.
- Con `--aplicar`, escribe `configuracion/calibracion.yaml` en cualquier
  estado, para auditoría. El motor **solo** usa sus umbrales si el estado es
  `CALIBRADO` y su procedencia coincide con el proyecto: perfil, modelos y
  `hash_corpus` del índice. Si cambia el corpus o el perfil, la calibración se
  ignora y vuelven los umbrales del perfil.
- Si el corpus cambió desde que se importó el golden, primero
  `rag golden validar` y, si corresponde, vuelve a importar.
- El banco universal de las pruebas (`tests/datos/banco_universal/`) es de
  regresión y no se puede usar para calibrar.
