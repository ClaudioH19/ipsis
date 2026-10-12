# Integrar ipsis en HTML y frameworks web

Tu sitio sirve la página; `ipsis serve` sirve el asistente, su índice y
`/widget.js`. El navegador carga ese script y consulta `/config` y `/ask`
en la URL del asistente. No necesitas instalar un paquete npm de ipsis ni
importar un módulo JavaScript. Usa un **script clásico**, sin `type="module"`.

## 1. Preparar el asistente

En la carpeta del proyecto, con ipsis ya [instalado](instalacion.md):

```bash
ipsis init --profile light --language es
ipsis models download
ipsis load ./documents
ipsis index
ipsis widget theme apply search
ipsis configure cors_origins=http://127.0.0.1:8080
ipsis serve --no-open
```

Omite `init` si el proyecto ya existe. En `cors_origins` va el origen de
**tu página**, con protocolo y puerto, no la URL del asistente. Para React
usa `http://127.0.0.1:5173`, Svelte `:5174`, Astro `:4321`, Angular `:4200`
o Python `:8080`. `localhost` y `127.0.0.1` son orígenes distintos.
Reinicia el servicio después de cambiar CORS. Si admites varios sitios,
declara la lista en `config/assistant.yaml`:

```yaml
cors_origins:
  - http://127.0.0.1:8080
  - http://127.0.0.1:5173
```

Abre `http://127.0.0.1:8000/ready` para comprobar que el asistente está
listo. El sitio de ejemplo se ejecuta en **otra terminal**, mientras ipsis
sigue funcionando.

## 2. HTML: pegar el script

Guarda esto como `index.html` en la carpeta de tu sitio:

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mi sitio</title>
  </head>
  <body>
    <h1>Documentación</h1>
    <script src="http://127.0.0.1:8000/widget.js"
            data-api="http://127.0.0.1:8000"
            data-position="bottom-right" defer></script>
  </body>
</html>
```

Sirve esa carpeta con `python -m http.server 8080 --bind 127.0.0.1` y
abre `http://127.0.0.1:8080`. Usa HTTP en vez de abrir una URL `file://`.
El script crea el widget flotante. También puedes generar el código:

```bash
ipsis widget snippet --api https://asistente.tu-dominio.cl
```

Para un chat **dentro de la página**, reemplaza el script anterior por:

```html
<div style="height:560px">
  <ipsis-chat api="http://127.0.0.1:8000" mode="embedded"></ipsis-chat>
</div>
<script src="http://127.0.0.1:8000/widget.js" defer></script>
```

El elemento debe existir antes de que se ejecute el script. Elige el script
automático o el elemento explícito; cargar ambos ejemplos duplica el widget.
Se admite un widget por documento del navegador. Su Shadow DOM aísla el
CSS: personalízalo con `ipsis widget style` o `/admin/panel`.

## 3. Elegir un framework

El repositorio incluye ejemplos independientes. Clónalo para ejecutarlos,
o copia el componente indicado en tu aplicación. Los ejemplos JavaScript
usan Node **22.12 o superior de la rama 22.x**. Cada `package.json` fija las
dependencias; ejecuta los comandos desde la carpeta del ejemplo elegido.

| Sitio | Carpeta | Archivo de integración | Página local |
|---|---|---|---|
| HTML | [examples/html](../../../examples/html) | [index.html](../../../examples/html/index.html), [config.js](../../../examples/html/config.js) | `http://127.0.0.1:8080` |
| Astro | [examples/astro](../../../examples/astro) | [IpsisChat.astro](../../../examples/astro/src/components/IpsisChat.astro) | `http://127.0.0.1:4321` |
| Svelte 5 | [examples/svelte](../../../examples/svelte) | [IpsisChat.svelte](../../../examples/svelte/src/IpsisChat.svelte) | `http://127.0.0.1:5174` |
| React 19 | [examples/react](../../../examples/react) | [IpsisChat.jsx](../../../examples/react/src/IpsisChat.jsx) | `http://127.0.0.1:5173` |
| Angular 20 | [examples/angular](../../../examples/angular) | [ipsis-chat.component.ts](../../../examples/angular/src/ipsis-chat.component.ts) | `http://127.0.0.1:4200` |
| Python / FastAPI | [examples/python](../../../examples/python) | [app.py](../../../examples/python/app.py) | `http://127.0.0.1:8080` |

### Astro

En `examples/astro`, copia `.env.example` a `.env`, ejecuta `npm install`
y luego `npm run dev`. `npm run build` genera el sitio estático en `dist/`.
Configura `PUBLIC_IPSIS_API` con la URL del asistente y
`PUBLIC_IPSIS_WIDGET_KEY` si el proyecto exige una clave de widget.

En un sitio Astro existente, copia `IpsisChat.astro` e inclúyelo una vez
al final del `<body>` del layout compartido:

```astro
---
import IpsisChat from '../components/IpsisChat.astro';
---
<IpsisChat />
```

