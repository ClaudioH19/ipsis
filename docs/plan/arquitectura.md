# Arquitectura V3

Tres criterios guían la estructura:

- **Mínima:** cada carpeta existe porque agrupa una responsabilidad. Nada de
  duplicados ni de archivos de otra época.
- **Entendible:** el nombre de la carpeta dice qué hay dentro. Las
  dependencias van en una sola dirección.
- **Auditable:** toda decisión del asistente se puede reconstruir desde
  archivos legibles (configuración, calibración, estadísticas del índice,
  diagnóstico por consulta) y una prueba hace cumplir las reglas de
  dependencia.

## 1. Repositorio

```text
rag-extractivo/
├── README.md               # qué es, instalación por perfil, ciclo de uso
├── CHANGELOG.md
├── LICENSE                 # pendiente: decisión del autor
├── pyproject.toml          # dependencias, extras y configuración de pytest
├── Dockerfile              # imagen base (ARG PERFIL)
├── .github/workflows/ci.yml
├── rag/                    # el paquete: código + recursos
├── tests/                  # espejo de rag/ + datos de prueba + integración
├── ejemplos/               # integración web: html/, react/, wordpress/ (probados en CI)
└── docs/                   # guías, metodología, decisiones y este plan
```

**Sale de la raíz:** `configuracion/`, `documentos/` y `data/` (eran un
proyecto de prueba mezclado con la librería; las pruebas crean uno temporal
con `rag init`), `docker-compose.yml` (pasa a plantilla de
`rag desplegar preparar`), `pytest.ini` (pasa a `pyproject.toml`),
`requirements*.txt`, `PLAN_V2.md`, `build/` y `*.egg-info/`.

### 1.1 Paquete `rag/`

```text
rag/
├── nucleo/          # contratos.py (Protocol), esquemas.py (Pydantic), registro.py (Registry)
├── configuracion/   # esquemas.py, carga.py, perfiles.py, migraciones.py
├── lenguaje/        # paquete.py (idiomas), texto.py (terminos/oraciones), lexico.py (BM25, TF-IDF, señales),
│                    # entidades.py (universales + del paquete), dominio.py (reglas del cliente)
├── ingesta/         # parsear.py, chunking.py, metadata.py, catalogo.py, ingesta.py
├── modelos/         # catalogo.py, descarga.py, onnx.py (base), denso.py, reranker.py, lector.py
├── indice/          # qdrant.py, estadisticas.py, manifiesto.py
├── consulta/        # motor.py, contexto.py, admision.py
│   └── etapas/      # conversacional, analisis, recuperacion, filtros, reranking, lectura,
│                    # seleccion, politica, verificacion, redaccion (un archivo cada una)
├── evaluacion/      # banco.py, golden.py, metricas.py, calibracion.py, comparacion.py (funciones puras)
├── aplicacion/      # casos de uso compartidos por CLI y API: proyecto, corpus, consulta (construir_motor),
│                    # evaluacion (evaluar, benchmark), estilos, widget, despliegue, diagnostico (doctor),
│                    # registro_base (raíz de composición)
├── cli/             # __init__.py (main), base.py (Comando), comandos/<grupo>.py
├── servicio/        # api.py, seguridad.py, estaticos/
└── recursos/        # plantillas/ (proyecto), idiomas/, perfiles/, despliegue/
```

Hoy hay 30 módulos sueltos en `rag/`. Quedan 12 carpetas con nombres de
dominio y ningún archivo suelto, salvo `__init__.py`.

### 1.2 Capas y dependencias permitidas

```text
nucleo ◀── configuracion ◀── lenguaje ◀── ingesta · modelos · indice ◀── consulta ◀── evaluacion ◀── aplicacion ◀── cli · servicio
```

- Un módulo solo importa de su capa o de capas a su izquierda.
- `nucleo`, `configuracion` y `lenguaje` no importan librerías pesadas
  (`onnxruntime`, `qdrant_client`, `fastapi`).
