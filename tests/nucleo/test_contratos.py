from __future__ import annotations

import pytest
from pydantic import ValidationError

from rag import __version__
from rag.nucleo.registro import RegistroComponentes
from rag.configuracion.carga import configuracion_efectiva, guardar_snapshot_configuracion
from rag.nucleo.esquemas import AssistantResult, AssistantState, EvidenceSpan
from rag.configuracion.esquemas import validar_asistente, validar_motor


def test_registro_crea_y_enumera_componentes():
    registro = RegistroComponentes()
    registro.registrar("Chunker", "Mi-Chunker", lambda valor=1: {"valor": valor})

    assert registro.disponibles("chunker") == ["mi_chunker"]
    assert registro.crear("CHUNKER", "mi-chunker", valor=3) == {"valor": 3}


def test_registro_no_pisa_una_implementacion_sin_permiso():
    registro = RegistroComponentes()
    registro.registrar("parser", "builtin", dict)
    with pytest.raises(ValueError, match="ya registrado"):
        registro.registrar("parser", "builtin", list)


def test_evidencia_exige_offsets_coherentes_con_el_texto():
    with pytest.raises(ValidationError, match="largo del texto"):
        EvidenceSpan(
            doc_id="manual", chunk_id="c1", texto="dato",
            offset_inicio=10, offset_fin=20,
        )


def test_diagnostico_interno_no_se_serializa():
    resultado = AssistantResult(
        estado=AssistantState.SIN_RESPUESTA,
        motivo="sin_fragmentos",
        mensaje_usuario="No encontré información.",
        diagnostico={"score": 0.1},
    )
    assert "diagnostico" not in resultado.model_dump()


def test_configuracion_agrega_version_y_prefijo_documento_compatibles():
    asistente = validar_asistente({"nombre_asistente": "Demo"})
    motor = validar_motor({
        "recuperacion": {
            "modelo": "intfloat/multilingual-e5-small",
            "estrategia_chunking": "CH-F256",
            "coleccion_base": "demo",
        }
    })
    assert asistente["config_version"] == 4
    assert motor["config_version"] == 4
    assert "prefijo_documento" not in motor["recuperacion"]  # lo define el catálogo de modelos


def test_configuracion_rechaza_claves_desconocidas():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        validar_asistente({"nombre_asistente": "Demo", "clave_inventada": True})


def test_configuracion_migra_version_cero_de_forma_idempotente():
    datos = {
        "recuperacion": {
            "modelo": "modelo",
            "estrategia_chunking": "chunks",
            "coleccion_base": "demo",
        }
    }
    primero = validar_motor(datos)
    segundo = validar_motor(primero)
    assert primero == segundo
    assert primero["config_version"] == 4


def test_configuracion_v1_unifica_reranker_en_componentes():
    datos = {
        "config_version": 1,
        "recuperacion": {
            "modelo": "modelo",
            "estrategia_chunking": "chunks",
            "coleccion_base": "demo",
            "reranker": "cross_encoder",
        },
    }

    migrado = validar_motor(datos)

    assert migrado["config_version"] == 4
    assert "reranker" not in migrado["recuperacion"]
    assert migrado["componentes"]["reranker"] == "cross_encoder"


def test_configuracion_rechaza_version_futura():
    with pytest.raises(ValueError, match="solo soporta"):
        validar_asistente({"config_version": 99})


def test_abstencion_selecciona_umbrales_propios_del_retriever_sin_mutar_base():
    from rag.configuracion.carga import config_abstencion

    cfg = {
        "abstencion": {
            "version": "densa_sin_calibrar",
            "capa_a_fuera_dominio": {
                "senal": "score_top1_denso",
                "umbral": 0.8,
                "grounding_lexico": {"oov_max": 0.5},
            },
            "confianza_alta": {"senal": "score_top1_denso", "umbral": 0.85},
            "perfiles_retriever": {
                "alternativo": {
                    "version": "alternativa_sin_calibrar",
                    "senal": "senal_alternativa",
                    "umbral_fuera_dominio": 0.25,
                    "umbral_confianza_alta": 0.7,
                }
            },
        }
    }

    densa = config_abstencion(cfg, retriever="qdrant")
    alternativa = config_abstencion(cfg, retriever="alternativo")

    assert densa["capa_a_fuera_dominio"]["umbral"] == 0.8
    assert alternativa["capa_a_fuera_dominio"]["umbral"] == 0.25
    assert alternativa["confianza_alta"]["umbral"] == 0.7
    assert alternativa["confianza_alta"]["senal"] == "senal_alternativa"
    assert "perfiles_retriever" in cfg["abstencion"]


def test_registry_resuelve_nombre_y_opciones():
    registro = RegistroComponentes()
    registro.registrar("fusion", "rrf", lambda k=0: {"k": k})
    resultado = registro.resolver_configuracion({"fusion": {"nombre": "rrf", "k": 17}})
    assert resultado == {"fusion": {"k": 17}}


def test_snapshot_incluye_defaults_y_se_puede_persistir(tmp_path):
    motor = tmp_path / "motor.yaml"
    dominio = tmp_path / "asistente.yaml"
    motor.write_text(
        "recuperacion:\n  modelo: modelo\n  estrategia_chunking: chunks\n  coleccion_base: demo\n",
        encoding="utf-8",
    )
    dominio.write_text("nombre_asistente: Demo\n", encoding="utf-8")
    snapshot = configuracion_efectiva(ruta_motor=str(motor), ruta_dominio=str(dominio))
    assert snapshot["motor"]["componentes"]["fusion"] == "rrf"
    salida = guardar_snapshot_configuracion(
        str(tmp_path / "out.yaml"), ruta_motor=str(motor), ruta_dominio=str(dominio)
    )
    assert salida.endswith("out.yaml")
    assert (tmp_path / "out.yaml").exists()


def test_version_del_api_proviene_del_paquete():
    from rag.servicio.api import app

    assert app.version == __version__


def test_componentes_base_registra_adaptadores_sin_cargar_modelos():
    from rag.aplicacion.registro_base import registrar_componentes_base

    registro = registrar_componentes_base(RegistroComponentes())
    assert registro.disponibles("parser") == ["builtin"]
    assert registro.disponibles("fusion") == ["rrf"]
    assert registro.crear("fusion", "rrf", k=10).k == 10


def test_fusion_rrf_es_determinista_y_conserva_el_candidato():
    from rag.nucleo.esquemas import ChunkRecord, RetrievalCandidate
    from rag.aplicacion.registro_base import FusionRRF

    def candidato(chunk_id: str) -> RetrievalCandidate:
        return RetrievalCandidate(chunk=ChunkRecord(
            chunk_id=chunk_id, doc_id="doc", texto_fuente=chunk_id,
            texto_embedding=chunk_id, offset_inicio=0, offset_fin=len(chunk_id),
        ))

    fusionados = FusionRRF(k=1).fusionar(
        [[candidato("a"), candidato("b")], [candidato("b"), candidato("a")]],
        limite=2,
    )
    assert [c.chunk.chunk_id for c in fusionados] == ["a", "b"]
    assert fusionados[0].signals.fusion_rank == 1


def test_el_nucleo_no_importa_dependencias_pesadas():
    import subprocess
    import sys

    codigo = (
        "import sys, rag.nucleo.contratos, rag.nucleo.esquemas, rag.nucleo.registro; "
        "pesados = ('qdrant_client', 'onnxruntime', 'torch', 'sentence_transformers', 'fastapi'); "
        "print(','.join(m for m in pesados if m in sys.modules))"
    )
    salida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, check=True)
    assert salida.stdout.strip() == ""
