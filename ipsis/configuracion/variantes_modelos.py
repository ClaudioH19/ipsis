"""Variantes de medium que cambian un modelo, para evaluar candidatos por componente."""
from copy import deepcopy

CASCADE = {"recuperar_n": 20, "rerank_k": 4, "leer_m": 2,
           "max_caracteres_lectura": 600, "concordancia": False}
BASE = {"denso": "intfloat/multilingual-e5-small",
        "reranker": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        "lector": "dewdev/mdeberta-v3-base-squad2-onnx"}
VARIANTES_MODELOS = {
    "granite": {"denso": "ibm-granite/granite-embedding-311m-multilingual-r2"},
    "granite97": {"denso": "ibm-granite/granite-embedding-97m-multilingual-r2"},
    "harrier": {"denso": "onnx-community/harrier-oss-v1-270m-ONNX"},
    "gemma2": {"denso": "onnx-community/embeddinggemma-2-ONNX"},
    "horizon-base": {"reranker": "Horizon-Labs/multilingual-reranker-base"},
    "horizon-small": {"reranker": "Horizon-Labs/multilingual-reranker-small"},
    "granite-horizon": {"denso": "ibm-granite/granite-embedding-311m-multilingual-r2",
                        "reranker": "Horizon-Labs/multilingual-reranker-base"},
}


def ajustes_variante(nombre: str) -> dict:
    """Ajustes del motor; mismo lector/cascada para atribuir las diferencias."""
    cambios = VARIANTES_MODELOS[nombre]
    return {"modelos": {**BASE, **cambios}, "cascada": deepcopy(CASCADE)}


__all__ = ["VARIANTES_MODELOS", "ajustes_variante"]
