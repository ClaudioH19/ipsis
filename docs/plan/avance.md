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
| P2.3 | ✅ | 2026-10-03 | 304 + 21 lentas | Nuevo rag/configuracion/rutas.py como única fuente de rutas. dominio.yaml une perfil.yaml y categorias.yaml (taxonomía bajo 'taxonomia'); desaparece la clave 'perfil' de asistente.yaml y el concepto _generico. La CLI migra el proyecto al arrancar cualquier comando. Corrige un defecto: cargar_dominio aplicaba la versión por defecto antes de migrar. La caché global de modelos llega con P5.2. |
| P2.4 | ✅ | 2026-10-03 | 304 | docs: README con mapa, guia/ (configuracion, web, golden), metodologia/. ejemplos con un solo README. docker-compose pasa a rag/recursos/despliegue/. data/ eliminado. .dockerignore actualizado. |
| P3.1 | ✅ | 2026-10-03 | 308 + 21 lentas | es.yaml generado desde los datos del código para una migración exacta. palabras_generales se conserva como clave transitoria hasta P4.4 (sin 'curso' ni 'universidad'). Corrige un defecto: YAML 1.1 leía 'no' como false. La migración borra configuracion/dominios/idiomas. 'rag configurar idioma=' también valida el paquete. |
| P3.2 | ✅ | 2026-10-03 | 322 + 21 lentas | Corrige un defecto: la selección de oraciones perdía el texto anterior a un punto no seguido de espacio (p. ej. «1.5»). La división en oraciones de chunking no afectaba el resultado (solo armaba un conjunto de palabras) y se eliminó. Orden de terminos(): casefold, quitar tildes latinas y luego stem, para que «garantía» y «garantias» coincidan. Caracterización sin cambios. |
| P3.3 | ✅ | 2026-10-03 | 351 (suite completa) | fecha (numérica, normalizada a ISO) y monto (símbolo o código ISO 4217 de una lista cerrada; grupos de tres dígitos = miles). Un punto final de oración no bloquea la coincidencia. Caracterización sin cambios. Requiere reindexar para que el inventario incluya los nuevos tipos. |
| P3.4 | ✅ | 2026-10-03 | 351 (suite completa) | Las listas de palabras van al paquete; la estructura de los patrones queda en código y es común a es/en/pt (el calificador del plazo puede ir antes o después de la unidad). Idioma activo como el perfil: configurar_idioma / usar_idioma; el motor lo aplica por consulta. valor_norm de fechas con nombre: 2024-03-15, --03-15, 2_dow5_m01; '3 meses' pasa de 3_mese a 3_mes. Los marcadores de excepción/condición salen del paquete. Requiere reindexar. |
| P3.5 | ✅ | 2026-10-03 | 352 (suite completa) | cargar_plantillas(paquete, dominio) arma el mismo diccionario que antes leía de textos.yaml, así redaccion y conversacional casi no cambian. Las contracciones («de el» -> «del») pasan al paquete. 'rag doctor' valida los textos del idioma en lugar de exigir textos.yaml. La migración conserva en idioma.yaml solo lo que el proyecto había cambiado. La migración lee el YAML del paquete desde los recursos para no subir de capa. |
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
