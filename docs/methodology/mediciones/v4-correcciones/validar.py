"""Verifica objetivos, regresiones por caso, procedencia, pruebas y G5."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile

SALIDA = Path(__file__).resolve().parent
RAIZ = SALIDA.parents[3]
comparacion = json.loads((SALIDA / "vigente-comparacion.json").read_text(encoding="utf-8"))
pruebas = ET.parse(SALIDA / "pruebas-vigentes.xml").getroot()
suites = list(pruebas.iter("testsuite"))
totales = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
totales["aprobadas"] = totales["tests"] - totales["failures"] - totales["errors"] - totales["skipped"]
hash_actual = hashlib.sha256()
con_zip = []
with zipfile.ZipFile(SALIDA / "vigente-code.zip") as z:
    nombres = z.namelist()
    assert len(nombres) == len(set(nombres))
    actuales = {p.relative_to(RAIZ).as_posix() for p in (RAIZ / "ipsis").rglob("*")
                if p.is_file() and p.suffix in {".py", ".yaml", ".js"}}
    con_zip.extend(sorted(actuales - set(nombres)))
    # La captura ordena Path por componentes, no strings POSIX completos.
    # Su orden ya está conservado en el ZIP y forma parte del hash publicado.
    for nombre in nombres:
        contenido = z.read(nombre)
        hash_actual.update(nombre.encode()); hash_actual.update(b"\0"); hash_actual.update(contenido)
        if (RAIZ / nombre).read_bytes() != contenido:
            con_zip.append(nombre)
hash_captura = json.loads((SALIDA / "vigente-codigo.json").read_text(encoding="utf-8"))["sha256_py_yaml_js"]
assert hash_actual.hexdigest() == hash_captura
latencias = {base: json.loads((SALIDA / carpeta / "resumen.json").read_text(encoding="utf-8"))
             for base, carpeta in (("V4", "pareadas-v4"), ("F1", "pareadas-f1"))}
criterios = {"suite": not totales["failures"] and not totales["errors"], "codigo_medido_actual": not con_zip,
             "ocho_objetivos": all(t["correcta"] for t in comparacion["objetivos"].values()),
             "latencia_ambas_bases": all(d["g5"] for d in latencias.values())}
for base, bancos in comparacion["bases"].items():
    for banco, perfiles in bancos.items():
        filas = [f for idiomas in perfiles.values() for f in idiomas.values()]
        criterios[f"{base}_{banco}_sin_perdidas"] = all(not f["perdidas"] for f in filas)
        criterios[f"{base}_{banco}_sin_errores_nuevos"] = all(not f["errores_nuevos"] for f in filas)
        if banco == "conversaciones":
            criterios[f"{base}_sin_herencia_indebida"] = all(f["despues"]["herencia_indebida"] <= f["antes"]["herencia_indebida"] for f in filas)
            criterios[f"{base}_herencia_no_disminuye"] = all(f["despues"]["herencia_correcta"] >= f["antes"]["herencia_correcta"] for f in filas)
            criterios[f"{base}_sin_directas_negativas"] = all(f["despues"]["directas_indebidas"] <= f["antes"]["directas_indebidas"] for f in filas)
            datos = json.loads((SALIDA / "vigente-conversaciones.json").read_text(encoding="utf-8"))
            criterios["retornos_007_015"] = all(t["heredo"] for idiomas in datos.values() for d in idiomas.values()
                for t in d["turnos"] if t["conversacion"].endswith(("-007", "-015")) and t["turno"] == 3)
            texto = (SALIDA / "caracterizacion.md").read_text(encoding="utf-8")
            criterios[f"{base}_estados_explicados"] = all(id in texto for f in filas for id in f["cambios_estado"])
etiquetas = __import__("yaml").safe_load((RAIZ / "tests/datos/banco_consultas/intenciones.yaml").read_text(encoding="utf-8"))
datos = json.loads((SALIDA / "vigente-consultas.intenciones.json").read_text(encoding="utf-8"))
errores_intencion = []
for fila in datos:
    diag = fila["diagnostico"]
    if diag.get("origen") == "similitud" and diag.get("aceptada"):
        id = fila["sesion"].split("evaluacion:")[-1]
        sufijo = id.split("-", 1)[-1]
        if sufijo in etiquetas and etiquetas[sufijo] != fila["intencion"]:
            errores_intencion.append(fila)
criterios["sin_error_intencion_natural"] = not errores_intencion
resultado = {"criterios": criterios, "pruebas": totales, "hash_codigo": hash_captura,
             "archivos_distintos": con_zip, "latencia": latencias, "errores_intencion_natural": errores_intencion,
             "alcance": "Criterios de los bancos locales; no certifican exactitud general ni corrigen todos los errores previos del lector."}
(SALIDA / "validacion.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"criterios": criterios, "pruebas": totales}, ensure_ascii=False, indent=2), flush=True)
if not all(criterios.values()):
    raise SystemExit(1)
