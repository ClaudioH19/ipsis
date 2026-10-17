# Fuentes tabulares y consultas deterministas

Revisión del 2026-10-14. La propuesta de conectores, permisos, sincronización y
consulta exacta de este documento todavía no está implementada. Los cambios
actuales se limitan al banco de ayuda del motor v2 y a esta revisión.

## Hallazgos del código actual

| Aspecto | Estado observado | Consecuencia |
|---|---|---|
| Formatos | [tabulares.py](../../ipsis/ingesta/tabulares.py) lee XLSX, XLS, CSV y TSV. | CSV ya puede ser una entrada; no hace falta convertirlo a Excel. |
| Recuperación | Se conserva cada fila con encabezados y coordenadas. [ingesta.py](../../ipsis/ingesta/ingesta.py) usa el fragmentado por registro. | Se localizan registros; no se calcula stock ni se agregan filas. |
| Columnas | El parser conserva todas las columnas. XLSX incluye hojas ocultas con aviso y notas fuera de tablas. | El archivo debe contener únicamente información apta para su audiencia antes de cargarlo. |
| Conexión DB | La ingesta trabaja con archivos del catálogo. No se encontró un conector de base de datos ni un programador de sincronización. | Un CSV exportado es una copia de datos; cargarlo no habilita consultas en vivo. |
| Actualización | [catalogo.py](../../ipsis/ingesta/catalogo.py) puede conservar como activas dos versiones con el mismo nombre y contenido distinto. | Repetir `load` no es un reemplazo seguro de un inventario. Hay que resolver la vigencia y reindexar. |
| Acceso | [seguridad.py](../../ipsis/servicio/seguridad.py) indica que la clave del widget es pública y no autentica usuarios finales. | No sirve como separación de datos privados por persona, rol o bodega. |
| Templates v2 | [motor.py](../../ipsis/consulta/v2/motor.py) usa el banco `recursos/voz` para cortesía y ayuda fija. | Este es el banco prioritario para corregir la descripción del producto actual. |
| Templates heredados | `recursos/tonos`, identidad inicial y algunas FAQs siguen usando vocabulario documental. | Hay una segunda migración de textos pendiente; no corresponde anunciar que todo el catálogo ya es neutral. |

## Identidad y templates

La identidad propuesta es: **asistente multipropósito que recupera información
de las fuentes configuradas en un proyecto y muestra su procedencia**. El tipo
de fuente y las operaciones disponibles son capacidades de la instalación.
La identidad general no debe prometer que ya existe una conexión a una DB.

Textos recomendados:

- Bienvenida: «Indica el tema, nombre o identificador que quieres consultar».
- Capacidad: «Recupero información de las fuentes indexadas de este proyecto y
  muestro su procedencia».
- Sin coincidencias: «No encontré coincidencias en las fuentes consultadas».
  Esto no prueba que el registro no exista en el sistema original.
- Campo sin configurar: «Este campo no está disponible para esta consulta».
- Copia vencida: «La última actualización disponible es del [fecha y hora]».
- Ejemplo: «Consulta [identificador] y el campo [nombre visible]».

«Fuentes» permite abarcar documentos y datos tabulares. Un template de ayuda
no debe prometer ejecutar tareas, redactar respuestas nuevas, modificar una
DB, dar valores en tiempo real ni deducir equivalencias entre campos.
Los ejemplos de inventario pertenecen a una configuración de inventario;
procedimientos, contratos y otras fuentes pueden ofrecer sus propios ejemplos.

En esta revisión se neutralizaron la identidad, capacidad y orientación del
banco v2 en es/en/pt. Se añadieron FAQs sobre acceso DB, actualización y
columnas sensibles. Las preguntas fijas siguen siendo ayuda sobre el
asistente: no contienen respuestas sobre el negocio y no sustituyen búsquedas
mixtas. El selector y el comportamiento de recuperación no cambiaron.

La siguiente migración de textos debe cubrir los tonos de v1 y los nombres
predeterminados de `assistant.yaml`, carga y paquetes de idiomas. Debe
preservar los nombres elegidos por usuarios de proyectos existentes y comprobar
los contratos de variantes del tono; una búsqueda y reemplazo general no basta.

## Función útil para bodegas

La función inicial propuesta es **consultar registros autorizados por
identificador y mostrar campos seleccionados con su origen y fecha de corte**.
El contrato general sirve también para catálogos, activos, pedidos y otros
registros. No necesita que todas las bases tengan una columna llamada `stock`.

