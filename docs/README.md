# Documentación

| Carpeta | Contenido |
|---|---|
| [arquitectura.md](arquitectura.md) | Módulos, flujos y diagramas |
| [guia/](guia/) | Cómo instalar, usar, configurar, evaluar, personalizar y desplegar el asistente |
| [metodologia/](metodologia/README.md) | Una ficha por técnica: qué hace, cómo, límites y pruebas |
| [decisiones/](decisiones/) | Decisiones de arquitectura (ADR) numeradas |

## Arquitectura

[arquitectura.md](arquitectura.md): capas de `ipsis/`, qué hace cada módulo,
el flujo de una consulta y de la ingesta, el servicio, el despliegue y dónde
se audita cada decisión, con diagramas.

## Mapa del repositorio

| Carpeta | Para qué existe |
|---|---|
| `ipsis/` | El paquete: código por capas y recursos |
| `tests/` | Pruebas espejo de `ipsis/`, más `datos/` (corpus y bancos sintéticos) e `integracion/` |
| `ejemplos/` | Integraciones web probadas: HTML, React y WordPress |
| `herramientas/avatar/` | Build reproducible del motor del avatar y Folio (solo desarrollo) |
| `docs/` | Esta documentación |
| `.github/` | Formularios de issues y plantilla de pull request |
