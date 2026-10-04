# Uso

El ciclo de trabajo de un asistente y la referencia de todos los comandos.
La instalación, los perfiles, el VPS y los modos están en
[instalacion.md](instalacion.md). El detalle de cada archivo de configuración
está en [configuracion.md](configuracion.md).

> Las partes marcadas **(P12.x)** están planificadas y todavía no existen.

## Ciclo de trabajo

```text
rag init → rag modelos descargar → rag cargar → rag indexar → rag doctor → rag servir
                                                    ↑                  │
                    documentos nuevos o cambiados ──┘                  ↓
                                         rag preguntar / widget en tu sitio
```

Opcional, para medir y ajustar:

```text
rag golden plantilla → (una persona completa golden.csv) → rag golden importar
  → rag evaluar → rag calibrar --aplicar
```

## Qué responde el asistente

Cada respuesta tiene un estado, que el widget pinta distinto:

| Estado | Qué significa |
|---|---|
| `ok` | Encontró el texto que responde; lo muestra literal, con la cita |
| `relacionado` | No hay respuesta directa; muestra lo más cercano y lo dice |
| `sin_respuesta` | No está en los documentos |
| `conversacional` | Saludo, agradecimiento, despedida o «qué puedes hacer» |

El asistente nunca redacta contenido: el texto viene literal de tus
documentos, y las citas, con documento, sección y offsets, van debajo para
comprobarlo.

## Referencia de comandos

### Proyecto

| Comando | Qué hace |
|---|---|
| `rag init [--perfil light\|medium\|heavy] [--idioma es] [--nombre-asistente N] [--descripcion-dominio D] [--force]` | Crea `configuracion/` y `documentos/`. Sin `--force` no pisa un proyecto existente |
| `rag configurar clave=valor …` | Edita `asistente.yaml`: `nombre_asistente`, `descripcion_dominio`, `idioma`, `perfil`, `cors_origenes`, `claves_widget` (listas separadas por coma) y `registro.activo` (true o false) |
| `rag perfil mostrar` | Perfil activo, modelos, presupuesto p95 y si el índice y la calibración le sirven |
| `rag perfil cambiar <perfil>` | Cambia el perfil. Avisa si hay que reindexar; la calibración anterior deja de aplicarse |
| `rag snapshot-config [--salida RUTA]` | Escribe la configuración efectiva, con los valores por defecto resueltos |

### Modelos

| Comando | Qué hace |
|---|---|
| `rag modelos listar` | Modelos del perfil activo: licencia, archivo ONNX de tu CPU y si están en la caché |
| `rag modelos descargar [--perfil P]` | Descarga lo que falte a la caché global. Con `--perfil` prepara otro perfil sin activarlo |
| `rag modelos verificar` | Comprueba que los archivos estén completos y hace una inferencia mínima por modelo. No descarga |
| `rag modelos exportar <id_hf> [--int8]` | Solo desarrollo, con el extra `[exportar]`: convierte a ONNX en `exportados/` |

### Corpus

| Comando | Qué hace |
|---|---|
| `rag cargar <archivo\|carpeta>` | Copia los documentos (PDF con texto, DOCX, MD, TXT) a `documentos/` y los cataloga. Si un archivo tiene el mismo nombre que otro ya cargado y distinto contenido, se agrega aparte: para retirar el anterior, marca `vigente: false` en `documentos/catalogo.yaml` |
| `rag indexar [--corpus CARPETA]` | Reconstruye el índice completo. Ejecútalo después de cada cambio de documentos o de un cambio de perfil que lo pida |

### Consulta

| Comando | Qué hace |
|---|---|
| `rag servir [carpeta] [--host H] [--port P] [--reindexar]` | Levanta la API y el widget. Con una carpeta de documentos, crea y prepara un proyecto privado en `.rag-extractivo/`. Pendiente **(P12.6)**: `--modo desarrollo\|produccion` |
| `rag preguntar "<pregunta>" [--url URL] [--timeout S]` | Pregunta al servicio en marcha |
| `rag preguntar "<pregunta>" --diagnostico` | Ejecuta el motor localmente, sin servicio, y muestra etapas con su latencia, señales, términos foco, la regla que decidió y el tramo exacto. En modo Qdrant local, detén `rag servir` antes |

