# Plan V3: asistente extractivo multilingüe en cascada

Este plan reemplaza a `PLAN_V2.md`, `docs/ruta.md`, `docs/avance.md` y
`docs/arquitectura.md`, que se eliminan en P0.2. Su historia queda en git y en
la referencia de respaldo `refs/respaldos/2026-10-03-pre-limpieza`. Al cerrar
V3 (P13.2), este directorio también se borra.

## Objetivo

Un asistente que responde **solo con texto literal** de los documentos del
cliente, en varios idiomas, en CPU, y que **se abstiene** cuando el pasaje se
parece a la pregunta pero no contiene la respuesta. Tiene tres perfiles de
instalación:

| Perfil | p95 objetivo | Cómo decide |
|---|---|---|
| `light` | ≤ 150 ms | Recuperación híbrida + señales léxicas (BM25, IDF, términos foco) |
| `medium` | ≤ 1 s | Lo anterior + reranker cross-encoder + lector QA extractivo |
| `heavy` | ≤ 5 s | Modelos grandes, más candidatos, recuperación dirigida y concordancia |

El repositorio queda **mínimo, entendible y auditable**: 12 carpetas con
nombre de dominio dentro de `rag/`, pruebas que reflejan esa estructura,
una prueba que hace cumplir las dependencias entre capas, y cada decisión
reconstruible desde archivos legibles.

## Documentos

| Archivo | Contenido |
|---|---|
| [arquitectura.md](arquitectura.md) | Estructura del repositorio y del proyecto del cliente, capas, flujo en cascada, política, patrones, auditoría y reglas de código |
| [lexico-y-multilenguaje.md](lexico-y-multilenguaje.md) | BM25 y TF-IDF: estadísticas, señales, salidas tempranas; inventario de reglas atadas al español y paquetes de idioma |
| [modelos-y-perfiles.md](modelos-y-perfiles.md) | Runtime ONNX, modelos candidatos con licencias y definición de perfiles |
| [comandos-y-golden.md](comandos-y-golden.md) | Todos los comandos, formato del golden set y algoritmo de calibración |
| [tareas.md](tareas.md) | 69 tareas en 14 fases, cada una con criterios de aceptación |
| [avance.md](avance.md) | Bitácora que va llenando quien ejecuta |

## Instrucciones para quien ejecuta

1. Lee este archivo, [arquitectura.md](arquitectura.md) y **solo** la tarea en
   curso de [tareas.md](tareas.md), más el documento que esa tarea cite.
2. Una tarea por vez, en orden. No adelantes trabajo.
3. Antes de empezar, la suite rápida debe estar en verde (comando `PYTEST` en
   [tareas.md](tareas.md)).
4. Una tarea termina cuando cumple **todos** sus criterios. Si uno no se
   puede cumplir, detente y explica por qué. No relajes el criterio.
5. Al cerrar, actualiza [avance.md](avance.md): estado, fecha, número de
   pruebas y desvíos.
6. Haz commit por tarea **solo si el usuario lo autorizó**, con el formato
   `P<fase>.<n>: <resumen>`.
7. Para ubicar código, usa `graphify query "<pregunta>"` antes de leer
   archivos completos. Tras cada fase, ejecuta `graphify update .`.
8. No inventes nombres de modelos, versiones ni cifras. Lo que haya que
   verificar se verifica en la fuente y se anota en [avance.md](avance.md).
9. Las tareas marcadas ⚠ requieren una decisión o autorización del usuario.

## Principios

- **Nunca se genera texto.** La respuesta es un tramo literal con documento,
  sección y offsets exactos. Los mensajes salen de plantillas del paquete de
  idioma.
- **Ante la duda, abstenerse.** Un falso `ok` es el error más grave.
- **Explicable antes que opaco.** Las señales léxicas deciden lo que pueden
  decidir y explican la abstención («no encontré información sobre
  “garantía”»). Los modelos se usan donde aportan.
- **Medir antes de decidir.** Los umbrales salen de `rag calibrar`; las
  técnicas nuevas se adoptan solo si mejoran el benchmark.
- **CPU primero.** ONNX Runtime, sin torch en producción.