- `cli` y `servicio` solo llaman a `aplicacion` (y a `nucleo` para los tipos). Esta regla estricta se activa en P11.1; hasta entonces rige solo el orden de capas.
- `tests/test_arquitectura.py` analiza los imports con `ast` y falla si se
  rompe una regla. La arquitectura se audita sola en cada CI.

Cada `__init__.py` de carpeta tiene un docstring de 2–4 líneas: qué hace la
capa y de quién puede depender.

### 1.3 Pruebas

```text
tests/
├── conftest.py            # fixtures: proyecto temporal con `rag init`, dobles en memoria
├── test_arquitectura.py   # reglas de dependencia entre capas
├── datos/
│   ├── corpus/            # 2 documentos sintéticos (hoy en tests/caracterizacion/corpus)
│   ├── banco/             # banco sintético versionado (hoy en tests/evaluacion/sintetico)
│   └── caracterizacion/   # salida esperada por perfil
├── nucleo/ configuracion/ lenguaje/ ingesta/ modelos/ indice/ consulta/ evaluacion/ cli/ servicio/
└── integracion/           # punta a punta: portabilidad, caracterización, navegador, ejemplos web
```

Una prueba vive en la carpeta del módulo que prueba. Las que hoy se solapan
(`test_contratos_v2`, `test_frontera_tipos`, `test_intercambio_componentes` y
`test_pipeline`) se consolidan al moverlas.

### 1.4 Documentación

```text
docs/
├── README.md        # índice y mapa de carpetas (1 línea por carpeta)
├── guia/            # instalacion.md, uso.md (comandos), golden.md, configuracion.md, web.md, despliegue.md
├── metodologia/     # una ficha por técnica: recuperacion, lexico, reranker, lector, politica, calibracion, multilenguaje
├── decisiones/      # ADR numerados (0001…)
└── plan/            # este plan; al cerrar V3 se borra y su resumen pasa a CHANGELOG y ADR
```

### 1.5 Proyecto del cliente (lo crea `rag init`)

```text
mi-asistente/
├── documentos/            # archivos fuente + catalogo.yaml
├── configuracion/
│   ├── asistente.yaml     # identidad, idioma, perfil, seguridad, CORS
│   ├── motor.yaml         # solo las sobrescrituras del perfil (casi siempre vacío)
│   ├── estilos.yaml       # presentación del widget
│   ├── dominio.yaml       # opcional: reglas regex y categorías propias (une perfil.yaml + categorias.yaml)
│   ├── idioma.yaml        # opcional: sobrescribe mensajes del paquete de idioma
│   └── calibracion.yaml   # generado por `rag calibrar`, con procedencia
├── golden/                # golden.csv del cliente, banco/ versionado, reportes/
└── .rag/                  # generado, no se versiona: indice/ (Qdrant + estadisticas.json + manifiesto.json), registros/
```

Desaparecen `configuracion/textos.yaml` (pasa al paquete de idioma),
`configuracion/categorias.yaml` y `configuracion/dominios/` (pasan a
`dominio.yaml`). La caché de modelos es global por usuario
(`RAG_MODELOS_DIR`, por defecto `~/.cache/rag-extractivo/modelos`) para no
descargar lo mismo en cada proyecto.

## 2. Flujo de una consulta (cascada)

Cada etapa recibe un `ContextoConsulta`, lo completa y puede **cerrar la
consulta** asignando `ctx.resultado`. Las etapas baratas van primero. Las
señales léxicas permiten **salidas tempranas** que evitan ejecutar modelos.

```text
pregunta
 [1] conversacional ── patrón del paquete de idioma ─────────────────▶ respuesta fija
 [2] analisis ──────── términos (stem), entidades, términos foco (IDF)
 [3] recuperacion ──── Qdrant: denso e5 + BM25 (TF cliente, IDF servidor), RRF → top N
                       señales: s_ret, acuerdo
 [4] filtros ───────── premisa (entidad pedida que no existe) ───────▶ sin_respuesta
                       s_oov alto + s_ret bajo ─────────────────────▶ sin_respuesta (fuera de dominio)
                       ningún candidato contiene un término foco ──▶ salta [5] y [6]
 [5] reranking ─────── cross-encoder → top K, s_rr                   (medium, heavy)
 [6] lectura ───────── lector QA: tramo o «sin respuesta», s_qa      (medium, heavy)
 [7] seleccion ─────── oración que contiene el tramo (o mejor s_lex en light)
                       s_cov, s_foco sobre esa oración
 [8] politica ──────── cascada_v1 con umbrales calibrados → ok | relacionado | sin_respuesta
 [9] verificacion ──── texto == corpus[ini:fin]; entidades de la respuesta presentes en la fuente
[10] redaccion ─────── mensajes del paquete de idioma + citas ───────▶ AssistantResult + diagnóstico
```

