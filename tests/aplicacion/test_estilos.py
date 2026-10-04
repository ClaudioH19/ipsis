"""Tests de ``ipsis/aplicacion/estilos.py`` y del endpoint ``/estilos.css``.

La promesa que verifican: `configuracion/estilos.yaml` es el ÚNICO
archivo que hay que tocar para repintar el widget entero, y borrar
cualquier clave de él nunca rompe nada — el widget vuelve a su valor de
repuesto.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from ipsis.servicio.api import app
from ipsis.aplicacion.estilos import RUTA_ESTILOS, cargar_estilos, render_css

client = TestClient(app)


def test_el_archivo_de_estilos_del_repositorio_es_valido():
    """El tema que se distribuye tiene que cargar y rendear sin error: es el
    que `ipsis init` copia a cada proyecto nuevo."""
    tema = cargar_estilos(RUTA_ESTILOS)
    assert tema, "configuracion/estilos.yaml está vacío o no existe"
    css = render_css(tema)
    assert ".rw-raiz{" in css


def test_cada_seccion_del_yaml_llega_al_css():
    """Colores, tipografía, forma, sombras y animaciones tienen que acabar
    en variables CSS. Si alguien agrega una sección al YAML y se olvida de
    mapearla, este test no lo atrapa — pero sí atrapa que una sección
    existente deje de emitirse."""
    css = render_css({
        "colores": {"acento": "#ff0000", "texto": "#111111"},
        "tipografia": {"familia": "Georgia, serif", "tamano_mensaje": "15px"},
        "forma": {"radio_panel": "0px", "ancho_panel": "420px"},
        "sombras": {"panel": "none", "boton": "none"},
        "animaciones": {"activadas": True, "duracion_panel": ".5s", "curva": "linear"},
    })
    for esperado in ("--rw-acento:#ff0000", "--rw-texto:#111111",
                     "--rw-fuente:Georgia, serif", "--rw-tamano-mensaje:15px",
                     "--rw-radio-panel:0px", "--rw-ancho-panel:420px",
                     "--rw-sombra-panel:none", "--rw-dur-panel:.5s", "--rw-curva:linear"):
        assert esperado in css, f"falta {esperado} en el CSS generado"


def test_modo_oscuro_va_en_su_propio_bloque():
    css = render_css({"colores": {"acento": "#123456"},
                      "colores_oscuro": {"fondo": "#000000"}})
    assert "@media (prefers-color-scheme:dark)" in css
    indice_claro = css.index("--rw-acento:#123456")
    indice_oscuro = css.index("--rw-fondo:#000000")
    assert indice_claro < indice_oscuro, "el bloque oscuro debe ir después del claro para ganar"


def test_apagar_animaciones_las_apaga_todas():
    """`activadas: false` tiene que apagar el movimiento de un golpe, sin
    tener que poner cada duración en cero a mano."""
    css = render_css({"animaciones": {"activadas": False}})
    assert "animation:none !important" in css
    assert "transition:none !important" in css


def test_tema_vacio_no_rompe_nada():
    """Un YAML vacío, o borrado, produce una hoja sin declaraciones: el
    widget se queda con sus valores de repuesto en vez de quedar sin
    estilos."""
    css = render_css({})
    assert ".rw-raiz{" not in css
    assert css.strip().startswith("/*")


def test_clave_borrada_vuelve_al_valor_de_repuesto():
    """Quitar una clave del YAML no debe emitir una variable vacía, que
    dejaría la propiedad rota: simplemente no se emite."""
    css = render_css({"colores": {"acento": "#abcdef", "fondo": ""}})
    assert "--rw-acento:#abcdef" in css
    assert "--rw-fondo" not in css


def test_css_extra_va_al_final():
    """El escape para lo que no cubran las claves tiene que poder
    sobreescribir todo lo anterior, así que va último."""
    css = render_css({"colores": {"acento": "#000000"},
                      "css_extra": ".rw-msg-ok{border-radius:0;}"})
    assert css.index("--rw-acento") < css.index(".rw-msg-ok{border-radius:0;}")


def test_endpoint_estilos_css_responde_con_el_tema():
    r = client.get("/estilos.css")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")
    assert "--rw-acento" in r.text


def test_el_widget_enlaza_la_hoja_del_servidor_despues_de_sus_repuestos():
    """El orden es lo que hace que el YAML gane: el widget declara sus
    valores de repuesto en un <style> y enlaza /estilos.css DESPUÉS."""
    js = client.get("/widget.js").text
    assert "temaServidor.href" in js, "el widget no enlaza la hoja del servidor"
    # Se compara contra el appendChild real, no contra la primera mención de
    # "/estilos.css" del archivo, que está en un comentario más arriba.
    assert js.index("raiz.appendChild(estilos)") < js.index("raiz.appendChild(temaServidor)")


def test_todas_las_variables_del_yaml_existen_en_el_widget():
    """Cada variable que el renderizador puede emitir tiene que estar
    realmente consumida por el CSS del widget. Si no, el YAML ofrecería una
    clave que no hace nada — el peor tipo de configuración."""
    css_generado = render_css(cargar_estilos(RUTA_ESTILOS))
    js = client.get("/widget.js").text
    variables = {linea.strip().split(":")[0]
                 for linea in css_generado.splitlines()
                 if linea.strip().startswith("--rw-")}
    assert variables, "el tema del repositorio no emite ninguna variable"
    sin_usar = [v for v in sorted(variables) if f"var({v})" not in js]
    assert not sin_usar, f"el YAML ofrece variables que el widget no usa: {sin_usar}"


def test_init_deja_el_archivo_de_estilos(tmp_path: Path, monkeypatch):
    """`ipsis init` tiene que dejar el tema en el proyecto nuevo, con sus
    comentarios: son la documentación de cada clave."""
    from ipsis.configuracion.carga import inicializar_estilos_si_falta

    origen = Path(RUTA_ESTILOS).resolve()
    monkeypatch.chdir(tmp_path)
    assert inicializar_estilos_si_falta(origen=str(origen)) is True
    creado = tmp_path / "configuracion" / "estilos.yaml"
    assert creado.exists()
    assert "colores:" in creado.read_text(encoding="utf-8")
    assert yaml.safe_load(creado.read_text(encoding="utf-8"))
    # Nunca pisa un tema ya existente.
    assert inicializar_estilos_si_falta(origen=str(origen)) is False
