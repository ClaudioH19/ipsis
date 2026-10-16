# Tareas: coherencia entre código, perfiles y documentación

Análisis e inventario: [coherencia.md](coherencia.md). Estado de cada tarea:
[coherencia-avance.md](coherencia-avance.md).

Este archivo está escrito para que cada tarea la ejecute un agente (Sonnet
5.5) en una sesión propia, sin depender del contexto de otra conversación.
Todo lo que el agente no podría deducir leyendo el código está escrito
abajo, en «Reglas fijas» y en los puntos ⚠ de cada tarea.

## Cómo trabajar una tarea

1. Leer este archivo completo, [coherencia.md](coherencia.md) y la fila de
   la tarea en el avance.
2. Trabajar **solo** en la rama asignada a la sesión (nunca `main`). No hacer
   merge a `main`, no abrir PR y no hacer push a otra rama sin pedido
   explícito del usuario.
3. Hacer **una tarea por sesión**. Si depende de otra que no está ✅,
   detenerse e informarlo.
4. Al llegar a un punto ⚠: **detenerse y preguntar al usuario**, con las
   opciones y una recomendación. No elegir por cuenta propia.
5. Al terminar: pruebas en verde, commit con mensaje descriptivo, push a la
   rama y actualizar la fila del avance (estado, fecha, commit y notas).

Estados del avance: ✅ hecho · 🔶 en curso · ⬜ pendiente · ⛔ bloqueado ·
⚠ espera al usuario.

## Comandos

- Preparar: `uv sync --locked --extra test`.
- `PYTEST` = `uv run --locked --extra test pytest -q -p no:cacheprovider`.
- Durante el desarrollo: `PYTEST tests/test_documentacion.py`. Antes del
  commit: `PYTEST -m "not slow and not modelos and not browser"`.
- Modelos (solo C2): `IPSIS_MODELS_DIR=.cache/modelos`; descargar con
  `ipsis models download --profile medium`.

## Reglas fijas (no se deducen del código)

Romper cualquiera de estas reglas invalida la tarea, aunque las pruebas
pasen.

1. **Solo documentación, descripciones y pruebas.** No cambiar valores por
   defecto, perfiles (salvo el campo `description`), migraciones, ranking ni
   comportamiento del widget. Si algo parece un error de código, se anota en
   el avance y se pregunta.
2. **El código es la fuente de verdad.** Cuando la documentación y el código
   discrepan, se corrige la documentación. Las fuentes de verdad son:
   - perfiles: `ipsis/recursos/perfiles/{light,medium}.yaml`
     (`models`, `language_rerankers`, `language_rerank_candidates`);
     cargados con `ipsis.configuracion.perfiles.cargar_perfil_instalacion`;
   - versión de configuración: `CONFIG_VERSION` en
     `ipsis/configuracion/esquemas.py`;
   - formatos: `EXTENSIONES_SOPORTADAS` en `ipsis/ingesta/parsear.py`;
   - versión del paquete: `pyproject.toml`;
   - comportamiento del widget: `docs/guide/web.md` y el `CHANGELOG.md`
     (`[Unreleased]`), que son lo más reciente.
3. **Inglés y español en el mismo commit.** Cada archivo tiene su par:
   `README.md` ↔ `README.es.md`, `docs/guide/<x>.md` ↔ `docs/es/guia/<y>.md`
   (configuration↔configuracion, deployment↔despliegue, golden↔golden,
   installation↔instalacion, integrations↔integraciones,
   inventories↔inventarios, personality↔personalidad, usage↔uso, web↔web).
4. **Nunca inventar cifras.** Latencias, tamaños y aciertos se miden o se
   citan con su fuente (archivo y línea). Si no se pueden medir, la tarea
   queda ⛔ con el error exacto.
5. **Lo histórico se marca, no se borra.** Las cifras de `heavy` o del motor
   v1 se conservan, con una línea «Histórico (…), fecha» encima.
6. **Estilo de la documentación existente.** Frases cortas, sin marketing,
   sin emojis nuevos fuera de los encabezados del README que ya los tienen.
   El español usa comillas «», como el resto de `docs/es/`.
7. **No tocar `docs/plan/` salvo el avance de este plan** (y C7, que lo pide).

---

## C1. Pruebas de coherencia

- **Objetivo:** que las contradicciones del inventario fallen en una prueba,
  antes de corregirlas.
