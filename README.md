# rag-extractivo

Asistente documental local que recupera y muestra texto literal de tus propios
documentos. No usa un modelo generativo para redactar respuestas: si no
encuentra evidencia suficiente, lo indica explícitamente.

## Características

- PDF con capa de texto, DOCX, Markdown y TXT.
- Recuperación híbrida: embeddings multilingües + búsqueda léxica en Qdrant.
- Respuestas extractivas con documento, sección y offsets verificables.
- Estados `ok`, `relacionado`, `sin_respuesta` y `conversacional`.
- API FastAPI, CLI y widget web embebible.
- Ejecución local en CPU; después de descargar el modelo puede operar sin red.
- Configuración y apariencia editables mediante YAML.
- Núcleo independiente del dominio: una instalación nueva comienza sin corpus
  ni reglas institucionales.

## Instalación

Desde PyPI, cuando el paquete sea publicado:

```bash
pip install rag-extractivo
```

Desde GitHub:

```bash
pip install "rag-extractivo @ git+https://github.com/USUARIO/rag-extractivo.git"
```

Para desarrollar desde un clon:

```bash
python -m venv .venv
python -m pip install -e ".[test]"
```

En PowerShell puedes invocar explícitamente el intérprete del entorno:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

No copies ni publiques `.venv`: una instalación editable contiene rutas
absolutas. Si mueves el checkout, reinstala con `pip install -e .` o crea un
entorno nuevo.

## Inicio rápido

Crea una carpeta vacía para cada asistente:

```bash
mkdir mi-asistente
cd mi-asistente
rag init
rag configurar nombre_asistente="Asistente de soporte" descripcion_dominio="los manuales de producto"
rag cargar /ruta/a/mis/documentos
rag indexar
rag doctor
rag servir
```

También puedes servir directamente una carpeta documental. Se crea un proyecto
privado en `.rag-extractivo/`, se cargan los archivos y se construye el índice
si hace falta:

```bash
rag servir ./mis-documentos
```

Si la ruta ya es un proyecto, se completan únicamente los archivos faltantes.
Usa `--reindexar` para reconstruir expresamente el índice.

Para elegir y revisar la presentación del widget sin editar CSS ni iniciar el
servicio:

```bash
rag widget tema listar
rag widget tema aplicar editorial
rag widget tema vista-previa
```

Los presets disponibles son `clasico`, `minimal`, `editorial` y `contraste`.
La vista previa se escribe por defecto en `.cache/widget-vista-previa.html` y
muestra respuestas directas, relacionadas, abstención, conversación y citas.
En `configuracion/estilos.yaml`, `presentacion` permite elegir densidad
`comoda|compacta`, citas `acordeon|abiertas|ocultas` y la visibilidad de la
etiqueta de estado. `/config` publica estos valores en modo de solo lectura.

Para exportar el cliente y un snippet:

```bash
rag widget exportar ./public/rag --api https://api.example.com
```

La integración declarativa usa:

```html
<rag-extractivo-chat
  api="https://api.example.com"
  posicion="abajo-derecha">
</rag-extractivo-chat>
<script src="./public/rag/widget.js"></script>
```

El componente admite `api`, `widget-key`, `color`, `titulo`, `saludo` y
`posicion`. Emite los eventos `rag:abierto`, `rag:cerrado`, `rag:pregunta`,
`rag:respuesta` y `rag:error`.

Para inspeccionar los defaults y la selección efectiva de componentes:

```bash
rag snapshot-config
```

El snapshot queda en `.cache/configuracion-efectiva.yaml`. La sección
`componentes` de `configuracion/motor.yaml` usa nombres estables y permite
seleccionar las implementaciones registradas sin cambiar el pipeline.

Para evaluar el backend activo contra un banco versionado y guardar el reporte:

```bash
rag evaluar --banco data/golden/manifiesto.json --salida reporte.json
```

El comando devuelve código distinto de cero si detecta algún falso `ok`.

Para reproducir una comparación aislada entre Qdrant denso e híbrido con el
banco sintético incluido:

```bash
rag benchmark --banco tests/evaluacion/sintetico/manifiesto.json \
  --salida reportes/benchmark
```

El resultado registra configuración, índice, dataset, calibración de `dev` y
métricas. No cambia defaults ni convierte automáticamente los umbrales sugeridos
en configuración de producción.

