# Construcción de tablas de sinónimos

Herramienta de desarrollo, con Python 3.11/3.12 y solo biblioteca estándar.
No se ejecuta al instalar el paquete. Los archivos ya descargados están
guardados en el repositorio y el uso habitual es **offline por defecto**.
Las fuentes y condiciones de activación están en
[ADR 0007](../../docs/decisions/0007-versioned-lexical-sources.md).

## Generar y comprobar

Desde la raíz del repositorio:

```bash
python herramientas/sinonimos/construir.py all
python herramientas/sinonimos/construir.py all --offline
python herramientas/sinonimos/construir.py all --check
```

En Windows usar `.venv\Scripts\python.exe` en lugar de `python`.
`es`, `en` y `pt` permiten construir un solo idioma. Las rutas por defecto se
resuelven respecto al repositorio, aunque el comando se invoque desde otra
carpeta. `--cache`, `--output` y `--sources` permiten rutas explícitas.

- Fuentes originales: `herramientas/sinonimos/datos/fuentes/`, comprimidas
  sin pérdida, con avisos y hashes. Permanecen disponibles en otro clon.
- Salida: `ipsis/recursos/sinonimos/`, incluida en el paquete.
- El comando exige los originales locales y los verifica. `--offline`
  confirma ese comportamiento; `--download` es la única opción que permite
  descargas explícitas al actualizar una fuente.
- `--check`: construye en memoria y compara cada archivo byte a byte;
  implica offline y no corrige una salida alterada. Devuelve código 1 si difiere.
- Una descarga incompleta o caché corrupta falla antes de escribir salidas.
  Revisar el motivo y eliminar únicamente el archivo corrupto de la caché
  antes de repetir. Nunca reemplazar el hash esperado por el de un error HTTP.

Las tres fuentes fueron aprobadas el 2026-10-06. Se pueden reconstruir así:

```bash
python herramientas/sinonimos/construir.py all --offline --output ipsis/recursos/sinonimos
python herramientas/sinonimos/construir.py all --check --output ipsis/recursos/sinonimos
```

Ese comando produce archivos. La integración usa los grupos WordNet
filtrados únicamente para ampliar BM25, conservando el vector y los controles
de aceptación de la pregunta original. Cuenta primero los sentidos del
léxico maestro para bloquear lemas ambiguos, incluso cuando otro sentido se
descartó por tamaño. Los diccionarios completos de Kaikki, formas
morfológicas y tesauros siguen siendo material de desarrollo; no se cargan
como equivalencias. Descargar no implica activar todas las relaciones.

Para guardar por primera vez originales ya descargados desde otra carpeta:

```bash
python herramientas/sinonimos/construir.py all --cache .cache/sinonimos/fuentes --archive-sources herramientas/sinonimos/datos/fuentes
```

El archivado verifica las fuentes offline y conserva los TAB comprimidos con
fecha gzip fija. Rechaza sustituir un original existente por datos distintos.

## Archivos producidos

- `<idioma>.tsv`: cabecera comentada, una fila por `synset_id`, categoría
  gramatical y lemas separados por tabuladores; UTF-8, Unicode NFC, LF.
- `<idioma>.lexicon.tsv`: léxico maestro completo, sin filtros ni cambios
  de mayúsculas o tildes. Conserva todos los sentidos, expresiones y grupos
  de un solo lema. Es TSV con escapado CSV para preservar cualquier carácter.
  Permite revisar y modificar los filtros sin perder datos.
- `<idioma>.manifest.json`: versión del conversor, procedencia, filtros,
  conteos de entrada y descartes, tamaño y SHA-256 del TSV.
- `licencias/`: avisos y citas originales, sin cambios, también verificados
  con SHA-256. Las licencias de los datos se conservan separadas de la AGPL
  del código.
- `FUENTES.md`: índice de atribuciones de los idiomas de la carpeta.
  Construir un idioma conserva las atribuciones de los demás.

## Vocabulario ampliado con tesauros

El conversor v3 incorpora cuatro tesauros de la distribución LibreOffice,
fijados al commit `32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4`: OpenThesaurus
español, WordNet 2.1/MyThes inglés y las variantes portuguesas pt_PT/pt_BR.
Los originales comprimidos y avisos están en `datos/tesauros/`; ya no se
necesita volver a descargarlos. `fuentes.json` conserva las URL y hashes.

