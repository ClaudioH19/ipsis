# Despliegue de {{nombre_asistente}}

Generado por `ipsis deploy prepare` (perfil `{{perfil}}`). Esta carpeta
trae todo lo que el servicio necesita: configuración, documentos, índice,
calibración y avatares. Cópiala completa al servidor (VPS).

## 1. En el servidor

Necesitas Docker con el plugin `compose`. Luego, dentro de esta carpeta:

```bash
cp .env.example .env               # y completa IPSIS_ADMIN_TOKEN si quieres /admin
sudo chown -R 10001:10001 config .ipsis   # el contenedor no corre como root
docker compose --profile https up -d --build
```

- **HTTPS:** con el perfil `https`, Caddy pide y renueva el certificado de
  `{{dominio}}`. Antes, apunta el DNS del dominio a la IP del servidor y abre
  los puertos 80 y 443.
- **Sin Caddy:** `docker compose up -d --build` deja el asistente solo en
  `127.0.0.1:8000`, para tu propio proxy.
- **Comprobar:** `curl https://{{dominio}}/ready` responde 200 si todo está
  listo; si no, `proyecto.bloqueante` dice qué falta y con qué comando.

La primera construcción descarga los modelos del perfil. Después el
servicio no usa la red.

## 2. En tu sitio web

Pega antes de `</body>`:

```html
{{snippet}}
```

Y autoriza tu sitio en el servicio (en `config/assistant.yaml`,
`cors_origins`), por ejemplo con `ipsis configure cors_origins=https://www.tu-sitio.cl`
antes de preparar el despliegue.

## 3. Panel `/admin`

1. Genera un token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Ponlo en `.env` como `IPSIS_ADMIN_TOKEN=...`.
3. `docker compose --profile https up -d`.
4. Abre `https://{{dominio}}/admin/panel` y pega el token.

En producción `/admin` exige HTTPS. Sin token, el panel no existe.

## Cambiar configuración

Desde la carpeta del proyecto en tu equipo, antes de preparar el despliegue:

```bash
ipsis configure cors_origins=https://www.tu-sitio.cl query_log.enabled=true
ipsis configure posture.mode=strict
ipsis profile set medium
ipsis models download
ipsis profile show
ipsis snapshot-config --output reports/config-review.yaml
```

`configure` edita `config/assistant.yaml`. La lectura y los umbrales se ajustan
en `config/engine.yaml`, combinando este bloque con el que ya exista:

```yaml
profile_overrides:
  cascade:
    read_m: 2
    max_reading_chars: 600
  default_thresholds:
    ok: 0.80
    focus: 1.0
```

Son valores de `medium`, no una garantía de precisión. La precedencia es
perfil, ajustes y calibración vigente. Para medir cambios de lectura o umbrales,
renombra `config/calibration.yaml` y conserva el archivo anterior; esos cambios
no invalidan automáticamente todas las calibraciones. La versión 1 se ignora
bajo el criterio de evaluación nuevo: vuelve a calibrar.

Evalúa en el proyecto original, que contiene el golden (no se copia a esta carpeta):

```bash
ipsis golden validate
ipsis evaluate --output reports/evaluation.json
ipsis benchmark --bank golden/bank/manifest.json --profiles light,medium --output reports/profiles
ipsis calibrate                    # revisar dev y test antes de usar --apply
ipsis doctor
```

La respuesta completa se mide igual para todos los perfiles; QA tiene su propia
métrica y no aplica sin lector. `evaluate` falla ante directas sin el dato esperado
o falsos `ok`. Una comprobación `test` fallida no bloquea automáticamente `--apply`.
`doctor` y `/ready` validan funcionamiento, no exactitud de respuestas.

Después de desplegar, puedes editar `config/assistant.yaml` o `config/engine.yaml`
de esta carpeta y ejecutar `docker compose restart asistente`. Para usar la CLI
del contenedor, detén primero el servicio si Qdrant es local:

```bash
docker compose stop asistente
docker compose run --rm --no-deps asistente ipsis configure posture.mode=strict
docker compose run --rm --no-deps asistente ipsis doctor
docker compose --profile https up -d
```

Cambios de corpus, fragmentación o modelo denso requieren `ipsis index`, validar
el golden y recalibrar. Tono y avatar usan `ipsis personality` o `config/personality.yaml`;
los estilos usan `ipsis widget style` o `config/styles.yaml`.

## Actualizar

Medium usa e5-small + mMiniLM + mDeBERTa y cascada 20/4/2. Otros modelos
se eligen en `config/engine.yaml::profile_overrides.models` (claves `dense`,
`reranker`, `reader`); conserva `retrieval.model: null` para usar ese denso.
La imagen lee estos ajustes al descargar. Si cambian, reindexa y reconstruye
con `docker compose build --no-cache asistente` antes de arrancar. En el
repositorio fuente, `python herramientas/evaluacion/general.py --download`
ejecuta la regresión documental; el golden real del proyecto sigue siendo
necesario para valorar sus respuestas.

- **Documentos o configuración:** en tu equipo, `ipsis load`, `ipsis index`
  y `ipsis deploy prepare` de nuevo; copia la carpeta y ejecuta
  `docker compose --profile https up -d --build`.
- **Licencia:** AGPL-3.0. Si modificas el código, define `IPSIS_SOURCE_URL`
  en `.env` con la URL de tus cambios.
