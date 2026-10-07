import hashlib
import json
import runpy
import shutil
import sys
from pathlib import Path

raiz = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(raiz/'tests'))
helper = runpy.run_path(str(raiz/'tests/integracion/test_caracterizacion.py'))
carpeta = Path(__file__).resolve().parent
antes, despues = (json.loads((carpeta/f'{m}-caracterizacion.json').read_text(encoding='utf-8'))
                  for m in ('antes','despues'))
historica = raiz/'docs/methodology/mediciones/f2/caracterizacion-historica'
historica.mkdir(exist_ok=True)
informe = {'base_y_final_iguales': True, 'tolerancia_score': 0.001, 'cambios_historicos': []}
for perfil, preguntas in antes.items():
    archivo = raiz/f'tests/datos/caracterizacion/{perfil}.json'
    original = historica/archivo.name
    if not original.is_file():
        shutil.copy2(archivo, original)
    previo = json.loads(original.read_text(encoding='utf-8'))
    for pregunta, a in preguntas.items():
        d = despues[perfil][pregunta]
        assert helper['_sin_scores'](a) == helper['_sin_scores'](d), (perfil,pregunta)
        assert all(abs(a['confidence'][k]-d['confidence'][k]) <= 0.001 for k in ('top1','margin'))
        assert all(abs(x['score']-y['score']) <= 0.001 for x,y in zip(a['fragments'],d['fragments']))
        h = previo[pregunta]
        if h != a:
            informe['cambios_historicos'].append(dict(perfil=perfil,pregunta=pregunta,
                estado_historico=h['status'],estado_antes_f2=a['status'],
                campos=[k for k in a if a[k] != h[k]]))
    # La referencia viene del código previo, nunca del candidato solo.
    archivo.write_text(json.dumps(preguntas,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
(carpeta/'caracterizacion.json').write_text(json.dumps(informe,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(informe,ensure_ascii=False,indent=2))
