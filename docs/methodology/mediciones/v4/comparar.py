"""Compara por identidad de caso; conserva cambios y límites, no solo totales."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import zipfile

import yaml

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parents[3]


def cargar(nombre):
    return json.loads((RAIZ / nombre).read_text(encoding="utf-8"))


def correcta(c):
    return c["directa"] and not c["falso_ok"] and not c["sin_literal"]


def erronea(c):
    return c["directa"] and (c["falso_ok"] or c["sin_literal"])


def comparar(base, final):
    informe = {}
    for banco in ("consultas", "universal"):
        antes, despues = (cargar(f"{m}-{banco}.json") for m in (base, final))
        filas = []
        for perfil, idiomas in despues.items():
            for idioma, d in idiomas.items():
                a = antes[perfil][idioma]
                assert set(a["casos"]) == set(d["casos"])
                ca, cd = ({i for i, c in v["casos"].items() if correcta(c)} for v in (a, d))
                ea, ed = ({i for i, c in v["casos"].items() if erronea(c)} for v in (a, d))
                cambios = [dict(id=i, antes=a["casos"][i], despues=c) for i, c in d["casos"].items()
                           if (c["estado"], correcta(c), erronea(c)) !=
                           (a["casos"][i]["estado"], correcta(a["casos"][i]), erronea(a["casos"][i]))]
                filas.append(dict(perfil=perfil, idioma=idioma, correctas_antes=len(ca), correctas_despues=len(cd),
                                  erroneas_antes=len(ea), erroneas_despues=len(ed), nuevas_erroneas=sorted(ed-ea),
                                  falsos_ok_nuevos=sorted(i for i, c in d["casos"].items()
                                                        if c["falso_ok"] and not a["casos"][i]["falso_ok"]),
                                  correctas_perdidas=sorted(ca-cd), cambios=cambios,
                                  parafrasis_antes=sum("parafrasis" in i for i in ca),
                                  parafrasis_despues=sum("parafrasis" in i for i in cd)))
        informe[banco] = filas
    antes, despues = (cargar(f"{m}-conversaciones.json") for m in (base, final))
    filas = []
    for perfil, idiomas in despues.items():
        for idioma, d in idiomas.items():
            a = antes[perfil][idioma]
            def tabla(v):
                return {f'{t["conversacion"]}:{t["turno"]}': t for t in v["turnos"]}
            ta, td = tabla(a), tabla(d)
            assert set(ta) == set(td)
            def mala(t):
                return t["directa"] and (t["directa_esperada"] is False or bool(t["respuesta"]) and not t["correcta"])
            filas.append(dict(perfil=perfil, idioma=idioma, antes=a["resumen"], despues=d["resumen"],
                              nuevas_erroneas=sorted(i for i, t in td.items() if mala(t) and not mala(ta[i])),
                              correctas_perdidas=sorted(i for i, t in ta.items() if t["correcta"] and not td[i]["correcta"]),
                              nuevas_herencias_indebidas=sorted(i for i, t in td.items()
                                                              if t["hereda"] is False and t["heredo"] and not ta[i]["heredo"]),
                              cambios=[dict(id=i, antes=ta[i], despues=t) for i, t in td.items()
                                       if (t["estado"], t["correcta"], t["heredo"]) !=
                                       (ta[i]["estado"], ta[i]["correcta"], ta[i]["heredo"])],
                              retoma_007_015=[dict(id=i, antes=ta[i]["heredo"], despues=td[i]["heredo"])
                                             for i in (f"{idioma}-conv-007:3", f"{idioma}-conv-015:3")]))
    informe["conversaciones"] = filas
    informe["calidad_sin_regresiones_por_caso"] = all(not f["nuevas_erroneas"] and not f["correctas_perdidas"] and
        not f.get("nuevas_herencias_indebidas") for fs in informe.values() if isinstance(fs, list) for f in fs)
    informe["g2"] = all(not f["falsos_ok_nuevos"] and not f["correctas_perdidas"] for f in informe["universal"])
    informe["g3"] = (all(f["erroneas_despues"] <= f["erroneas_antes"] for f in informe["consultas"]) and
                     sum(f["correctas_despues"] for f in informe["consultas"]) >= sum(f["correctas_antes"] for f in informe["consultas"]))
    informe["g4"] = all(f["despues"][k] <= f["antes"][k] for f in filas for k in ("herencia_indebida", "directas_indebidas"))
    informe["f4_herencia"] = all(f["despues"]["herencia_correcta"] >= f["antes"]["herencia_correcta"] for f in filas)
    return informe


def auditoria_intenciones(final="corregido"):
    etiquetas = yaml.safe_load((REPO / "tests/datos/banco_consultas/intenciones.yaml").read_text(encoding="utf-8"))
    informe = {}
    for banco in ("consultas", "universal", "conversaciones"):
        filas = []
        registros = cargar(f"{final}-{banco}.intenciones.json")
        antes, despues = (cargar(f"{m}-{banco}.json") for m in ("antes", final))
        for perfil in ("light", "medium"):
            for idioma in ("es", "en", "pt"):
                rr = [r for r in registros if r["perfil"] == perfil and r["idioma"] == idioma]
                aceptadas = [r for r in rr if r["diagnostico"].get("aceptada")]
                fila = dict(perfil=perfil, idioma=idioma, consultas=len(rr),
                            patrones=sum(r["diagnostico"].get("origen") == "patron" for r in rr),
                            intentos=sum(r["diagnostico"].get("origen") == "similitud" for r in rr),
                            aceptadas=len(aceptadas), detalle=aceptadas)
                if banco == "consultas":
                    errores = []
                    efectos = []
                    for r in aceptadas:
                        caso = r["sesion"].split(":", 1)[1]
                        esperada = etiquetas[caso.split("-", 1)[1]]
                        if r["intencion"] != esperada:
                            errores.append(caso)
                        a, d = (v[perfil][idioma]["casos"][caso] for v in (antes, despues))
                        efectos.append(dict(id=caso, esperada=esperada, elegida=r["intencion"],
                                            correcta_antes=correcta(a), correcta_despues=correcta(d),
                                            erronea_antes=erronea(a), erronea_despues=erronea(d),
                                            estado_antes=a["estado"], estado_despues=d["estado"]))
                    fila.update(errores_intencion=errores, efectos=efectos)
                filas.append(fila)
        informe[banco] = filas
    return informe


def pruebas(nombre):
    suites = ET.parse(RAIZ / nombre).getroot().findall("testsuite")
    return {k: sum(float(s.attrib.get(k, 0)) for s in suites)
            for k in ("tests", "failures", "errors", "skipped", "time")}


def diferencias_capturas():
    with zipfile.ZipFile(RAIZ / "final-code.zip") as a, zipfile.ZipFile(RAIZ / "final-revision-code.zip") as d:
        nombres = set(a.namelist()) | set(d.namelist())
        cambios = [p for p in sorted(nombres) if p not in a.namelist() or p not in d.namelist() or a.read(p) != d.read(p)]
    assert cambios == ["ipsis/aplicacion/consulta.py"], cambios
    return cambios


def main():
    informe = dict(codigo_evaluado="corregido", desde_inicio=comparar("antes", "corregido"), desde_f1=comparar("f1", "corregido"),
                   intenciones=auditoria_intenciones(), pruebas=pruebas("pruebas-corregidas.xml"),
                   pruebas_separacion=pruebas("pruebas-separacion.xml"),
                   pruebas_diagnostico=pruebas("pruebas-diagnostico.xml"),
                   cambios_post_medicion=[], cambios_post_medicion_anterior=diferencias_capturas(),
                   latencia_desde_inicio=cargar("pareadas-corregidas/resumen.json"),
                   latencia_desde_f1=cargar("pareadas-f1-corregidas/resumen.json"))
    informe["g1"] = all(informe[k]["failures"] == informe[k]["errors"] == 0 for k in ("pruebas", "pruebas_diagnostico"))
    informe["g5"] = informe["latencia_desde_f1"]["g5"] and informe["latencia_desde_inicio"]["g5"]
    (RAIZ / "comparacion.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"g1": informe["g1"], "g5": informe["g5"], **{k: informe["desde_f1"][k] for k in ("g2", "g3", "g4", "f4_herencia")}}))
    for referencia in ("desde_inicio", "desde_f1"):
        for banco in ("consultas", "universal", "conversaciones"):
            for fila in informe[referencia][banco]:
                print(referencia, banco, fila["perfil"], fila["idioma"], "cambios", len(fila["cambios"]),
                      "perdidas", fila["correctas_perdidas"], "errores", fila["nuevas_erroneas"])


if __name__ == "__main__":
    main()
