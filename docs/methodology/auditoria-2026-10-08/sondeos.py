"""Sondeos de límites de guardias y calibración; no son consultas con modelos.

Desde la raíz: python docs/methodology/auditoria-2026-10-08/sondeos.py
No modifica la configuración del proyecto. Escribe solo en un directorio temporal.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ipsis.configuracion.calibracion import ProcedenciaCalibracion, umbrales_aplicables
from ipsis.configuracion.perfiles import cargar_perfil_instalacion, perfil_efectivo
from ipsis.consulta.etapas.lectura import hay_discordancia
from ipsis.consulta.etapas.politica import SenalesPolitica, regla_cascada, verificar_premisa_textos
from ipsis.consulta.etapas.verificacion import verificar_fidelidad
from ipsis.evaluacion.banco import (
    ArchivoCorpus, BancoEvaluacion, CasoEvaluacion, CorpusBanco, EvidenciaEsperada, ManifiestoBanco,
)
from ipsis.evaluacion.calibracion import calibrar, escribir_calibracion
from ipsis.evaluacion.metricas import ObservacionEvaluacion, SenalesObservadas
from ipsis.nucleo.esquemas import EvidenceSpan, LecturaQA
from ipsis.lenguaje.entidades import configurar_idioma
from ipsis.lenguaje.paquete import cargar_paquete


def ejecutar() -> dict:
    configurar_idioma(cargar_paquete("es"))
    perfil = cargar_perfil_instalacion("medium")
    u = perfil.umbrales_por_defecto
    textos = ["La garantía dura 6 meses.", "El mantenimiento se realiza cada 12 meses."]
    premisa = verificar_premisa_textos("¿La garantía dura 12 meses?", textos)
    fuente = [{"texto": " ".join(textos), "doc_titulo": "Manual", "seccion_path": []}]
    fidelidad = verificar_fidelidad("La garantía dura 12 meses.", fuente)
    regla = regla_cascada(SenalesPolitica(
        s_ret=0.55, s_oov=0.0, s_foco=1.0, s_cov=0.0, s_rr=None, s_qa=0.99,
    ), u)
    afirmacion = "El cliente paga el envío."
    negacion = "El cliente no paga el envío."
    lecturas = [LecturaQA(
        indice_pasaje=i, inicio=0, fin=len(texto), texto=texto,
        prob_respuesta=0.99, prob_sin_respuesta=0.01,
    ) for i, texto in enumerate([afirmacion, negacion])]

    # Dev admite 70 respuestas correctas; test admite 60 trampas incorrectas.
    texto = "La garantía dura 24 meses."
    casos, observaciones = [], []
    for split, respondible, n, qa in [("dev", True, 70, 0.9), ("dev", False, 10, 0.5),
                                    ("test", False, 60, 0.95)]:
        for i in range(n):
            identificador = f"{split}-{int(respondible)}-{i}"
            casos.append(CasoEvaluacion(
                dataset_version="1", id=identificador, split=split,
                categoria="exacta" if respondible else "sin_respuesta", pregunta="¿Cuánto dura?",
                estado_esperado="respuesta_directa" if respondible else "sin_respuesta",
                respondible=respondible, respuesta_literal="24 meses" if respondible else None,
                evidencias=[EvidenciaEsperada(doc_id="d", offset_inicio=0, offset_fin=len(texto),
                                             texto=texto)] if respondible else [],
            ))
            observaciones.append(ObservacionEvaluacion(
                caso_id=identificador, backend="sondeo", estado="relacionado", respuesta=texto,
                regla="relacionado", evidencias=[EvidenceSpan(
                    doc_id="d", chunk_id="c", texto=texto, offset_inicio=0, offset_fin=len(texto))],
                senales=SenalesObservadas(s_ret=0.9, s_oov=0, s_foco=1, s_cov=1,
                                          s_qa=qa, dominio=0.9),
            ))
    banco = BancoEvaluacion(manifiesto=ManifiestoBanco(
        dataset_id="sondeo", dataset_version="1", tipo="sintetico", estado="estable",
        casos="sondeo.jsonl", corpus=CorpusBanco(directorio=".", archivos=[ArchivoCorpus(
            ruta="d.txt", doc_id="d")], sha256="0" * 64), categorias_requeridas=[], uso="evaluacion",
    ), casos=casos)
    resultado = calibrar(banco, observaciones, u)
    procedencia = ProcedenciaCalibracion(
        perfil="medium", modelos=perfil.modelos.model_dump(), hash_corpus="corpus-sondeo",
        hash_lexico="lexico-sondeo", banco="sondeo@1", hash_banco="0" * 64,
    )
    with tempfile.TemporaryDirectory(prefix="ipsis-auditoria-") as temporal:
        ruta = escribir_calibracion(resultado, procedencia, Path(temporal) / "calibration.yaml")
        aplicados = umbrales_aplicables(
            ruta, perfil="medium", modelos=perfil.modelos.model_dump(),
            hash_corpus=procedencia.hash_corpus, hash_lexico=procedencia.hash_lexico,
        )
        cambiado = perfil_efectivo(
            "medium", ajustes={"cascada": {"leer_m": 1, "max_caracteres_lectura": 100}},
            ruta_calibracion=ruta, hash_corpus=procedencia.hash_corpus,
            hash_lexico=procedencia.hash_lexico,
        )
    return {
        "alcance": "funciones reales con entradas sintéticas; no reproduce una respuesta del motor",
        "premisa_sin_asociacion": {"pregunta": "¿La garantía dura 12 meses?", "fuentes": textos,
                                    "premisa_valida": premisa.premisa_valida},
        "fidelidad_sin_asociacion": {"respuesta_sintetica": "La garantía dura 12 meses.",
                                    "fiel": fidelidad.fiel},
        "qa_alta_cobertura_cero": {"s_qa": 0.99, "s_cov": 0.0, "regla": regla},
        "negacion_no_detectada_por_concordancia": {"tramos": [afirmacion, negacion],
                                                   "discordancia": hay_discordancia(lecturas)},
        "calibracion_test_excede": {"estado": resultado.estado.value,
                                    "verificacion_test": resultado.verificacion_test,
                                    "aceptadas_test": resultado.test.riesgo.n,
                                    "erroneas_test": resultado.test.riesgo.x,
                                    "umbrales_aplicables": aplicados is not None},
        "calibracion_tras_cambio_cascada": {"leer_m": cambiado.cascada.leer_m,
                                            "max_caracteres_lectura": cambiado.cascada.max_caracteres_lectura,
                                            "origen_umbrales": cambiado.origen_umbrales},
    }


if __name__ == "__main__":
    print(json.dumps(ejecutar(), ensure_ascii=False, indent=2))
