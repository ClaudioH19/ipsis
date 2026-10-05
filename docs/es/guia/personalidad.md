# Personalidad: tono de las respuestas y avatar

El **tono** decide cómo suena el asistente alrededor del texto de tus
documentos. No decide qué responde. El texto del documento va literal y las
citas van debajo, para comprobarlo. Cambiar de tono no cambia el estado de
ninguna respuesta, ni pide reindexar ni recalibrar.

## Configuración: `config/personality.yaml`

`ipsis init` lo crea con comentarios. Se edita a mano o con
`ipsis personality …` (referencia en [uso.md](uso.md)). Cada cambio por
terminal se valida completo antes de escribirse; si no pasa, el archivo queda
igual.

```bash
ipsis personality tone list                     # los 7 tonos, con un ejemplo
ipsis personality tone apply formal
ipsis personality tone try --situation no_answer
ipsis personality validate                      # sale con 1 si algo impide arrancar el motor
```

`tone.variety: fixed` usa siempre la primera variante de cada situación
(`rotating` es el valor por defecto).

```yaml
config_version: 1
tone:
  active: cordial          # cordial | formal | serious | upbeat | friendly | empathetic | direct
  variety: rotating        # rotating | fixed
  templates: {}            # textos propios por situación
avatar:
  enabled: true
  definition: folio
  placement: header        # header | top-corner | bottom-corner
  size: 56
  in_launcher: true
  gaze: {enabled: true, eye_range: 6, head_range: 8, dead_zone: 24}
  idle_minutes: 2
  colors: {}               # {body: "#rrggbb", eyes: "#rrggbb"}
  events: {}               # evento → animación o expresión
```

Los nombres de claves, tonos, situaciones y eventos están en inglés en todos
los idiomas; el texto de las plantillas sí está en el idioma del proyecto.

## Avatar

