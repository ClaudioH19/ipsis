"""Grupo modelos: ver, descargar, verificar y exportar los modelos ONNX del perfil."""
from __future__ import annotations

import argparse

from ipsis.aplicacion.modelos import (
    ExportacionFallida,
    ExportacionNoDisponible,
    SinProyecto,
    descargar_modelos,
    exportar_modelo,
    listar_modelos,
    verificar_modelos,
)
from ipsis.aplicacion.proyecto import PerfilInvalido
from ipsis.cli.base import Comando, Grupo

ACCION_DESCARGAR = "  Acción: ipsis modelos descargar"


def _mb(n: int) -> str:
    return f"{n / 1_000_000:,.0f} MB".replace(",", ".")


def _sin_proyecto(e: SinProyecto) -> int:
    print(f"Error: {e}.")
    print("  Acción: ipsis init (o indica --perfil en 'ipsis modelos descargar')")
    return 1


def _licencia(licencia: str, atribucion: str | None) -> str:
    return f"{licencia}; atribución: {atribucion}" if atribucion else licencia


class ComandoModelosListar(Comando):
    nombre = "listar"
    ayuda = "Muestra los modelos del perfil activo: licencia, archivo ONNX y si están en la caché."

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            r = listar_modelos()
        except SinProyecto as e:
            return _sin_proyecto(e)
        print(f"Perfil: {r.perfil}")
        for m in r.modelos:
            print(f"\n{m.rol}: {m.id_hf}")
            print(f"  Licencia:   {_licencia(m.licencia, m.atribucion)}")
            print(f"  Parámetros: {m.parametros / 1e6:.0f}M")
            print(f"  ONNX:       {m.archivo}")
            print("  Caché:      " + (f"disponible ({_mb(m.bytes_en_disco)})" if m.en_cache else "falta"))
        if any(not m.en_cache for m in r.modelos):
            print()
            print(ACCION_DESCARGAR)
        return 0


class ComandoModelosDescargar(Comando):
    nombre = "descargar"
    ayuda = "Descarga a la caché global los modelos del perfil activo (o de --perfil) que falten."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--perfil", default=None,
                            help="Perfil cuyos modelos descargar (light, medium o heavy); no cambia el perfil "
                                 "activo. Por defecto: el perfil activo del proyecto.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            r = descargar_modelos(args.perfil, avisar=lambda rol, id_hf: print(f"Descargando {rol}: {id_hf} ..."))
        except PerfilInvalido as e:
            print(f"Error: {e}")
            return 1
        except SinProyecto as e:
            return _sin_proyecto(e)
        for m in r.modelos:
            estado = "descargado" if m.estado == "descargado" else "ya disponible"
            print(f"{m.rol}: {m.id_hf} -- {estado}")
            print(f"  Licencia: {_licencia(m.licencia, m.atribucion)}")
        if r.error:
            print(f"Error: {r.error}")
            return 1
        print(f"Modelos del perfil {r.perfil} listos en la caché global ({r.cache}).")
        return 0


class ComandoModelosVerificar(Comando):
    nombre = "verificar"
    ayuda = "Comprueba que los modelos del perfil activo están completos y hacen una inferencia de prueba."

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            r = verificar_modelos()
        except SinProyecto as e:
            return _sin_proyecto(e)
        etiquetas = {"ok": "OK", "falta": "FALTA", "no_carga": "NO CARGA", "inferencia_fallida": "FALLA"}
        print(f"Perfil: {r.perfil}")
        for m in r.modelos:
            print(f"  {m.rol:9} {m.id_hf:45} {etiquetas[m.estado]}")
            if m.mensaje:
                print(f"            {m.mensaje}")
        if r.ok:
            print("Verificación completa: todos los modelos cargan e infieren.")
            return 0
        print("Verificación incompleta.")
        if any(m.estado == "falta" for m in r.modelos):
            print(ACCION_DESCARGAR)
        if any(m.estado != "falta" and m.estado != "ok" for m in r.modelos):
            print("  Acción: borra ese modelo de la caché y vuelve a ejecutar 'ipsis modelos descargar'")
        return 1


class ComandoModelosExportar(Comando):
    nombre = "exportar"
    ayuda = "Desarrollo: convierte un modelo de Hugging Face a ONNX (requiere el extra [exportar])."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("id_hf", help="Repositorio de Hugging Face, p.ej. organizacion/modelo.")
        parser.add_argument("--int8", action="store_true",
                            help="Además genera model_int8.onnx con cuantización dinámica de onnxruntime.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            r = exportar_modelo(args.id_hf, int8=args.int8)
        except ExportacionNoDisponible as e:
            print("Error: la exportación requiere las dependencias de desarrollo "
                  f"({', '.join(e.faltantes)} no están instaladas).")
            print(f"  Acción: {e.instalar}")
            return 1
        except FileExistsError as e:
            print(f"Error: {e}")
            return 1
        except ExportacionFallida as e:
            print(f"Error: la exportación de {args.id_hf} falló: {e}")
            print("  Revisa el id del repositorio y que las versiones de optimum y transformers sean compatibles.")
            return 1
        print(f"ONNX exportado: {r.onnx}")
        if r.int8:
            print(f"ONNX int8:      {r.int8}")
        print("No se agregó al catálogo ni a los perfiles: adoptarlo es un paso aparte.")
        return 0


def grupo_modelos() -> Grupo:
    return Grupo("modelos", "Modelos ONNX del perfil: listar, descargar, verificar o exportar.",
                 "Operación sobre los modelos.",
                 [ComandoModelosListar(), ComandoModelosDescargar(), ComandoModelosVerificar(),
                  ComandoModelosExportar()])


__all__ = ["ComandoModelosDescargar", "ComandoModelosExportar", "ComandoModelosListar",
           "ComandoModelosVerificar", "grupo_modelos"]
