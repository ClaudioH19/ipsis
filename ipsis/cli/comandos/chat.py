"""``ipsis help`` y ``ipsis chat``: el menú y el modo interactivo de la terminal.

En el modo interactivo lo que se escribe es una pregunta, y lo que empieza con
``/`` es un comando: los propios del modo (``/help``, ``/diagnostics``,
``/reload``, ``/exit``) o cualquier comando de la CLI (``/doctor``, ``/index``,
``/load ./manuales``). El motor se carga una vez y se reutiliza, con la misma
conversación: las preguntas de seguimiento («¿y con 90?») heredan el tema. Antes
de correr un comando de la CLI se cierra el motor (el índice local de Qdrant no
admite dos clientes); se vuelve a cargar con la pregunta siguiente.
"""
from __future__ import annotations

import argparse
import shlex

from ipsis.cli.base import Comando
from ipsis.recursos.mensajes import t


class ComandoAyuda(Comando):
    nombre = "help"
    ayuda = "help.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("comando", metavar="command", nargs="?", help=t("help.arg_command"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        if not args.comando:
            from ipsis.cli.menu import imprimir_menu

            imprimir_menu()
            return 0
        from ipsis.cli import main

        try:
            return main([args.comando, "--help"])
        except SystemExit as salida:  # argparse termina tras imprimir la ayuda
            return int(salida.code or 0)


# Comandos propios del modo interactivo: nombre → clave de su descripción.
PROPIOS = {
    "/help": "chat.cmd_help",
    "/diagnostics": "chat.cmd_diagnostics",
    "/reload": "chat.cmd_reload",
    "/exit": "chat.cmd_exit",
}


class ComandoChat(Comando):
    nombre = "chat"
    ayuda = "chat.help"

    def __init__(self, entrada=input, construir_motor=None) -> None:
        self.entrada = entrada  # se inyecta en las pruebas
        self.construir_motor = construir_motor
        self.motor = None
        self.diagnostico = False

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--diagnostics", dest="diagnostico", action="store_true", help=t("chat.opt_diagnostics"))

    # --- motor ---------------------------------------------------------------------------
    def _motor(self):
        if self.motor is None:
            print(t("chat.loading"))
            if self.construir_motor is not None:
                self.motor = self.construir_motor()
            else:
                from ipsis.aplicacion.consulta import construir_motor_del_proyecto

                self.motor = construir_motor_del_proyecto()
                self.motor.calentar()
        return self.motor

    def _cerrar_motor(self) -> None:
        if self.motor is not None:
            cerrar = getattr(self.motor, "cerrar", None)
            if callable(cerrar):
                cerrar()
            self.motor = None

    # --- bucle ---------------------------------------------------------------------------
    def ejecutar(self, args: argparse.Namespace) -> int:
        self.diagnostico = bool(getattr(args, "diagnostico", False))
        print(t("chat.welcome"))
        try:
            while True:
                try:
                    linea = self.entrada("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not linea:
                    continue
                if linea in ("/exit", "/quit"):
                    break
                if linea.startswith("/"):
                    self._comando(linea)
                else:
                    self._preguntar(linea)
        finally:
            self._cerrar_motor()
        print(t("chat.bye"))
        return 0

    def _comando(self, linea: str) -> None:
        partes = shlex.split(linea[1:], posix=True) if linea[1:].strip() else []
        if not partes or partes[0] == "help":
            self._ayuda()
            return
        nombre = partes[0]
        if nombre == "diagnostics":
            valor = partes[1].lower() if len(partes) > 1 else ""
            self.diagnostico = (not self.diagnostico) if valor not in ("on", "off") else valor == "on"
            print(t("chat.diagnostics_on") if self.diagnostico else t("chat.diagnostics_off"))
            return
        if nombre == "reload":
            self._cerrar_motor()
            print(t("chat.reloaded"))
            return
        from ipsis.cli import main
        from ipsis.cli.menu import descripciones

        if nombre not in descripciones() or nombre == "chat":
            print(t("chat.unknown", command=nombre))
            return
        self._cerrar_motor()  # el índice local admite un solo cliente
        try:
            main(partes)
        except SystemExit:
            pass  # argparse: --help o argumentos inválidos ya se informaron

    def _ayuda(self) -> None:
        print(t("chat.commands"))
        for nombre, clave in PROPIOS.items():
            print(f"  {nombre:14} {t(clave)}")
        print(f"  {'/<command>':14} {t('chat.cmd_any')}")

    def _preguntar(self, pregunta: str) -> None:
        from ipsis.aplicacion.consulta import MotorNoListo, diagnosticar_pregunta
        from ipsis.cli.comandos.consulta import etiqueta_estado, imprimir_diagnostico

        try:
            d = diagnosticar_pregunta(pregunta, self._motor())
        except MotorNoListo as e:
            print(t("ask.not_ready", error=e))
            print(t("cli.action", action="/doctor"))
            self.motor = None
            return
        except Exception as e:  # noqa: BLE001 -- índice bloqueado, modelo faltante, configuración inválida...
            print(t("ask.engine_failed", error=e))
            print(t("cli.action", action="/doctor"))
            self._cerrar_motor()
            return
        if self.diagnostico:
            imprimir_diagnostico(d)
            return
        print(etiqueta_estado(d.estado))
        print(d.respuesta)
        for e in d.evidencias:
            print(t("ask.evidence", doc_id=e["doc_id"], start=e["offset_inicio"], end=e["offset_fin"]))


__all__ = ["ComandoAyuda", "ComandoChat", "PROPIOS"]