El widget muestra un avatar de
[@bible-strong/avatar-web](https://github.com/smontlouis/bible-strong-avatar-lab).
Se diseña en el Studio ([avatars.bible-strong.app](https://avatars.bible-strong.app))
y se exporta como `.avatar.json`.

```bash
ipsis personality avatar import ./mi-avatar.avatar.json --name mi-avatar
ipsis personality avatar apply mi-avatar
ipsis personality avatar events                  # evento → animación (y respaldos)
ipsis personality avatar assign thinking looking-up
ipsis personality avatar colors --body "#f5f1e8" --eyes "#1e293b"
```

- **Al importar** se revisa: hasta 256 KiB, JSON sin claves duplicadas,
  campos obligatorios, la expresión `neutral`, claves con el formato
  `minusculas-y-guiones` y colores `#rrggbb`. La librería valida el resto al
  cargar el avatar en el navegador.
- **Cada evento** del widget tiene una clave sugerida y un respaldo. Si el
  avatar no tiene la clave, se usa el respaldo en cadena, hasta `neutral`.
  Así cualquier avatar funciona, aunque no defina todas las animaciones.
- **Si el avatar falta o no es válido,** el widget muestra el ícono y
  `ipsis doctor` lo marca como aviso: no bloquea el servicio.

### Folio, el avatar por defecto

Una hoja de papel viva: ladeada, con la esquina que se levanta y dos ojos de
tinta. No tiene boca: expresa con los ojos y el giro. Es lo que hace el
proyecto: lee, mira la cita antes de afirmar y no exagera.

- `happy` es sobrio: primero mira hacia las citas y después se alegra.
- En `unsure` y `sorry` nunca hay gesto de éxito.
- Colores: papel `#f5f1e8` y tinta `#1e293b`; se cambian con
  `ipsis personality avatar colors`.

Para revisar todas sus animaciones, desde la raíz del repositorio:
`python -m http.server 8765` y abre
`http://127.0.0.1:8765/herramientas/avatar/muestra.html`.

### Cómo reacciona el avatar

| Evento | Cuándo | Tipo |
|---|---|---|
| `idle` | panel cerrado | persistente |
| `attentive` | panel abierto, sin escribir | persistente |
| `typing` | mientras se teclea; vuelve a `attentive` 1,2 s después | persistente |
| `thinking` · `thinking_long` | esperando la respuesta; «long» pasados 3 s | persistente |
| `sleepy` | sin actividad durante `avatar.idle_minutes` minutos | persistente |
| `greeting` · `farewell` | primera apertura · al cerrar | transitorio |
| `sent` | al enviar la pregunta | transitorio |
| `answer_ok` · `answer_related` · `no_answer` · `conversational` | según el estado de la respuesta | transitorio |
| `error` | falla de red o del servicio | transitorio |
| `wake_up` | primera actividad tras `sleepy` | transitorio |

- Un transitorio suena una vez y vuelve al persistente vigente. Uno de mayor
  prioridad interrumpe a otro: el error gana a todo, y las respuestas ganan
  a `sent`.
- **Mirada:** con `avatar.gaze.enabled`, los ojos y la cabeza siguen al
  puntero en reposo (`idle` o `attentive`). Hay una zona muerta al centro
  (`dead_zone`, en px) y vuelve al centro tras 1,5 s quieto. Con «reducir
  movimiento» del sistema no sigue el puntero.
- La pestaña oculta pausa la animación.
- En el teléfono el avatar mide 40 px y se oculta con el teclado abierto.

## Tonos incluidos

En español, inglés y portugués:

| Tono | Carácter | Ejemplo para `no_answer` (es) |
|---|---|---|
| `cordial` (por defecto) | amable y claro | «No encontré esa información en los documentos disponibles.» |
| `formal` | trato de usted, sin exclamaciones | «Lamentablemente, esa información no figura en los documentos disponibles.» |
| `serious` | sobrio, frases cortas | «Esa información no está en los documentos.» |
| `upbeat` | entusiasta, sin exagerar hechos | «¡Busqué a fondo, pero eso no aparece en los documentos! Prueba con otra pregunta.» |
| `friendly` | tuteo, coloquial suave | «Uy, eso no lo encuentro en tus documentos.» |
| `empathetic` | reconoce lo que la persona necesita | «Entiendo que lo necesitas; no aparece en los documentos disponibles.» |
| `direct` | seco e imperativo, nunca agresivo | «No está en los documentos. Pregunta otra cosa.» |

Cada tono trae 18 situaciones con 5 variantes cada una: 90 por tono e
idioma, 1.890 en total.

## Situaciones

| Situación | Cuándo se usa | Variables |
|---|---|---|
| `greeting`, `thanks`, `farewell`, `capability` | respuestas conversacionales | `{assistant_name}`, `{domain_description}` (thanks: solo la segunda; farewell: ninguna) |
| `opening` | antes del texto del documento | — |
| `addition`, `condition`, `exception` | entre fragmentos del documento | — |
| `related_intro` | respuesta relacionada, no directa | — |
| `missing_focus` | relacionada, falta el término principal | `{term}` (obligatoria) |
| `no_answer` | no está en los documentos | — |
| `premise_not_found` | se preguntó por algo que no existe | `{entity}` (obligatoria) |
| `welcome`, `waiting`, `citations_hint`, `network_error`, `rate_limit_error`, `service_error` | textos del widget | `welcome`: `{assistant_name}` |

## Variedad y trazabilidad

- En una conversación, la variante se elige por sesión, turno y situación, y
  no se repite en turnos seguidos.
- La misma sesión y el mismo turno dan siempre el mismo texto.
- Cada variante usada queda como id de plantilla (por ejemplo,
  `formal.opening.3`) en `ipsis ask --diagnostics` y en el registro de
  consultas. `ipsis audit` cuenta las consultas por tono.

## Textos propios del proyecto

En `config/personality.yaml` puedes reemplazar las situaciones que
quieras:

```yaml
tone:
  templates:
    no_answer:
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
  (`ipsis/recursos/tonos/<idioma>/_reglas.yaml`): insultos, culpar al
  usuario, condescendencia.

## Configurar por HTTP (`/admin`)

Con `IPSIS_ADMIN_TOKEN` definido, el servicio expone una API para cambiar la
personalidad y el widget sin terminal (ver modos y seguridad en
[despliegue.md](despliegue.md)). Todas las llamadas llevan
`Authorization: Bearer <token>`. Los cuerpos usan los mismos nombres que los
archivos YAML.

| Método y ruta | Qué hace |
|---|---|
| `GET /admin/personality` | Configuración, tonos (con ejemplo), situaciones, eventos, avatares y estado del avatar |
| `PUT /admin/personality` | Cambio parcial, p. ej. `{"tone": {"active": "formal"}}`. Se valida completo; si falla responde 422 con los `errors` y no escribe |
| `POST /admin/personality/preview` | `{"tone": "formal", "situation": "no_answer"}` → las variantes con las variables del proyecto |
| `GET /admin/avatars` · `POST /admin/avatars` | Lista, o importa `{"name": "mi-avatar", "definition": {…}}` |
| `GET /admin/styles` · `PUT /admin/styles` | Tema y ubicación del widget (`styles.yaml`), con la misma validación que la terminal |
| `GET /admin/styles/flat` · `POST /admin/styles/set` | Cada valor `seccion.clave`, o `{"assignments": ["colors.accent=#0ea5e9"]}` |
| `GET /admin/styles/presets` · `POST /admin/styles/preset` | Lista los presets visuales, o aplica uno: `{"name": "editorial"}` (`classic`, `minimal`, `editorial`, `contrast`) |

Los cambios, por HTTP o por terminal, se ven sin reiniciar:

- el servicio revisa la fecha de `personality.yaml`, `language.yaml` y
  `assistant.yaml` en cada consulta, y el motor toma las plantillas nuevas;
- `/config` entrega al widget la microcopia y el avatar vigentes.

## Panel gráfico (`/admin/panel`)

![Pestaña Avatar del panel: Folio, colores, eventos y vista previa](../../assets/panel-avatar.png)

Es la misma API, con formularios. Abre `https://tu-dominio/admin/panel`
(o `http://127.0.0.1:8000/admin/panel` en tu máquina) y pega el token. El
panel habla inglés por defecto y español con `IPSIS_LANG=es` en el servicio.

| Pestaña | Qué hace |
|---|---|
| **Tono** | Elige el tono y la variedad. Por situación, muestra las 5 variantes con las variables del proyecto y deja escribir textos propios. Si un texto no pasa el linter, muestra los errores y no guarda nada |
| **Avatar** | Importa un `.avatar.json` (se valida antes de guardar), elige el avatar, sus colores, ubicación y tamaño, y asigna cada evento a una animación. El botón ▶ dispara el evento en la vista previa |
| **Widget** | Aplica un preset y cambia el color de acento, la posición, el tamaño, el lanzador y cómo se muestran las citas. «Estilo completo» edita cada valor de `styles.yaml`: colores claros y oscuros, tipografía, formas, sombras y animaciones |

- **Vista previa:** el widget real, servido por tu servicio. Se recarga sola
  tras cada cambio guardado.
- **Token:** se guarda solo en la pestaña del navegador (`sessionStorage`).
  Se borra al cerrarla o con «Salir».
- **Seguridad:**
  - el panel no carga nada de otros dominios;
  - su política de contenido (CSP) prohíbe scripts en línea;
  - sigue las mismas reglas de transporte que la API: en producción, HTTPS
    salvo desde la propia máquina;
  - sin `IPSIS_ADMIN_TOKEN`, el panel no existe (404).
- Sus archivos no tienen datos: todo lo que muestra llega por la API con el
  token.

## Neutralidad de los tonos incluidos

Los tonos que trae el paquete son neutros:

- **Sin regionalismos:** nada de «pega», «chao», «e aí», «no worries».
- **Sin formas con género para la persona:** «Te doy la bienvenida» en vez
  de «Bienvenido»; nada de «o senhor».
- **Sin saludos que dependan de la hora:** nada de «Buenos días».
- **En portugués,** formas válidas en Brasil y en Portugal: sustantivos en
  vez de gerundios («Busca em andamento»).

La lista de cada idioma está en `_reglas.yaml` (`regionalisms`) y una
prueba la hace cumplir.

Tus textos propios (`tone.templates`) se revisan con la misma lista, pero
como **aviso**, no como error: se guardan igual, porque un sitio local
puede querer hablar como su público. El aviso aparece en
`ipsis personality validate`, en `ipsis doctor` y en la pestaña Tono del
panel. Si el idioma del proyecto no tiene paquete propio (por ejemplo, `fr`),
no se revisa.

## Revisión humana de un tono nuevo

El linter no juzga el sentido. Antes de publicar un tono, una persona
revisa:

1. **Tono reconocible:** las 90 variantes suenan al mismo carácter.
2. **Honestidad:** `related_intro` y `missing_focus` dicen que no es una
   respuesta directa; `no_answer` y `premise_not_found` no sugieren que la
   información exista en otra parte.
3. **Sin contenido:** ninguna plantilla se lee como algo que dice el
   documento.
4. **El conector encaja:** `opening`, `addition`, `condition` y `exception`
   suenan bien seguidos de una cita que empieza en mayúscula.
5. **Naturalidad en el idioma:** sin calcos ni regionalismos que confundan.
6. **`direct` sin agresión:** seco, nunca hiriente.
