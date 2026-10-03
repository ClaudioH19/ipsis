# Ejemplos de integración web

Los tres ejemplos usan el mismo Web Component y no duplican la interfaz:

- `html/`: página estática; cambia `API` en `config.js` y sírvela por HTTP.
- `react/`: aplicación Vite con un adaptador React que escucha los eventos del
  componente.
- `wordpress/`: plugin instalable que registra el shortcode
  `[rag_extractivo]`.

Antes de abrirlos, inicia el servicio con `rag servir <carpeta>` y permite el
origen del sitio mediante `rag configurar cors_origenes=...`. La clave pública
del widget identifica la integración, pero no reemplaza la protección del
servidor o del proxy.
