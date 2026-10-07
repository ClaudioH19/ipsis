"""Captura el contrato HTTP sin sobrescribir la referencia de pytest."""
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import httpx

raiz = Path(__file__).resolve().parents[2]
codigo, salida = (Path(p).resolve() for p in sys.argv[1:3])
os.environ['PYTHONPATH'] = str(codigo)
os.environ['PYTHONUTF8'] = '1'
os.environ['IPSIS_LANG'] = 'es'
os.environ['TEMP'] = os.environ['TMP'] = str(raiz/'.cache/plan-v4/tmp')
modulo = subprocess.check_output([sys.executable, '-c', 'import ipsis; print(ipsis.__file__)'],
                                  cwd=raiz/'.cache/plan-v4/tmp', env=os.environ, encoding='utf-8').strip()
assert Path(modulo).is_relative_to(codigo), modulo
sys.path.insert(0, str(raiz/'tests'))
datos = runpy.run_path(str(raiz/'tests/integracion/test_caracterizacion.py'))
todo = {}
for perfil in ('light', 'medium'):
    servicio = datos['url_servicio'].__wrapped__(perfil)
    try:
        url = next(servicio)
        observaciones = {}
        for pregunta in datos['PREGUNTAS']:
            respuesta = httpx.post(url+'/ask', json={'question': pregunta, 'session_id':'caracterizacion'}, timeout=60)
            respuesta.raise_for_status()
            observaciones[pregunta] = datos['_resumen'](respuesta.json())
        todo[perfil] = observaciones
        print(perfil, {p:r['status'] for p,r in observaciones.items()}, flush=True)
    finally:
        servicio.close()
salida.write_text(json.dumps(todo, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
