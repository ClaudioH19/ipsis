# herramientas/avatar

Empaqueta el motor del avatar ([@bible-strong/avatar-web](https://github.com/smontlouis/bible-strong-avatar-lab),
AGPL-3.0) para el widget. Solo desarrollo: no entra en el wheel; se versiona
el resultado.

```bash
cd herramientas/avatar
npm ci                  # versiones exactas de package-lock.json
npm run construir       # escribe ipsis/servicio/estaticos/avatar.js, .LICENSE.txt y .sha256
npm run verificar       # falla si el resultado difiere de lo versionado
node validar.mjs        # valida los avatares incluidos con la librería real
```

## Visualizador de Folio

Desde la raíz del repositorio, con uv:

```bash
uv run --locked python herramientas/avatar/visualizador.py
```

Abre <http://127.0.0.1:8765/>. `visualizador.html` conserva la vista oscura
con el logo de referencia, las situaciones del widget, el catálogo completo
de animaciones y expresiones y los controles de pausa y movimiento.
El catálogo se lee del JSON de Folio y las situaciones usan las asignaciones
de `config/personality.yaml` en el directorio actual, o los valores por defecto
si falta ese archivo. Las selecciones sirven para probar los gestos.

Folio flota por defecto al estar en reposo o atento, conservando sus ojos y
el movimiento de fondo mientras sigue el puntero. La flotación también se
mantiene al desactivar **Vida propia**; **Pausar** congela ambos comportamientos.
El mouse mueve los ojos y la cabeza; al pasar sobre Folio hace un gesto amable.
El campo **Escribe para probar sus reacciones** muestra cómo escucha mientras
tecleas y vuelve a leer el borrador tras 1,2 segundos de pausa. Preguntas,
exclamaciones, saludos, emociones, frases y emoticonos cambian su expresión. Estas pruebas no
envían una consulta al servicio. La mirada y los gestos se suspenden al pausar
y con movimiento reducido.
**Vida propia** está activada al abrir la vista: mientras espera, Folio hace
gestos suaves de curiosidad, lectura, miradas y guiños con pausas aleatorias
de 1,8 a 3,6 segundos entre reacciones. También usa las animaciones de saludo,
asentimiento, escucha, balanceo, saltos y flotación. Con menos frecuencia baila,
gira, da una vuelta sobre su eje o sale y vuelve como avioncito. Son **16
reacciones**: los bucles duran solo un ciclo y los gestos más llamativos se
separan por al menos 45 segundos. No repite el mismo gesto seguido.
Elegir un gesto del catálogo permite examinarlo sin reacciones superpuestas;
elige **Esperando** en las situaciones o reactiva **Vida propia** para volver
al comportamiento autónomo. **Pausar** congela también las reacciones.

El botón **Detener visualizador** cierra el servidor y conserva los archivos.
También puedes usar Ctrl+C. Si el puerto está ocupado, usa
`uv run --locked python herramientas/avatar/visualizador.py --puerto 8766`.

`muestra.html` sigue disponible como grilla de todas las poses y animaciones:
sirve la raíz con `uv run --locked python -m http.server 8766 --bind 127.0.0.1` y abre
<http://127.0.0.1:8766/herramientas/avatar/muestra.html?avatar=folio>.

## Diccionario de reacciones al texto

`reacciones-texto.json` contiene el vocabulario compartido por el widget y el
visualizador. Cada clave es una expresión existente de Folio; sus listas
`palabras`, `frases` y `emoticonos` son opcionales. Por ejemplo:

```json
{
  "sleepy": {
    "palabras": ["sueño", "cansado", "cansada"],
    "frases": ["necesito descansar"],
    "emoticonos": ["😴", "🥱"]
  }
}
```

El diccionario incluye 12 expresiones:

| Expresión | Ejemplos |
|---|---|
| `wink` | hola, buenos días, hasta luego |
| `kind` | gracias, te quiero, ❤️ |
| `happy` | jajaja, feliz, 🎉 |
| `sorry` | triste, me siento mal, 😢 |
| `worried` | miedo, nerviosa, 😰 |
| `sleepy` | sueño, cansada, 😴 |
| `unsure` | no entiendo, no me queda claro, 🤷 |
| `curious` | ayuda, explícame, quiero saber |
| `thinking` | investigar, un momento, 🤔 |
| `nod-down` | de acuerdo, entendido, 👍 |
| `surprised` | increíble, wow, 😮 |
| `reading` | libro, documento, 📖 |

Para ampliar el vocabulario, añade entradas a estas listas o un grupo con
otra expresión existente; no necesitas modificar el detector. Ignora
mayúsculas y tildes, reconoce palabras completas y admite espacios repetidos
en frases. Sobre los últimos 480 caracteres, elige la coincidencia más
reciente; una frase completa gana a las palabras que contiene. Omite
negaciones simples como «no estoy triste». Un signo de pregunta tiene
prioridad y produce curiosidad; una exclamación sin coincidencias produce
sorpresa. Sin señales usa lectura; con el campo vacío vuelve a estar atento.

Después de editar el JSON, desde la raíz del repositorio:

```bash
node --test herramientas/avatar/autonomia-folio.test.mjs
node herramientas/avatar/construir.mjs
```

Las pruebas comprueban que cada entrada del diccionario se reconoce y que
su expresión existe. El build incorpora el JSON en `avatar.js`; recarga el
visualizador o el widget para probar los cambios.

## Motor del avatar

- `construir.mjs`: esbuild, un solo ESM minificado. Las licencias de cada
  paquete incluido salen del metafile y van a `avatar.js.LICENSE.txt`.
- `folio.js`: dibuja Folio con las piezas y colores de `docs/assets/logo.svg`.
  Usa el runtime de avatar-core para los gestos, transiciones, parpadeo y
  movimiento reducido. `entrada.js` mantiene el renderer de avatar-web para
  las demás definiciones. Los temas pueden cambiar los colores con
  `--rw-folio-papel`, `--rw-folio-tinta`, `--rw-folio-borde`,
  `--rw-folio-pliegue`, `--rw-folio-renglon` y `--rw-folio-resalte`.
- `movimiento-folio.js`: trayectorias de la hoja completa (`spin`, `flip`,
  `bounce`, `sway`, `dance`, `float`, `paper-plane-out`, `paper-plane-in`). Su duración se toma de la animación
  del JSON; se pausan y reanudan con el controlador y se omiten con
  `prefers-reduced-motion`. Se asignan a eventos desde el panel o la CLI.
  `idle`, `attentive` y `listening` conservan sus poses con un ciclo de flotación de
  cuatro segundos, independiente de la duración de sus gestos.
- `avion-folio.js`: dobleces de esquinas, cuerpo y alas, despegue y llegada
  del avioncito. La secuencia dura 3,2 segundos; los ojos acompañan los
  dobleces redondeados y se acomodan sobre el ala. Cada vuelo elige un lado
  y una curva; las ráfagas de la estela se desplazan y desvanecen. La pausa
  conserva el recorrido y la estela. Folio lo usa al enviar (`sent`) y encontrar una cita
  (`answer_ok`); las asignaciones personalizadas tienen prioridad.
- `vida-folio.js`: cuerpo vivo. Un resorte amortiguado por canal (x, y, giro, escala) mueve el lienzo con las
  propiedades CSS `translate`, `rotate` y `scale` (no toca el `transform` de Folio). `apuntar(x, y)` inclina el
  cuerpo hacia el puntero y lo agranda al acercarse; `escribir(inputType, valor)` da un cabeceo por tecla, mantiene la
  inclinación hacia el campo, sacude la cabeza al borrar, sobresalta (`surprised`) al borrar cinco veces en 0,9 s y
  guiña (`wink`) al vaciar un campo de al menos cuatro caracteres. El widget lo crea con `crearVida(lienzo,
  {puede, reaccionar})`; `puede` lo limita a reposo, atento o escribiendo, y no hace nada con movimiento reducido.
  El bucle de animación duerme en reposo. `node --test herramientas/avatar/vida-folio.test.mjs` lo comprueba con un
  reloj falso.
- `autonomia-folio.js`: reacciones espontáneas superpuestas al reposo. El
  widget las activa en `idle` y `attentive`, y las interrumpe al teclear,
  buscar, responder o seguir el puntero. No cambia el evento del chat ni
  dispara mensajes. Se suspenden con la pestaña oculta y se omiten con
  `prefers-reduced-motion`. El renderer ofrece `setAutonomy(boolean)`;
  las muestras del catálogo mantienen la autonomía apagada por defecto.
  `node --test herramientas/avatar/autonomia-folio.test.mjs` comprueba el
  repertorio, las frecuencias, los ciclos y la excursión del avioncito.
- `interacciones-folio.js`: señales locales del borrador (`reactionForText`)
  y grilla de mirada compartida (`withPointerGaze`). El renderer expone
  `react(expression)` para superponer gestos de contacto o escritura, también
  con la autonomía apagada. Las búsquedas, respuestas y errores mantienen
  prioridad en el widget; el contacto no intercepta los clics del lanzador.
- El build es reproducible: mismas versiones, mismo sha256. Git no convierte
  los fines de línea de esos archivos (ver `.gitattributes`).
- Para actualizar la librería: cambia la versión exacta en `package.json`,
  `npm install`, `npm run construir`, y corre las pruebas de navegador.
