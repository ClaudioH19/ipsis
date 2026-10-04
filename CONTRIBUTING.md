# Cómo contribuir

¡Gracias por querer mejorar rag-extractivo! Esta guía resume cómo trabajar
en el repositorio. Antes de proponer un cambio grande, abre un issue para
conversarlo.

## Principios que no se negocian

- **Nada generativo.** Toda afirmación es un tramo literal del documento; lo
  único agregado son plantillas fijas y revisadas ([ADR 0001](docs/decisiones/0001-respuestas-no-generativas.md)).
- **Sin entrenamiento.** Ni fine-tuning ni pesos aprendidos: la calibración
  solo elige umbrales entre valores observados.
- **Abstenerse es mejor que equivocarse.** Un cambio que sube la cobertura a
  costa de falsos `ok` no se acepta.
- **Nada de texto de un idioma en Python.** Palabras, patrones y mensajes van
  en los paquetes de `rag/recursos/idiomas/` y `rag/recursos/tonos/`.
- **Capas en una sola dirección.** `tests/test_arquitectura.py` lo verifica
  (ver [arquitectura](docs/arquitectura.md)).

## Preparar el entorno

```bash
git clone https://github.com/ClaudioH19/Deterministic-Retrieval-Assistant-Chat.git rag-extractivo
cd rag-extractivo
python -m venv .venv
.venv/bin/python -m pip install -e ".[test,browser]"     # .venv\Scripts\python.exe en Windows
.venv/bin/python -m playwright install chromium
```

## Pruebas

```bash
python -m pytest -m "not slow and not browser"   # rápidas (segundos)
python -m pytest -m browser                      # widget y panel en Chromium
python -m pytest                                 # todo; las lentas descargan o usan modelos reales
```

- Una prueba vive en la carpeta del módulo que prueba (`tests/<capa>/`).
- Las etapas del motor se prueban con dobles en memoria, sin modelos.
- Si un cambio altera respuestas a propósito, regenera la caracterización
  y explica el porqué en el commit.
- La CI corre en Linux y Windows con Python 3.11 y 3.12.

## El motor del avatar

`rag/servicio/estaticos/avatar.js` se genera; no se edita a mano:

```bash
cd herramientas/avatar
npm ci && npm run construir    # o npm run verificar para comprobar el sha256
```

Ver [herramientas/avatar/LEEME.md](herramientas/avatar/LEEME.md).

## Estilo

- Código y comentarios en español; los comentarios explican el porqué.
- Mensajes de error accionables: dicen qué comando ejecutar.
- Una técnica nueva necesita su [ficha metodológica](docs/metodologia/README.md),
  y una decisión de arquitectura, su ADR en `docs/decisiones/`.
- Actualiza la guía correspondiente en `docs/guia/` y el `CHANGELOG.md`.
  `tests/test_documentacion.py` falla si un comando no está en
  `docs/guia/uso.md` o si un enlace queda roto.

## Pull requests

1. Una rama por cambio, con commits pequeños y mensajes descriptivos.
2. Las pruebas rápidas y las de navegador en verde.
3. Completa la plantilla del PR: qué cambia, cómo se probó y si afecta
   respuestas, índices o la configuración (`config_version`).

Al contribuir aceptas publicar tu aporte bajo la licencia
[AGPL-3.0](LICENSE) y el [código de conducta](CODE_OF_CONDUCT.md).
