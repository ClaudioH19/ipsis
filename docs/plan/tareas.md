# Tareas del plan V4

Lee primero [README.md](README.md): reglas, criterios globales (G1–G6) y
decisiones. Cada tarea dice qué hacer, dónde y cómo comprobar que terminó.

**Convenciones**

- `PYTEST` = `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` (suite completa, ≈ 10 min).
- `MEDIR_CONSULTAS` = `python tests/datos/banco_consultas/medir.py <salida.json> light,medium es,en,pt` (F1.7).
- `MEDIR_CONVERSACIONES` = `python tests/datos/banco_conversaciones/medir.py <salida.json> light,medium es,en,pt`.
- `MEDIR_UNIVERSAL` = `MEDIR_CONSULTAS` con el banco `banco_universal`.
- «Medir» = las tres mediciones, comparadas con la línea base de F1.4 y anotadas en [avance.md](avance.md).

---

## F1. Bancos de evaluación

### F1.1 Banco de consultas a 60 casos por idioma

- **Pasos:** tres documentos nuevos por idioma (reglamento con artículos
  numerados, preguntas frecuentes de soporte TI, política de viáticos) junto
  al manual de adquisiciones y los documentos universales como distractores.
  Por idioma: 14 exactas, 20 paráfrasis (coloquiales, con palabras que el
  documento no usa), 16 trampas del mismo tema, 4 fuera de dominio,
  3 premisas falsas y 3 ambiguas. Regenerar con `construir.py`.
- **Archivos:** `tests/datos/banco_consultas/{es,en,pt}/{corpus,casos.yaml}`.
- **Aceptación:** 60 casos por idioma con esas categorías; toda respuesta
  literal ubicada en el corpus (lo exige `construir.py`).

### F1.2 Banco de conversaciones

- **Pasos:** 20 conversaciones por idioma, de 2 a 4 turnos, sobre el corpus
  del banco de consultas. Por turno: `hereda`, `respuesta` (literal) o
  `directa: false`. Cubrir: seguimiento de varios turnos, cambio de tema
  deliberado (también empezando con «y»), pregunta fuera de dominio en medio,
  trampa y premisa falsa dentro de un seguimiento, vuelta a un tema de dos
  turnos atrás. Medidor `medir.py` con resumen por perfil e idioma.
- **Archivos:** `tests/datos/banco_conversaciones/{es,en,pt}/conversaciones.yaml`, `medir.py`.
- **Aceptación:** F1.3 en verde; `medir.py` corre en los tres idiomas.

### F1.3 Pruebas estructurales

- **Pasos:** sin modelos: derivados del banco de consultas al día, 60 casos
  y categorías por idioma, capacidades válidas, respuestas de las
  conversaciones literales en el corpus, el primer turno no declara `hereda`.
- **Archivos:** `tests/evaluacion/test_banco_consultas.py`.
- **Aceptación:** pasa en < 5 s.

### F1.4 Línea base

- **Pasos:** medir el código actual (sin F4/F2/F3): banco de consultas,
  conversaciones y universal, light y medium × es/en/pt.
- **Aceptación:** tablas en [avance.md](avance.md); los archivos JSON de la
  medición se guardan fuera del repo y su resumen va en avance.md.

### F1.5 Documentación de los bancos

- **Archivos:** `docs/methodology/evaluation.md` (bancos y tamaño de
  muestra), `CHANGELOG.md`.
- **Aceptación:** la tabla de bancos describe ambos; el límite de D1 está
  escrito.

### F1.6 Commit

- **Pasos:** commit de F1.1–F1.5 y F1.7 en `v2/ruta` (D6).
- **Aceptación:** `git status` limpio; `PYTEST` en verde.

### F1.7 Medidor del banco de consultas en el repo

- **Pasos:** llevar al repo el medidor que hoy vive fuera
  (`tests/datos/banco_consultas/medir.py`): caso por caso, con el chequeo de
  la respuesta literal, y la opción de medir otro árbol de código
  (`IPSIS_CODIGO=<worktree>`) para comparar con un commit anterior.
- **Aceptación:** reproduce las cifras de F1.4.

---

## F4. Memoria de la conversación (ADR 0006)

### F4.1 Temas, núcleo, compactación y retomar

