# Integración y medición local

> **Actualización (2026-10-08):** el perfil heavy se retiró después de estas
> mediciones; ninguna variante superó a medium. Ver la actualización de
> [ADR 0003](../../decisions/0003-onnx-and-profiles.md). Las variantes de la
> regresión general se construyen ahora sobre medium (`medium+<variante>`).

Decisión de uso: **medium es la opción recomendada**. Heavy queda como
alternativa experimental con soporte técnico y cobertura de regresión, sin
ventaja de calidad demostrada. Su sustitución mejoró el heavy anterior, pero
no justifica ofrecerlo como un nivel superior a medium. La descripción del
perfil y las guías reflejan esta distinción.

La integración añade al catálogo seis modelos con revisión fija: Granite
311M/97M R2, Harrier-270M, EmbeddingGemma 2 y Horizon multilingual base/small.
Todos cargaron con CPUExecutionProvider y ejecutaron inferencia real. Se
validaron pooling CLS o salida agregada, padding explícito, prefijos,
dimensiones, valores finitos, normalización y archivos externos. EmbeddingGemma
2 usa solo texto y entradas vacías para imagen/vídeo/audio. El runtime también
soporta último token; Qwen/GTE siguen como investigación, sin promoción.

Las variantes aíslan un componente, conservando mDeBERTa, los umbrales y
cascada 20/4/2, 600 caracteres, sin concordancia. `granite-horizon` cambia dos
componentes. Se construye un índice nuevo en un proyecto temporal por trabajo;
los artefactos capturan el perfil efectivo y los contratos completos. La
configuración del modelo denso se aplica al indexado y a la recuperación.

El primer banco general bien formateado (versión 1.0.0, 26 casos) dio 10/12 aciertos respondibles y
cero respuestas incorrectas aceptadas en medium y los seis candidatos.
Horizon base/small subieron p95 a 1150/748 ms, frente a 545 ms de medium;
no mejoraron precisión en esos casos. Estos tiempos son de esa corrida, no
una garantía para otros documentos.

En el banco de consultas español, Granite-311M obtuvo 25/34 aciertos y cero
errores aceptados, igual que medium. El heavy anterior tenía 21/34 y dos
errores aceptados bajo el mismo criterio de respuesta completa v2; sus
artefactos están en [evaluación anterior](../evaluacion-v2/README.md). Esta
comparación de exactitud no atribuye el cambio solo al modelo: también cambia
la cascada. Las latencias entre corridas históricas no son una medición
controlada del efecto exclusivo del recuperador.

El nuevo heavy predeterminado usa Granite-311M R2 + mMiniLM + mDeBERTa y la
cascada acotada anterior. Granite dispone de ONNX del fabricante y una revisión
verificada. La decisión corrige el heavy anterior; **no hay demostración de
mayor precisión que medium**. Horizon queda opcional por su coste sin ganancia
en el primer banco. El nombre heavy y la fecha de entrenamiento no sustituyen
una evaluación del corpus real del cliente.

El [banco general](../../../tests/datos/banco_general/README.md) y su referencia
congelada permiten comprobar los tres perfiles, tres calidades y cuatro
temas/formatos después de cambios. El [procedimiento](../../../herramientas/evaluacion/README.md)
incluye comandos, CI y modos exploratorio, regresión y estricto. La referencia
es una caracterización, no una certificación de precisión: los fallos existentes
quedan visibles y una referencia con esos fallos puede pasar regresión.

Las configuraciones alternativas y el regreso al heavy anterior
están documentados en la [guía](../../es/guia/configuracion.md#modelos-alternativos).

## Resultados y límites observados

Se completó el banco de consultas español para medium y los seis candidatos
individuales (420 observaciones). Todos conservan exactamente los mismos 25
aciertos; no hay preguntas ganadas o perdidas frente a medium. Ambos Horizon
añaden un error aceptado en «¿Quién lo aprueba?» sin antecedente. Su p95 fue
13.786 ms (base) y 5.391 ms (small), frente a 3.442 ms en medium y 3.352 ms
en Granite-311M. Son latencias exploratorias: durante parte de estas corridas
se ejecutaron pruebas de código; diferencias pequeñas no prueban superioridad.
La combinada Granite/Horizon no se ejecutó completa: Horizon ya incumplía
precisión y presupuesto por separado, sin aportar aciertos. Continúa disponible
como variante para investigación, sin aprobación de calidad.

La prueba general 1.1.0 añade las dos preguntas ambiguas conocidas, sin cambiar
los documentos ni las evidencias originales. Se ejecutaron 84 preguntas por
perfil (252 observaciones), con los tres niveles de formato. En **cada calidad**:

| Perfil | Correctas / respondibles | Incorrectas aceptadas | Negativas sin respuesta directa |
|---|---:|---:|---:|
| light | 9/12 | 3 | 13/16 |
| medium | 10/12 | 0 | 16/16 |
| heavy (Granite-311M R2) | 10/12 | 0 | 16/16 |

La ejecución estricta falla para light en las tres calidades: responde a dos
preguntas de coste con datos de mantenimiento/despacho y a una premisa falsa
de temperatura con un pasaje. Se conserva este resultado fallido y no se
presenta como aprobación. La referencia de regresión registra esos defectos
conocidos para impedir errores nuevos o pérdida de aciertos; no los corrige ni
los transforma en éxitos.

Medium/heavy dejan como `relacionado` dos paráfrasis respondibles: anticipación
para pedir teletrabajo y rango de temperatura. Aunque no aceptan respuestas
incorrectas en este conjunto, no alcanzan cobertura completa. También hay
desajustes de clasificación: solo 4/16 negativos tienen el estado exacto
esperado; los demás suelen quedar `relacionado`, incluidas consultas que
deberían pedir aclaración o quedar fuera de dominio. La tabla distingue esta
clasificación de no aceptar una respuesta incorrecta. La prueba no certifica
que esas rutas de UX estén resueltas ni garantiza precisión en documentos reales.

- [Primer banco bien formateado](candidatos-bueno-v1.md) y [JSON](candidatos-bueno-v1.json).
- [Seis candidatos en consultas](candidatos-consultas.md) y [JSON](candidatos-consultas.json).
- [Prueba general estricta](general-estricto-v11.md) y [JSON](general-estricto-v11.json).
- [Inferencia real de los seis modelos](verificacion-inferencia.json).
- [Artefactos por pregunta y pruebas de código](artefactos-implementacion.zip).
- [Referencia de regresión](../../../tests/datos/banco_general/linea_base.json).
- [Medición de referencia](general-referencia-v11.md) y [JSON](general-referencia-v11.json).

La suite de código sin `slow/browser` pasó: 1024 pruebas, dos omisiones,
115 excluidas. La regresión real queda también incorporada a pytest y CI.
La repetición contra la referencia (los tres perfiles, las tres calidades) y
las comprobaciones de banco/documentación pasaron: 15 pruebas en 224,76 s.
Se fijaron los bytes del banco en `.gitattributes` para conservar los hashes
en Windows y Linux. El workflow quedó configurado; su ejecución remota tendrá
lugar al publicar los cambios en el repositorio.
