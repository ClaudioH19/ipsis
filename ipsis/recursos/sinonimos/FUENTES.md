# Fuentes de los sinónimos

Archivos derivados; cada fuente conserva sus propios avisos y licencia.

Conversión: pertenencia a synsets, normalización NFC y filtros de palabras, sentidos y tamaño.
Cada *.lexicon.tsv conserva todos los lemas y sentidos originales, sin esos filtros.
Los TSV WordNet omiten definiciones; las vistas de diccionario conservan glosas para revisión offline.
No se convierten flexiones ni relaciones semánticas distintas de sinonimia en equivalencias.

## en: Open English Wordnet 2025

- Fuente: https://en-word.net/downloads
- Versión/instantánea: `2025`; revisión: 2026-10-06
- Licencia declarada: CC-BY-4.0; underlying Princeton WordNet notice retained
- Atribución: The Open English Wordnet Team (2019-present); derived from Princeton University WordNet. Both attributions and original license notices are retained.
- Descarga: https://en-word.net/static/english-wordnet-2025.xml.gz
- SHA-256 de entrada: `9ca6d1dcb75f822fdd66617f7d9da48142ace38dd544d6ad5e2feca1674ad3fe`
- SHA-256 del TSV: `fbf845c229ba35fbeb29cde491fc023ae10e3828171eb75b98660a3a1f9509f0`
- Filtros y conteos: `en.manifest.json`
- Léxico maestro completo: `en.lexicon.tsv`, SHA-256 `1797fee96c41ea7d448229a8930650ea0149f438ddd7785486ae36f4d80f357c`
- Aviso original: [licencias/en.LICENSE](licencias/en.LICENSE)
- Aviso original: [licencias/en.WNDB_License.txt](licencias/en.WNDB_License.txt)

### Complemento: WordNet 2.1 MyThes (LibreOffice)

- Fuente: https://github.com/LibreOffice/dictionaries/tree/32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4/en
- Versión: `LibreOffice dictionaries 32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4`; licencia declarada: Princeton WordNet 2.1 license
- Atribución: Princeton University, WordNet 2.1 (2005); conversi?n wn2ooo por Daniel Naber; distribuci?n LibreOffice.
- Descarga: https://raw.githubusercontent.com/LibreOffice/dictionaries/32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4/en/th_en_US_v2.dat; SHA-256: `8a3e4637450b7277428da248f0a604b5c92942bc30507220c051181462340f39`
- Transformación: decodificación a UTF-8 y TSV; se conservan etiquetas y términos originales.
- Las filas son entradas dirigidas del tesauro, no synsets ni grupos de equivalencia.
- Modificación preparada el 2026-10-06; datos para revisión offline.
- Aviso: [licencias/en-thes.WordNet_license.txt](licencias/en-thes.WordNet_license.txt)

### Diccionario extenso: Wiktionary English / Kaikki

- Fuente: https://kaikki.org/dictionary/English/index.html
- Instantánea: enwiktionary 2026-09-02; Kaikki extraction 2026-10-03; licencia: CC-BY-SA-4.0 (Wiktionary data; dual GFDL availability declared by distributor)
- Atribución: English Wiktionary contributors; Kaikki/Wiktextract, Tatu Ylonen (2022), Wiktionary as Machine-Readable Structured Data, LREC 2022. Original pages and notices retained.
- Descarga: https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl.gz?download=1
- SHA-256 del gzip original completo: `6d40e0067718aeb3321db30297761ca803838390627111a29a5426fee4557faf`
- Original completo archivado sin pérdida en partes bajo herramientas/sinonimos/datos/diccionarios/.
- Derivados: entradas léxicas, vocabulario tipado, flexiones y relaciones explícitas de sinonimia.
- Se omiten etimología, pronunciación, traducciones y ejemplos en la vista léxica; el original los conserva.
- Las flexiones, alternativas y palabras de diccionario no se convierten en equivalencias.
- Cambios preparados el 2026-10-06; manifiesto: `diccionarios/en.manifest.json`
- Aviso/procedencia: [licencias/CC-BY-SA-4.0.html](licencias/CC-BY-SA-4.0.html)
- Aviso/procedencia: [licencias/en.kaikki-source.html](licencias/en.kaikki-source.html)

## es: Multilingual Central Repository (Spanish), OMW distribution