| Consulta | Requisito de configuración | Resultado |
|---|---|---|
| Localizar un artículo | Campo identificador, tipo textual y clave única | Registro exacto o estado sin coincidencias. |
| Mostrar ubicación | Campo físico configurado y etiqueta visible | Valor literal de la ubicación. |
| Consultar existencia | Campo con significado verificado, unidad y alcance | Valor de ese campo a la fecha de corte. |
| Consultar por bodega | Clave compuesta y bodega autorizada | Registro en esa bodega; si falta identificarla, se solicita precisión. |
| Revisar instrucciones | Fuentes documentales habilitadas | Pasajes con sus referencias, como hoy. |

La configuración debe indicar qué representa cada fila: producto, producto y
bodega, producto y lote, ubicación, o movimiento. Varias filas de movimientos
no se convierten en existencias por elegir una columna llamada `cantidad`.
Tampoco hay equivalencia automática entre existencia física, disponible y
reservada. Un valor `0`, una celda vacía y la ausencia de registro son estados
distintos. Un cero no afirma por sí solo que no se pueda atender un pedido.

Si una instalación necesita totales, disponibilidad o alertas, puede exponer
una vista calculada y mantenida por el sistema de origen, con una definición
explícita. Otra fase podría implementar operaciones tipadas y probadas; cada
operación requeriría unidades, reglas de nulos, filtros y permisos. No debe
deducirse una fórmula de negocio a partir de la pregunta ni sumar candidatos
del ranking: una búsqueda de texto no garantiza encontrar todas las filas.

## Mapeo explícito, independiente del esquema físico

Ejemplo **ilustrativo de un contrato futuro**, no configuración aceptada por
ipsis actualmente:

```yaml
source_id: warehouse_inventory
approved_view: assistant_inventory
record_key: [item_code, warehouse_code]
fields:
  item_code:
    column: cod_art
    type: string
    label: Código
  warehouse_code:
    column: cod_bod
    type: string
    label: Bodega
  available_quantity:
    column: cantidad_disponible
    type: decimal
    label: Existencia disponible
    unit: unidades
    aliases: [existencia disponible, cantidad disponible]
operations: [lookup_by_key, show_fields]
refresh:
  interval_seconds: 300
  max_age_seconds: 600
  stale_behavior: reject_value_lookup
```

El administrador elige `cantidad_disponible` después de verificar su significado
en esa base. Otra instalación puede mapear `qty_available` al mismo campo
lógico. Los alias pertenecen a esa fuente: no son sinónimos globales que
equiparen `stock` y `cantidad` en cualquier documento. Se conserva el valor
literal original y la referencia; la etiqueta configurada es presentación.

Al activar el contrato se comprueban columnas, tipos, clave y unidades. Si
falta una columna o cambia su tipo, la actualización falla; no se elige otra
columna por parecido. Una nueva columna no se publica automáticamente.
Las claves mantienen ceros iniciales. CSV necesita un contrato explícito de
separador, codificación, nulos, decimales y fechas para la sincronización;
el lector genérico actual detecta el separador y no valida estos tipos.

El flujo exacto recibe operación, fuente, clave y campos. Puede presentarse
como formulario o controles estructurados. La entrada libre solo se traduce
a ese contrato mediante reglas y alias configurados; si hay varias
interpretaciones, se solicita precisión. La búsqueda natural actual sigue
sirviendo para explorar información; el ranking no certifica una consulta
exacta de existencias.

Para la misma operación normalizada, principal autorizado, configuración y
snapshot, se obtiene el mismo registro y estado, con un orden estable.
Estados previstos: `ok`, `not_found`, `ambiguous`, `field_unavailable`,
`stale` y `source_unavailable`. El mensaje de denegación no confirma la
existencia de tablas, columnas o registros restringidos.

## Publicación de datos permitidos

El formato no es una barrera de acceso. CSV simplifica el intercambio de una
tabla y evita hojas ocultas, pero puede contener los mismos datos sensibles.
Excel puede mantenerse como entrada manual para fuentes ya revisadas.

El conector propuesto lee una **vista aprobada**, con una cuenta de solo
lectura limitada a esa vista. La selección de tablas, columnas y filas es
explícita y deniega lo que no esté configurado. Las restricciones de filas
incluyen organización y bodega cuando corresponda. Nunca se exporta toda la
DB para ocultar columnas después en el widget. Detectores de datos sensibles
pueden asistir en la revisión, pero no sustituyen la lista de campos permitidos.

Los datos excluidos no deben llegar a archivos de exportación, texto canónico,
embeddings, payloads, contexto ampliado, logs ni copias temporales. Los filtros
se aplican antes de indexar; las restricciones de audiencia también antes de
recuperar y de abrir contexto. Ante públicos diferentes, se requieren índices
separados o autenticación y filtros que cubran todas las rutas de lectura.
La clave pública del widget actual no satisface ese requisito.