- **Archivo:** `tests/test_documentacion.py` (ya tiene la prueba de comandos
  de la CLI y la de enlaces; seguir su estilo: nombres en español, `RAIZ`,
  `pytest.mark.parametrize` con `ids=["en", "es"]`).
- **Pruebas nuevas:**
  1. `test_tabla_de_perfiles_nombra_los_modelos_vigentes`: para `light` y
     `medium`, cada id de modelo no nulo de `models.dense`,
     `models.reranker` y de `language_rerankers` debe aparecer, por su nombre
     corto (la parte tras la última `/`, sin `-ONNX`), en `README.md`,
     `README.es.md`, `docs/guide/installation.md` y
     `docs/es/guia/instalacion.md`. **No exigir el lector** (`models.reader`):
     v2 no lo carga; se exige en cambio que la fila de `medium` de esos
     cuatro archivos **no** lo presente como parte del perfil vigente.
     Decidir cómo localizar la fila (por ejemplo, la línea de la tabla que
     empieza con `` | `medium` ``) y documentarlo en el docstring.
  2. `test_ejemplos_usan_la_config_version_vigente`: en `docs/guide/`,
     `docs/es/guia/` y `docs/methodology/fuentes-v2.md`, toda línea
     `config_version: N` dentro de un bloque de código YAML debe tener
     `N == CONFIG_VERSION`. Excepción: los ejemplos de `personality.md` /
     `personalidad.md` (`config_version: 1` es la versión de otro archivo,
     `tone`); declararla en una lista explícita con el motivo.
  3. `test_formatos_soportados_en_los_readme`: cada extensión de
     `EXTENSIONES_SOPORTADAS` se nombra en ambos README (aceptar el nombre
     del formato: `.md`/`.markdown` → «Markdown», `.tex` → «LaTeX»,
     `.pdf` → «PDF», etc.; definir el mapa en la prueba).
  4. `test_guias_en_y_es_tienen_las_mismas_secciones`: para cada par de la
     regla 3, el mismo número de encabezados `##`. Diferencias permitidas en
     un diccionario `DIFERENCIAS_PERMITIDAS = {}` (vacío al inicio), con el
     motivo como valor.
  5. `test_badge_de_version_coincide_con_pyproject`: la versión del badge de
     ambos README coincide con `project.version` de `pyproject.toml`.
- **Marcar como esperadas las fallas actuales:** cada prueba que falle hoy
  lleva `@pytest.mark.xfail(strict=True, reason="coherencia CN: …")` con la
  tarea que la arregla (C2, C3, C4 o C5). `strict=True` hace que la prueba
  avise cuando la tarea la arregle, y esa tarea quita el `xfail`.
- **Aceptación:**
  - sobre el commit de partida fallan (como xfail) al menos: perfiles (I1,
    I2), config_version (I5), formatos (I7), secciones de `web.md` y de
    `deployment.md` (I9, I10);
  - la prueba 5 pasa hoy (README y `pyproject.toml` dicen 1.0.0);
  - `PYTEST tests/test_documentacion.py` termina en menos de 5 s;
  - en el avance, la lista de qué prueba falla por qué inconsistencia.

## C2. Perfiles, modelos y cifras

- **Depende de:** C1.
- **Contexto:** desde el 2026-10-15 `medium` usa `bge-reranker-v2-m3` con 10
  candidatos en español y portugués y mMiniLM en los demás idiomas
  (`medium.yaml:41-49`; decisión en
  `docs/plan/precision-ingesta-avance.md`, sección «Decisión: reranker por
  idioma en `medium`», con sus cifras medidas: p50 1,4 s y p95 1,7 s sobre
  documentos reales, 4 CPU, int8; bge 560 MB). V2 no carga el lector QA por
  defecto (`docs/methodology/fuentes-v2.md`).
