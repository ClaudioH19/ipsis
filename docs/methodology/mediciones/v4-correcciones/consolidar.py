"""Consolida bancos independientes y conversaciones, comprobando su procedencia."""
from pathlib import Path
import difflib
import json
import shutil
import zipfile

SALIDA = Path(__file__).resolve().parent
RAIZ = SALIDA.parents[3]
with zipfile.ZipFile(SALIDA / "final-code.zip") as a, zipfile.ZipFile(SALIDA / "elipsis-code.zip") as b:
    assert set(a.namelist()) == set(b.namelist())
    diferencias = [n for n in a.namelist() if a.read(n) != b.read(n)]
    assert diferencias == ["ipsis/consulta/etapas/lectura.py"], diferencias
    antes, despues = (z.read(diferencias[0]).decode("utf-8") for z in (a, b))
    previo = "        pregunta_lectura = ctx.pregunta_usuario or ctx.pregunta\n"
    inicio = despues.index("        pregunta_lectura = ctx.pregunta\n")
    fin = despues.index('        ctx.diagnostico["pregunta_lectura"]', inicio)
    actual = despues[inicio:fin]
    assert antes.replace(previo, actual) == despues
    assert "if ctx.pregunta_usuario:" in actual
    for n in b.namelist():
        assert (RAIZ / n).read_bytes() == b.read(n), n

informe = {"codigo_vigente": "elipsis-code.zip", "diferencias_codigo": diferencias,
           "diff": list(difflib.unified_diff(antes.splitlines(), despues.splitlines(), fromfile="final", tofile="elipsis")),
           "bancos": {}, "alcance": "La única diferencia actúa cuando pregunta_usuario no está vacía. Los bancos independientes usan una sesión nueva por caso; se reutilizan sus resultados sin esa rama."}
for banco, ronda in (("consultas", "final"), ("universal", "final"), ("conversaciones", "elipsis")):
    for sufijo in (".json", ".intenciones.json"):
        origen = SALIDA / f"{ronda}-{banco}{sufijo}"
        assert origen.exists(), origen
        shutil.copyfile(origen, SALIDA / f"vigente-{banco}{sufijo}")
    auditoria = json.loads((SALIDA / f"{ronda}-{banco}.intenciones.json").read_text(encoding="utf-8"))
    if banco != "conversaciones":
        sesiones = [(f["perfil"], f["idioma"], f["sesion"]) for f in auditoria]
        assert len(sesiones) == len(set(sesiones)), "El banco independiente reutiliza una sesión"
        assert all(f["sesion"].startswith("evaluacion:") for f in auditoria)
    informe["bancos"][banco] = {"ronda": ronda, "consultas_auditadas": len(auditoria)}
for sufijo in ("-code.zip", "-codigo.json"):
    shutil.copyfile(SALIDA / f"elipsis{sufijo}", SALIDA / f"vigente{sufijo}")
(SALIDA / "procedencia-vigente.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"diferencias": diferencias, "bancos": informe["bancos"]}, ensure_ascii=False, indent=2), flush=True)
