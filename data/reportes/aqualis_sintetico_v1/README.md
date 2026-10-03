# Línea base sintética Aqualis v1

Artefactos generados con:

```bash
rag benchmark \
  --banco tests/evaluacion/sintetico/manifiesto.json \
  --salida data/reportes/aqualis_sintetico_v1
```

- `qdrant_vectorial.json` y `qdrant_hibrida.json` contienen configuración,
  índice, calibración `dev`, métricas y observaciones.
- `comparacion.json` reúne únicamente resultados compatibles.
- `decisiones` permanece vacío deliberadamente.

El banco tiene 12 casos sintéticos y sirve como prueba reproducible y línea
base de defectos. No tiene tamaño ni diversidad suficientes para elegir un
backend predeterminado o publicar umbrales de producción. Esas decisiones
requieren el golden set manual descrito en `data/golden/README.md`.

SQLite FTS5 participó en la primera ejecución de C.3 y fue retirado después de
producir un falso `ok` bloqueante ante una pregunta ambigua. El resultado queda
registrado en `docs/avance.md`, pero su artefacto y su implementación ya no
forman parte del producto.