Los secretos de conexión permanecen en el entorno del servicio o un almacén
de secretos, no en YAML exportable ni en el navegador. Las consultas están
predefinidas y sus valores parametrizados; la pregunta nunca se ejecuta como
SQL. Las etiquetas y nombres de exportación también deben revisarse, porque
pueden revelar información. Si se ofrece descargar CSV para abrirlo en Excel,
esa salida necesita tratamiento de celdas interpretables como fórmulas sin
alterar el dato canónico recuperable.

## Actualización y vigencia

Flujo propuesto:

```mermaid
flowchart LR
    V[Vista aprobada de la DB] --> C[Conector de solo lectura]
    C --> P[Validar contrato y permisos]
    P --> S[Snapshot permitido y manifiesto]
    S --> I[Preparar y construir nuevo índice]
    I --> A[Activar generación completa]
    A --> Q[Consultar registros y documentos]
```

CSV puede ser un artefacto intermedio opcional; un adaptador puede construir
registros directamente. El contrato de seguridad y procedencia es el mismo.
La primera versión puede usar snapshots completos pequeños, antes de abordar
actualizaciones incrementales y detección de borrados.

Cada ejecución debe:

1. Obtener una lectura consistente de la vista aprobada, con límites de tiempo
   y tamaño. Evitar ejecuciones superpuestas de la misma fuente.
2. Validar tipos, columnas, claves únicas, permisos y restricciones de filas.
   Una extracción parcial no es un snapshot válido. Un conjunto vacío puede
   ser una actualización legítima: no debe confundirse con un fallo, aunque
   el parser tabular actual rechaza archivos sin filas de datos.
3. Registrar identificador de fuente, generación, hash, versión del contrato,
   fecha de extracción y, si existe, marca de actualización del origen. Una
   fecha de extracción no prueba que la DB se haya actualizado recientemente.
4. Preparar el nuevo índice fuera del activo. Publicar conjuntamente índice,
   registros, catálogo, contexto y manifiesto cuando todas las etapas pasen.
5. Sustituir la generación anterior, incluyendo registros borrados y versiones
   retiradas. Mantener los cursores ligados a una generación o invalidarlos
   explícitamente para no mezclar resultados de dos actualizaciones.
6. Mostrar la fecha de corte y aplicar el límite de antigüedad. Un escaneo cada
   cinco minutos ofrece una copia periódica; no promete información siempre
   actualizada ni tiempo real. Para consultar el valor al momento se necesita
   una operación DB en vivo, limitada y autorizada, como capacidad posterior.

Si falla la extracción o el índice, se conserva la generación anterior con su
fecha original; se rechazan consultas exactas de valores cuando venza el
límite configurado. Una revocación de permisos bloquea el acceso afectado de
inmediato: no puede seguir sirviéndose la copia anterior por disponibilidad.
Un rollback debe validar la política vigente y no reexponer campos retirados.
Las copias antiguas y registros de ejecución necesitan una retención definida.

## Orden de implementación y criterios de aceptación

1. **Ayuda neutral del motor actual:** cambio realizado en esta revisión.
   Comprobar las FAQs completas, cortesía, consultas mixtas y recursos es/en/pt.
2. **Migración restante de identidad y tonos:** comprobar variantes e identidad
   de proyectos nuevos, preservando las personalizaciones existentes.
3. **Contrato tabular:** lista de campos permitidos, tipos, claves y aliases por
   fuente. Pruebas con `stock`, `cantidad`, `qty_available`, claves compuestas,
   encabezados duplicados, nulos y cambio de esquema. Ningún alias deduce una
   equivalencia empresarial sin configuración.
4. **Consulta exacta:** probar aislamiento por audiencia, coincidencia de clave,
   ambigüedad, ceros iniciales y ausencia de campos. El ranking documental no
   decide valores ni agregaciones. Mismo contrato y snapshot, mismo resultado.
5. **Conector y sincronización:** empezar por un motor DB concreto y vistas
   aprobadas. Probar columnas y tablas excluidas, restricciones de filas, fallo
   parcial, borrados, snapshot vacío, reintentos, atomicidad, cursores, caducidad
   y revocación. Revisar índice, contexto, archivos temporales y logs para
   comprobar que ningún dato excluido se publicó.

La elección del primer motor DB, la audiencia del inventario y la antigüedad
máxima admisible quedan por definir al implementar esa fase. No son necesarias
para neutralizar la ayuda ni para reconocer que CSV ya está soportado.
