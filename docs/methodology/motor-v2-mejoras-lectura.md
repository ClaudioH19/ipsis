# V2: lectura por campos y separación de ranking/QA

Estado: experimental, 2026-10-11. Implementación posterior al
[diagnóstico](motor-v2-diagnostico.md). Se conserva v1 como motor por defecto.

## Cambios aplicados

1. `campos-1` prepara tablas para el lector mediante etiquetas y valores,
   con mapa de cada copia a su celda, elemento, offsets y localizador XML.
   Incluye contexto previo y encabezados externos de unidades posteriores.
   Los separadores añadidos no tienen referencias fuente. Se publica la
   tabla literal, incluso cuando QA solo propone destacar un porcentaje.
2. QA no desplaza pasajes ni certifica respuestas. El ranking determina el
   orden; `top_k` limita la publicación. Las propuestas QA quedan en
   `answer_blocks[].highlights` como `possible_fragment` con referencias
   separadas. V2 publica `related` y omite `exact_answer` y confianza alta.
   El diagnóstico registra el pasaje principal y la preferencia de QA.
   `ipsis audit` verifica también las referencias de los destacados.
3. Los presupuestos de v2 se validan independientemente de la cascada de v1:
   recuperación 60, reranking hasta 60, conservación 8 y lectura 4 por defecto;
   ventanas de 384 tokens, solape 128 y 12 000 caracteres por contexto.
   Se exige `read_m <= rerank_k <= rerank_candidates <= retrieve_n`.
   El perfil conserva la elección de modelos, no determina esos presupuestos.

No se añadieron patrones de intención, foco, veto de ordinales o reglas por
documento. Los modelos siguen siendo los encoders y QA locales del perfil.
La representación derivada nunca se verifica como si fuera una cita literal;
se verifican sus copias y se conservan las referencias discontinuas.

Cuando Word no declara cabecera, la primera fila aporta etiquetas por posición
y el supuesto queda señalado en vista previa y diagnóstico. Esto puede ser
inadecuado para tablas sin cabecera. La configuración estructural sigue siendo
optativa y su soporte se describe en [preparación](preparacion-estructural.md).

## Comparación del corpus real

Se conservaron el código anterior y el final en snapshots separados, con los
mismos tres DOCX. Se comprobaron sus hashes y la igualdad de los textos fuente
y de búsqueda de los 366 hijos y 112 padres. Se revisaron once preguntas:
las originales, formulaciones precisas y controles de arancel ausente, sujeto
inexistente y sujeto ajeno. Todas las consultas finales terminaron sin error;
las 44 referencias publicadas, incluidos destacados, coincidieron literalmente
con la extracción canónica. Esto acredita procedencia, no pertinencia.

| Caso | Antes | Variante final |
|---|---|---|
| Fecha original | QA elegía el prerrequisito del glosario como `ok` | Primero queda el pasaje del período diciembre–marzo, como recuperado |
| Duración ambigua | QA elegía el nombre de la práctica en el glosario | Primero queda el contexto de duración; la mayor puntuación QA del glosario no lo desplaza |
| Ponderaciones de P1 con nombre exacto | Tabla correcta, sin extracción QA positiva | Tabla correcta completa y propuesta de destacado en su celda |
| Ponderaciones de P2 | Tabla correcta con `ok` por QA | Se conserva primera la tabla completa; QA solo destaca una posible celda |
| Duración precisa de P1 | Primero el pasaje correcto | Se conserva primero el pasaje correcto |
| Ponderación coloquial de la primera práctica | Primero tabla P2; P1 no se leía | Sigue fallando: P1 queda octava y no se lee; primero queda un título sin pesos |
| Meses con formulación precisa | No recuperaba el período útil en la salida | Sigue fallando: muestra duración en semanas |
| Arancel/sujeto ausente o ajeno | Resultados relacionados sin respuesta demostrada | Continúa mostrando resultados relacionados; no acredita ausencia de información |

La lectura por campos mejora el acceso a una celda de la tabla correctamente
seleccionada, pero no corrige un ranking equivocado. El control de arancel
ilustra el límite: QA propuso «6 SCT» con puntuación alta; se registra como
posible fragmento dentro de una fuente relacionada, sin anunciarlo como precio.
Los destacados también pueden ser semánticamente incorrectos.

## Variante descartada y costos

Se probó además usar campos para embeddings/BM25 y reranking. Esa variante
incluyó la tabla P1 entre las tres fuentes de la consulta coloquial, pero
regresó en duración precisa: colocó P2 antes que P1. No se conserva como
representación por defecto. Búsqueda y reranking mantienen su texto contextual
anterior; solamente el lector usa campos.

Los modelos se ejecutaron secuencialmente con dos hilos ONNX y sin descargas.
Hubo un intento inicial fallido por memoria al cargar QA; no forma parte de
la comparación semántica. La muestra final de RSS alcanzó aproximadamente
3,06 GiB. Los nuevos presupuestos aumentan trabajo de CPU; no se atribuyen
los tiempos registrados a latencia de servicio porque durante la corrida final
también se ejecutaron pruebas técnicas. Falta una medición aislada y repetida.

## Validación y reproducción

La suite dirigida aprobó 715 pruebas, con una omitida; el empaquetado aprobó
una prueba adicional (716 en total). Cubre v1/v2, configuración, API, preparación, mapas,
identidad de celdas, auditoría, aislamiento del comparador y arquitectura.
La evaluación documental reservada, modelos alternativos, destacados del
widget y bloques tabulares siguen pendientes. No hay promoción a producción.

Para preparar una copia con la variante final:

```powershell
ipsis prepare --project C:/ruta/proyecto --output C:/ruta/copia-nueva --index
```

Opciones externas en `config/engine.yaml`:

```yaml
pipeline: v2
v2:
  retrieve_n: 60
  rerank_candidates: 60
  rerank_k: 8
  read_m: 4
  max_context_chars: 12000
  max_passage_tokens: 384
  stride: 128
```

Los artefactos reales permanecen excluidos de Git:

- `.cache/motor-v2/structured-reader-fields-project/`: copia final preparada,
  índice y vista previa.
- `.cache/motor-v2/fields-validation/review.json`: once pares revisados,
  referencias verificadas y hashes de código/preguntas.
- `.cache/motor-v2/fields-validation/review.py`: comprobación reproducible de
  procedencia; no actúa como juez semántico.
- `.cache/motor-v2/fields-validation/reader_final.json`: corrida final con
  código congelado, respuestas y trazas completas.
- `.cache/motor-v2/fields-validation/combined_final.json`: control descartado
  con campos también para búsqueda/reranking.

La referencia anterior usa los siete casos originales de `before.json` y los
cuatro controles Unicode de `before_controls.json`. Los otros cuatro registros
iniciales tenían caracteres dañados por la consola y se excluyen; el informe
pareado exige igualdad exacta de las preguntas. El comparador valida también
que `source-root` corresponda al paquete realmente importado, para impedir
una sustitución silenciosa por la instalación editable.
