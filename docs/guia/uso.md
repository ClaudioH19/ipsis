# Uso

El ciclo de trabajo de un asistente y la referencia de todos los comandos.
La instalación y los perfiles están en [instalacion.md](instalacion.md); el
VPS, Docker y los modos, en [despliegue.md](despliegue.md). El detalle de cada archivo de configuración
está en [configuracion.md](configuracion.md).

## Ciclo de trabajo

```text
ipsis init → ipsis modelos descargar → ipsis cargar → ipsis indexar → ipsis doctor → ipsis servir
                                                    ↑                  │
                    documentos nuevos o cambiados ──┘                  ↓
                                         ipsis preguntar / widget en tu sitio
```

Opcional, para medir y ajustar:

```text
ipsis golden plantilla → (una persona completa golden.csv) → ipsis golden importar
  → ipsis evaluar → ipsis calibrar --aplicar
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
| `ipsis init [--perfil light\|medium\|heavy] [--idioma es] [--nombre-asistente N] [--descripcion-dominio D] [--force]` | Crea `configuracion/` y `documentos/`. Sin `--force` no pisa un proyecto existente |
| `ipsis configurar clave=valor …` | Edita `asistente.yaml`: `nombre_asistente`, `descripcion_dominio`, `idioma`, `perfil`, `cors_origenes`, `claves_widget` (listas separadas por coma) y `registro.activo` (true o false) |
| `ipsis perfil mostrar` | Perfil activo, modelos, presupuesto p95 y si el índice y la calibración le sirven |
| `ipsis perfil cambiar <perfil>` | Cambia el perfil. Avisa si hay que reindexar; la calibración anterior deja de aplicarse |
| `ipsis snapshot-config [--salida RUTA]` | Escribe la configuración efectiva, con los valores por defecto resueltos |

### Modelos

| Comando | Qué hace |
|---|---|
| `ipsis modelos listar` | Modelos del perfil activo: licencia, archivo ONNX de tu CPU y si están en la caché |
| `ipsis modelos descargar [--perfil P]` | Descarga lo que falte a la caché global. Con `--perfil` prepara otro perfil sin activarlo |
| `ipsis modelos verificar` | Comprueba que los archivos estén completos y hace una inferencia mínima por modelo. No descarga |
| `ipsis modelos exportar <id_hf> [--int8]` | Solo desarrollo, con el extra `[exportar]`: convierte a ONNX en `exportados/` |

### Corpus

| Comando | Qué hace |
|---|---|
| `ipsis cargar <archivo\|carpeta>` | Copia los documentos (PDF con texto, DOCX, MD, TXT) a `documentos/` y los cataloga. Si un archivo tiene el mismo nombre que otro ya cargado y distinto contenido, se agrega aparte: para retirar el anterior, marca `vigente: false` en `documentos/catalogo.yaml` |
| `ipsis indexar [--corpus CARPETA]` | Reconstruye el índice completo. Ejecútalo después de cada cambio de documentos o de un cambio de perfil que lo pida |

### Consulta

| Comando | Qué hace |
|---|---|
| `ipsis servir [carpeta] [--host H] [--port P] [--reindexar] [--modo produccion\|desarrollo]` | Levanta la API y el widget. Con una carpeta de documentos, crea y prepara un proyecto privado en `.ipsis-project/`. `--modo`: ver [despliegue.md](despliegue.md#modos-de-ejecución-desarrollo-y-producción); en desarrollo, sin `IPSIS_ADMIN_TOKEN`, imprime un token temporal |
| `ipsis preguntar "<pregunta>" [--url URL] [--timeout S]` | Pregunta al servicio en marcha |
| `ipsis preguntar "<pregunta>" --diagnostico` | Ejecuta el motor localmente, sin servicio, y muestra etapas con su latencia, señales, términos foco, la regla que decidió, el tramo exacto, el tono y las plantillas usadas. En modo Qdrant local, detén `ipsis servir` antes |

### Operación

| Comando | Qué hace |
|---|---|
| `ipsis doctor` | Diagnóstico de solo lectura: configuración, perfil, idioma, stemmer, modelos, índice, calibración, golden, CORS, personalidad y modo. Cada error trae su acción. Sale con 0 si no hay errores |
| `ipsis auditar [--desde FECHA] [--hasta FECHA]` | Revisa el registro de consultas: estados, reglas, tonos y si cada evidencia sigue siendo literal del corpus. Con `--desde`/`--hasta` (`AAAA-MM-DD` o ISO 8601, UTC por defecto, inclusivas) solo cuenta ese rango. El registro se activa con `ipsis configurar registro.activo=true` |

### Personalidad

Detalle en [personalidad.md](personalidad.md). Solo presentación: no pide
reindexar ni recalibrar.

| Comando | Qué hace |
|---|---|
| `ipsis personalidad mostrar` | Tono activo, variedad y avatar (ubicación, tamaño, mirada, colores, eventos con respaldo) |
| `ipsis personalidad validar` | Revisa `personalidad.yaml`, las plantillas propias y el avatar. Sale con 1 si hay errores |
| `ipsis personalidad tono listar` | Tonos del idioma del proyecto, con un ejemplo de cada uno |
| `ipsis personalidad tono aplicar <tono>` | Activa `cordial`, `formal`, `serio`, `animoso`, `cercano`, `empatico` o `directo` |
| `ipsis personalidad tono probar [--tono T] [--situacion S]` | Imprime las variantes con las variables del proyecto |
| `ipsis personalidad avatar listar` | Avatares incluidos e importados |
| `ipsis personalidad avatar importar <archivo.avatar.json> [--nombre N]` | Valida un avatar exportado del Studio y lo copia a `configuracion/avatares/` |
| `ipsis personalidad avatar aplicar <nombre>` | Usa ese avatar en el widget |
| `ipsis personalidad avatar eventos` | Qué animación o expresión dispara cada evento, y cuáles usan un respaldo |
| `ipsis personalidad avatar asignar <evento> <clave>` | Asigna a un evento una clave que el avatar tenga |
| `ipsis personalidad avatar colores [--cuerpo #rrggbb] [--ojos #rrggbb]` | Colores del avatar, sin modificar su archivo |

Sin terminal: el panel gráfico `/admin/panel` hace lo mismo con
formularios y una vista previa del widget. Necesita `IPSIS_ADMIN_TOKEN`; ver
[personalidad.md](personalidad.md#panel-gráfico-adminpanel).

### Golden set y evaluación

Detalle en [golden.md](golden.md).

| Comando | Qué hace |
|---|---|
| `ipsis golden plantilla [--n 40] [--force]` | Genera `golden/golden.csv` y `golden/LEEME.txt` a partir de tus documentos |
| `ipsis golden importar <archivo>` | Valida el CSV, JSONL o SQuAD 2.0, ubica las respuestas, separa dev y test, y escribe `golden/banco/` |
| `ipsis golden validar` | Comprueba el banco contra el corpus actual |
| `ipsis golden exportar --formato squad2\|csv [--salida RUTA]` | Exporta el banco |
| `ipsis evaluar [--banco MANIFIESTO] [--salida RUTA]` | Métricas del perfil activo, con la cota de falsos `ok` |
| `ipsis calibrar [--alfa 0.05] [--aplicar]` | Elige umbrales con control de riesgo usando solo dev. No entrena nada |
| `ipsis comparar <a.json> <b.json> [--salida RUTA]` | Compara dos reportes de `ipsis evaluar` |
| `ipsis benchmark --banco M [--banco M2…] [--perfiles …] [--experimentos] [--solo-latencia] [--repeticiones N] [--salida DIR]` | Compara perfiles: seguridad, cobertura, latencia y costo |

### Widget

Detalle en [web.md](web.md).

| Comando | Qué hace |
|---|---|
| `ipsis widget tema listar` | Presets visuales disponibles |
| `ipsis widget tema aplicar <preset> [--ruta RUTA]` | Aplica un preset a `configuracion/estilos.yaml` |
| `ipsis widget tema vista-previa [--ruta RUTA] [--salida RUTA]` | Genera un HTML para ver el tema |
| `ipsis widget estilo mostrar [--seccion S]` | Cada valor de estilo: `presentacion`, `ubicacion`, `colores`, `colores_oscuro`, `tipografia`, `forma`, `sombras` y `animaciones` |
| `ipsis widget estilo cambiar seccion.clave=valor …` | Cambia uno o más valores (p. ej. `colores.acento=#0ea5e9 forma.radio_panel=10px`). Rechaza claves inexistentes y caracteres CSS peligrosos; si algo falla, no escribe nada |
| `ipsis widget exportar <carpeta> [--api URL] [--posicion P]` | Exporta `widget.js`, `snippet.html`, el motor del avatar (`avatar.js` y sus licencias) y la definición del avatar activo, para servirlos aparte. `P`: `abajo-derecha`, `abajo-izquierda`, `arriba-derecha`, `arriba-izquierda` o `incrustado` |
| `ipsis widget snippet [--api URL] [--componente] [--clave K]` | Imprime el código para pegar en tu sitio, según `estilos.yaml::ubicacion` |

### Despliegue

| Comando | Qué hace |
|---|---|
| `ipsis desplegar preparar [--destino D] [--dominio DOM] [--wheel W] [--forzar]` | Genera en `dist/` todo lo necesario para un VPS: proyecto, índice, `Dockerfile`, `docker-compose.yml` con Caddy opcional y `LEEME_despliegue.md`. Ver [despliegue.md](despliegue.md) |

## Variables de entorno

| Variable | Efecto |
|---|---|
| `IPSIS_MODELS_DIR` | Carpeta de la caché global de modelos |
| `HF_HUB_OFFLINE=1` | Nunca usa la red |
| `IPSIS_ONNX_THREADS` | Hilos de onnxruntime |
| `QDRANT_MODO`, `QDRANT_URL` | Qdrant `local` o `servidor` |
| `IPSIS_MODE`, `IPSIS_ADMIN_TOKEN`, `IPSIS_TRUSTED_PROXY`, `IPSIS_ADMIN_IPS`, `IPSIS_DOCS`, `IPSIS_DEMO`, `IPSIS_SOURCE_URL` | Modo de ejecución y `/admin`; ver [despliegue.md](despliegue.md) |

## Problemas frecuentes

| Síntoma | Qué hacer |
|---|---|
| «already accessed» al indexar o diagnosticar | Qdrant local está bloqueado por `ipsis servir`: detén el servicio o usa Qdrant en modo servidor |
| `ipsis doctor` dice que faltan modelos | `ipsis modelos descargar` |
| Índice incompatible tras cambiar de perfil | `ipsis indexar` |
| Los documentos cambiaron | `ipsis indexar` (`ipsis doctor` lo detecta) |
| El navegador bloquea el widget | Agrega el origen exacto del sitio con `ipsis configurar cors_origenes=https://…` |
| El widget muestra un ícono en vez del avatar | La CSP de tu sitio no permite `'unsafe-eval'` (lo necesita el motor del avatar), o el avatar no es válido: `ipsis personalidad validar`. El chat funciona igual |
| `/ready` responde 503 | Lee `proyecto.bloqueante`: trae el chequeo que falla y el comando que lo arregla (lo mismo que `ipsis doctor`) |
