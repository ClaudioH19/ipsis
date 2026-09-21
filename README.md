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

## Límites actuales

- Los PDF escaneados requieren OCR externo; se rechazan para evitar indexar
  contenido vacío silenciosamente.
- Los umbrales creados por `rag init` son valores iniciales genéricos y deben
  validarse con preguntas representativas del corpus real.
- El modo Qdrant local bloquea su carpeta mientras otro proceso la usa.
- El historial conversacional todavía no se utiliza para resolver preguntas
  de seguimiento.