- **Pasos:** reemplazar `ResolutorSeguimiento` por `MemoriaConversacion` en
  `ipsis/consulta/seguimiento.py`. La conversación es una sucesión de temas:
  - **núcleo** = los términos más específicos (máx. 3) de la pregunta que
    abrió el tema; se heredan mientras dure;
  - **último seguimiento** = los términos propios del turno anterior; se
    heredan una vez y luego se pliegan (compactación);
  - **vocabulario** = el de los últimos 3 pasajes que respondieron el tema;
  - una pregunta con tema propio fuera del tema en curso **retoma** un tema
    anterior si todos sus términos están en él (máx. 4 temas guardados) o
    **abre uno nuevo** sin heredar;
  - una pregunta fuera de dominio no cambia el tema.
- **Archivos:** `ipsis/consulta/seguimiento.py`, `motor.py`,
  `etapas/analisis.py`, `etapas/seleccion.py` (registro de la evidencia).
- **Aceptación:** pruebas unitarias de F4.5; G1–G6; en conversaciones,
  herencia correcta ≥ línea base y las conversaciones -007 y -015 (memoria de
  más de un turno) mejoran en los tres idiomas.

### F4.2 Vencimiento por inactividad y tope configurables

- **Pasos:** cada conversación guarda su último uso; se olvida tras
  `expiry_minutes` sin uso (por defecto 30) y se purga al acceder (las
  sesiones están ordenadas por uso). Tope `max_sessions` (por defecto 1024).
  Claves nuevas y opcionales en `engine.yaml` → `conversation:`, con su
  nombre en `configuracion/glosario.py` y su esquema.
- **Archivos:** `ipsis/consulta/seguimiento.py`, `ipsis/configuracion/{esquemas,glosario,perfiles}.py`,
  plantilla de `engine.yaml`, `docs/guide/configuration.md` y su espejo en español.
- **Aceptación:** prueba con reloj inyectado (vence a los N minutos, no
  antes); un proyecto sin la clave funciona igual; `ipsis doctor` sin avisos
  nuevos.

### F4.3 Reinicio al salir de la página (D5)

- **Pasos:** el widget genera un `session_id` por carga de página (sin
  `localStorage`).
- **Archivos:** `ipsis/servicio/estaticos/widget.js`, `docs/guide/web.md` y espejo.
- **Aceptación:** recargar la página empieza una conversación nueva; cerrar y
  abrir el panel la conserva; prueba del widget en verde.

### F4.4 Diagnóstico

- **Pasos:** el diagnóstico muestra si el turno heredó, retomó un tema o abrió
  uno nuevo, y el núcleo del tema en curso.
- **Archivos:** `ipsis/nucleo/esquemas.py`, `ipsis/cli/comandos/consulta.py`.
- **Aceptación:** `ipsis ask --diagnostics` lo muestra; esquema estricto en verde.

### F4.5 Pruebas

- **Pasos:** pruebas unitarias sin modelos: vencimiento con reloj
  inyectado, tope, aislamiento entre sesiones, cambio de tema con «y»,
  retomar un tema de dos turnos atrás, pregunta fuera de dominio en medio,
  el núcleo sobrevive a la compactación, concurrencia básica.
- **Archivos:** `tests/consulta/test_seguimiento.py`.

### F4.6 Medir

- **Aceptación:** G1–G6 y lo de F4.1, anotado en avance.md.

### F4.7 Documentación

- **Pasos:** ADR 0006 (memoria de la conversación: modelo de temas,
  vencimiento, privacidad, D5); diagrama de la vida de una pregunta y tabla
  «Understanding the question» en `docs/architecture.md`; CHANGELOG; README
  (límites conocidos).
- **Aceptación:** `tests/test_documentacion.py` en verde; los diagramas renderizan.

---

## F2. Sinónimos por idioma versionados en el repo

### F2.1 Fuentes y licencias ⚠

- **Pasos:** relevar, por idioma, recursos léxicos abiertos con versión
  publicada: Open English WordNet (inglés), OpenWN-PT (portugués), el
  WordNet en español del MCR y los datos de Open Multilingual WordNet. Como
  alternativa, Wiktionary. Para cada uno: licencia exacta, versión, URL de
  descarga, suma SHA-256, tamaño y cobertura (palabras sueltas, grupos).
  Comprobar la compatibilidad con AGPL-3.0 de los datos versionados.
