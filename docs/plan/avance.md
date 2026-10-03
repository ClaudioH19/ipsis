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
| P9.2 | ⬜ | | | |
| P9.3 | ⬜ | | | |
| P9.4 | ⬜ | | | |
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
- **P8.4 — preguntas en otro idioma que el corpus.** Con `s_oov` 1,0 nunca dan `ok`
  (sin_respuesta o relacionado): el proyecto responde en el idioma de su corpus.