- Fuente: https://github.com/omwn/omw-data/tree/406bf83b3c507a3d1f26e88252d5d66893fd36bf/wns/mcr
- Versión/instantánea: `MCR 3.0 / omw-data 406bf83b3c507a3d1f26e88252d5d66893fd36bf`; revisión: 2026-10-06
- Licencia declarada: CC-BY-3.0 (Spanish lexical data)
- Atribución: Aitor Gonzalez-Agirre, Egoitz Laparra and German Rigau (2012), Multilingual Central Repository version 3.0; distributed by OMW, Francis Bond and Ryan Foster (2013). See original citation.bib and LICENSE.
- Descarga: https://raw.githubusercontent.com/omwn/omw-data/406bf83b3c507a3d1f26e88252d5d66893fd36bf/wns/mcr/wn-data-spa.tab
- SHA-256 de entrada: `0ec37ce94ee2acc63ad6b120e1051f9841d172778cc24adc0023fb8dccf0a7cd`
- SHA-256 del TSV: `5a3a88f408f097e3f0dee754b8913b2f6cda8853888b3fd02d5c201c2c4e6258`
- Filtros y conteos: `es.manifest.json`
- Léxico maestro completo: `es.lexicon.tsv`, SHA-256 `feb88ed2f7fdb5e4aa2a4230130f8f5c40ad748244719b941866603cbd978457`
- Aviso original: [licencias/es.LICENSE](licencias/es.LICENSE)
- Aviso original: [licencias/es.citation.bib](licencias/es.citation.bib)

### Complemento: OpenThesaurus Espa?ol (LibreOffice)

- Fuente: https://github.com/LibreOffice/dictionaries/tree/32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4/es
- Versión: `LibreOffice dictionaries 32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4`; licencia declarada: LGPL-2.1
- Atribución: Marcelo Garrone, OpenThesaurus Espa?ol; snapshot 2012-01-11; distribuci?n LibreOffice.
- Descarga: https://raw.githubusercontent.com/LibreOffice/dictionaries/32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4/es/th_es_v2.dat; SHA-256: `ee0b7ad7dfede636aa5d5509cbbcbab59bef4cb8cbdff01f9528b15bd139b889`
- Transformación: decodificación a UTF-8 y TSV; se conservan etiquetas y términos originales.
- Las filas son entradas dirigidas del tesauro, no synsets ni grupos de equivalencia.
- Modificación preparada el 2026-10-06; datos para revisión offline.
- Aviso: [licencias/es-thes.README_th_es.txt](licencias/es-thes.README_th_es.txt)
- Aviso: [licencias/es-thes.LGPLv2.1.txt](licencias/es-thes.LGPLv2.1.txt)
- Aviso: [licencias/es-thes.LICENSE.md](licencias/es-thes.LICENSE.md)

### Diccionario extenso: Wiktionary Spanish / Kaikki

- Fuente: https://kaikki.org/dictionary/Spanish/index.html
- Instantánea: enwiktionary 2026-09-02; Kaikki extraction 2026-10-03; licencia: CC-BY-SA-4.0 (Wiktionary data; dual GFDL availability declared by distributor)
- Atribución: English Wiktionary contributors; Kaikki/Wiktextract, Tatu Ylonen (2022), Wiktionary as Machine-Readable Structured Data, LREC 2022. Original pages and notices retained.
- Descarga: https://kaikki.org/dictionary/Spanish/kaikki.org-dictionary-Spanish.jsonl.gz?download=1
- SHA-256 del gzip original completo: `c805cfb9f13c1769400d08e4a01bc4aeefb67775cbb36e2e4deb199e0af57b38`
- Original completo archivado sin pérdida en partes bajo herramientas/sinonimos/datos/diccionarios/.
- Derivados: entradas léxicas, vocabulario tipado, flexiones y relaciones explícitas de sinonimia.
- Se omiten etimología, pronunciación, traducciones y ejemplos en la vista léxica; el original los conserva.
- Las flexiones, alternativas y palabras de diccionario no se convierten en equivalencias.
- Cambios preparados el 2026-10-06; manifiesto: `diccionarios/es.manifest.json`
- Aviso/procedencia: [licencias/CC-BY-SA-4.0.html](licencias/CC-BY-SA-4.0.html)
- Aviso/procedencia: [licencias/es.kaikki-source.html](licencias/es.kaikki-source.html)

## pt: OpenWN-PT, OMW distribution

- Fuente: https://github.com/omwn/omw-data/tree/406bf83b3c507a3d1f26e88252d5d66893fd36bf/wns/por
- Versión/instantánea: `omw-data 406bf83b3c507a3d1f26e88252d5d66893fd36bf`; revisión: 2026-10-06
- Licencia declarada: CC-BY-SA-3.0; original WordNet/Wiktionary provenance notice retained
- Atribución: Valeria de Paiva and Alexandre Rademaker (2012), Revisiting a Brazilian WordNet; distributed by OMW, Francis Bond and Ryan Foster (2013). See original citation.bib and LICENSE, including WordNet and Wiktionary notices.
- Descarga: https://raw.githubusercontent.com/omwn/omw-data/406bf83b3c507a3d1f26e88252d5d66893fd36bf/wns/por/wn-data-por.tab
- SHA-256 de entrada: `0ba180e2d2a5317e61b4ebe94a7e969e68eea2d9e60705e1e9053c6e2ac5e684`
- SHA-256 del TSV: `1fce782bd81048a68dbf47a41f25797668908eaa2aae9d1b9880c11e0d2b1b36`
- Filtros y conteos: `pt.manifest.json`
- Léxico maestro completo: `pt.lexicon.tsv`, SHA-256 `3616be7a7d393f8745720848099c65476233bf8631119059e068ec8ff58328fa`
- Aviso original: [licencias/pt.LICENSE](licencias/pt.LICENSE)
- Aviso original: [licencias/pt.citation.bib](licencias/pt.citation.bib)