### 2.1 Política `cascada_v1`

| Señal | Origen | Perfiles |
|---|---|---|
| `s_ret` | Score top-1 de recuperación, normalizado | todos |
| `acuerdo` | Coincidencia entre los top de denso y BM25 | todos |
| `s_oov` | Masa IDF de la pregunta ausente del corpus | todos |
| `s_cov`, `s_foco` | Cobertura IDF y términos foco en la oración elegida | todos |
| `s_rr` | Sigmoide del logit del reranker | medium, heavy |
| `s_qa` | Probabilidad del tramo menos la de «sin respuesta» | medium, heavy |

Reglas, en orden (la primera que se cumple decide):

1. Premisa falla → `sin_respuesta` (`premisa`).
2. `s_oov ≥ τ_oov` y señal de dominio < `τ_dominio` → `sin_respuesta` (`fuera_dominio`). La señal de dominio es max(`s_ret`, `s_rr`): el reranker confirma el dominio pero no lo niega (sus logits no son una escala absoluta). `s_ret` es el coseno normalizado con el piso del modelo denso.
3. `s_foco ≥ τ_foco` **y** `s_oov < τ_oov` (el vocabulario de la pregunta existe en el corpus) **y**:
   - con lector: `s_qa ≥ τ_ok`;
   - sin lector (light): `s_ret ≥ τ_ok` y `s_cov ≥ τ_cov` y `acuerdo ≥ 0,5`;

   → `ok`.
4. Señal de dominio ≥ `τ_rel` → `relacionado`. Si `s_foco < τ_foco`, el mensaje nombra el término foco ausente.

**La decisión de la política manda sobre el lector.** En `relacionado`, el
tramo del lector **nunca** se presenta como respuesta: no hay
`respuesta_exacta` y el texto muestra los pasajes bajo el encabezado de
«no encontré una respuesta directa». En `ok`, la oración que responde va
**primero** y el contexto va solo después: la presentación nunca debe hacer
parecer que otra cifra es la respuesta. El lector QA, en cambio, lee una
ventana centrada en la ancla, que no se muestra.
5. Si no → `sin_respuesta`.

Todos los `τ` vienen de `configuracion/calibracion.yaml` (`rag calibrar`).
Sin calibración vigente, se usan los valores conservadores del perfil y
`rag doctor` lo advierte. La decisión guarda la regla que decidió y todas las
señales.

## 3. Patrones de diseño

| Patrón | Dónde | Para qué |
|---|---|---|
| **Strategy + Protocol** | `nucleo/contratos.py` | Retriever, reranker, lector, política y verificador intercambiables |
| **Registry / Factory** | `nucleo/registro.py`, `aplicacion/registro_base.py` | Construir componentes por nombre desde la configuración; los imports pesados viven dentro de la factory |
| **Pipeline** | `consulta/motor.py` + `consulta/etapas/` | El perfil define la lista de etapas; el motor las recorre y mide cada una en un solo lugar |
| **Template Method** | `modelos/onnx.py::ModeloOnnx` | Descarga, sesión, tokenizador y lotes comunes; cada modelo implementa `preparar` e `interpretar` |
| **Adapter** | `indice/qdrant.py`, `modelos/*` | Aíslan Qdrant y onnxruntime detrás de los contratos |
| **Command** | `cli/comandos/*` | Un comando = una clase con `registrar` y `ejecutar` |
| **Facade (casos de uso)** | `aplicacion/*` | La CLI y la API comparten la lógica; los comandos solo presentan |
| **Configuración por capas** | `configuracion/perfiles.py` | perfil ← `motor.yaml` ← `calibracion.yaml` (si la procedencia coincide) |
| **Value objects** | `nucleo/esquemas.py` | Todo dato que cruza una frontera es Pydantic estricto |

