# Documentación

| Carpeta | Contenido |
|---|---|
| [guia/](guia/) | Cómo instalar, configurar, evaluar y publicar el asistente |
| [metodologia/](metodologia/README.md) | Una ficha por técnica: qué hace, cómo, límites y pruebas |
| [decisiones/](decisiones/) | Decisiones de arquitectura (ADR) numeradas |
| [plan/](plan/README.md) | Plan V3 en ejecución; se elimina al cerrarlo |

## Mapa del repositorio

| Carpeta | Para qué existe |
|---|---|
| `rag/` | El paquete: código por capas (ver `plan/arquitectura.md` §1.2) y recursos |
| `rag/recursos/` | Plantillas que copia `rag init` y plantillas de despliegue |
| `tests/` | Pruebas espejo de `rag/`, más `datos/` (corpus y banco sintéticos) e `integracion/` |
| `ejemplos/` | Integraciones web probadas: HTML, React y WordPress |
| `docs/` | Esta documentación |
| `.github/` | Integración continua |