- **Pasos:**
  1. Tabla de perfiles de `README.md` y `README.es.md`: fila `medium` con
     «e5-small + reranker (bge-reranker-v2-m3 en es/pt; mMiniLM en otros
     idiomas) + búsqueda híbrida».
  2. Tabla de `docs/guide/installation.md:17` y `docs/es/guia/instalacion.md:17`:
     sin lector en la fila vigente; tamaño en disco = suma de los modelos que
     se descargan para ese perfil e idioma, leída de
     `ipsis models list` o del catálogo de modelos (citar la fuente en el
     commit); latencia con la cifra medida citada arriba y su condición
     («p95 1,7 s, documentos reales en español, 4 CPU»). Si se quiere una
     cifra para inglés, medirla (paso 5) o escribir «no medida».
  3. `medium.yaml::description`: quitar «and an extractive QA reader» y
     mencionar el reranker por idioma. Solo ese campo.
  4. ⚠ **Presupuesto que muestra el panel** (`ipsis/aplicacion/panel.py:143`
     publica `p95_budget_ms` del perfil, 1000 ms en `medium`, mientras v2
     usa `v2.query_budget_ms`, 2500). Opciones: (a) documentar que
     `p95_budget_ms` aplica al motor v1 y que v2 se rige por
     `query_budget_ms`, sin tocar el código; (b) que el panel muestre el de
     v2 cuando el motor es v2 (es cambio de código: rompe la regla 1 y
     requiere aprobación). Recomendación: (a) ahora, (b) como tarea aparte.
  5. Opcional, solo si los modelos se descargan: medir `medium` en inglés con
     `herramientas/evaluacion/ranking_pasajes.py --perfil medium --idioma en
     --salida <carpeta fuera del repo>` y anotar p50/p95 y la máquina en el
     avance.
  6. ADR 0003: añadir al bloque de actualización del inicio una línea que
     diga que la latencia «1 s» de la tabla es del motor v1 y apunte a la
     decisión del reranker por idioma. ⚠ Preguntar si esa decisión merece un
     ADR 0010 propio; recomendación: sí, corto, porque cambia el modelo
     descargado según el idioma.
  7. `herramientas/evaluacion/ranking_pasajes.py:313` acepta
     `--perfil heavy`, que ya no existe: quitar `"heavy"` de `choices`.
  8. Quitar el `xfail` de la prueba 1 de C1.
- **Aceptación:** la prueba de perfiles pasa sin `xfail`; ninguna cifra
  nueva sin fuente; las dos versiones de idioma cambian en el mismo commit.

## C3. Versión de configuración y preparación estructural

- **Depende de:** C1.
- **Pasos:**
  1. `config_version: 7` → `8` en `docs/guide/configuration.md:35,84`,
     `docs/es/guia/configuracion.md:36,86` y
     `docs/methodology/fuentes-v2.md:19`. Revisar que el resto de cada bloque
     de ejemplo siga siendo válido para la versión 8 (comparar con
     `ipsis/recursos/plantillas/engine.yaml`); si falta un campo nuevo
     relevante (`retrieval.preparation`), añadirlo.
  2. `docs/methodology/fuentes-v2.md:13-14`: reemplazar «La preparación
     estructural de DOCX continúa siendo optativa y experimental» por lo que
     dice ADR 0009: es la predeterminada para proyectos v2 nuevos y migrados;
     `retrieval.preparation.mode: legacy` vuelve atrás y requiere reindexar.
  3. Buscar otras menciones: `grep -rn "experimental\|config_version: 7" docs README*`
     fuera de `docs/plan/`, y corregir las vigentes (marcar las históricas).
  4. Quitar el `xfail` de la prueba 2 de C1.
- **Aceptación:** prueba 2 en verde; `fuentes-v2.md` no contradice ADR 0009.

## C4. Widget en español

- **Depende de:** C1.
- **Contexto:** `docs/guide/web.md` tiene dos secciones que la versión en
  español no tiene: «Try the widget and configure the project» y «Guidance
  separate from search results». Además describe el diseño actual (buscador
  abajo, mensaje del asistente con `{count}`, icono «?» de ayuda,
  `avatar.placement: message`, `response_mode` y `assistant_messages` en
  `GET /config`). Ver también `CHANGELOG.md`, `[Unreleased]` → «Added».
- **Pasos:**
  1. Traducir esas dos secciones a `docs/es/guia/web.md`, en el mismo orden.
  2. Recorrer `docs/guide/web.md` párrafo a párrafo frente al español y
     llevar al español todo lo que falte (tabla de `GET /config` incluida).
     No traducir literalmente: seguir el registro de `docs/es/`.
  3. `docs/es/guia/web.md:218` y `README.es.md:53,206` (y su par en
     `README.md:53,205`): el «menú Ayuda» ahora es un icono «?» en la
     cabecera del asistente.
  4. Ver si alguna captura de `docs/assets/` muestra el menú o la fila
     «Orientación de ipsis / Ayuda» antiguos. Si es así, regenerarla con
     `uv run --extra browser python herramientas/capturas_widget.py`; si el
     entorno no tiene Chromium, dejarlo anotado en el avance (⛔ parcial),
     sin editar imágenes a mano.
  5. Quitar el `xfail` de la prueba 4 de C1 en lo que respecta a `web.md`.
