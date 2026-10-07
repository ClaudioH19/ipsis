# Propuesta concreta: fuentes léxicas por idioma

Fecha: 2026-10-06. Desarrolla F2 del plan V4. El objetivo es recuperar
paráfrasis sin convertir parecido temático en una respuesta directa.

## Fuentes propuestas

| Idioma | Fuente y versión fijada | Licencia declarada | Formato de entrada |
|---|---|---|---|
| es | MCR 3.0, distribución OMW, commit `406bf83b3c507a3d1f26e88252d5d66893fd36bf` | CC BY 3.0 para los datos españoles | OMW tab (`spa:lemma`) |
| en | Open English Wordnet 2025, edición sin Namenet | CC BY 4.0 y aviso de Princeton WordNet para los datos de base | WN-LMF XML comprimido |
| pt | OpenWN-PT, distribución OMW, mismo commit fijado | CC BY-SA 3.0; conservar también el aviso de procedencia WordNet/Wiktionary | OMW tab (`lemma`) |

Fuentes primarias:
[MCR/OMW](https://github.com/omwn/omw-data/tree/406bf83b3c507a3d1f26e88252d5d66893fd36bf/wns/mcr),
[Open English Wordnet](https://en-word.net/downloads),
[OpenWN-PT/OMW](https://github.com/omwn/omw-data/tree/406bf83b3c507a3d1f26e88252d5d66893fd36bf/wns/por).
OMW es el distribuidor de las instantáneas es/pt, no otra fuente que se mezcle.
Su versión de datos no se presenta como la última versión del proyecto original.

La herramienta fija URL, bytes y SHA-256 tanto del diccionario como de sus
avisos en `herramientas/sinonimos/fuentes.json`. No usa `main`, búsquedas web
ni descargas al instalar ipsis. Los datos derivados conservan sus licencias
y atribuciones; no se afirma que hayan pasado a ser AGPL por estar en el repo.
Las tres fuentes fueron aprobadas por el usuario el 2026-10-06, con la
indicación de ampliar la cobertura y guardar los archivos para trabajar
después sin volver a descargarlos.

## Conversión y contrato

1. Conservar las descargas originales en `herramientas/sinonimos/datos/fuentes/`,
   comprimidas sin pérdida con sus avisos y un manifiesto de hashes.
   Reconstruir offline por defecto; descargar solo con `--download` para
   una actualización explícita. Verificar SHA-256 y tamaño antes de analizar.
2. Extraer solamente pertenencia de lemas a synsets. Ignorar enlaces de
   antonimia, hiperonimia, derivación y similitud: no son equivalencias.
3. Conservar el synset original y su categoría gramatical. No fusionar
   sentidos que comparten un lema ni hacer cierre transitivo.
4. Normalizar Unicode NFC y minúsculas, conservando tildes. Admitir solo
   palabras alfabéticas sueltas. Locuciones, guiones, cifras y nombres con
   mayúscula inicial se excluyen en esta primera versión.
5. Contar sentidos antes de los filtros de tamaño. La tabla filtrada admite
   hasta **tres sentidos** por lema (incluyendo otras categorías), y excluye
   grupos con más de **8** lemas sueltos. Conservar solo grupos con al menos
   dos lemas después de filtrar. No truncar un grupo grande.
6. No inventar conjugaciones en esta entrega. Los grupos manuales existentes
   conservan formas irregulares; una futura tabla morfológica necesita fuente,
   procedencia y pruebas propias. El stemmer no resuelve todas las flexiones.
7. Emitir UTF-8 con LF, orden estable y una fila por sentido:
   `synset_id<TAB>pos<TAB>lema1<TAB>lema2…`. Cabecera comentada con versión
   del formato, idioma, fuente, versión y hash de entrada.
8. Emitir también `<idioma>.lexicon.tsv`: todos los grupos de lemas del
   original, sin filtros, manteniendo mayúsculas, tildes, locuciones,
   polisemia y grupos de un miembro. El TSV maestro permite revisar el
   diccionario completo sin tener que descargar ni analizar XML otra vez.
9. Emitir por idioma un manifiesto con filtros, conteos de entrada/descarte,
   número de grupos/lemas, tamaño y hash de salida, más avisos y `FUENTES.md`.
   La fecha procede del manifiesto fijado, no del reloj de cada construcción.

Presupuesto: **2 MiB de TSV filtrado por idioma**, y **16 MiB de léxico
maestro por idioma**. Los límites son candidatos para futura evaluación, no una
garantía de desambiguación ni de corrección semántica.

## Integración posterior a la conversión

### Ampliación de vocabulario solicitada

El conversor v3 añade tesauros de LibreOffice desde el commit inmutable
`32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4`. La solicitud de más vocabulario
se implementa como preparación de datos locales; la activación y evaluación
de equivalencias sigue siendo la entrega C.

| Idioma | Complemento | Avisos conservados |
|---|---|---|
| es | OpenThesaurus Español, snapshot 2012-01-11 | README del tesauro, LGPL 2.1 y LICENSE.md de la distribución |
| en | MyThes/WordNet 2.1 distribuido por LibreOffice | Licencia Princeton WordNet 2.1 |
| pt | Tesauro pt_PT, compilación de OpenThesaurus/Onto.PT/PAPEL | README completo y LICENSES.txt; avisos GPL 2 o posterior, CC BY 3.0 y procedencia PAPEL |
| pt | Tesauro pt_BR | Aviso permisivo de Kevin B. Hendricks y colaboradores, con requisitos de conservar avisos y marcar modificaciones |

Se guardan descargas originales comprimidas sin pérdida en
`herramientas/sinonimos/datos/tesauros/`, y por idioma dos archivos nuevos:
`*.thesaurus.tsv` conserva las filas dirigidas y etiquetas;
`*.vocabulary.tsv` deduplica formas y registra fuentes. No se mezclan
estos registros con los synsets WordNet. El MyThes inglés incluye marcas
explícitas de antónimos y términos genéricos/relacionados/similares; se
preservan en sus registros y no se incorporan como equivalencias ni como
términos de sinónimos al inventario. Pueden figurar independientemente como
lemas o entradas de otras filas.

El inventario combinado tiene **96.633** formas/expresiones es,
**193.124** en y **94.108** pt: **383.865**, con **110.886** incorporaciones.
De ellas, **57.315** son palabras alfabéticas minúsculas. El inventario
también conserva expresiones y variantes de escritura; estos conteos no
certifican intercambiabilidad. Los TSV filtrados conservan sus hashes.

Los complementos tienen un presupuesto independiente de 64 MiB por archivo,
con avisos y reconstrucción offline incluida en wheel/sdist. Las fuentes
originales siguen presentes para revisar etiquetas o modificar el extractor
sin repetir la descarga. Detalle de URL, hashes, formatos y procedimiento:
[`herramientas/sinonimos/README.md`](../../herramientas/sinonimos/README.md).

### Condiciones de activación

La ampliación siguiente (conversor v4) incorpora además los diccionarios
completos de Wiktionary/Kaikki para **los tres idiomas**, extracción
2026-10-03 del dump enwiktionary 2026-09-02. Se descargaron y archivaron
los gzip originales íntegros: 675.305.401 bytes en partes de hasta 24 MiB.
`diccionarios.json` fija fecha, metadatos HTTP, hashes y avisos; la URL
mutable del proveedor nunca se consulta durante la reconstrucción.

Inventarios ampliados: es **1.325.362**, en **1.740.739**, pt **569.099**;
total **3.635.200** formas y expresiones. Los nuevos índices distinguen
lemas, flexiones, variantes y procedencia anterior. Se conservan además
registros de morfología y sinonimia explícita con sentidos y calificadores.
Los glosarios son datos de revisión y no una fuente de respuestas del motor.

Las proyecciones léxicas locales permiten reconstruir más rápido; se
verifican también los originales completos. `--raw-dictionaries` vuelve
a analizar los originales para auditar o modificar la proyección. Los
derivados comprimidos se empaquetan y no se descargan al instalar.

Las condiciones de activación siguientes siguen aplicándose:

- Mantener grupos automáticos separados de `sinonimos` manuales. Conservar
  fuente/sentido/POS en el índice de consulta y en el diagnóstico.
- Usar grupos automáticos primero para recuperación, cuando el término
  original no esté en el corpus. Ante varios sentidos o alternativas
  ambiguas después del stemming, no expandir automáticamente.
- **No alimentar `equivalentes()` con todo el diccionario:** esa función
  también modifica `s_foco` para palabras presentes, fuera de la guarda OOV.
  Aceptar equivalencia para responder requiere un cambio separado y medido.
- Los sinónimos del proyecto tienen precedencia por término: sobrescribir
  equivalencias conflictivas, no unir grupos. Las siglas y locuciones de
  `domain.yaml` necesitan tratamiento de frases, no la tabla de palabras sueltas.
- Cargar una vez por idioma mediante `importlib.resources`; incluir TSV,
  manifiestos y licencias en wheel/sdist. Un idioma desconocido no recibe
  sinónimos ingleses por el respaldo de mensajes de interfaz.
- Incorporar el hash efectivo de recursos léxicos y sobrescrituras del
  proyecto a la procedencia de la calibración. Activar o actualizar sinónimos
  cambia las señales: una calibración anterior no conserva automáticamente
  su certificación solo porque el corpus y los modelos no cambiaron.
  Invalidar también las cachés de comprensión y la memoria de temas al
  recargar esa configuración.

## Entregas y aceptación

**A. Conversor reproducible:** fuentes fijadas, lectores OMW y WN-LMF,
descarga verificada, generación offline y `--check`, informes y pruebas
sintéticas de polisemia, sentidos separados y caché corrupta. Generar una
vista previa real en `.cache/`, sin modificar las respuestas del motor.

**B. Incorporación de datos (hecha):** aprobación registrada, originales
comprimidos guardados en `herramientas/sinonimos/datos/fuentes/`, tablas
filtradas y léxicos completos en `ipsis/recursos/sinonimos/`, con avisos.
El wheel incluye los derivados; el sdist además incluye el conversor y los
originales para reconstruir sin red. La carga automática en el motor
corresponde a C y todavía requiere medición de calidad de respuesta.

**C. Activación medida:** comparar antes/después consultas, conversaciones
y universal en light/medium × es/en/pt. Exigir ningún identificador con
error nuevo, ninguna respuesta correcta perdida por combinación e informar
media/p95, arranque y memoria. Si un grupo falla, excluirlo explícitamente
con motivo y caso de prueba, sin ajustar los umbrales de la política.
Mantener la misma revisión del código y corpus para aislar el efecto de F2.

Las correcciones a las métricas detectadas en la revisión se realizan antes
de C y generan una nueva línea base; no se comparan conteos de definiciones
distintas. El banco de consultas es de regresión: no certifica riesgo ni
elige umbrales de producción. La suma de casos respondibles en `test` es
51 (17 por idioma), insuficiente para certificar 5 % con cero errores.

**D. Mantenimiento:** actualizar una versión y sus hashes, regenerar,
revisar el diff por sentido y atribución, medir, ejecutar pruebas y crear
un commit coherente. Publicar o hacer push solo cuando se solicite.

El trabajo de F4 que ya está en el árbol de trabajo se conserva. Esta entrega
no da F4 por terminado ni sustituye las mediciones pendientes del plan V4.
