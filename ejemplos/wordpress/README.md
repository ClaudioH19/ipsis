# Ejemplo WordPress

1. Copia esta carpeta a `wp-content/plugins/rag-extractivo-widget`.
2. Activa **rag-extractivo Widget** en el panel de plugins.
3. Inserta el shortcode en una página:

```text
[rag_extractivo api="https://rag.example" clave="sitio-publico" color="#7c3aed"]
```

Permite el origen de WordPress en `cors_origenes` del servicio. La clave queda
visible en el HTML y, por tanto, es un identificador público, no un secreto.
