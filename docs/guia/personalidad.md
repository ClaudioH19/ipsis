# Personalidad: tono de las respuestas

El **tono** decide cómo suena el asistente alrededor del texto de tus
documentos. No decide qué responde. El texto del documento va literal y las
citas van debajo, para comprobarlo. Cambiar de tono no cambia el estado de
ninguna respuesta, ni pide reindexar ni recalibrar.

## Configuración: `configuracion/personalidad.yaml`

`rag init` lo crea con comentarios. Se edita a mano o con `rag personalidad …`
(referencia en [uso.md](uso.md)). Cada cambio por terminal se valida completo
antes de escribirse; si no pasa, el archivo queda igual.

```bash
rag personalidad tono listar                 # los 7 tonos, con un ejemplo
rag personalidad tono aplicar formal
rag personalidad tono probar --situacion sin_respuesta
rag personalidad validar                     # sale con 1 si algo impide arrancar el motor
```

`tono.variedad: fija` usa siempre la primera variante de cada situación.

## Avatar

El widget muestra un avatar de
[@bible-strong/avatar-web](https://github.com/smontlouis/bible-strong-avatar-lab).
Se diseña en el Studio ([avatars.bible-strong.app](https://avatars.bible-strong.app))
y se exporta como `.avatar.json`.

```bash
rag personalidad avatar importar ./mi-avatar.avatar.json --nombre mi-avatar
rag personalidad avatar aplicar mi-avatar
rag personalidad avatar eventos              # evento → animación (y respaldos)
rag personalidad avatar asignar pensando mirando-arriba
rag personalidad avatar colores --cuerpo "#f5f1e8" --ojos "#1e293b"
```

- **Al importar** se revisa: hasta 256 KiB, JSON sin claves duplicadas,
  campos obligatorios, la expresión `neutral`, claves con el formato
  `minusculas-y-guiones` y colores `#rrggbb`. La librería valida el resto al
  cargar el avatar en el navegador.
- **Cada evento** del widget tiene una clave sugerida y un respaldo. Si el
  avatar no tiene la clave, se usa el respaldo en cadena, hasta `neutral`.
  Así cualquier avatar funciona, aunque no defina todas las animaciones.
- **Si el avatar falta o no es válido,** el widget muestra el ícono y
  `rag doctor` lo marca como aviso: no bloquea el servicio.

### Folio, el avatar por defecto

Una hoja de papel viva: ladeada, con la esquina que se levanta y dos ojos de
tinta. No tiene boca: expresa con los ojos y el giro. Es lo que hace el
proyecto: lee, mira la cita antes de afirmar y no exagera.
- `contento` es sobrio: primero mira hacia las citas y después se alegra.
- En `dudoso` y `apenado` nunca hay gesto de éxito.
- Colores: papel `#f5f1e8` y tinta `#1e293b`; se cambian con
  `rag personalidad avatar colores`.

Para revisar todas sus animaciones, desde la raíz del repositorio:
`python -m http.server 8765` y abre
`http://127.0.0.1:8765/herramientas/avatar/muestra.html`.

### Cómo reacciona el avatar

| Evento | Cuándo | Tipo |
|---|---|---|
| `inactivo` | panel cerrado | persistente |
| `atento` | panel abierto, sin escribir | persistente |
| `escribiendo` | mientras se teclea; vuelve a `atento` 1,2 s después | persistente |
| `pensando` · `pensando_largo` | esperando la respuesta; «largo» pasados 3 s | persistente |
| `somnoliento` | sin actividad durante `avatar.inactividad_min` minutos | persistente |
| `saludo` · `despedida` | primera apertura · al cerrar | transitorio |
| `enviado` | al enviar la pregunta | transitorio |
| `respuesta_ok` · `respuesta_relacionada` · `sin_respuesta` · `conversacional` | según el estado de la respuesta | transitorio |
| `error` | falla de red o del servicio | transitorio |
| `despertar` | primera actividad tras `somnoliento` | transitorio |

- Un transitorio suena una vez y vuelve al persistente vigente. Uno de mayor
  prioridad interrumpe a otro: el error gana a todo, y las respuestas ganan
  a `enviado`.
- **Mirada:** con `avatar.mirada.activa`, los ojos y la cabeza siguen al
  puntero en reposo (`inactivo` o `atento`). Hay una zona muerta al centro
  (`zona_muerta`, en px) y vuelve al centro tras 1,5 s quieto. Con
  «reducir movimiento» del sistema no sigue el puntero.
- La pestaña oculta pausa la animación.
- En el teléfono el avatar mide 40 px y se oculta con el teclado abierto.

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

## Configurar por HTTP (`/admin`)

Con `RAG_ADMIN_TOKEN` definido, el servicio expone una API para cambiar la
personalidad y el widget sin terminal (ver modos y seguridad en
[instalacion.md](instalacion.md)). Todas las llamadas llevan
`Authorization: Bearer <token>`.

| Método y ruta | Qué hace |
|---|---|
| `GET /admin/personalidad` | Configuración, tonos (con ejemplo), situaciones, eventos, avatares y estado del avatar |
| `PUT /admin/personalidad` | Cambio parcial, p. ej. `{"tono": {"activo": "formal"}}`. Se valida completo; si falla responde 422 con los errores y no escribe |
| `POST /admin/personalidad/vista-previa` | `{"tono": "formal", "situacion": "sin_respuesta"}` → las variantes con las variables del proyecto |
| `GET /admin/avatares` · `POST /admin/avatares` | Lista, o importa `{"nombre": "mi-avatar", "definicion": {…}}` |
| `GET /admin/estilos` · `PUT /admin/estilos` | Tema y ubicación del widget (`estilos.yaml`), con la misma validación que la terminal |
| `GET /admin/estilos/presets` · `POST /admin/estilos/preset` | Lista los presets visuales, o aplica uno: `{"nombre": "editorial"}` (`clasico`, `minimal`, `editorial`, `contraste`) |

Los cambios, por HTTP o por terminal, se ven sin reiniciar:
- el servicio revisa la fecha de `personalidad.yaml`, `idioma.yaml` y
  `asistente.yaml` en cada consulta, y el motor toma las plantillas nuevas;
- `/config` entrega al widget la microcopia y el avatar vigentes.

## Panel gráfico (`/admin/panel`)

Es la misma API, con formularios. Abre `https://tu-dominio/admin/panel`
(o `http://127.0.0.1:8000/admin/panel` en tu máquina) y pega el token.

| Pestaña | Qué hace |
|---|---|
| **Tono** | Elige el tono y la variedad. Por situación, muestra las 5 variantes con las variables del proyecto y deja escribir textos propios. Si un texto no pasa el linter, muestra los errores y no guarda nada |
| **Avatar** | Importa un `.avatar.json` (se valida antes de guardar), elige el avatar, sus colores, ubicación y tamaño, y asigna cada evento a una animación. El botón ▶ dispara el evento en la vista previa |
| **Widget** | Aplica un preset y cambia el color de acento, la posición, el tamaño, el lanzador y cómo se muestran las citas |

- **Vista previa:** el widget real, servido por tu servicio. Se recarga sola
  tras cada cambio guardado.
- **Token:** se guarda solo en la pestaña del navegador (`sessionStorage`).
  Se borra al cerrarla o con «Salir».
- **Seguridad:**
  - el panel no carga nada de otros dominios;
  - su política de contenido (CSP) prohíbe scripts en línea;
  - sigue las mismas reglas de transporte que la API: en producción, HTTPS
    salvo desde la propia máquina;
  - sin `RAG_ADMIN_TOKEN`, el panel no existe (404).
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

La lista de cada idioma está en `_reglas.yaml` (`regionalismos`) y una
prueba la hace cumplir.

Tus textos propios (`tono.plantillas`) se revisan con la misma lista, pero
como **aviso**, no como error: se guardan igual, porque un sitio local
puede querer hablar como su público. El aviso aparece en
`rag personalidad validar`, en `rag doctor` y en la pestaña Tono del panel.
Si el idioma del proyecto no tiene paquete propio (por ejemplo, `fr`), no se
revisa.

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
