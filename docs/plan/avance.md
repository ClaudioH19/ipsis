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
| P3.6 | ✅ | 2026-10-03 | 331 | /config publica 'interfaz' del paquete (con idioma.yaml). widget.js usa TEXTOS con respaldo en español y los reemplaza al recibir /config. Sintaxis JS verificada con node --check. La prueba de navegador se omite: Playwright no está instalado en este entorno. |
| P3.7 | ✅ | 2026-10-03 | 404 (suite completa) | en.yaml y pt.yaml completos; 52 pruebas parametrizadas (≥3 casos por regla e idioma) confirman el mismo valor_norm en los tres idiomas. Además: stopwords de palabras clave y la etiqueta «(sin sección)» pasan al paquete. Criterio de P3 precisado: los mensajes al operador quedan en español. |
| P4.1 | ✅ | 2026-10-03 | 11 nuevas | EstadisticasLexicas con df, largo medio y forma de superficie; escritura atómica. |
| P4.2 | ✅ | 2026-10-03 | (mismo commit) | lexico.py puro: id por crc32, BM25 doc/consulta/puntaje, TF-IDF, coseno y MMR. Recibe las estadísticas por Protocol para no depender de la capa indice. |
| P4.3 | ✅ | 2026-10-03 | 413 (suite completa) | Vector disperso = bm25_doc(terminos()) con id crc32; Qdrant aplica IDF. Sin vocabulario: las estadísticas se guardan por colección en .rag/indice/<colección>.estadisticas.json (el benchmark crea varias colecciones). La consulta usa el stemmer guardado en las estadísticas, no la configuración. Desvío: el inventario de entidades y las estadísticas de grounding siguen en archivos propios hasta P4.4/P5.4. BM25 solo recupera el chunk correcto en 3/3 preguntas de prueba; caracterización sin cambios. |
| P4.4 | ✅ | 2026-10-03 | 417 (suite completa) | Señales en lexico.py y esquema SenalesLexicas. El grounding de layered_v1 pasa a 'entidad en inventario o s_oov < oov_max (0,5)'; se eliminan palabras_generales (paquetes y código) y las estadísticas df antiguas. Si la pregunta trae entidades, decide la premisa (conserva el mensaje «No encontré información sobre …»). Cambio deliberado de caracterización: «¿Atienden los domingos?» pasa de relacionado (mostraba reembolsos y filtro) a sin_respuesta. Hallazgo: con 2 términos foco, la oración correcta puede contener solo uno; umbral por defecto de s_foco = 0,5. |
| P4.5 | ✅ | 2026-10-03 | 417 (suite completa) | Las unidades se puntúan con s_lex usando las estadísticas del índice (o tf-isf local si faltan) y el stemmer del idioma activo. Se eliminan Jaccard, la ruta densa, palabras_contenido, STOPWORDS_ES y redaccion.metodo_seleccion (la migración v2→v3 lo retira). terminos_pregunta() queda en lexico.py como único lugar. Caracterización sin cambios. |
| P4.6 | ✅ | 2026-10-03 | 417 (suite completa) | Palabras clave = mayor TF-IDF con el IDF del corpus completo (calculado antes de armar los payloads), devueltas en su forma original. Categorías comparan términos con stem: plurales y tildes ya no impiden coincidir con palabras gatillo. |
| P5.1 | ✅ | 2026-10-03 | — | Licencias, parámetros y archivos ONNX verificados con la API de Hugging Face (tabla en modelos-y-perfiles.md §2). ⛔ Decisión del usuario pendiente: xlm-roberta-large-squad2 no tiene ONNX confiable; heavy usa mdeberta con leer_m=4 mientras tanto. e5 se usa en fp32 porque su int8 publicado exige AVX-512 VNNI. |
| P5.2 | ✅ | 2026-10-03 | 6 nuevas | ModeloSpec con ONNX por arquitectura (x86_64/arm64) y caché global en formato huggingface_hub; ruta_local() falla con 'rag modelos descargar'. huggingface-hub declarado como dependencia. |
| P5.3 | ✅ | 2026-10-03 | 398 rápidas + 3 modelos | ModeloOnnx (sesión única, tokenizador, entradas) y CodificadorDenso con prefijos y pooling promedio. Verificado: vectores idénticos a sentence-transformers (coseno 1,0). Registrado como dense_encoder: onnx. onnxruntime y tokenizers declarados. |
| P5.4 | ✅ | 2026-10-03 | 429 (suite completa con modelos) | Indexación y consulta con CodificadorDenso ONNX: los pasajes llevan 'passage: ' (corrige el defecto de E5). Manifiesto por colección con modelo, dimensión, stemmer, hash del corpus, versión del payload e inventario de entidades (reemplaza el archivo de inventario). Prefijos fuera de la configuración: los define el catálogo. Caracterización regenerada: solo cambian los cosenos top1 (±0,01), ningún estado ni texto. rag doctor revisa el modelo en la caché global. |
| P5.5 | ✅ | 2026-10-03 | 429 (suite completa) | Sin sentence-transformers ni torch: dense_encoder por defecto 'onnx' (la migración v2→v3 convierte 'sentence_transformers'). Extra [exportar] con optimum y torch solo para desarrollo. Dockerfile y CI sin torch. Verificado en un venv limpio (229 MB): init → cargar → indexar → consulta funcionan, torch no está instalado ni cargado. |
| P5.6 | ✅ | 2026-10-03 | 436 (suite completa) | Presets light/medium/heavy/bm25 en rag/recursos/perfiles; perfil_efectivo fusiona perfil ← motor.yaml::ajustes_perfil ← calibracion.yaml (solo si perfil y modelos coinciden). asistente.yaml::perfil (v2 migra a light; rag init usa medium). recuperacion.modelo es opcional: si falta, manda el denso del perfil. Umbral foco por defecto 0,5. Desvío: la migración se hizo sobre config_version 3 (no 3→4) porque v3 aún no se publicó. |
| P6.1 | ✅ | 2026-10-03 | 436 (suite completa) | ContextoConsulta y 9 clases de etapa (un archivo por responsabilidad, base en etapas/base.py). El motor recorre la lista, mide <nombre>_ms y aplica la admisión a todas menos la conversacional. Los nombres de medición existentes se conservan (confianza, evidencia); se agregan filtros, politica, redaccion y verificacion. Sin cambios en pruebas ni caracterización. |
| P6.2 | ✅ | 2026-10-03 | 438 (suite completa) | Etapas registradas en el registry (tipo 'etapa') y armadas desde perfil_efectivo; una etapa desconocida falla al construir con mensaje accionable. Filtros calcula términos foco y s_oov; recuperación marca la salida temprana y el motor salta las etapas usa_modelos. Desvío: medium/heavy aún no listan reranking/lectura (se agregan en P7.1/P7.3) para no romper el arranque; los nombres de etapa siguen el flujo vigente (layered_v1) hasta P8. |
| P6.3 | ✅ | 2026-10-03 | 439 (suite completa) | QueryDiagnostic v2: perfil, senales_lexicas (foco, s_oov, IDF de cada término, términos ausentes del corpus), puntajes_rerank, lecturas, regla y salto_modelos. |
| P7.1 | ✅ | 2026-10-03 | 442 (suite completa) | RerankerOnnx (pares pregunta-pasaje) y etapa reranking (usa_modelos): ordena por logit, desempata por chunk_id y deja rerank_k. Con reranker se recuperan recuperar_n candidatos. medium/heavy incluyen la etapa; el motor calienta el reranker al arrancar. Medido: 20 pasajes en 124 ms (mmarco int8); separa garantía (4,18) del resto (negativos). Las pruebas rápidas y la caracterización usan --perfil light. |
| P7.2 | ✅ | 2026-10-03 | fast + 5 de modelos nuevas | LectorOnnx: ventanas con stride (truncado only_second), mejor tramo entre los 20 mejores bordes, softmax contra [CLS], offsets de carácter verificados. Hallazgo: el int8 publicado de mdeberta da logits planos e int16 no carga; se usa fp32 (1,1 GB). Medido con fp32: filtro → «6 meses», garantía → «24 meses» (s_qa 1,00); garantía contra el pasaje del filtro → s_qa 0,00; pregunta en inglés sobre texto en español → «24 meses». 50-110 ms por pasaje. |
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
