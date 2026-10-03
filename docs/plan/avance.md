# Avance del plan V3

Estados: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado (explicar en «Hallazgos»).

Línea base antes del plan (2026-10-03): 323 pruebas rápidas pasan, 2 se
omiten y 21 quedan deseleccionadas (`-m "not slow"`, 152 s).

| Tarea | Estado | Fecha | Pruebas | Notas |
|---|---|---|---|---|
| P0.1 | ✅ | 2026-10-03 | 323 | Commits `d2b234e` (estado previo) y `855d4b3` (plan). |
| P0.2 | ✅ | 2026-10-03 | 312 | −11 pruebas del evaluador antiguo. `.cache/` conserva carpetas bloqueadas por OneDrive (ignoradas por git). |
| P0.3 | ✅ | 2026-10-03 | 312 | `--import-mode=importlib` se pospone a P2.1 (requiere quitar `tests/__init__.py` y el import cruzado de `test_portabilidad`). La marca es `modelos("org/nombre", ...)`; la caché se busca en `RAG_MODELOS_DIR` o `~/.cache/rag-extractivo/modelos` con la estructura de huggingface_hub. |
| P1.1 | ✅ | 2026-10-03 | 313 | DecisionAbstencion y Resultado pasan a nucleo/esquemas para que nucleo no dependa de consulta. Prueba nueva: el núcleo no importa dependencias pesadas. |
| P1.2 | ✅ | 2026-10-03 | 313 | Sin desvíos. |
| P1.3 | ✅ | 2026-10-03 | 313 | Sin desvíos. |
| P1.4 | ✅ | 2026-10-03 | 300 | −13 pruebas: 7 duplicaban tests/test_abstencion.py (capas y umbral) y 6 cubrían el adaptador legado. Las 4 de premisa siguen, ahora sobre verificar_premisa_textos. |
| P1.5 | ✅ | 2026-10-03 | 300 | Conversación importa _cargar_plantillas/_elegir_variante de redaccion (dependencia dentro de consulta). |
| P1.6 | ✅ | 2026-10-03 | 300 | rag/indice.py se fusionó en rag/indice/qdrant.py. Las etiquetas históricas en comentarios se limpian en P13.1 (criterio agregado). |
| P1.7 | ✅ | 2026-10-03 | 300 | comparacion.py se fusionó en evaluacion/benchmark.py y exportar_widget.py en servicio/widget.py. |
| P1.8 | ✅ | 2026-10-03 | 303 | Para cumplir las capas: Motor.desde_configuracion → aplicacion/consulta.py::construir_motor; evaluar_backend_activo y ejecutar_benchmark → aplicacion/evaluacion.py (benchmark recibe main de la CLI por inyección); actualizar_dominio → aplicacion/proyecto.py; estilos.py y widget.py → aplicacion/; evaluacion/benchmark.py → evaluacion/comparacion.py. La regla estricta cli/servicio→aplicacion queda para P11.1. |
| P1.9 | ✅ | 2026-10-03 | 303 + 18/18 caracterización | Wheel con 63 archivos, incluye plantillas y estáticos. Grafo actualizado. |
| P2.1 | ✅ | 2026-10-03 | 303 + 21 lentas | Desvío: test_contratos, test_frontera_tipos y test_intercambio no se fusionaron (cubren cosas distintas); quedan en nucleo/ y consulta/. Helpers de PDF y rutas en tests/apoyo.py (pythonpath=tests, import-mode=importlib, pendiente de P0.3). .gitattributes apunta a tests/datos. |
| P2.2 | ✅ | 2026-10-03 | 303 + 21 lentas | Fixture autouse proyecto_suite (rag init en temporal + chdir) en lugar de una fixture explícita por prueba. Corrige un defecto: PALABRAS_GENERALES_ES dependía del directorio actual al importarse; ahora sale del recurso del paquete. Dockerfile ejecuta rag init en build. CI ya usaba rag init en carpeta temporal. |
| P2.3 | ⬜ | | | |
| P2.4 | ⬜ | | | |
| P3.1 | ⬜ | | | |
| P3.2 | ⬜ | | | |
| P3.3 | ⬜ | | | |
| P3.4 | ⬜ | | | |
| P3.5 | ⬜ | | | |
| P3.6 | ⬜ | | | |
| P3.7 | ⬜ | | | |
| P4.1 | ⬜ | | | |
| P4.2 | ⬜ | | | |
| P4.3 | ⬜ | | | |
| P4.4 | ⬜ | | | |
| P4.5 | ⬜ | | | |
| P4.6 | ⬜ | | | |
| P5.1 | ⬜ | | | |
| P5.2 | ⬜ | | | |
| P5.3 | ⬜ | | | |
| P5.4 | ⬜ | | | |
| P5.5 | ⬜ | | | |
| P5.6 | ⬜ | | | |
| P6.1 | ⬜ | | | |
| P6.2 | ⬜ | | | |
| P6.3 | ⬜ | | | |
| P7.1 | ⬜ | | | |
| P7.2 | ⬜ | | | |
| P7.3 | ⬜ | | | |
| P7.4 | ⬜ | | | |
| P7.5 | ⬜ | | | |
| P7.6 | ⬜ | | | |
| P8.1 | ⬜ | | | |
| P8.2 | ⬜ | | | |
| P8.3 | ⬜ | | | |
| P8.4 | ⬜ | | | |
| P9.1 | ⬜ | | | |
| P9.2 | ⬜ | | | |
| P9.3 | ⬜ | | | |
| P10.1 | ⬜ | | | |
| P10.2 | ⬜ | | | |
| P10.3 | ⬜ | | | |
| P10.4 | ⬜ | | | |
| P10.5 | ⬜ | | | |
| P11.1 | ⬜ | | | |
| P11.2 | ⬜ | | | |
| P11.3 | ⬜ | | | |
| P11.4 | ⬜ | | | |
| P11.5 | ⬜ | | | |
| P11.6 | ⬜ | | | |
| P12.1 | ⬜ | | | |
| P12.2 | ⬜ | | | |
| P12.3 | ⬜ | | | |
| P12.4 | ⬜ | | | |
| P13.1 | ⬜ | | | |
| P13.2 | ⬜ | | | |
| P13.3 | ⬜ | | | |

## Hallazgos y desvíos

Anota aquí lo que una tarea descubrió y que afecta a tareas posteriores.
