import json
from pathlib import Path

raiz = Path(__file__).resolve().parent
def cargar(nombre):
    return json.loads((raiz / nombre).read_text(encoding="utf-8"))
def correcta(c):
    return c["directa"] and not c["falso_ok"] and not c["sin_literal"]
def erronea(c):
    return c["directa"] and (c["falso_ok"] or c["sin_literal"])
informe = {}
for banco in ("consultas", "universal"):
    antes, despues = (cargar(f"{m}-{banco}.json") for m in ("antes", "despues"))
    filas = []
    for perfil, idiomas in despues.items():
        for idioma, d in idiomas.items():
            a = antes[perfil][idioma]
            assert set(a["casos"]) == set(d["casos"])
            ca, cd = ({i for i,c in v["casos"].items() if correcta(c)} for v in (a,d))
            ea, ed = ({i for i,c in v["casos"].items() if erronea(c)} for v in (a,d))
            cambios = [i for i,c in d["casos"].items() if (c["estado"],correcta(c),erronea(c)) !=
                       (a["casos"][i]["estado"],correcta(a["casos"][i]),erronea(a["casos"][i]))]
            filas.append(dict(perfil=perfil,idioma=idioma,correctas_antes=len(ca),correctas_despues=len(cd),
                              erroneas_antes=len(ea),erroneas_despues=len(ed),nuevas_erroneas=sorted(ed-ea),
                              correctas_perdidas=sorted(ca-cd),cambios=cambios,
                              parafrasis_antes=sum("parafrasis" in i for i in ca),
                              parafrasis_despues=sum("parafrasis" in i for i in cd),
                              media_antes=a["media_ms"],media_despues=d["media_ms"],
                              cambio_latencia_pct=round(100*(d["media_ms"]/a["media_ms"]-1),2)))
    informe[banco] = filas
antes, despues = (cargar(f"{m}-conversaciones.json") for m in ("antes","despues"))
filas = []
for perfil, idiomas in despues.items():
    for idioma, d in idiomas.items():
        a = antes[perfil][idioma]
        def tabla(v):
            return {f'{t["conversacion"]}:{t["turno"]}':t for t in v["turnos"]}
        ta,td = tabla(a),tabla(d)
        assert set(ta) == set(td)
        def mala(t):
            return t["directa"] and (t["directa_esperada"] is False or bool(t["respuesta"]) and not t["correcta"])
        filas.append(dict(perfil=perfil,idioma=idioma,antes=a["resumen"],despues=d["resumen"],
                          nuevas_erroneas=sorted(i for i,t in td.items() if mala(t) and not mala(ta[i])),
                          correctas_perdidas=sorted(i for i,t in ta.items() if t["correcta"] and not td[i]["correcta"]),
                          nuevas_herencias_indebidas=sorted(i for i,t in td.items() if t["hereda"] is False and
                                                          t["heredo"] and not ta[i]["heredo"]),
                          cambios=sorted(i for i,t in td.items() if (t["estado"],t["correcta"],t["heredo"]) !=
                                        (ta[i]["estado"],ta[i]["correcta"],ta[i]["heredo"]))))
informe["conversaciones"] = filas
informe["calidad_sin_regresiones"] = all(not f["nuevas_erroneas"] and not f["correctas_perdidas"] and
    not f.get("nuevas_herencias_indebidas") for fs in (informe[b] for b in ("consultas","universal","conversaciones")) for f in fs)
informe["g5"] = all(f["media_despues"] <= 1.1*f["media_antes"] for f in informe["universal"] if f["perfil"] == "light")
(raiz / "comparacion.json").write_text(json.dumps(informe,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:informe[k] for k in ("calidad_sin_regresiones","g5")},ensure_ascii=False))
for banco in ("consultas","universal"):
    for f in informe[banco]:
        print(banco,f["perfil"],f["idioma"],f["correctas_antes"],f["correctas_despues"],f["erroneas_antes"],f["erroneas_despues"],f["cambio_latencia_pct"],f["cambios"])
