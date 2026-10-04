# Personalidad: tono de las respuestas

El **tono** decide cómo suena el asistente alrededor del texto de tus
documentos. No decide qué responde. El texto del documento va literal y las
citas van debajo, para comprobarlo. Cambiar de tono no cambia el estado de
ninguna respuesta, ni pide reindexar ni recalibrar.

> La configuración por terminal (`rag personalidad …`) llega en P12.4. La API
> y el panel `/admin`, en P12.6 y P12.7. El avatar, en P12.10.

## Tonos incluidos

En español, inglés y portugués:

| Tono | Carácter | Ejemplo para `sin_respuesta` (es) |
|---|---|---|
| `cordial` (por defecto) | amable y claro | «No encontré esa información en los documentos disponibles.» |
| `formal` | trato de usted, sin exclamaciones | «Lamentablemente, esa información no figura en los documentos disponibles.» |
| `serio` | sobrio, frases cortas | «Esa información no está en los documentos.» |
| `animoso` | entusiasta, sin exagerar hechos | «¡Busqué a fondo, pero eso no aparece en los documentos! Prueba con otra pregunta.» |
| `cercano` | tuteo, coloquial suave | «Uy, eso no lo encuentro en tus documentos.» |
| `empatico` | reconoce lo que la persona necesita | «Entiendo que lo necesitas; no aparece en los documentos disponibles.» |
| `directo` | seco e imperativo, nunca agresivo | «No está en los documentos. Pregunta otra cosa.» |

Cada tono trae 18 situaciones con 5 variantes cada una: 90 por tono e
idioma, 1.890 en total.

## Situaciones

| Situación | Cuándo se usa | Variables |
|---|---|---|
| `saludo`, `agradecimiento`, `despedida`, `capacidad` | respuestas conversacionales | `{nombre_asistente}`, `{descripcion_dominio}` (agradecimiento: solo la segunda; despedida: ninguna) |
| `apertura` | antes del texto del documento | — |
| `complemento`, `condicion`, `excepcion` | entre fragmentos del documento | — |
| `relacionado_intro` | respuesta relacionada, no directa | — |
| `foco_ausente` | relacionada, falta el término principal | `{termino}` (obligatoria) |
| `sin_respuesta` | no está en los documentos | — |
| `premisa_no_encontrada` | se preguntó por algo que no existe | `{entidad}` (obligatoria) |
| `bienvenida`, `esperando`, `invitacion_citas`, `error_red`, `error_limite`, `error_servicio` | textos del widget | `bienvenida`: `{nombre_asistente}` |

## Variedad y trazabilidad

- En una conversación, la variante se elige por sesión, turno y situación, y
  no se repite en turnos seguidos.
- La misma sesión y el mismo turno dan siempre el mismo texto.
- Cada variante usada queda como `plantilla_id` (por ejemplo,
  `formal.apertura.3`) en `rag preguntar --diagnostico` y en el registro de
  consultas. `rag auditar` cuenta las consultas por tono.

## Textos propios del proyecto

En `configuracion/personalidad.yaml` puedes reemplazar las situaciones que
quieras:

```yaml
tono:
  plantillas:
    sin_respuesta:
    - Eso no está en el manual del equipo.
    - El manual no cubre esa consulta.
```

## Reglas de toda plantilla

Las comprueba un linter; las mismas reglas aplican a tus sobrescrituras:

- Forma:
  - una línea, de hasta 200 caracteres;
  - si abre «¡» o «¿», los cierra.
- Contenido prohibido:
  - dígitos, porque afirmarían un dato que no viene del documento;
  - URLs, HTML, Markdown y emojis;
  - palabras enteras en mayúsculas.
- Variables: solo las de su situación, sin formato.
- Conectores: los que introducen texto del documento terminan en «:».
- Variedad: las 5 variantes son distintas, y ninguna se repite en otra
  situación del mismo tono.
- Ninguna expresión de la lista prohibida del idioma
  (`rag/recursos/tonos/<idioma>/_reglas.yaml`): insultos, culpar al
  usuario, condescendencia.

## Revisión humana de un tono nuevo

El linter no juzga el sentido. Antes de publicar un tono, una persona
revisa:

1. **Tono reconocible:** las 90 variantes suenan al mismo carácter.
2. **Honestidad:** `relacionado_intro` y `foco_ausente` dicen que no es una
   respuesta directa; `sin_respuesta` y `premisa_no_encontrada` no sugieren
   que la información exista en otra parte.
3. **Sin contenido:** ninguna plantilla se lee como algo que dice el
   documento.
4. **El conector encaja:** `apertura`, `complemento`, `condicion` y
   `excepcion` suenan bien seguidos de una cita que empieza en mayúscula.
5. **Naturalidad en el idioma:** sin calcos ni regionalismos que confundan.
6. **`directo` sin agresión:** seco, nunca hiriente.