El componente usa `<script is:inline src={...} defer>` para que Astro
conserve el script remoto clásico. No necesita `client:load`. El ejemplo
usa navegación con carga completa de página. Si empleas `ClientRouter`,
conserva el elemento entre transiciones y gestiona la inicialización del
script: el widget actual no se conecta automáticamente a elementos nuevos.
Ver [scripts de Astro](https://docs.astro.build/en/guides/client-side-scripts/).

### Svelte

En `examples/svelte`, copia `.env.example` a `.env`, ejecuta `npm install`
y `npm run dev`. Configura `VITE_IPSIS_API` y, si corresponde,
`VITE_IPSIS_WIDGET_KEY`. Compila con `npm run build`.

Copia `IpsisChat.svelte` en una aplicación Svelte y úsalo una vez en el
componente raíz:

```svelte
<script>
  import IpsisChat from './IpsisChat.svelte';
</script>
<IpsisChat api="https://asistente.tu-dominio.cl"
           onAnswer={(detail) => console.info(detail.status)} />
```

Carga el script en `onMount`, después de crear el elemento, y retira sus
listeners cuando se destruye. En SvelteKit va en el `+layout.svelte` raíz
persistente; usa `PUBLIC_IPSIS_API` de `$env/static/public` en lugar de las
variables específicas de Vite. `onMount` no se ejecuta durante SSR.
Ver [ciclo de vida de Svelte](https://svelte.dev/docs/svelte/lifecycle-hooks).

### React

En `examples/react`, copia `.env.example` a `.env`, ejecuta `npm install`
y `npm run dev`. Configura `VITE_IPSIS_API` y, si corresponde,
`VITE_IPSIS_WIDGET_KEY`. Compila con `npm run build`.

Copia `IpsisChat.jsx` en una aplicación React:

```jsx
import { IpsisChat } from './IpsisChat.jsx';

export default function App() {
  return <IpsisChat api="https://asistente.tu-dominio.cl"
    onAnswer={(detail) => console.info(detail.status)}
    onError={(detail) => console.error(detail.message)} />;
}
```

El adaptador carga el script una vez y escucha eventos DOM nativos. Cambiar
los callbacks o usar Strict Mode no vuelve a cargarlo. Ubícalo fuera del
contenido que cambia con las rutas, en el layout persistente de la aplicación.
En un framework con SSR, declara el adaptador como componente cliente cuando
corresponda (por ejemplo `'use client'` en Next.js).
Ver [efectos de React](https://react.dev/reference/react/useEffect).

### Angular

En `examples/angular`, edita `src/config.ts` con la URL del asistente y la
clave opcional. Ejecuta `npm install` y `npm run dev`.
Compila con `npm run build`.

Para una aplicación Angular existente, copia `config.ts` y
`ipsis-chat.component.ts`, añade `IpsisChatComponent` a los `imports` del
componente raíz y coloca `<app-ipsis-chat />` fuera del router outlet.
El adaptador standalone declara `CUSTOM_ELEMENTS_SCHEMA` para aceptar
`<ipsis-chat>`, usa `[attr.api]` para asignar el atributo HTML y carga el
script con `afterNextRender` en el navegador después de renderizar.
Ver [esquema de elementos personalizados](https://angular.dev/api/core/CUSTOM_ELEMENTS_SCHEMA)
y [hook de renderizado](https://angular.dev/api/core/afterNextRender).

### Python: servir el HTML con FastAPI

Desde `examples/python`:

```bash
uv run --no-project --with fastapi --with uvicorn uvicorn app:app --host 127.0.0.1 --port 8080
```

La página lee `IPSIS_API` y `IPSIS_WIDGET_KEY` del entorno. Por defecto usa
el asistente local sin clave. El ejemplo escapa los valores al insertarlos
en atributos HTML. FastAPI sirve la página en `/`; el navegador carga el
widget desde ipsis en el puerto 8000. Mantén `ipsis serve` ejecutándose en
su propio proyecto. No inicia otro motor ni usa una API Python interna.
Las mismas etiquetas HTML funcionan en templates de Flask o Django.
Ver [respuestas HTML de FastAPI](https://fastapi.tiangolo.com/advanced/custom-response/#html-response).

## Eventos, rutas y configuración

Escucha el elemento `<ipsis-chat>` con
`element.addEventListener('ipsis:answer', handler)`. `event.detail.status`
contiene el estado y `event.detail.answer` contiene la respuesta completa
de `/ask`, incluidos sus `fragments`. También existen `ipsis:error`,
`ipsis:open`, `ipsis:close` e `ipsis:question`. Los adaptadores usan estos
mismos eventos; no generan respuestas.

El widget actual se inicializa al ejecutar el script, no al reconectar el
elemento personalizado. Conserva su elemento montado, carga `widget.js`
una vez por documento y mantén fija la URL y la clave durante esa página.
Cambiar de ruta no debe recrearlo. Para cambiar de asistente, recarga la
página. Una vez cargado, `window.Ipsis.open()` y `.close()` controlan el panel;
no hay una API pública `mount()` o `destroy()`.

## Publicar y resolver problemas

Reemplaza la URL local por la URL HTTPS del asistente y permite el origen
de producción del sitio. Si cambias variables incorporadas durante el build,
vuelve a compilar. Sigue la [guía de despliegue](despliegue.md).
`127.0.0.1` en el navegador apunta al equipo del visitante. Una página HTTPS
debe cargar el asistente por HTTPS. La clave del widget es pública;
el token de administración permanece en el servidor.

| Síntoma | Qué comprobar |
|---|---|
| No aparece el widget | `/widget.js` devuelve JavaScript; no hay errores de script/CSP; el elemento existe antes de cargar |
| Error de CORS | Incluye el origen exacto de la página en `cors_origins` y reinicia ipsis |
| 401/403 en `/ask` | Si el proyecto exige clave, añade `widget-key` al elemento o `data-widget-key` al script |
| 503 / no está listo | Revisa `/ready`, ejecuta `ipsis doctor` y carga/indexa los documentos |
| Widget duplicado | Inclúyelo una vez en el layout; no pegues además el script automático |

La [guía del widget](web.md) detalla ubicación, tamaño incrustado, estilos,
CSP, avatar, exportación estática y API JavaScript. En Windows usa `npm.cmd`
si PowerShell bloquea el lanzador `npm.ps1`.