- **Aceptación:** tabla en avance.md; **el usuario aprueba cada fuente**
  antes de F2.2.

### F2.2 Script de construcción (lo corre quien desarrolla)

- **Pasos:** `herramientas/sinonimos/construir.py <idioma>`: descarga la
  versión fijada (verifica SHA-256), filtra y escribe
  `ipsis/recursos/sinonimos/<idioma>.tsv` ordenado y determinista, más
  `ipsis/recursos/sinonimos/FUENTES.md` con atribución, licencia, versión,
  fecha y suma. El usuario final nunca descarga nada.
- **Filtros:** palabras sueltas; grupos de sentido de hasta N miembros;
  descartar palabras con más de K sentidos (polisemia); formas regulares
  generadas (plural, conjugaciones frecuentes).
- **Aceptación:** correr dos veces da el mismo archivo; tamaño total dentro
  del presupuesto acordado en F2.1.

### F2.3 Carga en el paquete de idioma

- **Pasos:** el paquete suma los grupos del archivo a los escritos a mano
  (que siguen corrigiendo las formas irregulares). El índice raíz → grupos se
  arma una vez por paquete, no por consulta.
- **Archivos:** `ipsis/lenguaje/paquete.py`, `ipsis/lenguaje/consultas.py`.
- **Aceptación:** latencia G5; arranque del motor medido.

### F2.4 Sinónimos del proyecto

- **Pasos:** `domain.yaml` → `synonyms:` (grupos propios: «OC» = Orden de
  Compra), con prioridad sobre los del idioma.
- **Archivos:** configuración, glosario, guía de configuración.
- **Aceptación:** prueba con un proyecto que declara un grupo.

### F2.5 Pruebas

- **Pasos:** formato del TSV, atribución presente, el wheel incluye los
  archivos, presupuesto de tamaño; reproducibilidad del script con la fuente
  en caché (prueba lenta, sin red se omite).

### F2.6 Medir

- **Aceptación:** G1–G6 y, en paráfrasis del banco de consultas, correctas ≥
  línea base. Si sube algún falso ok, se ajustan los filtros de F2.2 antes de
  cerrar.

### F2.7 Mantenimiento

- **Pasos:** documentar cómo actualizar una fuente (subir la versión fijada,
  regenerar, medir, commit) en `herramientas/sinonimos/README.md`.

### F2.8 Documentación

- **Pasos:** ADR 0007 (fuentes de sinónimos y por qué no vectores: D4);
  `docs/methodology/lexical.md`; avisos de terceros (atribución) en el
  README; CHANGELOG.

---

## F3. Respaldo por similitud para la intención

### F3.1 Preguntas de ejemplo por intención

- **Pasos:** cada intención del paquete suma `ejemplos` (5 a 10 preguntas
  naturales por idioma), distintas de las de los bancos.
- **Archivos:** `ipsis/recursos/idiomas/{es,en,pt}.yaml`, `paquete.py`.

### F3.2 Clasificación por similitud

- **Pasos:** al construir el motor, codificar los ejemplos con el modelo
  denso del perfil (una vez por idioma). Solo si ningún patrón reconoce la
  intención, comparar el vector de la pregunta (el mismo que usa la
  confianza) con los ejemplos; aceptar la intención si la similitud supera
  τ y el margen sobre la segunda supera δ. Sin modelo denso (perfil bm25),
  no actúa.
- **Aceptación:** el diagnóstico dice si la intención vino de un patrón o
  de la similitud, con su puntaje; latencia G5.

### F3.3 Elegir τ y δ

- **Pasos:** con el split `dev` del banco de consultas: los valores más
  bajos sin ninguna intención equivocada; reportar en `test`.
- **Aceptación:** tabla en avance.md.

### F3.4 Pruebas y medición

- **Aceptación:** G1–G6; cuántas preguntas sin patrón reciben intención y
  con qué efecto en correctas y directas erróneas.

### F3.5 Documentación

- **Pasos:** ADR 0005 (sección nueva), `docs/methodology/lexical.md`,
  diagrama, CHANGELOG.

---

## F5. Cierre

### F5.1 Resumen y cierre del plan

- **Pasos:** tabla final contra la línea base; resumir en CHANGELOG, ADR y
  metodología; borrar `docs/plan/`.
- **Aceptación:** G1–G6 en el estado final; el usuario aprueba el cierre.
