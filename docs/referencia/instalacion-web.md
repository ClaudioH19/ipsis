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

## Distribución prevista para V2

- paquete npm `@rag-extractivo/widget`;
- bundles ESM y UMD autocontenidos;
- Web Component `<rag-extractivo-chat>`;
- tipos TypeScript;
- ejemplos para HTML, React y CMS;
- matriz SemVer de compatibilidad entre widget y API.

La ruta `/widget.js` se conservará para instalaciones sin npm.

