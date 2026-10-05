# Despliegue de {{nombre_asistente}}

Generado por `ipsis desplegar preparar` (perfil `{{perfil}}`). Esta carpeta
trae todo lo que el servicio necesita: configuración, documentos, índice,
calibración y avatares. Cópiala completa al servidor (VPS).

## 1. En el servidor

Necesitas Docker con el plugin `compose`. Luego, dentro de esta carpeta:

```bash
cp .env.ejemplo .env               # y completa IPSIS_ADMIN_TOKEN si quieres /admin
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
`cors_origins`), por ejemplo con `ipsis configurar cors_origins=https://www.tu-sitio.cl`
antes de preparar el despliegue.

## 3. Panel `/admin`

1. Genera un token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Ponlo en `.env` como `IPSIS_ADMIN_TOKEN=...`.
3. `docker compose --profile https up -d`.
4. Abre `https://{{dominio}}/admin/panel` y pega el token.

En producción `/admin` exige HTTPS. Sin token, el panel no existe.

## Actualizar

- **Documentos o configuración:** en tu equipo, `ipsis cargar`, `ipsis indexar`
  y `ipsis desplegar preparar` de nuevo; copia la carpeta y ejecuta
  `docker compose --profile https up -d --build`.
- **Licencia:** AGPL-3.0. Si modificas el código, define `IPSIS_SOURCE_URL`
  en `.env` con la URL de tus cambios.
