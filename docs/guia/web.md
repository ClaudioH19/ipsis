# Instalación en sitios web

La integración tiene dos partes: un backend Python y un cliente de navegador.
El navegador no puede ejecutar directamente el índice o los modelos Python.

## Disponible actualmente

### Backend

```bash
pip install rag-extractivo
rag init
rag cargar ./mis-documentos
rag indexar
rag servir
```

También puede desplegarse mediante la imagen Docker del proyecto.

### Widget mediante script

```html
<script
  src="https://mi-api.example/widget.js"
  data-api="https://mi-api.example"
  data-widget-key="identificador-publico-del-sitio">
</script>
```

Configura `cors_origenes` con el origen exacto del sitio. La clave incluida en
HTML es pública: sirve para identificar y limitar tráfico, no sustituye una
credencial secreta del servidor.

## Web Component y exportación

```bash
rag widget exportar ./public/rag --api https://mi-api.example
```

El comando genera `widget.js` y `snippet.html`. El elemento
`<rag-extractivo-chat>` admite los atributos `api`, `widget-key`, `color`,
`titulo`, `saludo` y `posicion`; sus eventos públicos son `rag:abierto`,
`rag:cerrado`, `rag:pregunta`, `rag:respuesta` y `rag:error`. La forma anterior
basada únicamente en atributos `data-*` del `<script>` continúa disponible.

## Ejemplos ejecutables

- `ejemplos/html`: página estática configurable desde `config.js`;
- `ejemplos/react`: proyecto Vite y adaptador de eventos para React;
- `ejemplos/wordpress`: plugin instalable con el shortcode
  `[rag_extractivo]`.

La suite `pytest -m browser` arranca una API controlada y usa Chromium real
para verificar teclado, captura y restitución del foco, semántica de diálogo,
pantalla móvil, respuestas con citas y recuperación ante errores de red.

## Distribución prevista para V2

- paquete npm `@rag-extractivo/widget`;
- bundles ESM y UMD autocontenidos;
- tipos TypeScript;
- matriz SemVer de compatibilidad entre widget y API.

La ruta `/widget.js` se conserva para instalaciones sin npm.