### Operación

| Comando | Qué hace |
|---|---|
| `rag doctor` | Diagnóstico de solo lectura: configuración, perfil, idioma, stemmer, modelos, índice, calibración, golden y CORS. Cada error trae su acción. Sale con 0 si no hay errores |
| `rag auditar` | Revisa el registro de consultas: estados, reglas y si cada evidencia sigue siendo literal del corpus. El registro se activa con `rag configurar registro.activo=true` |

### Golden set y evaluación

Detalle en [golden.md](golden.md).

| Comando | Qué hace |
|---|---|
| `rag golden plantilla [--n 40] [--force]` | Genera `golden/golden.csv` y `golden/LEEME.txt` a partir de tus documentos |
| `rag golden importar <archivo>` | Valida el CSV, JSONL o SQuAD 2.0, ubica las respuestas, separa dev y test, y escribe `golden/banco/` |
| `rag golden validar` | Comprueba el banco contra el corpus actual |
| `rag golden exportar --formato squad2\|csv [--salida RUTA]` | Exporta el banco |
| `rag evaluar [--banco MANIFIESTO] [--salida RUTA]` | Métricas del perfil activo, con la cota de falsos `ok` |
| `rag calibrar [--alfa 0.05] [--aplicar]` | Elige umbrales con control de riesgo usando solo dev. No entrena nada |
| `rag comparar <a.json> <b.json> [--salida RUTA]` | Compara dos reportes de `rag evaluar` |
| `rag benchmark --banco M [--banco M2…] [--perfiles …] [--experimentos] [--solo-latencia] [--repeticiones N] [--salida DIR]` | Compara perfiles: seguridad, cobertura, latencia y costo |

### Widget

Detalle en [web.md](web.md).

| Comando | Qué hace |
|---|---|
| `rag widget tema listar` | Presets visuales disponibles |
| `rag widget tema aplicar <preset> [--ruta RUTA]` | Aplica un preset a `configuracion/estilos.yaml` |
| `rag widget tema vista-previa [--ruta RUTA] [--salida RUTA]` | Genera un HTML para ver el tema |
| `rag widget exportar <carpeta> [--api URL] [--posicion abajo-derecha\|abajo-izquierda]` | Exporta `widget.js` y `snippet.html` para servirlos aparte |

### Planificados (P12)

| Comando | Tarea |
|---|---|
| `rag personalidad mostrar\|validar` | P12.4 |
| `rag personalidad tono listar\|aplicar <tono>\|probar` | P12.4: tonos `cordial`, `formal`, `serio`, `animoso`, `cercano`, `empatico` y `directo` |
| `rag personalidad avatar listar\|importar\|aplicar\|eventos\|asignar\|colores` | P12.4: avatar «Folio» y los que importes |
| `rag widget snippet` | P12.5 |
| `rag desplegar preparar` | P12.13 |

## Variables de entorno

| Variable | Efecto |
|---|---|
| `RAG_MODELOS_DIR` | Carpeta de la caché global de modelos |
| `HF_HUB_OFFLINE=1` | Nunca usa la red |
| `RAG_HILOS_ONNX` | Hilos de onnxruntime |
| `QDRANT_MODO`, `QDRANT_URL` | Qdrant `local` o `servidor` |
| `RAG_MODO`, `RAG_ADMIN_TOKEN`, `RAG_PROXY_CONFIABLE`, `RAG_ADMIN_IPS`, `RAG_DOCS`, `RAG_DEMO` | Modo de ejecución y panel `/admin` **(P12.6)**; ver [instalacion.md](instalacion.md) |

## Problemas frecuentes

| Síntoma | Qué hacer |
|---|---|
| «already accessed» al indexar o diagnosticar | Qdrant local está bloqueado por `rag servir`: detén el servicio o usa Qdrant en modo servidor |
| `rag doctor` dice que faltan modelos | `rag modelos descargar` |
| Índice incompatible tras cambiar de perfil | `rag indexar` |
| Los documentos cambiaron | `rag indexar` (`rag doctor` lo detecta) |
| El navegador bloquea el widget | Agrega el origen exacto del sitio con `rag configurar cors_origenes=https://…` |
