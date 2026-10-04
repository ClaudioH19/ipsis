# Ejemplos de integración web

Los tres ejemplos usan el mismo Web Component y no duplican la interfaz:

- `html/`: página estática; cambia `API` en `config.js` y sírvela por HTTP.
- `react/`: aplicación Vite con un adaptador React que escucha los eventos del
  componente.
- `wordpress/`: plugin instalable que registra el shortcode
  `[ipsis]`.

Antes de abrirlos, inicia el servicio con `ipsis servir <carpeta>` y permite el
origen del sitio mediante `ipsis configurar cors_origenes=...`. La clave pública
del widget identifica la integración, pero no reemplaza la protección del
servidor o del proxy.

## HTML

Cambia `API` en `html/config.js` y sirve la carpeta por HTTP.

## React

1. Copia `.env.example` a `.env` y ajusta la URL y la clave pública.
2. Ejecuta `npm install`.
3. Ejecuta `npm run dev` o verifica la compilación con `npm run build`.

El adaptador conserva el Web Component como fuente única de la interfaz y
traduce `rag:respuesta` y `rag:error` a callbacks de React.

## WordPress

1. Copia esta carpeta a `wp-content/plugins/ipsis-widget`.
2. Activa **ipsis Widget** en el panel de plugins.
3. Inserta el shortcode en una página:

```text
[ipsis api="https://ipsis.example" clave="sitio-publico" color="#7c3aed"]
```

Permite el origen de WordPress en `cors_origenes` del servicio. La clave queda
visible en el HTML y, por tanto, es un identificador público, no un secreto.
