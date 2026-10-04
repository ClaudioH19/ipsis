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
| P7.3 | ✅ | 2026-10-03 | 451 (suite completa) | Etapa lectura (usa_modelos): lee leer_m candidatos; la evidencia es la oración que contiene el tramo y el contrato HTTP gana respuesta_exacta opcional (solo aparece si existe). medium/heavy incluyen la etapa. Medido con medium en el corpus sintético: filtro → «6 meses», garantía → «24 meses», reembolso → «10»; repuestos → relacionado; precio → sin_respuesta. Latencia ~1,2-1,3 s: la lectura toma ~1 s porque lee pasajes completos de ~256 tokens; se optimiza en P7.6. |
| P7.4 | ✅ | 2026-10-03 | 452 (suite completa) | La etapa de evidencia calcula s_foco y s_cov sobre la oración que se mostrará (la del tramo del lector o la elegida en light) y los guarda en ctx.lexicas y en el diagnóstico. Prueba: «6 meses» del pasaje del filtro ante la pregunta por la garantía → s_foco = 0. |
| P7.5 | ✅ | 2026-10-03 | 453 (suite completa) | Concordancia en heavy (cascada.concordancia): si los dos mejores tramos confiables de pasajes distintos traen entidades del mismo tipo con valores distintos, la decisión baja a relacionado (motivo discordancia). La recuperación dirigida por entidad ya existía para todos los perfiles. |
| P7.6 | ✅ | 2026-10-03 | 454 (suite completa) | rag benchmark --solo-latencia (20 rep. light/medium, 10 heavy, corpus sintético, CPU local): light p50 70 / p95 82 ms (presup. 150); medium p50 749 / p95 886 ms (presup. 1000; reranking ~146, lectura ~548); heavy p50 1951 / p95 2221 ms (presup. 4000; reranking ~1103, lectura ~844). El lector lee una ventana de max_caracteres_lectura (600 medium, 1200 heavy) elegida por s_lex en vez del pasaje completo. |
| P8.1 | ✅ | 2026-10-03 | 483 (suite completa) | CascadaV1 en politica.py, registrada como abstention_policy cascada_v1 (aún no activa). Decide en EtapaPolitica vía decidir_contexto(ctx) con s_ret/s_oov/s_foco/s_cov/acuerdo/s_rr/s_qa; umbrales del perfil (construir_motor pasa umbrales=umbrales_por_defecto). Guarda regla en capa_decisora y señales en diagnostico.senales_politica. relacionado por foco ausente nombra la palabra de la pregunta (mensajes.relacionado_foco_ausente). EtapaPolitica conserva el motivo fuera_dominio. Requiere que politica corra DESPUÉS de evidencia (s_foco/s_cov se miden sobre la oración de evidencia): lo hace P8.2. 29 pruebas en tests/consulta/test_cascada.py. |
| P8.2 | ✅ | 2026-10-03 | 502 (suite completa) | Perfiles con cascada_v1 (config v4 migra layered_v1→cascada_v1; plantilla y default actualizados) y politica después de evidencia. Caracterización por perfil: light.json y medium.json (medium si sus modelos están en caché). Cambios de estado deliberados — light: reembolso tras instalar ok→relacionado (s_cov 0,20: el tramo no cubre la pregunta), precio sin_respuesta→relacionado (muestra lo cercano con encabezado de no-respuesta). medium vs. light anterior: visita, recargo art. 4 y presión 4,0 bar relacionado→ok (tramos correctos del lector), reembolso tras instalar ok→relacionado (s_qa 0,76 < 0,8), precio sin_respuesta→relacionado. Sin falsos ok en la caracterización; ver hallazgos (s_ret normalizado, dominio = max(s_ret, s_rr), falso ok conocido «¿Qué incluye la garantía?»). |
| P8.3 | ✅ | 2026-10-03 | 481 (suite completa) | Borrados LayeredV1, decidir_capas, tiene_grounding_*, verificar_respaldo_dato_solicitado y sus regex (precio/duración/cantidad en español), config_abstencion y test_politica.py (lo cubre test_cascada.py). El protocolo AbstentionPolicy queda en decidir_contexto(ctx); EtapaFiltros ya no decide dominio. motor.yaml::abstencion queda en max_fragmentos_adicionales (la migración v3→v4 poda capa_a/confianza_alta/zona_gris/perfiles_retriever). Caracterización light/medium sin cambios: la guardia ya no decidía nada con cascada_v1. El rg de aceptación no devuelve nada. |
| P8.4 | ✅ | 2026-10-03 | 484 (suite completa) | Banco v1.1.0: 27 casos, 15 sin respuesta (56%): 12 trampas «mismo tema, dato ausente» (garantía del filtro, repuestos, quién autoriza el reembolso, agua de pozo, qué incluye la garantía, litros por hora, teléfono, domingos; 3 en inglés) y 4 respondibles nuevos (vencimiento de garantía, presión, sábados, una en inglés). Falsos ok: light 0/19, medium 0/19. Cobertura de ok en respondibles: light 2/8, medium 4/8. Para llegar a 0: s_foco/s_cov se miden en la oración ancla (light medía la ventana entera) y ok exige s_oov < τ_oov (ver hallazgos). Caracterización: medium «¿Qué pasa si no estoy en la visita?» ok→relacionado (s_oov 0,84). |
| P8.5 | ✅ | 2026-10-03 | 488 (suite completa) | La ventana mostrada empieza en la oración ancla y agrega contexto solo a la derecha (también si el chunk entra completo). El lector usa centrada=True: sin el contexto previo, mdeberta daba s_qa 0 a «¿Qué recargo se cobra según el artículo 4?». Prueba: relacionado no publica respuesta_exacta y lleva el encabezado de no-respuesta. Caracterización: sin cambios de estado; light ahora abre con «El filtro de sedimentos se cambia cada 6 meses» y «El reembolso se paga en un plazo de 10 días hábiles» (antes «Instalación…» y «La empresa responde dentro de 5 días hábiles»). Banco v1.1.0: falsos ok 0 en light y medium; literalidad light 0,50→0,75, medium 0,625→0,875. |
| P8.6 | ✅ | 2026-10-03 | 4 (test_portabilidad; suite completa 488 en P8.5) | test_portabilidad mantiene el caso literal («¿Cuántos meses cubre…?» → ok) y la paráfrasis («¿Cuánto dura la garantía del equipo X100?» → hoy relacionado). La paráfrasis acepta ok o relacionado, pero falla si sus fragmentos o su texto pierden «18 meses». |
| P9.1 | ✅ | 2026-10-03 | 500 (suite completa) | rag/evaluacion/golden.py: leer_csv (BOM, coma o punto y coma, ignora filas vacías de la plantilla), leer_jsonl, leer_squad2 (is_impossible → sin_respuesta; extensiones rag_tipo/rag_subtipo/rag_par), ubicar_respuesta (literal y con espacios colapsados, mapeo a offsets originales, alias de documento, aviso si se repite), oracion_de (evidencia = oración de la línea), separar_dev_test (50/50 estratificado, orden por hash), avisos_de_tamano (mínimo 30, balance 30%, sin trampa_mismo_tema, «no certifica» si < 59 respondibles en test) y a_banco (exacta/parafrasis por s_cov ≥ 0,6; junta todos los errores con su fila). CasoEvaluacion gana subtipo y par opcionales. ambigua → necesita_aclaracion (formato del banco); su métrica se revisa en P10.1. |
| P9.2 | ✅ | 2026-10-03 | 506 (suite completa) | generar_plantilla(corpus, paquete, n) en rag/evaluacion/golden.py, sin modelos ni LLM. Secciones = bloques consecutivos con la misma ruta, partidas a 1200 caracteres. TF-IDF con IDF sobre las secciones (no se recibe est: con IDF de chunks/documentos los términos clave salían como cifras); se omiten cifras sueltas. MMR elige secciones diversas y garantiza primero una por documento. ~35% de trampas (7 de 20) en pares mínimos: id r001 + t001 (subtipo trampa_mismo_tema, par=r001, mismo documento y fragmento). Se mantiene par en vez de un pair_id nuevo: ya sobrevive al import desde P9.1. 3 conversacionales completas por idioma (verificadas contra los patrones del paquete). escribir_plantilla escribe golden.csv (UTF-8 con BOM) y LEEME.txt. golden_instrucciones pasa a ser un bloque estructurado (leeme, nota_respondible, nota_trampa, conversacionales) en es, en y pt, con ejemplos bien/mal de trampa y el tamaño necesario para certificar. Importar: una trampa cuyo par quedó sin completar es aviso (se mide sin par), no error. |
| P9.3 | ✅ | 2026-10-03 | 514 (suite completa) | rag golden plantilla [--n] [--force] | importar <csv|jsonl|json> | validar | exportar --formato squad2|csv [--salida]. CLI fina → rag/aplicacion/golden.py → rag/evaluacion/golden.py; sin modelos ni red. plantilla no pisa golden.csv sin --force (convención de 'rag init --force'). importar: lista todos los errores con archivo:fila y no escribe nada si hay errores; banco con escritura atómica (temporal + os.replace, manifiesto al final) y procedencia {formato, archivo} sin fecha. validar: solo lectura; detecta corpus cambiado (hash), documento faltante y offsets. SQuAD 2.0: context = párrafo de la evidencia, answer_start relativo y verificado; al importar, context+answer_start fijan la ocurrencia. Extensión opcional 'rag' {tipo, subtipo, par, notas}: par y subtipo sobreviven; un SQuAD externo sin ella importa igual. Pérdidas documentadas: conversacionales no se exportan; premisa_falsa/ambigua son is_impossible en el estándar (el tipo vuelve por la extensión); trampas sin par van con context vacío. Ida y vuelta por squad2 = mismo contenido QA (plan actualizado); por CSV = mismo banco. Desvíos: (1) menos de 30 filas pasa a aviso, no error (la falta de muestra no es error; la ida y vuelta exigida usa 2 filas); (2) las instrucciones de la plantilla van en la columna 'instrucciones' (se ignora al importar), así 'notas' queda libre; (3) validar_evidencias_contra_corpus junta todos los errores. |
| P9.4 | ✅ | 2026-10-03 | 527 (suite completa) | tests/datos/banco_universal/{es,en,pt}: 90 casos (30 por idioma: 10 exactas, 5 paráfrasis, 10 trampas mismo tema en par, 3 fuera de dominio, 1 premisa falsa, 1 ambigua), 5 microdocumentos por idioma, 10 capacidades. Multilingüe, no cross-lingual. Fuentes (corpus/*.md, casos.yaml) → construir.py → banco.jsonl + manifiesto.json en el formato interno; una prueba verifica que coinciden. Manifiesto con uso: regresion; exigir_calibrable lo rechaza. Línea base en linea_base.json (light y medium; tabla en Hallazgos). Prueba lenta: falla si hay un falso ok nuevo respecto de la línea base (no exige 0: los 4 de hoy van a P10 sin corregir). Desvío: 1 premisa + 1 ambigua por idioma. linea_base.evaluar restaura el idioma y el perfil globales que rag indexar cambia (contaminaba las pruebas posteriores). |
| P10.1 | ✅ | 2026-10-03 | 545 (suite completa) | metricas.py: SenalesObservadas (s_ret, s_oov, s_foco, s_cov, s_lex, acuerdo, s_rr, s_qa, dominio tal como decidió la política; None si no aplica). ObservacionEvaluacion gana idioma, regla, senales y respuesta_exacta, que evaluar_backend_activo llena desde el diagnóstico real. FilaCaso (vista por caso). ResumenCobertura: cobertura directa y relacionada, recall sin respuesta, falsos ok, tasa sobre no respondibles y directas sin literal. Global, por grupo (exacta, parafrasis, trampa_mismo_tema, sin_respuesta, fuera_de_dominio, premisa_falsa, ambigua) y por idioma, en ReporteMetricas.cobertura. riesgo_aceptadas (n = respuestas ok, x = falsos ok + directas sin literal) con cota_superior_clopper_pearson (CDF binomial + bisección, sin SciPy) y n_minimo. Falso ok unificado: no respondible y no conversacional. linea_base.py resume desde el reporte formal y coincide con la línea base de P9.4. Sin cambios en política, umbrales ni modelos. Definiciones, referencias y hallazgos en Hallazgos. Una corrida completa tuvo 1 fallo intermitente que no se reprodujo (ni aislado ni en una segunda corrida completa). |
| P10.2 | ✅ | 2026-10-03 | 566 (suite completa) | Auditoría: acuerdo nunca se calculaba (lexico.acuerdo sin llamadas; su condición en light era inerte); se retira de cascada_v1 y de los documentos, sin cambio de comportamiento, y queda como candidata para P10.4. s_lex es señal interna de selección y no se agrega. regla_cascada (pura) la comparten política y calibración; no regresión: re-decidir con los umbrales del perfil reproduce cada estado (sintético y 180 casos del banco universal). τ_oov se separa en oov_dominio y oov_ok (0,6 ambos; un oov anterior vale para los dos; corregido que un oov en ajustes_perfil quedaba ignorado). Línea base universal sin cambios. calibracion.py: calibrar(banco, observaciones, umbrales_perfil, alfa, confianza) con exigir_calibrable; búsqueda conjunta (foco, oov_ok) × barrido de ok sobre valores observados en dev; elige la cobertura directa máxima con cota CP ≤ α y verifica la combinación con la política completa; test se reporta aparte. Estados calibrado/muestra_insuficiente/sin_umbral_seguro (los dos últimos mantienen los umbrales del perfil). escribir_calibracion/cargar_calibracion; configuracion/calibracion.py valida la procedencia (perfil, modelos, hash_corpus del índice) y construir_motor solo aplica estado calibrado. Se retiran calibrar_umbral y CalibracionDev. Análisis del banco universal y hard negatives inseparables en Hallazgos. |
| P10.3 | ✅ | 2026-10-03 | 576 (suite completa, incluye la lenta de medium) | rag calibrar [--alfa 0.05] [--aplicar]: CLI fina → calibrar_proyecto (aplicacion/evaluacion.py) → calibrar (P10.2, sin cambios). Valida alfa en (0,1); hash_corpus del manifiesto del índice activo (sin índice: «rag indexar»); golden vigente y calibrable (corpus cambiado: «rag golden validar»; uso regresion: rechazado); evalúa con evaluar_backend_activo (inyectable). Sin --aplicar no escribe; con --aplicar escribe calibracion.yaml en cualquier estado, solo «calibrado» se habilita. Salidas: CALIBRADO 0, MUESTRA_INSUFICIENTE 0, SIN_UMBRAL_SEGURO 1, errores 1. 9 pruebas de CLI con motor falso (tres estados, procedencia del índice, errores) y 1 lenta: medium sobre el banco v1.1.0 importado da muestra_insuficiente con el hash del índice real. Guía golden.md con la sección Calibrar. Hallazgos (desempate y estratificación del split) en Hallazgos. |
| P10.4 | ✅ | 2026-10-03 | 586 (suite completa) + benchmark real bm25/light/medium/heavy | rag benchmark --banco M [--banco…] --perfiles bm25,light,medium,heavy [--experimentos]: proyecto temporal por perfil y banco (idioma del manifiesto), evaluar_backend_activo con motor calentado, métricas de reporte_cobertura, p50/p95 por consulta y por etapa, presupuesto, modelos (parámetros y ONNX en disco, no RAM) e indexado aparte. Escribe golden/reportes/benchmark-perfiles.{json,md} y un artefacto por perfil y banco para rag comparar (etiquetado por perfil). Salida ≠ 0 si un perfil excede el presupuesto o, con un banco de evaluación, da falsos ok; las variantes no cortan. Se corrigen el perfil bm25 (era light: ahora recuperacion_modo dispersa, modo dispersa en buscar y en el retriever, seleccionable para diagnóstico pero no en rag init), el idioma en el manifiesto del banco y la limpieza en Windows. Experimentos: medium τ_ok 0,85 → POSPONER (falsos ok 3→1, misma cobertura); acuerdo → DESCARTAR (sin efecto, +4,6 ms p95). Tabla, hallazgos y decisiones en Hallazgos. |
| P10.5 | ✅ | 2026-10-03 | 586 (suite completa; sin el código descartado) | texttiling_v1 implementado temporalmente en ingesta/chunking.py (párrafos por sección; coseno TF-IDF entre ventanas de hasta 2 párrafos; corte si sim < media − desv/2 del documento o al superar 256 palabras; sin cruzar secciones ni solape) y comparado con CH-F256 (actual) y CH-SEC (control) en bm25/light/medium/heavy sobre v1.1.0 y bm25/light/medium sobre el universal, con índices separados. DESCARTADO: da los mismos estados que CH-SEC (la cohesión solo agregó 1 frontera en 4 bancos) y frente a CH-F256 sube los falsos ok (v1.1.0 medium 0→1, universal light 1→2). Se borraron la estrategia, sus pruebas y el parámetro interno del benchmark; tablas, casos y decisión en Hallazgos. |
| P11.1 | ✅ | 2026-10-03 | 596 (suite completa, incluidas las lentas) | rag/cli.py (925 líneas) → paquete rag/cli/: __init__.py (registro_de_comandos explícito, construir_parser, main), __main__.py, base.py (Comando con registrar/ejecutar, Grupo, registrar) y comandos/{proyecto,corpus,consulta,golden,evaluacion,operacion,web}.py con 20 Commands. Sin módulo puente; el script sigue en rag.cli:main. Las 24 pantallas de --help quedaron idénticas. La lógica pasó a aplicacion/: proyecto (inicializar_proyecto, completar_proyecto_existente, guardar_snapshot, migrar_proyecto_activo y lecturas para el servicio), corpus.py nuevo (archivos_de_ruta, cargar_documentos, indexar_proyecto), evaluacion (comparar_reportes), benchmark (benchmark_perfiles), golden (ErrorGolden), consulta (Motor y sus errores, construir_motor_del_proyecto). servicio/api.py dejó de importar configuracion, consulta y lenguaje. tests/test_arquitectura.py: regla cli/servicio → solo aplicacion, nucleo y recursos, con prueba sintética. Pruebas nuevas: entrypoint, importación sin efectos, registro de los 20 comandos, despacho al caso de uso, código de salida, python -m rag.cli, y ayuda en todo el árbol. |
| P11.2 | ✅ | 2026-10-04 | 610 (14 nuevas) | Commit ee7e78d. rag perfil mostrar / cambiar; estado del índice por manifiestos (modelo, dimensión, payload) y de la calibración con motivo_no_aplicable; no descarga, indexa, calibra ni borra; conserva ajustes_perfil, índice y calibracion.yaml. |
| P11.3 | ✅ | 2026-10-04 | 627 (17 nuevas) | Commit 5e0ffa6. rag modelos listar / descargar / verificar / exportar. Caché global y descarga simulada en las pruebas; verificar hace una inferencia mínima por modelo; exportar importa torch/optimum solo en su flujo y sin el extra indica pip install "rag-extractivo[exportar]". ruta_local exige todos los archivos del ModeloSpec. Abierto: el extra [exportar] no fija versiones compatibles (optimum 2.1 + transformers 5.17 fallan). |
| P11.4 | ✅ | 2026-10-04 | 647 (20 nuevas) | rag doctor: ReporteDoctor con 9 chequeos ordenados (configuración, perfil, idioma, stemmer, modelos, índice, calibración, golden, CORS) en ok/aviso/error/no_evaluado; acumula fallos, cada error trae acción y el resumen no las repite. Sin red, sin ONNX, sin escribir. Índice por manifiesto + stemmer + colección Qdrant + hash del corpus recalculado sin modelos. Calibración y golden opcionales (avisos). Idioma sin paquete = error: el respaldo del plan no existe en el código. |
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

- **P8.2 — `s_ret` crudo no sirve.** El coseno de e5 vale ~0,72-0,88 incluso con
  preguntas ajenas. `ModeloSpec.coseno_piso` (0,7 en e5) lo normaliza:
  `s_ret = (cos − piso)/(1 − piso)`. Los umbrales de light (dominio/relacionado 0,33,
  ok 0,5) equivalen a los cosenos 0,80/0,85 que usaba `layered_v1`.
- **P8.2 — `s_rr` no es una escala absoluta.** mmarco da 0,08 a «¿Cuánto dura la
  garantía?» con el pasaje correcto. La señal de dominio es max(`s_ret`, `s_rr`):
  el reranker confirma el dominio pero no lo niega. Revisar con bge (heavy) en P10.
- **P8.2 — falso `ok` conocido (medium):** «¿Qué incluye la garantía?» → «24 meses»
  (`s_qa` 0,97; «incluye» no está en el corpus y `terminos_foco` solo toma términos
  presentes). Light da relacionado. Lo cubre el banco trampa (P8.4) y se decide en
  P10 entre: foco con términos ausentes, `τ_ok` calibrado, o concordancia/heavy.
- **P8.2 — corpus sintético diminuto.** Con 2 chunks el IDF es degenerado (ausente
  1,79 vs. presente 0,18-0,69): `s_oov` sale alto (0,7-0,8) en preguntas del dominio.
  No ajustar `τ_oov` con este corpus; calibrar con el golden del cliente (P9-P10).
- **P8.4 — `ok` exige `s_oov < τ_oov`.** Ninguna señal léxica separa «¿Cuándo vence
  la garantía?» (correcta) de «¿Qué incluye la garantía?» (trampa): mismo `s_oov` 0,72,
  `s_cov` 0,28 y el mismo tramo del lector («24 meses…», `s_qa` 0,99/0,97). Se eligió
  precisión: si casi todo el vocabulario de la pregunta falta en el corpus, la
  respuesta es `relacionado`, que igual muestra el pasaje. Costo en corpus
  diminutos: «¿Cuánto dura la garantía del X100?» frente a «cubre 18 meses» queda
  en relacionado (por eso cambió la pregunta de `test_portabilidad`). P10 decide
  si separar `τ_oov` de dominio y de ok, calibrado con Clopper-Pearson.
- **P8.4 — light muestra contexto antes que la respuesta.** La ventana de 500
  caracteres crece hacia la izquierda desde la oración ancla. A «¿En cuántos días
  hábiles se paga el reembolso?» responde empezando por «La empresa responde dentro
  de 5 días hábiles.» (literalidad 0,5). La decisión ya usa la oración ancla
  (`oracion_foco` en el diagnóstico); falta mostrarla primero, sin expandir hacia la
  izquierda, como ya ocurre cuando la ancla es una entidad. Pendiente para P10
  (métrica de literalidad).
- **Revisión externa (2026-10-03, Codex), adoptada en el plan.**
  - Restricción de producto: no se entrena nada (README).
  - Estadística: con 0 errores hacen falta ≥ 59 aceptados para certificar
    α = 0,05. Tres estados de calibración (comandos-y-golden.md §4.1).
  - Tareas nuevas: P8.5 (presentación), P8.6 (paráfrasis en pruebas) y P9.4
    (banco universal es/en/pt, solo CI).
  - Pares mínimos en el golden; `oov_dominio`/`oov_ok` separados en P10.2.
  - Heavy conserva mdeberta (modelos-y-perfiles.md).
  - El verificador de respuesta no se evalúa antes de P10.
- **P9.4 — línea base del banco universal** (90 casos: 30 por idioma, 45 sin
  respuesta; `tests/datos/banco_universal/linea_base.json`). Las respondibles
  dan `ok` o `relacionado`, nunca abstención; toda respuesta `ok` muestra la
  respuesta literal.

  | Perfil | Falsos ok (de 45) | Exactas con ok | Paráfrasis con ok | Respondibles en relacionado | Trampas rechazadas |
  |---|---|---|---|---|---|
  | light | 1 (es 1, en 0, pt 0) | 22/30 (es 8, en 5, pt 9) | 0/15 | 23/45 | 29/30 |
  | medium | 3 (es 2, en 1, pt 0) | 30/30 | 2/15 (es 1, en 1, pt 0) | 13/45 | 28/30 |

  Falsos ok, que van a P10 sin corregir:
  - light `es-trampa-009`: «¿Cuántas muestras se rechazan cada mes?» →
    «Una muestra se rechaza si el tubo llega sin etiqueta…».
  - medium `es-trampa-001`: «¿Cuánto cuesta extender la garantía…?» →
    «…dura 24 meses…».
  - medium `en-trampa-004`: «Who approves the refund request?» → «The refund
    is paid within 10 business days after the request is approved».
  - medium `es-ambigua-001`: «¿Cuánto dura?» → «…dura 24 meses…».

  Los cuatro son la clase difícil: la misma entidad, un pasaje tentador y otra
  relación pedida (o una pregunta ambigua respondida con la primera duración).
- **P9.4 — las paráfrasis casi nunca dan ok** (light 0/15, medium 2/15).
  Quedan en `relacionado`, que muestra el pasaje correcto. Es el costo de
  `s_oov < τ_oov` y de las señales léxicas. P10.2 mide si `oov_ok` separado
  sube esta cobertura sin falsos `ok`.
- **P9.4 — light en inglés:** 5/10 exactas con ok, frente a 8-9 en es y pt.
  Revisar en P10 el stemmer, las stopwords del paquete `en` y el piso de
  coseno.
- **P9.4 — fuera de dominio en portugués:** un caso da `relacionado` en light
  y en medium, en vez de abstención. No es falso ok.
- **P9.4 — i18n de la cita:** en inglés la respuesta cita «(Fuente: …)». La
  etiqueta de la fuente no sale del paquete de idioma. Va junto con los
  mensajes de la CLI (P11/P13).
- **P10.1 — definiciones de las métricas** (`rag/evaluacion/metricas.py`).
  - **Falso ok:** respuesta directa (`respuesta_directa`/`respuesta_parcial`)
    en un caso no respondible: sin_respuesta, trampa_mismo_tema,
    fuera_de_dominio, premisa_falsa o ambigua. Las conversacionales no
    cuentan; es la misma definición en las métricas viejas y en las nuevas.
  - **Directa sin literal:** una respondible contestada sin mostrar su
    respuesta literal. Es otro error, contado aparte del falso ok.
  - **`tasa_falsos_ok_no_respondibles`** = falsos ok / no respondibles:
    «¿en cuántos casos donde no debía contestar, contestó?».
  - **`riesgo_aceptadas`** = P(error | el sistema respondió ok).
    - `n` = respuestas directas emitidas (no el total del banco).
    - `x` = falsos ok + directas sin literal.
    - Lleva su cota de Clopper-Pearson; `None` si n = 0.
  - **`cobertura_directa`** = respondibles con ok / respondibles.
    **`cobertura_relacionada`** = respondibles en relacionado / respondibles.
- **P10.1 — Clopper-Pearson.**
  - `cota_superior_clopper_pearson(0, 50, 0.95)` = 0,05816.
  - Referencia externa: R `binom.test(1, 10)` da el intervalo exacto al 95%
    [0,002528579; 0,445016117]. Su límite superior es la cota unilateral al
    97,5%, y la función da 0,4450161 (verificado también con el cuantil Beta
    de SciPy, sin usarlo en el código).
  - `n_minimo(0, 0,05)` = 59, porque n = 58 da 5,03%. Sale de la función, no
    de una constante.
- **P10.1 — banco universal con las métricas formales** (es+en+pt; coincide
  con `linea_base.json`). Ninguna respondible queda sin respuesta.

  | Perfil | Cobertura directa | Exacta | Paráfrasis | Relacionada | Falsos ok (de 45) | Trampas con falso ok | Riesgo aceptadas x/n (observado; cota 95%) |
  |---|---|---|---|---|---|---|---|
  | light | 22/45 (0,489) | 22/30 | 0/15 | 23/45 | 1 | 1/30 | 1/23 (0,043; 0,190) |
  | medium | 32/45 (0,711) | 30/30 | 2/15 | 13/45 | 3 | 2/30 | 3/35 (0,086; 0,207) |

  Por idioma, cobertura directa:
  - light: es 0,533, en 0,333, pt 0,600.
  - medium: es 0,733, en 0,733, pt 0,667.

  Estas cotas validan la herramienta. **No certifican** a ningún cliente: el
  banco universal no representa su corpus.
- **P10.1 — señales de los falsos ok conocidos** (`τ_ok` 0,8, `τ_foco` 0,5).
  - light `es-trampa-009`: `ok_lexico`, `s_ret` 0,515, `s_oov` 0,
    `s_foco` 0,5 (en el umbral), `s_cov` 0,667.
  - medium `es-trampa-001`: `ok_lector`, `s_qa` 0,833, `s_oov` 0,473,
    `s_cov` 0,527, `s_rr` 0,457.
  - medium `en-trampa-004`: `ok_lector`, `s_qa` 0,821, `s_oov` 0, `s_cov` 1,
    `s_rr` 0,159.
  - medium `es-ambigua-001`: `ok_lector`, `s_qa` 0,9999, `s_oov` 0,
    `s_rr` 0,088.

  Tres de los cuatro están a menos de 0,04 de su umbral (s_qa 0,82/0,83;
  s_foco 0,5). Lo usa P10.2.
- **P10.1 — `acuerdo` y `s_lex` nunca llegan a la política.**
  - `acuerdo` (denso vs. BM25) siempre es `None`, así que la condición
    «acuerdo ≥ 0,5» de light es inerte.
  - `s_lex` solo existe por oración, en la selección.

  No se corrige aquí: se decide en P10.2.
- **P10.1 — light en inglés:** de las 5 exactas que no dan ok, 4 tienen
  `s_oov` 0 y `s_cov` entre 0,67 y 1, pero `s_ret` normalizado entre 0,40 y
  0,50 (< τ_ok 0,5). La quinta tiene `s_cov` 0,53 (< τ_cov 0,6). La pérdida
  viene del coseno de e5 en inglés, no del stemmer. Se analiza en P10.2 o
  después.
- **P10.2 — auditoría de `acuerdo`.**
  - `rag/lenguaje/lexico.py::acuerdo()` existe y está probada, pero **ninguna
    etapa la llama**. No era un valor calculado que se perdía en el camino:
    nunca se calculó.
  - Calcularla exige dos búsquedas más por consulta (top-3 solo denso y solo
    BM25) y cambiaría las decisiones de light, así que no es plumbing.
  - Como la condición «acuerdo ≥ 0,5» siempre fue inerte (`None` pasaba),
    todo lo medido en P8-P10.1 se hizo sin ella. Se retira de `cascada_v1` y
    de la documentación, sin cambio de comportamiento: la caracterización, la
    línea base universal y la re-decisión de los 180 casos no cambian.
  - Cablearla queda como mejora candidata, a evaluar con evidencia en P10.4.
- **P10.2 — auditoría de `s_lex`:** es una señal interna de selección. Ordena
  oraciones, elige la ancla y la ventana del lector; el plan nunca la usó para
  decidir. Su `None` a nivel de pregunta es correcto y no se agrega a la
  política.
- **P10.2 — `τ_oov` separado.**
  - `oov_dominio` decide fuera de dominio: `s_oov ≥ τ` y dominio < `τ_dominio`.
  - `oov_ok` es la condición para responder directo: `s_oov < τ`.
  - Los perfiles traen ambos en 0,6. Un `oov` anterior (en `ajustes_perfil`,
    en una calibración o en el constructor de la política) vale para los dos
    vía `normalizar_umbrales`, sin intervención del cliente.
  - Defecto encontrado y corregido: un `oov` anterior en los ajustes del
    proyecto quedaba ignorado porque el perfil ya traía las claves nuevas.
    Ahora los ajustes se normalizan antes de fusionar.
- **P10.2 — política pura.** `regla_cascada(senales, umbrales, premisa_falla)`
  es la regla de `cascada_v1`; la usan producción y calibración. Prueba de no
  regresión: con los umbrales del perfil, re-decidir las observaciones
  reproduce exactamente cada estado (10 casos sintéticos y los 90 × 2 perfiles
  del banco universal).
- **P10.2 — calibración** (algoritmo en comandos-y-golden.md §4.2).
  - Los estados son calibrado, muestra_insuficiente y sin_umbral_seguro.
  - Solo `dev` elige los umbrales; `test` se reporta aparte.
  - `calibracion.yaml` guarda la procedencia (perfil, modelos, `hash_corpus`
    del índice y banco) y solo se aplica en estado calibrado con la misma
    procedencia (`construir_motor` relee el perfil con el hash del índice
    abierto).
  - Se retiran `calibrar_umbral`, `CalibracionDev` y `calibracion_dev` de los
    artefactos: solo calibraban el coseno crudo.
- **P10.2 — análisis sobre el banco universal** (90 casos; no se usa para
  elegir umbrales del producto). Con los defaults, la línea base no cambió.

  | Perfil | Configuración (análisis) | Cobertura directa | Paráfrasis | Falsos ok (trampas) | Riesgo x/n |
  |---|---|---|---|---|---|
  | medium | defaults | 0,711 | 2/15 | 3 (2) | 3/35 |
  | medium | oov_ok = 1,0 | 0,844 | 8/15 | 8 (5) | 8/46 |
  | medium | ok = 0,85 | 0,711 | 2/15 | 1 (0) | 1/33 |
  | medium | ok = 0,85 + oov_ok = 1,0 | 0,844 | 8/15 | 5 (2) | 5/43 |
  | light | defaults | 0,489 | 0/15 | 1 (1) | 1/23 |
  | light | ok = 0,40 | 0,622 (exacta 28/30) | 0/15 | 4 (3) | 4/32 |

  - `explorar_umbrales` da **muestra_insuficiente**: a lo más 13 (light) y 18
    (medium) respuestas sin error en dev, frente a las 59 necesarias. Es lo
    esperable de un banco de regresión.
  - Separar `oov_ok` de `oov_dominio` no cambia el recall de fuera de dominio
    (1,0 en todas las filas). En este banco los fuera de dominio ya tienen
    dominio bajo, así que unido y separado dan lo mismo. La separación sirve
    cuando un golden muestre paráfrasis con `s_oov` alto y dominio alto.
  - **Paráfrasis en light:** quedan bloqueadas por `s_cov < τ_cov` (0-0,42),
    no por `s_oov`. Una paráfrasis, por definición, no repite el vocabulario.
    Light no puede responderlas directo sin bajar `τ_cov`, que no se calibra.
    Es una limitación estructural del perfil léxico.
  - **Light en inglés:** bajar `τ_ok` a 0,40 sube las exactas de 22 a 28/30,
    pero agrega 3 falsos ok. La hipótesis (el umbral es alto) se confirma,
    pero el costo es real: lo decide la calibración con un golden suficiente.
  - **medium `ok` = 0,85:** elimina `es-trampa-001` (s_qa 0,83) y
    `en-trampa-004` (0,82) sin perder cobertura en este banco. Es una
    hipótesis para el golden del cliente, no un valor del producto.
- **P10.2 — hard negatives inseparables con las señales actuales.**
  - `es-ambigua-001` («¿Cuánto dura?»): `s_qa` 0,9999 y `s_oov` 0. Ningún
    `τ_ok` lo separa sin perder todas las respuestas.
  - `en-trampa-004` («Who approves the refund request?»): `s_oov` 0 y
    `s_cov` 1. Solo `τ_ok` lo separa, y por 0,02. `s_oov` no puede resolver
    estos casos: la relación pedida es otra con el mismo vocabulario.
  - Relajar `oov_ok` en medium suma 3 trampas más con falso ok: el costo de
    cobertura de paráfrasis está en esos hard negatives.
- **P10.3 — `rag calibrar [--alfa 0.05] [--aplicar]`.**
  - CLI fina → `aplicacion/evaluacion.py::calibrar_proyecto` →
    `evaluacion/calibracion.py::calibrar`.
  - Orden: perfil (sin calibración previa) → `hash_corpus` del manifiesto del
    índice que abre el proyecto (sin índice: error con «rag indexar») → golden
    vigente (`_cargar_banco_vigente`: si el corpus cambió, error con «rag golden
    validar») → `exigir_calibrable` → `evaluar_backend_activo` (inyectable) →
    `calibrar`.
  - Procedencia: perfil y modelos del perfil efectivo, `hash_corpus` del
    índice, `hash_banco` del golden importado.
  - Salidas: CALIBRADO y MUESTRA_INSUFICIENTE devuelven 0 (no es un fallo:
    siguen los umbrales del perfil). SIN_UMBRAL_SEGURO y los errores
    operacionales devuelven 1, igual que la guardia de `rag evaluar`.
  - `--aplicar` escribe `calibracion.yaml` en cualquier estado; solo
    «calibrado» se habilita.
  - Prueba lenta: medium sobre el banco sintético v1.1.0 (importado con `rag
    golden importar`, uso evaluación) da **muestra_insuficiente**: 1
    respuesta directa sin error en dev, frente a 59. Es lo correcto para 27
    casos; no se forzó «calibrado».
- **P10.3 — hallazgo: el desempate mueve umbrales que dev no informa.** Si
  dev no distingue valores (p. ej. todos los `s_oov` son 0), el desempate
  «más estricta» de P10.2 lleva `oov_ok` de 0,6 a ~0 y `foco` a 1,0 sin que
  los datos lo pidan, y eso puede bajar la cobertura fuera de la muestra.
  Propuesta para la próxima iteración de calibración: ante empate, preferir
  el valor del perfil. No se cambió en P10.3 (era cambiar el algoritmo).
- **P10.3 — hallazgo: el split estratifica por tipo público.** Las respondibles
  se separan como un solo grupo, sin distinguir exacta de paráfrasis. En el
  banco v1.1.0 las 3 exactas quedaron en test. Con bancos chicos conviene
  estratificar también por categoría interna (P9.1, a revisar).
- **P10.4 — benchmark por perfiles.** Banco universal es+en+pt (90 casos: 45
  respondibles y 45 no respondibles), CPU local, defaults sin calibrar. Comando:
  `rag benchmark --banco …/es --banco …/en --banco …/pt --perfiles
  bm25,light,medium,heavy --experimentos`; salida 0. Es un banco de
  regresión: **no certifica** ningún perfil.

  | Perfil | Cobertura directa | Exactas | Paráfrasis | Falsos ok | Trampas con falso ok | Riesgo x/n | p50 ms | p95 ms | Presupuesto |
  |---|---|---|---|---|---|---|---|---|---|
  | bm25 | 22/45 | 22/30 | 0/15 | 1/45 | 1/30 | 1/23 | 58 | 80 | 100 ✓ |
  | light | 22/45 | 22/30 | 0/15 | 1/45 | 1/30 | 1/23 | 59 | 85 | 150 ✓ |
  | medium | 32/45 | 30/30 | 2/15 | 3/45 | 2/30 | 3/35 | 595 | 815 | 1000 ✓ |
  | heavy | 31/45 | 29/30 | 2/15 | 2/45 | 2/30 | 2/33 | 1883 | 2130 | 4000 ✓ |
  | medium+ok0,85 (exp.) | 32/45 | 30/30 | 2/15 | 1/45 | 0/30 | 1/33 | 595 | 815 | — |
  | light+acuerdo (exp.) | 22/45 | 22/30 | 0/15 | 1/45 | 1/30 | 1/23 | 62 | 89 | — |

  - Rechazo: fuera de dominio y premisa falsa 100% en todos. Ninguna
    respondible queda sin respuesta, y ninguna directa sale sin la respuesta
    literal.
  - Por idioma (exactas con ok): light/bm25 es 8, en 5, pt 9; medium 10 en los
    tres; heavy es 9, en 10, pt 10.
  - Costo: los tamaños son de los archivos ONNX en disco, no RAM (no se mide).
    - light: e5-small, 118 M parámetros, 470 MB.
    - medium: lo de light + mmarco (118 M, 119 MB) + mdeberta (278 M,
      1114 MB).
    - heavy: e5-base (278 M, 1110 MB) + bge-reranker-v2-m3 (568 M, 571 MB) +
      mdeberta (1114 MB).
    - p95 por etapa: medium reranking 293 y lectura 513 ms; heavy reranking
      1207 y lectura 874 ms.
  - Latencia frente a P7.6 (otro banco): light 85 contra 82 ms, medium 815
    contra 886, heavy 2130 contra 2221. Sin regresiones.
  - Falsos ok por perfil:
    - bm25 y light: `es-trampa-009`.
    - medium: `es-trampa-001`, `en-trampa-004` y `es-ambigua-001`.
    - heavy: `es-trampa-001` y `en-trampa-004`.
- **P10.4 — qué se aprendió.**
  - **bm25 frente a light:** iguales en todo. Con 5 microdocumentos por idioma,
    los candidatos cubren casi todo el corpus con cualquier recuperación. El
    banco universal no tiene potencia para medir el aporte del denso: hace
    falta un corpus grande.
  - **light frente a medium:** el lector y el reranker suben las exactas de 22
    a 30 de 30 (el inglés de 5 a 10) y las paráfrasis de 0 a 2 de 15. Cuestan
    unos 730 ms más de p95 y 2 falsos ok más (trampas con `s_qa` 0,82 y 0,83).
  - **medium frente a heavy:** heavy corrige «¿Cuánto dura?» pero no las dos
    trampas del mismo tema. Pierde una exacta en español y cuesta 2,6 veces el
    p95. Con esta evidencia no compra seguridad material.
  - Las dos trampas (`es-trampa-001` y `en-trampa-004`) siguen inseparables
    incluso en heavy: queda evidencia para considerar otra señal **después**
    de P10, con las reglas de modelos-y-perfiles.md (no se implementa).
- **P10.4 — decisión: `medium` con `τ_ok` = 0,85 → POSPONER.** Baja los
  falsos ok de 3 a 1 (trampas de 2 a 0) con la misma cobertura (32/45) y la
  misma latencia. No se cambia el default: el umbral de cada cliente lo elige
  `rag calibrar`. Queda como candidato para una decisión posterior con más
  bancos.
- **P10.4 — decisión: `acuerdo` → DESCARTAR como señal de la política.** Los
  falsos ok, la cobertura y las trampas no cambian (1/45; `es-trampa-009` ya
  tiene acuerdo ≥ 0,5). Agrega dos búsquedas por pregunta: +3,4 ms en p50 y
  +4,6 ms en p95, y light sigue dentro de los 150 ms. Sin mejora medible, no
  justifica el costo. `lexico.acuerdo()` se conserva porque la usa el
  experimento del benchmark. Volver a medir con un corpus grande, donde denso
  y BM25 sí pueden discrepar.
- **P10.4 — defectos del benchmark corregidos.**
  - `bm25.yaml` era idéntico a light: mismas etapas y recuperación híbrida.
  - bm25 no se podía seleccionar (`AsistenteConfig.perfil`).
  - No existía el modo `dispersa`, ni en `buscar` ni en `RetrieverQdrant`.
  - Todos los artefactos se llamaban `qdrant_hibrida` y `rag comparar` los
    rechazaba; ahora se etiquetan por perfil.
  - En Windows, la limpieza del temporal con Qdrant abierto tapaba el error
    real.
  - De las 4 corridas reales, 2 fallaron antes de los arreglos y 1 más cuya
    salida perdí por un filtro de `grep`; no se reprodujo. La corrida de la
    tabla terminó con salida 0.
- **P10.5 — experimento `texttiling_v1` → DESCARTADO** (el código se borró).
  - **Implementación temporal:** una estrategia más en `ingesta/chunking.py`.
    - Párrafos de una sección como unidades; las secciones siempre cortan.
    - Coseno TF-IDF entre hasta 2 párrafos a cada lado de cada hueco
      (`terminos`, `tfidf_vector`, `coseno`, IDF local del documento).
    - Corta si `sim < media − desviación/2` de los huecos del documento (el
      umbral de Hearst, sin mirar el golden), o si se superan 256 palabras.
      Nunca parte un párrafo y no tiene solape.
    - Una ventana simétrica sobresegmentaba las secciones homogéneas y se
      descartó en las pruebas unitarias.
  - **Comparación:** mismos modelos, umbrales por defecto, hardware y
    preguntas, con un índice separado por variante. Se compara contra
    `CH-F256` (actual: 256 palabras, solape 15%, cruza secciones) y `CH-SEC`
    (control existente: un chunk por sección).
  - **Chunks:**

    | Banco | CH-F256 | CH-SEC | texttiling_v1 | Fronteras distintas tt/CH-SEC |
    |---|---|---|---|---|
    | v1.1.0 | 2 (media 152 palabras) | 9 (33) | 10 (30) | 1 |
    | universal es/en/pt | 5 cada uno (≈51) | 14 cada uno (≈18) | 14 cada uno (≈18) | 0 |

    Los documentos ya vienen bien seccionados: la cohesión solo agregó **una**
    frontera en los cuatro bancos.
  - **Calidad, banco v1.1.0** (criterio de P10.5; 8 respondibles, 17 no
    respondibles):

    | Chunker | Perfil | Directas | Exactas | Paráfrasis | Falsos ok | p95 ms | Indexado s |
    |---|---|---|---|---|---|---|---|
    | CH-F256 | bm25 / light | 2/8 | 2/5 | 0/3 | 0 | 120 / 113 | 7,6 / 3,7 |
    | CH-F256 | medium / heavy | 4/8 | 4/5 | 0/3 | 0 / 1 | 864 / 2328 | 3,3 / 6,0 |
    | CH-SEC | bm25 / light | 3/8 | 3/5 | 0/3 | 0 | 81 / 85 | 5,2 / 3,0 |
    | CH-SEC | medium / heavy | 4/8 | 4/5 | 0/3 | **1** / 1 | 600 / 2586 | 3,3 / 4,9 |
    | texttiling_v1 | bm25 / light | 3/8 | 3/5 | 0/3 | 0 | 83 / 86 | 4,5 / 3,6 |
    | texttiling_v1 | medium / heavy | 4/8 | 4/5 | 0/3 | **1** / 1 | 655 / **4229** | 3,7 / 8,7 |

  - **Banco universal** (90 casos; heavy no medido):

    | Chunker | bm25 / light directas | medium directas | Falsos ok bm25 / light / medium | Trampas con falso ok medium |
    |---|---|---|---|---|
    | CH-F256 | 22/45 | 32/45 (paráfrasis 2/15) | 1 / 1 / 3 | 2/30 |
    | CH-SEC = texttiling_v1 | 26/45 | 31/45 (paráfrasis 1/15) | 2 / 2 / 2 | 1/30 |

  - **Casos que cambian** (texttiling_v1 frente a CH-F256; idénticos con
    CH-SEC):
    - Mejoras: `exacta_sabados` (v1.1.0, bm25/light); `es-exacta-002`,
      `es-exacta-009`, `en-exacta-008` y `en-exacta-009` (universal,
      bm25/light).
    - Se quitan falsos ok: `es-trampa-009` (light) y `en-trampa-004` (medium).
    - **Nuevos falsos ok:** `trampa_telefono` (v1.1.0, medium),
      `es-trampa-004` y `en-trampa-004` (universal, bm25/light).
    - Empeora: `es-parafrasis-004` (medium, ok → relacionado).
  - **Decisión: DESCARTAR.**
    1. La cohesión no aporta nada medible: texttiling_v1 da exactamente los
       mismos estados que `CH-SEC`.
    2. Frente al chunker actual aumenta los falsos ok: v1.1.0 medium de 0 a 1
       y universal light de 1 a 2. Eso viola la regla de adopción aunque suba
       la cobertura de light.
    3. Heavy llegó a 4229 ms de p95 en esa corrida (probablemente ruido:
       CH-SEC, con los mismos chunks, dio 2586).

    Conclusión: las fronteras estructurales del documento ya hacen
    innecesario TextTiling en este producto. Se borraron la estrategia, sus
    pruebas y el parámetro interno del benchmark; queda solo este registro.
  - **Hallazgo aparte (no se adopta):** cortar por sección (`CH-SEC`) sube las
    exactas de light (+1 en v1.1.0, +4 en universal) pero también sus falsos
    ok. El chunk más chico deja la oración tentadora sola, con más cobertura
    léxica. Es un compromiso de granularidad para medir con el golden de un
    cliente, no un cambio de default.
- **P11.1 — CLI con patrón Command.** `rag/cli.py` (925 líneas) se reemplaza
  por el paquete `rag/cli/`, sin módulo puente:
  - `__init__.py`: `registro_de_comandos()` explícito, `construir_parser()` y
    `main()`.
  - `__main__.py`, para `python -m rag.cli`.
  - `base.py`: `Comando` (`registrar` y `ejecutar`), `Grupo` (subcomandos) y
    `registrar()`.
  - `comandos/`:
    - `proyecto.py`: init y configurar.
    - `corpus.py`: cargar e indexar.
    - `consulta.py`: servir y preguntar.
    - `golden.py`: los cuatro subcomandos.
    - `evaluacion.py`: evaluar, calibrar, comparar y benchmark.
    - `operacion.py`: doctor y snapshot-config.
    - `web.py`: widget tema listar, aplicar y vista-previa, y widget exportar.
  - 20 Commands. `modelos.py` no se crea: no había comandos de modelos y lo
    agrega P11.3.
  - El script sigue siendo `rag.cli:main`.
  - Las 24 pantallas de `--help` (raíz, grupos y hojas) quedaron idénticas a
    las anteriores, comparadas normalizando espacios.
- **P11.1 — lógica que salió de la CLI hacia `aplicacion/`.**
  - `proyecto.py`: `inicializar_proyecto` (y `ProyectoExistente`),
    `completar_proyecto_existente`, `guardar_snapshot` y
    `migrar_proyecto_activo`.
  - `corpus.py` (nuevo): `archivos_de_ruta`, `cargar_documentos` e
    `indexar_proyecto` (y `ErrorConfiguracion`).
  - `evaluacion.py`: `comparar_reportes`.
  - `benchmark.py`: `benchmark_perfiles` (salida por defecto, reportes y
    código de salida).
  - `golden.py` expone `ErrorGolden`.
  - `rag calibrar` ya no importa `EstadoCalibracion` ni `CALIBRABLES`: usa
    `estado.value` y `resultado.calibrables`.
- **P11.1 — `servicio` tenía imports prohibidos** (`api.py` importaba
  `configuracion.carga`, `consulta.motor` y `lenguaje.paquete`). Ahora usa:
  - `aplicacion.consulta`: `Motor`, `MotorNoListo`, `MotorSaturado` y
    `construir_motor_del_proyecto`.
  - `aplicacion.proyecto`: `configuracion_asistente`, `limite_de_peticiones`
    e `interfaz_del_idioma`.

  Los endpoints no cambian.
- **P11.1 — regla de frontera:** `tests/test_arquitectura.py` verifica que
  `cli` y `servicio` solo importen `aplicacion`, `nucleo` y `recursos`. Una
  prueba sintética muestra que detecta un import prohibido, incluso dentro de
  una función. Sin excepciones.
- **P11.1 — defecto evitado:** una función `comandos()` en `rag/cli/__init__.py`
  tapaba el subpaquete `rag.cli.comandos` (rompía `monkeypatch` y los imports
  por ruta). Se llama `registro_de_comandos()`.
- **P11.2 — `rag perfil mostrar | cambiar`.** Los casos de uso viven en
  `aplicacion/proyecto.py` y la CLI solo imprime.
  - **Índice:** el estado sale de los manifiestos. Si existe el manifiesto de
    la colección del perfil, se mira modelo, dimensión y payload. Si no,
    pero hay otro índice del proyecto, es `incompatible`. Si no hay ninguno,
    es `sin_indice`.
  - **Calibración:** usa `motivo_no_aplicable`, la misma regla del motor, con
    el `hash_corpus` del índice compatible.
  - **`es_compatible`** ahora también acepta `dimension`.
  - **`actualizar_dominio`** escribe primero en un temporal y luego hace
    `os.replace`.
  - **Desvío del instructivo:** los mensajes dicen `rag indexar` y no
    `rag indexar --reindexar`, porque ese flag no existe. `indexar` siempre
    reconstruye; `--reindexar` es de `servir`.
- **P11.3 — `rag modelos listar | descargar | verificar | exportar`.**
  Los casos de uso están en `aplicacion/modelos.py`. La prueba mínima está
  en `modelos/verificacion.py` y la exportación en `modelos/exportacion.py`.
  `torch` y `optimum` se importan solo dentro de `exportar`.
  - **Defecto corregido:** `ruta_local` (y con ella `esta_en_cache`) daba
    por presente un modelo con solo el ONNX. Ahora exige todos los archivos
    requeridos del `ModeloSpec` (ONNX, `tokenizer.json`, `config.json`).
  - **Descarga sin red:** con `HF_HUB_OFFLINE=1`, `descargar` falla con
    `ErrorDescarga`, que dice qué hacer.
  - **Defecto abierto (entorno de desarrollo):** el extra `[exportar]`
    (`optimum[onnxruntime]>=1.20`, `torch>=2.2`) no fija una combinación
    compatible. En el venv quedaron optimum 2.1.0 y transformers 5.17, y la
    exportación real falla con `ImportError: get_parameter_dtype`. En
    optimum 2.x, el exportador ONNX está en el paquete aparte
    `optimum-onnx`. El comando lo informa sin traceback y no deja una
    carpeta a medias.
  - **Pendiente:** fijar versiones del extra. Sin cambiar las dependencias,
    sí se verificó la cuantización int8 (`quantize_dynamic`) sobre un ONNX
    sintético.
- **P11.4 — `rag doctor` ampliado.**
  - **Estructura:** `aplicacion/diagnostico.py` devuelve un `ReporteDoctor`
    con `ChequeoDoctor` (clave, estado, mensaje, acciones, detalles y datos)
    en un orden fijo. Los estados son ok, aviso, error y no_evaluado; `listo`
    significa que no hay errores. Está pensado para que `/ready` (P12.4) lo
    reutilice.
  - **Composición:** reutiliza `estado_indice`, `estado_calibracion`,
    `estado_modelos`, `cargar_banco`, `cargar_paquete` y `terminos()`, sin
    reimplementar reglas.
  - **Cambios en las capas reutilizadas:**
    - `perfil_efectivo(ruta_calibracion=None)`: perfil sin calibración.
    - `estado_indice(perfil, stemmer=None)`: pasa el stemmer a
      `es_compatible`. P11.2 sigue llamándolo sin stemmer.
    - `huella_corpus()` en la ingesta: el mismo hash del manifiesto, sin
      modelos ni Qdrant.
  - **Se mantiene** `verificar_indice()` (lo usa `rag servir <carpeta>`).
    Ahora cierra el cliente de Qdrant para liberar el candado del modo local.
  - **Defecto (plan ≠ código, no resuelto):** `lexico-y-multilenguaje.md`
    dice que un idioma sin paquete funciona con las reglas universales y los
    textos de `en`. Pero `cargar_paquete` lanza error, `init` y `configurar`
    lo rechazan, y el motor no arranca. Por eso doctor lo marca como ERROR
    (`rag configurar idioma=<en|es|pt>`). Implementar ese respaldo es otra
    tarea.
  - **Hallazgo:** `rag cargar` no reemplaza un documento que ya está
    cargado. Para que el corpus cambie hay que editar el archivo en
    `documentos/`.
  - **Cambio de semántica:** antes, `doctor` daba 1 en un proyecto recién
    creado sin documentos. Ahora es un aviso y da 0, porque no hay nada que
    indexar.
- **Pendientes de P10.3, siguen abiertos.**
  - La calibración, ante empate, debería preferir el valor del perfil.
  - El split dev/test podría estratificar por exacta/paráfrasis.
- **P8.4 — preguntas en otro idioma que el corpus.** Con `s_oov` 1,0 nunca dan `ok`
  (sin_respuesta o relacionado): el proyecto responde en el idioma de su corpus.