- **Aceptación:** misma cantidad de secciones `##` en ambas guías del
  widget; ninguna mención vigente a un «menú Ayuda».

## C5. README y despliegue

- **Depende de:** C1.
- **Pasos:**
  1. `README.es.md:44`: añadir LaTeX a los formatos, como `README.md:44`.
  2. `docs/es/guia/despliegue.md`: traducir la sección «Continuous
     integration» de `docs/guide/deployment.md:3-53` en el mismo lugar.
  3. README (ambos), «Inicio rápido» y «Actualizar un proyecto existente»:
     - mencionar `ipsis sync` como la forma de reflejar cambios de la carpeta
       `documents/` (agregar, renombrar, quitar), con una línea y un enlace a
       la guía de uso;
     - en «Actualizar», decir que los proyectos v2 se migran a
       `config_version` 8 en el siguiente comando y que deben ejecutar
       `ipsis index` para la preparación estructural (texto de
       `CHANGELOG.md`, `[Unreleased]` → «Changed»).
  4. Quitar los `xfail` restantes de las pruebas 3 y 4.
- **Aceptación:** todas las pruebas de C1 en verde sin `xfail`, salvo las que
  dependan de tareas aún abiertas (anotarlas).

## C7. Historia y planes

- **Depende de:** C2–C5.
- **Pasos:**
  1. A cada nota de `docs/methodology/*.md` añadir bajo el título una línea
     de estado: `Estado: vigente (2026-10-XX)` o
     `Estado: histórico — motor v1` / `— perfil heavy, retirado 2026-10-08`.
     Criterio: describe el motor v2 o la ingesta actual → vigente. En duda,
     ⚠ preguntar con la lista.
  2. ⚠ Plan V4 (`docs/plan/tareas.md`, `avance.md`, `sinonimos.md`): F5.1
     espera la aprobación del usuario. Preguntar si se cierra. Si se
     aprueba, aplicar su propia regla: resumir lo que valga en CHANGELOG/ADR
     y borrar los tres archivos y su sección de `docs/plan/README.md`.
  3. `docs/plan/README.md`: el título y la primera frase hablan del plan V4
     como «vigente»; convertirlo en un índice de los planes abiertos.
- **Aceptación:** prueba de enlaces en verde (los enlaces a archivos
  borrados se actualizan).

## C8. Que no vuelva a pasar

- **Depende de:** C1.
- **Pasos:**
  1. `.github/PULL_REQUEST_TEMPLATE.md`, sección «Impact», dos casillas:
     «Changed a default, a profile or a supported format: the consistency
     tests in `tests/test_documentacion.py` pass» y «English and Spanish docs
     changed in the same commit».
  2. `CONTRIBUTING.md`: un párrafo «Documentation follows the code» con la
     regla 2 de este archivo y el nombre de las pruebas.
- **Aceptación:** la plantilla y la guía mencionan las pruebas por nombre.

## C6. Versión 1.1.0 (al final)

- **Depende de:** todas las anteriores en ✅.
- **Pasos:**
  1. ⚠ Confirmar el número. `[Unreleased]` cambia valores por defecto
     (preparación estructural, reranker por idioma) y migra la configuración
     a la versión 8 de forma automática, pero pide reindexar.
     Recomendación: **1.1.0**, con la reindexación destacada.
  2. `CHANGELOG.md`: `[Unreleased]` → `[1.1.0] - <fecha>` y un
     `[Unreleased]` vacío arriba.
  3. `pyproject.toml` `version`, badges de ambos README e instrucciones de
     instalación fijada (`@v1.0.0` → `@v1.1.0`, `README*.md`, sección
     «Actualizar»).
  4. `uv lock` si el número de versión aparece en `uv.lock`.
  5. **No crear el tag ni la release**: lo hace el usuario tras revisar.
- **Aceptación:** prueba 5 de C1 en verde; suite rápida en verde.
