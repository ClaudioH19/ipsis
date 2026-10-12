"""El estado de truncado/relleno no se mezcla entre consultas simultáneas."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

from ipsis.modelos.onnx import ModeloOnnx


def test_tokenizaciones_simultaneas_conservan_su_propia_ventana():
    primero, segundo, liberar = Event(), Event(), Event()

    class Tokenizador:
        ventana = None
        relleno = False

        def enable_truncation(self, max_length):
            self.ventana = max_length

        def enable_padding(self, pad_id):
            self.relleno = True

        def no_truncation(self):
            self.ventana = None

        def no_padding(self):
            self.relleno = False

        def encode_batch(self, textos):
            if textos == ["uno"]:
                primero.set()
                assert liberar.wait(5)
            else:
                segundo.set()
            return [(textos, self.ventana, self.relleno)]

    modelo = ModeloOnnx(SimpleNamespace(max_tokens=512, pad_token_id=0))
    modelo._tokenizador = Tokenizador()
    with ThreadPoolExecutor(max_workers=2) as executor:
        a = executor.submit(modelo.tokenizar, ["uno"], 256)
        assert primero.wait(5)
        b = executor.submit(modelo.tokenizar, ["dos"], 128)
        try:
            assert not segundo.wait(.1)
        finally:
            liberar.set()
        assert a.result(timeout=5) == [(["uno"], 256, True)]
        assert b.result(timeout=5) == [(["dos"], 128, True)]
    assert modelo._tokenizador.ventana is None and not modelo._tokenizador.relleno