### Complemento: Tesauro portugu?s europeo (LibreOffice)

- Fuente: https://github.com/LibreOffice/dictionaries/tree/32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4/pt_PT
- Versión: `LibreOffice dictionaries 32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4`; licencia declarada: GPL-2.0-or-later (base); CC-BY-3.0 (Onto.PT); conservar procedencia PAPEL
- Atribución: Daniel Naber, OpenThesaurus (base); Tiago F. Santos (compilaci?n 2016); Onto.PT, Hugo Gon?alo Oliveira y Paulo Gomes; PAPEL, Linguateca. Ver README original.
- Descarga: https://raw.githubusercontent.com/LibreOffice/dictionaries/32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4/pt_PT/th_pt_PT.dat; SHA-256: `daa89fee61347f401f005f3efd17fa8878eeeabd903ff4e684ab4bc1a53df2fd`
- Transformación: decodificación a UTF-8 y TSV; se conservan etiquetas y términos originales.
- Las filas son entradas dirigidas del tesauro, no synsets ni grupos de equivalencia.
- Modificación preparada el 2026-10-06; datos para revisión offline.
- Aviso: [licencias/pt-pt-thes.README_th_pt_PT.txt](licencias/pt-pt-thes.README_th_pt_PT.txt)
- Aviso: [licencias/pt-pt-thes.LICENSES.txt](licencias/pt-pt-thes.LICENSES.txt)

### Complemento: Tesauro portugu?s brasile?o (LibreOffice)

- Fuente: https://github.com/LibreOffice/dictionaries/tree/32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4/pt_BR
- Versión: `LibreOffice dictionaries 32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4`; licencia declarada: Aviso permisivo de Kevin B. Hendricks y colaboradores; ver original
- Atribución: Kevin B. Hendricks y colaboradores (2003); distribuci?n LibreOffice.
- Descarga: https://raw.githubusercontent.com/LibreOffice/dictionaries/32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4/pt_BR/th_pt_BR.dat; SHA-256: `0dae83c0b75e53837ef220431da049c716fa954f99fb77578eebf4e93d261af0`
- Transformación: decodificación a UTF-8 y TSV; se conservan etiquetas y términos originales.
- Las filas son entradas dirigidas del tesauro, no synsets ni grupos de equivalencia.
- Modificación preparada el 2026-10-06; datos para revisión offline.
- Aviso: [licencias/pt-br-thes.license-thes.readme](licencias/pt-br-thes.license-thes.readme)

### Diccionario extenso: Wiktionary Portuguese / Kaikki

- Fuente: https://kaikki.org/dictionary/Portuguese/index.html
- Instantánea: enwiktionary 2026-09-02; Kaikki extraction 2026-10-03; licencia: CC-BY-SA-4.0 (Wiktionary data; dual GFDL availability declared by distributor)
- Atribución: English Wiktionary contributors; Kaikki/Wiktextract, Tatu Ylonen (2022), Wiktionary as Machine-Readable Structured Data, LREC 2022. Original pages and notices retained.
- Descarga: https://kaikki.org/dictionary/Portuguese/kaikki.org-dictionary-Portuguese.jsonl.gz
- SHA-256 del gzip original completo: `026e1bd88b2652fb2ae8a5ade030a4273d74bdf3522f9caadea68558a788cb1d`
- Original completo archivado sin pérdida en partes bajo herramientas/sinonimos/datos/diccionarios/.
- Derivados: entradas léxicas, vocabulario tipado, flexiones y relaciones explícitas de sinonimia.
- Se omiten etimología, pronunciación, traducciones y ejemplos en la vista léxica; el original los conserva.
- Las flexiones, alternativas y palabras de diccionario no se convierten en equivalencias.
- Cambios preparados el 2026-10-06; manifiesto: `diccionarios/pt.manifest.json`
- Aviso/procedencia: [licencias/CC-BY-SA-4.0.html](licencias/CC-BY-SA-4.0.html)
- Aviso/procedencia: [licencias/pt.kaikki-source.html](licencias/pt.kaikki-source.html)

