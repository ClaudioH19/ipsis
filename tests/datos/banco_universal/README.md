# Banco universal de regresión

Prueba el **software**, no la instalación de un cliente. Es el mismo para todos,
corre sin red y nunca entrena ni calibra.

| | Banco universal (aquí) | Golden del cliente (`golden/`) |
|---|---|---|
| Prueba | El software: capacidades generales | La instalación de un cliente sobre su corpus |
| Corpus | Microdocumentos sintéticos de este repositorio | Los documentos del cliente |
| Uso | Pruebas, CI, regresión, comparación entre versiones | Evaluación y calibración de umbrales |
| Manifiesto | `uso: regresion` (`exigir_calibrable` lo rechaza) | `uso: evaluacion` |

El sistema no se ajusta para pasar este banco: si falla, se registra y se
analiza en P10.

## Contenido

Hay tres bancos: `es/`, `en/` y `pt/`. Son **multilingües, no cross-lingual**:
cada idioma tiene sus documentos y sus preguntas en ese idioma.

Cada idioma tiene 5 microdocumentos (garantía, reembolsos, riego, protocolo de
laboratorio y horarios de biblioteca) y 30 casos:

| Categoría (id) | Casos | Qué mide |
|---|---|---|
| `exacta` | 10 | Respondible con el vocabulario del documento |
| `parafrasis` | 5 | Respondible con otras palabras («¿Qué hago si se descompone?») |
| `trampa` | 10 | Mismo tema y misma entidad que su `par`, pero el dato no está (`subtipo: trampa_mismo_tema`) |
| `fuera` | 3 | Fuera del dominio (`estado_esperado: fuera_dominio`) |
| `premisa` | 1 | Supone una cifra que no existe |
| `ambigua` | 1 | No se puede responder sin aclarar |

Las respondibles cubren 10 capacidades (`notas: capacidad: …`): cantidad,
duración, fecha, persona, ubicación, condición, causa, procedimiento, lista y
sí/no.

Ejemplo de par mínimo:

- `es-exacta-004`: «¿En cuántos días hábiles se paga el reembolso?» → «10 días hábiles».
- `es-trampa-004`: «¿Quién aprueba la solicitud de reembolso?» → sin respuesta.

## Archivos

| Archivo | Se edita | Qué es |
|---|---|---|
| `<idioma>/corpus/*.md`, `<idioma>/casos.yaml` | a mano | Fuentes |
| `<idioma>/banco.jsonl`, `<idioma>/manifiesto.json` | `python tests/datos/banco_universal/construir.py` | Banco en el formato interno; una prueba verifica que coincide con las fuentes |
| `linea_base.json` | `python tests/datos/banco_universal/linea_base.py light,medium` | Resultado de referencia por perfil e idioma |

La prueba lenta (`tests/evaluacion/test_banco_universal.py`, marcas `slow` y
`modelos`) falla si aparece un falso `ok` que no estaba en la línea base, o si
una respuesta `ok` no muestra la respuesta literal. Si una mejora elimina
falsos `ok`, vuelve a registrar la línea base.
