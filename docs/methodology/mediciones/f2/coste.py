import json
import subprocess
import sys
from pathlib import Path

if len(sys.argv) > 1:
    import psutil
    from time import perf_counter
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.lenguaje.sinonimos import indice_automatico

    idioma = sys.argv[1]
    paquete = cargar_paquete(idioma)
    proceso = psutil.Process()
    antes = proceso.memory_info().rss
    inicio = perf_counter()
    indice = indice_automatico(idioma, paquete.stemmer)
    cold = (perf_counter() - inicio) * 1000
    despues = proceso.memory_info().rss
    inicio = perf_counter()
    for _ in range(10000):
        assert indice_automatico(idioma, paquete.stemmer) is indice
    warm = (perf_counter() - inicio) * 1000 / 10000
    grupos = {(g.fuente, g.sentido, g.pos) for gs in indice.values() for g in gs}
    print(json.dumps(dict(idioma=idioma, raices_indexadas=len(indice), grupos_indexados=len(grupos),
                         carga_fria_ms=cold, cache_ms=warm, rss_antes_bytes=antes,
                         rss_despues_bytes=despues, incremento_rss_bytes=despues-antes)))
else:
    resultados = []
    for idioma in ('es', 'en', 'pt'):
        salida = subprocess.check_output([sys.executable, __file__, idioma], encoding='utf-8')
        resultados.append(json.loads(salida))
    informe = dict(metodo='Proceso nuevo por idioma, RSS antes/despues; 10.000 accesos calientes. '
                         'Incluye inicializacion del stemmer; no es RSS del servicio completo.', resultados=resultados)
    Path(__file__).with_name('coste.json').write_text(json.dumps(informe, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(informe, ensure_ascii=False, indent=2))
