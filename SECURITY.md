# Seguridad

## Versiones con soporte

| Versión | Soporte |
|---|---|
| 0.8.x | ✅ |
| < 0.8 | ❌ |

## Reportar una vulnerabilidad

No abras un issue público. Usa el reporte privado de GitHub
(**Security → Report a vulnerability**) en este repositorio, con:

- la versión (`rag --version`) y el modo (`RAG_MODO`);
- los pasos para reproducirla y su impacto;
- si afecta al servicio, al widget, al panel `/admin` o a la imagen Docker.

Recibirás una respuesta inicial en un plazo de 7 días.

## Superficie y protecciones

| Componente | Protección |
|---|---|
| `/consultar` | CORS por origen, clave pública del widget, límite de peticiones y control de admisión (503) |
| Widget | Shadow DOM; todo texto de la API se inserta con `textContent`, nunca `innerHTML` |
| `/admin` y `/admin/panel` | Solo con `RAG_ADMIN_TOKEN` (≥ 32 caracteres), comparación en tiempo constante, HTTPS en producción, bloqueo tras 5 intentos fallidos, sin CORS, CSP estricta y auditoría en `.rag/registros/admin.jsonl` |
| Proxy | `X-Forwarded-*` solo se acepta de `RAG_PROXY_CONFIABLE` |
| Imagen Docker | Usuario no root, sin red en ejecución (`HF_HUB_OFFLINE=1`) |
| Datos | Los documentos y las preguntas no salen del servidor; el registro de consultas está apagado por defecto |

La clave pública del widget identifica una integración, pero no es un
secreto: la protección del servicio se completa en el proxy. Detalle en la
[guía de despliegue](docs/guia/despliegue.md).
