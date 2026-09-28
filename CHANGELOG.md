# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto sigue [SemVer](https://semver.org/lang/es/). Mientras la versión
sea 0.x, un cambio menor puede romper compatibilidad y se indica como tal.

## [Sin publicar]

### Cambiado

- **Requiere reindexar.** El tipo de entidad `nota` (escala 1,0–7,0) se
  reemplaza por `decimal`, que reconoce cualquier número con coma o punto
  decimal y lo normaliza a punto. Una escala propia se declara en el perfil;
  la plantilla `dominios/_generico/perfil.yaml` trae un ejemplo.
- Imagen Docker multi-stage construida desde el wheel, con usuario sin
  privilegios y healthcheck contra `/ready`.
- La versión que informa la API se lee del paquete instalado.
- Las pruebas usan un directorio temporal fuera del checkout (en Windows,
  `%LOCALAPPDATA%\rag-extractivo\pytest`); `RAG_PYTEST_BASETEMP` lo cambia.

### Corregido

- **Requiere reindexar.** `12,5%` se extraía como el porcentaje `5`, lo que
  hacía pasar la verificación de premisa a una pregunta por el 5 %.

### Agregado

- Contratos de componentes, esquemas versionados y registry
  (`rag.componentes`, `rag.esquemas`, `rag.registro`). Aún no los usa el
  pipeline; ver `docs/ruta.md`.
- `config_version` en `asistente.yaml` y `motor.yaml`, con validación estricta
  y migración de archivos sin versión.
- `rag snapshot-config`: escribe la configuración efectiva con defaults.
- CI en GitHub Actions: pruebas rápidas en Linux y Windows, integración con
  modelo real y prueba del wheel en un entorno limpio.
- Documentación: arquitectura, ADR, metodología de recuperación, ruta de
  trabajo y bitácora de avance.

## [0.7.0]

Versión inicial publicada en el repositorio.