Prueba la API desde otra terminal:

```bash
rag preguntar "¿Cada cuánto se cambia el filtro?"
```

La primera indexación descarga `intfloat/multilingual-e5-small`. El índice y
los documentos permanecen en la carpeta del proyecto creado por el usuario,
no dentro de la instalación de la librería.

## Integración web

Configura el origen del sitio que alojará el widget:

```bash
rag configurar cors_origenes=https://mi-sitio.example claves_widget=mi-sitio
```

Luego agrega:

```html
<script
  src="https://mi-servidor.example/widget.js"
  data-api="https://mi-servidor.example"
  data-widget-key="mi-sitio">
</script>
```

La clave identifica una integración, pero no es un secreto porque se entrega
al navegador. La protección real del servicio debe completarse en el proxy o
infraestructura de despliegue.

Hay integraciones ejecutables para [HTML](ejemplos/html/),
[React](ejemplos/react/) y [WordPress](ejemplos/wordpress/). Todas usan el
mismo Web Component y muestran dónde configurar la URL, la clave pública y
los eventos del widget.

## Plantillas y estilos globales

La fuente canónica está incluida dentro del paquete:

```text
rag/recursos/plantillas/
├── asistente.yaml
├── categorias.yaml
├── motor.yaml
├── textos.yaml
├── estilos.yaml
└── dominios/
    ├── _generico/perfil.yaml
    └── idiomas/es.yaml
```

`rag init` copia estos recursos a la carpeta actual:

```text
configuracion/
├── asistente.yaml   # identidad, idioma, CORS y claves del widget
├── categorias.yaml  # taxonomía del corpus
├── motor.yaml       # recuperación, Qdrant, abstención y límites
├── textos.yaml      # mensajes, conectores y respuestas conversacionales
├── estilos.yaml     # colores, tipografía, dimensiones y animaciones
└── dominios/
    ├── _generico/perfil.yaml
    └── idiomas/es.yaml
```

Las copias pertenecen al proyecto del usuario y pueden editarse sin modificar
la librería. `rag init` no sobrescribe configuraciones existentes salvo que se
use `--force` para reiniciar `asistente.yaml`.

Para agregar entidades particulares, crea otro perfil YAML bajo
`configuracion/dominios/<perfil>/perfil.yaml` y selecciónalo con:

```bash
rag configurar perfil=mi_perfil
```

## API

Endpoint principal:

```http
POST /consultar
Content-Type: application/json

{
  "pregunta": "¿Cuál es el plazo?",
  "id_sesion": "sesion-opcional"
}
```

La respuesta contiene el estado, el texto extractivo, la confianza, la
latencia y los fragmentos citados. También están disponibles `/health`,
`/ready`, `/config`, `/estilos.css`, `/widget.js` y `/widget/demo.html`.

## Desarrollo y verificación

```bash
python -m pytest -m "not slow"
python -m pytest
```

Las pruebas usan documentos sintéticos. El repositorio no distribuye corpus,
perfiles ni métricas de una institución concreta.

Para comprobar el artefacto distribuible:

```bash
python -m build
pip install dist/rag_extractivo-*.whl
```

La prueba decisiva es ejecutar `rag init` desde una carpeta vacía usando una
instalación normal, no el checkout del repositorio.

## Documentación

- [Plan V3: arquitectura, tareas y avance](docs/plan/README.md)
- [Referencia de configuración](docs/referencia/configuracion.md)
- [Metodologías implementadas](docs/metodologias/README.md)
- [Metodología de recuperación actual](docs/metodologias/recuperacion.md)
- [Instalación en sitios web](docs/referencia/instalacion-web.md)

Los archivos `asistente.yaml` y `motor.yaml` declaran `config_version: 2` y
se validan estrictamente al cargarse. Esto permite detectar errores de nombre
o tipos inválidos antes de indexar o iniciar la API, y prepara migraciones
explícitas cuando cambie el formato.

## Límites actuales

- Los PDF escaneados requieren OCR externo; se rechazan para evitar indexar
  contenido vacío silenciosamente.
- Los umbrales creados por `rag init` son valores iniciales genéricos y deben
  validarse con preguntas representativas del corpus real.
- El modo Qdrant local bloquea su carpeta mientras otro proceso la usa.
- El historial conversacional todavía no se utiliza para resolver preguntas
  de seguimiento.