| Idioma | Formas/expresiones WordNet | Vocabulario combinado | Incorporadas | Palabras alfabéticas minúsculas nuevas |
|---|---|---|---|---|
| es | 90.899 | 96.633 | 5.734 | 4.985 |
| en | 128.009 | 193.124 | 65.115 | 14.171 |
| pt | 54.071 | 94.108 | 40.037 | 38.159 |

El total combinado es **383.865 formas/expresiones**: **110.886** adicionales
(40,6%). Se deduplica por escritura exacta dentro de cada idioma; se
conservan mayúsculas y expresiones. No equivale a 383.865 palabras sueltas:
las incorporaciones de palabras alfabéticas minúsculas suman **57.315**.
No se generan conjugaciones ni se afirma que todo el vocabulario sea
intercambiable. Los lemas de WordNet y las tablas filtradas siguen teniendo
sus propios recuentos.

- `<idioma>.thesaurus.tsv`: una fila por entrada/sentido del tesauro,
  columnas `source_id`, `entry_id`, `headword`, `label`, `terms...`.
  Conserva etiquetas, orden, duplicados y anotaciones originales. Las
  filas son dirigidas y no se fusionan con synsets ni entre sí.
- `<idioma>.vocabulary.tsv`: índice de formas únicas, seguido de los ID
  de sus fuentes. Incluye lemas WordNet y entradas/términos de tesauro;
  excluye términos marcados como `antonym`, `generic term`, `related term`
  o `similar term`. Una palabra puede aparecer por otra entrada legítima.
  Este índice sirve para revisar cobertura, no como mapa de equivalencias.
- Los manifiestos registran cada complemento, sus conteos, aportes y hashes
  de los nuevos archivos. Los avisos figuran también en `FUENTES.md`.

MyThes declara su codificación en la primera línea: español usa ISO8859-1;
los otros tres, UTF-8. La salida usa TSV con escapado CSV y UTF-8. Los
originales mantienen sus bytes y licencias. Presupuesto independiente:
64 MiB por archivo de complemento. Ninguna tabla nueva se carga todavía
en las respuestas del motor.

Los comandos habituales `all` y `all --check` reconstruyen también estos
archivos offline. Para actualizar, `--supplement-cache <carpeta>` permite
otra carpeta de entradas. Para archivar entradas locales verificadas:

```bash
python herramientas/sinonimos/construir.py all --supplement-cache <carpeta> --archive-supplements <archivo-nuevo>
```

El archivado rechaza reemplazar originales distintos: generar en una
carpeta nueva y revisar el conjunto antes de versionar una actualización.

La fecha de revisión está fijada en [fuentes.json](fuentes.json); regenerar
mañana no introduce fechas nuevas. Versionar TSV, manifiestos, avisos y
FUENTES juntos, además de los originales comprimidos en `datos/fuentes/`.
La caché temporal ya no es necesaria para reconstruir la misma versión.

## Diccionarios extensos: español, inglés y portugués

> **Las descargas completas (`datos/diccionarios/`, 785 MB) ya no están en el
> árbol de trabajo**; siguen en el historial de git y están en `.gitignore`.
> Solo hacen falta para reconstruir estas tablas con `construir.py` (el
> producto usa las tablas ya construidas en `ipsis/recursos/sinonimos/`).
> Para recuperarlas: `git checkout c8084e6 -- herramientas/sinonimos/datos/diccionarios`
> y luego `git restore --staged herramientas/sinonimos/datos/diccionarios`.