### Contratos nuevos (borrador)

```python
# nucleo/contratos.py
class Etapa(Protocol):
    nombre: str
    def ejecutar(self, ctx: "ContextoConsulta") -> None: ...  # cierra con ctx.resultado

class Reranker(Protocol):
    def puntuar(self, pregunta: str, pasajes: Sequence[str]) -> list[float]: ...

class LectorQA(Protocol):
    def leer(self, pregunta: str, pasajes: Sequence[str]) -> list["LecturaQA"]: ...

# nucleo/esquemas.py
class LecturaQA(EsquemaEstricto):
    indice_pasaje: int
    inicio: int               # offset de carácter dentro del pasaje
    fin: int
    texto: str                # == pasaje[inicio:fin]
    prob_respuesta: float
    prob_sin_respuesta: float

class SenalesLexicas(EsquemaEstricto):
    terminos_foco: list[str]   # forma de superficie
    s_oov: float
    s_cov: float | None = None
    s_foco: float | None = None
    s_lex: float | None = None
    acuerdo: float | None = None

# consulta/contexto.py
@dataclass
class ContextoConsulta:
    pregunta: str
    id_sesion: str
    idioma: PaqueteIdioma
    analisis: QueryAnalysis | None = None
    senales: SenalesRecuperacion | None = None
    lexicas: SenalesLexicas | None = None
    candidatos: list[RetrievalCandidate] = field(default_factory=list)
    puntajes_rerank: list[float] | None = None
    lecturas: list[LecturaQA] | None = None
    saltar_modelos: bool = False          # salida temprana léxica
    evidencias: list[EvidenceSpan] = field(default_factory=list)
    decision: DecisionAbstencion | None = None
    resultado: AssistantResult | None = None
    diagnostico: dict = field(default_factory=dict)
```

## 4. Auditoría

Todo lo que influye en una respuesta queda en un archivo legible o en el
diagnóstico:

| Pregunta del auditor | Dónde se responde |
|---|---|
| ¿Con qué se construyó el índice? | `.rag/indice/manifiesto.json`: modelos, idioma, stemmer, hash del corpus, versión del esquema |
| ¿Por qué pesa tanto este término? | `.rag/indice/estadisticas.json`: df, N, largo medio |
| ¿De dónde salen los umbrales? | `configuracion/calibracion.yaml`: banco, hashes, α, resultado en `test` |
| ¿Por qué esta consulta dio `relacionado`? | Diagnóstico de la consulta (`rag preguntar --diagnostico` o el registro): etapas, señales, regla que decidió |
| ¿La respuesta es literal? | `rag auditar` recorre el registro de consultas y comprueba cada evidencia contra el corpus |

El registro de consultas (`.rag/registros/consultas.jsonl`) está apagado por
defecto (privacidad). Se activa con `asistente.yaml: registro.activo: true` y
guarda la pregunta, el estado, la regla, las señales y los offsets; no guarda
datos del usuario.

## 5. Reglas de código

- **Una sola implementación por concepto.** Por ejemplo, una sola
  `terminos()` y una sola `dividir_oraciones()`.
- **Sin módulos puente.** Al mover un módulo, se actualizan todos los imports
  en el mismo cambio.
- **Nada de texto de un idioma en Python.** Las palabras, patrones y mensajes
  viven en el paquete de idioma.
- **Imports pesados solo dentro de las factories.** `import rag` no carga
  onnxruntime ni qdrant_client.
- **Toda etapa se prueba sin modelos**, con dobles en memoria. Las pruebas
  con modelos llevan el marcador `modelos`; las lentas, `slow`.
- **Mensajes accionables:** todo error de configuración dice qué comando
  ejecutar.
- **Comentarios en español que explican el porqué.** Sin referencias a etapas
  históricas («Etapa C», «molde», «E4»).
