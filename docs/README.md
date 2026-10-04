# Documentación

| Carpeta | Contenido |
|---|---|
| [guia/](guia/) | Cómo instalar, usar, configurar, evaluar, personalizar y desplegar el asistente |
| [metodologia/](metodologia/README.md) | Una ficha por técnica: qué hace, cómo, límites y pruebas |
| [decisiones/](decisiones/) | Decisiones de arquitectura (ADR) numeradas |

## Arquitectura

Tres criterios guían la estructura:

- **Mínima:** cada carpeta agrupa una responsabilidad.
- **Entendible:** el nombre de la carpeta dice qué hay dentro y las
  dependencias van en una sola dirección.
- **Auditable:** toda decisión del asistente se puede reconstruir desde
  archivos legibles, y una prueba hace cumplir las reglas de dependencia.

### Capas de `rag/`

```text
nucleo ◀── configuracion ◀── lenguaje ◀── ingesta · modelos · indice ◀── consulta ◀── evaluacion ◀── aplicacion ◀── cli · servicio
```

| Capa | Responsabilidad |
|---|---|
| `nucleo/` | Contratos (`Protocol`), esquemas Pydantic estrictos y registry |
| `configuracion/` | Esquemas de los YAML, carga, perfiles, migraciones, calibración y personalidad |
| `lenguaje/` | Paquetes de idioma, `terminos()`, señales léxicas, entidades y tonos |
| `ingesta/` | Parsear, fragmentar, metadata y catálogo |
| `modelos/` | Catálogo, descarga y modelos ONNX (denso, reranker, lector) |
| `indice/` | Qdrant, estadísticas léxicas y manifiesto |
| `consulta/` | Motor, contexto y una etapa por archivo en `etapas/` |
| `evaluacion/` | Bancos, golden, métricas, calibración y benchmark (funciones puras) |
| `aplicacion/` | Casos de uso que comparten la CLI y la API |
| `cli/`, `servicio/` | Presentación: comandos y FastAPI (solo importan `aplicacion`, `nucleo` y `recursos`) |
| `recursos/` | Plantillas, idiomas, tonos, perfiles, avatares y despliegue |

Reglas: un módulo solo importa de su capa o de las anteriores;
`nucleo`, `configuracion` y `lenguaje` no cargan librerías pesadas;
`tests/test_arquitectura.py` lo verifica en cada CI.

### Flujo de una consulta

```text
pregunta
 conversacional ── patrón del paquete de idioma ─────────────▶ respuesta fija
 analisis ──────── términos (stem), entidades
 confianza ─────── coseno denso del mejor pasaje → s_ret
 filtros ───────── términos foco y s_oov
 recuperacion ──── Qdrant: e5 + BM25 con RRF, más la dirigida por entidad;
                   salida temprana si ningún candidato tiene un término foco
 reranking ─────── cross-encoder → s_rr                     (medium, heavy)
 lectura ───────── lector QA → tramo literal, s_qa          (medium, heavy)
 evidencia ─────── oración ancla → s_foco, s_cov
 politica ──────── cascada_v1 → ok | relacionado | sin_respuesta
 redaccion ─────── tono + citas
 verificacion ──── texto == corpus[inicio:fin]
```

Cada etapa completa un `ContextoConsulta` y puede cerrar la consulta. Las
fichas de [metodologia/](metodologia/README.md) detallan cada paso.

### Auditoría

| Pregunta del auditor | Dónde se responde |
|---|---|
| ¿Con qué se construyó el índice? | `.rag/indice/*.manifiesto.json`: modelo, stemmer, hash del corpus, versión del payload |
| ¿Por qué pesa tanto este término? | `.rag/indice/estadisticas.json`: df, N, largo medio |
| ¿De dónde salen los umbrales? | `configuracion/calibracion.yaml`: banco, hashes, α y resultado en `test` |
| ¿Por qué esta consulta dio `relacionado`? | `rag preguntar --diagnostico` o el registro: etapas, señales y regla que decidió |
| ¿La respuesta es literal? | `rag auditar`: comprueba cada evidencia del registro contra el corpus |

## Mapa del repositorio

| Carpeta | Para qué existe |
|---|---|
| `rag/` | El paquete: código por capas y recursos |
| `tests/` | Pruebas espejo de `rag/`, más `datos/` (corpus y bancos sintéticos) e `integracion/` |
| `ejemplos/` | Integraciones web probadas: HTML, React y WordPress |
| `herramientas/avatar/` | Build reproducible del motor del avatar y Folio (solo desarrollo) |
| `docs/` | Esta documentación |
| `.github/` | Integración continua |