El conversor v4 incorpora también las instantáneas de Wiktionary publicadas
por [Kaikki](https://kaikki.org/dictionary/), extraídas el 2026-10-03 del dump
enwiktionary 2026-09-02. La edición inglesa incluye datos léxicos de los tres
idiomas, no solamente inglés. Se descargaron **los tres archivos completos**.

- `datos/diccionarios/<idioma>.jsonl.gz.<parte>.part`: el gzip original,
  dividido sin pérdida en bloques de hasta 24 MiB. Concatenar las partes
  en el orden de `diccionarios.json` reproduce exactamente la descarga.
  Suman 675.305.401 bytes; cada parte tiene hash y también el gzip completo.
- `datos/diccionarios/<idioma>.lexical.<parte>.jsonl.gz`: proyecciones léxicas
  locales verificadas para reconstruir más rápido. Conservan palabra,
  idioma, POS, flexiones, glosas, etiquetas, identidades de sentido,
  `form_of`, `alt_of` y sinonimia. El original completo sigue disponible
  para cambiar el extractor o revisar cualquier campo omitido.
- `diccionarios.json`: instantánea, URL de descarga, metadatos HTTP,
  atribución, avisos y hashes de cada entrada local. Las URLs del proveedor
  son mutables; **la instantánea local queda fijada por fecha y SHA-256**.
  La construcción no consulta URLs ni acepta nuevos hashes automáticamente.

Los datos conservan la licencia declarada de Wiktionary (CC BY-SA 4.0,
con disponibilidad dual GFDL declarada por el distribuidor). Se incluyen
el texto de CC BY-SA 4.0 y las páginas originales de procedencia. Las
licencias de las fuentes anteriores siguen aplicándose a sus respectivos
datos; no se relicencia todo el inventario combinado bajo una sola licencia.

| Idioma | Inventario anterior | Inventario ampliado | Incorporaciones | Formas clasificadas como lemas | Registros de sinonimia |
|---|---|---|---|---|---|
| es | 96.633 | 1.325.362 | 1.228.729 | 108.026 | 56.585 |
| en | 193.124 | 1.740.739 | 1.547.615 | 758.100 | 725.169 |
| pt | 94.108 | 569.099 | 474.991 | 73.068 | 62.643 |

Inventario combinado: **3.635.200 formas únicas por idioma agregado**,
frente a 383.865; se incorporan **3.251.335** formas. La clasificación
como lema se refiere a los registros del nuevo diccionario; el inventario
también conserva flexiones, variantes, expresiones y nombres propios.
Las clases pueden solaparse. Los registros de sinonimia conservan la
dirección y sentido original; no son grupos de equivalencia ni necesariamente
pares únicos. Todas las cantidades exactas están en los manifiestos.

Nuevos derivados en `ipsis/recursos/sinonimos/diccionarios/`:

- `<idioma>.vocabulary.tsv.gz`: inventario combinado sin duplicados de
  escritura exacta, con tipos léxicos. Distingue `lemma`, `inflected_entry`,
  `inflected_form`, `alternative`, `explicit_synonym`, `legacy_vocabulary`
  y `unclassified_entry`. Una forma puede tener varios tipos. La procedencia
  anterior se consulta en `<idioma>.vocabulary.tsv`; el manifiesto fija su hash.
- `<idioma>.forms.tsv.gz`: formas declaradas por la fuente, palabra de
  entrada, POS, etiquetas y origen. No se inventan conjugaciones. Se
  excluyen encabezados de tabla, transliteraciones, IPA y marcadores vacíos
  del índice; la proyección original permite revisar esos descartes.
- `<idioma>.synonym-edges.tsv.gz`: relaciones de sinonimia explícitas,
  dirigidas, con sentido y calificadores. No contiene antónimos,
  traducciones ni equivalencias creadas a partir de flexiones.
- `<idioma>.entries.<parte>.jsonl.gz`: vista léxica de cada registro,
  con identidad estable y glosas para revisión; no se usa para responder.
- `<idioma>.manifest.json`: conteos separados, fuente, avisos y hashes.

`lemma` clasifica entradas sin indicación de flexión/variante en sus
sentidos; es una clasificación del extractor, no una certificación normativa.
Los nombres propios, expresiones y formas flexionadas permanecen identificables.
Ninguna cifra equivale a una lista completa de todas las palabras de un idioma,
ni implica que cada entrada tenga un sinónimo intercambiable en cualquier contexto.

Los comandos habituales `all` y `all --check` incluyen estos archivos.
Siempre verifican los originales completos y las proyecciones, sin red.
Para auditar o modificar la proyección, analizar directamente los originales:

```bash
python herramientas/sinonimos/construir.py all --raw-dictionaries --check
```

El modo original procesa varios GiB descomprimidos y tarda más. Las pruebas
comparan también el resultado de la proyección con el original. Los archivos
comprimidos nuevos se incluyen en el wheel; el sdist conserva además todos
los originales, proyecciones locales y herramientas de desarrollo. No hay
descargas al instalar ni carga automática en el motor de respuestas.

Para actualizar: descargar una instantánea nueva a una carpeta de revisión,
verificar idioma/formato, fijar su fecha y hash en `diccionarios.json`, y usar
`diccionarios.archivar()` para obtener partes sin pérdida. Regenerar las
proyecciones desde el original antes de usarlas como entrada de construcción.
Conservar los avisos y revisar conteos y cambios antes de versionar el conjunto.

## Filtros y límites

Los valores actuales son `max_members=8`, `max_senses=3` y 2 MiB de TSV
filtrado por idioma; el léxico maestro tiene un presupuesto independiente
de 16 MiB por idioma. El límite de un sentido de la primera vista previa
se amplió a tres para conservar más palabras, sin fusionar sus acepciones.
El recuento de sentidos considera todas las categorías y los
grupos que después se excluyen por tamaño. Compartir un lema no fusiona
grupos. Solo se extrae pertenencia a synsets; las relaciones semánticas y
las definiciones se ignoran.

Se mantienen tildes y se excluyen palabras con mayúsculas, locuciones,
guiones, cifras y signos. No se generan plurales/conjugaciones artificiales.
Esto limita cobertura y conserva el carácter conservador de la primera
entrega; no garantiza que cada sustitución sea correcta en un documento.
El lector OMW admite las dos variantes reales `lemma` y `spa:lemma`, y
salta las definiciones de cuatro columnas. El lector WN-LMF comprueba idioma
y versión, no consulta el DTD externo y no sigue relaciones de antonimia.

## Pruebas

```bash
python -m pytest -q tests/lenguaje/test_construir_sinonimos.py -m "not slow"
python -m pytest -q tests/lenguaje/test_construir_sinonimos.py -m slow
```

Las pruebas rápidas usan fuentes sintéticas. La prueba lenta reconstruye
los tres idiomas desde los originales del repositorio y los compara,
sin consultar `.cache` ni acceder a la red. Además se comprueba un aviso
corrupto, polisemia entre categorías, grupos grandes, Unicode, presupuesto
de salida y que `--check` detecte cambios sin sobrescribirlos.

Para comprobar el empaquetado:

```bash
python herramientas/sinonimos/verificar_paquetes.py
```

Construye wheel/sdist en una copia limpia bajo `.cache/sinonimos/paquetes/`
para evitar archivos obsoletos de `build/`. Compara tablas y avisos byte a
byte: el wheel incluye derivados y el sdist incluye también originales y
conversor para poder reconstruir sin descargas.

## Actualizar una fuente

1. Elegir una versión publicada o un commit inmutable y revisar los avisos.
2. Descargar el archivo y los avisos a una carpeta de revisión. Comprobar
   que son los datos esperados, no HTML ni una página de error.
3. Registrar URL, versión, bytes y SHA-256 en `fuentes.json`, con fecha de
   revisión y atribución. No usar URLs de `main` o `latest`.
4. Usar `--download --cache <carpeta-nueva> --output <vista-previa>` para
   no confundir la descarga nueva con los originales guardados. Para el
   desarrollo habitual de la misma versión no se descarga nada.
5. Comparar grupos incorporados/eliminados, su sentido y categoría, conteos,
   tamaño y cambios de licencia. Ejecutar `--offline` y `--check`.
6. Obtener la aprobación de la fuente que exige F2.1, si cambia; incorporar
   los artefactos juntos. Conservar las licencias aplicables a cada archivo.
7. Antes de activarla, medir consultas, conversaciones y universal contra
   la misma revisión del código. Ningún caso erróneo nuevo y ninguna
   respuesta correcta perdida por perfil/idioma; informar media y p95.
8. Comprobar wheel/sdist, pruebas y documentación; crear un commit del grupo
   coherente. Push solo si se solicita.
