# Guía de paráfrasis informales (etapa 6 del conjunto v2)

La siguen los redactores (dos subagentes Claude Haiku en paralelo) y se versiona junto con el código, para que la
etapa sea replicable. El redactor recibe **solo la pregunta**: no ve pasajes ni respuestas, así no puede copiar la
evidencia ni filtrar la respuesta.

## Qué escribir

Para cada pregunta, **una** reescritura como la escribiría una persona en un chat o en un buscador, con la misma
necesidad de información.

1. **Misma intención.** Pide exactamente el mismo dato. No agregues ni quites condiciones (fechas, lugares,
   nombres, cifras).
2. **Brecha léxica.** Cambia al menos una palabra de contenido por un sinónimo, una perífrasis o una expresión
   coloquial («¿En qué año se fundó…?» → «desde cuando existe…»; «fallecer» → «morir»; «cantidad» → «cuantos»).
3. **Conserva el ancla.** Los nombres propios, títulos y cifras se mantienen; pueden ir en minúsculas, sin tildes
   o abreviados («Segunda Guerra Mundial» → «2da guerra mundial»).
4. **Registro informal.** Varía, sin aplicar todo a la vez:
   - minúsculas;
   - sin «¿» y a veces sin «?»;
   - sin tildes;
   - abreviaturas de chat («q», «xq», «pa», «cuanto»);
   - estilo de buscador sin verbo («peli lego estreno»);
   - muletillas («oye», «alguien sabe»);
   - una errata ocasional.
5. **Castellano neutro latinoamericano**, sin modismos de un solo país.
6. **Longitud:** de 2 a 30 palabras.
7. **No respondas** la pregunta ni agregues datos que no estén en ella.

## Ejemplos

| Original | Informal |
|---|---|
| ¿Cuándo se estrenó la película de Lego? | cuando salio la peli de lego |
| ¿Qué país formó la primera Infantería de Marina? | q pais tuvo los primeros marines |
| ¿Cuál es la población de Buenos Aires? | cuanta gente vive en buenos aires? |
| ¿Quién escribió Cien años de soledad? | autor de cien años de soledad |

## Formato de salida

Un JSON por línea, en el mismo orden del pedido:

```json
{"id": "<id del pedido, sin cambios>", "informal": "<la reescritura>", "redactor": "<tu nombre de redactor>"}
```

`conjunto.py importar-parafrasis` valida cada línea:

- que sea distinta del original;
- que tenga de 2 a 30 palabras;
- que no agregue la respuesta;
- que conserve al menos una palabra de contenido;
- que no esté en inglés.

Las que no pasan se descartan y quedan contadas en el resumen.
