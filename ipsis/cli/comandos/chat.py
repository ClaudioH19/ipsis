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

    def __init__(self, entrada=None, construir_motor=None) -> None:
        self.entrada = entrada  # se inyecta en las pruebas; si no, la terminal o input()
        self.construir_motor = construir_motor
        self.motor = None
        self.estado = {"diagnostico": False}  # lo lee la barra inferior de la terminal

    @property
    def diagnostico(self) -> bool:
        return self.estado["diagnostico"]

    @diagnostico.setter
    def diagnostico(self, valor: bool) -> None:
        self.estado["diagnostico"] = bool(valor)

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--diagnostics", dest="diagnostico", action="store_true", help=t("chat.opt_diagnostics"))

    # --- motor ---------------------------------------------------------------------------
    def _motor(self):
        if self.motor is None:
            from ipsis.cli.progreso import actividad

            with actividad("engine"):
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
        entrada = self.entrada
        if entrada is None:
            from ipsis.cli.terminal import crear_entrada, imprimir_banner

            entrada = crear_entrada(self.estado)
            if entrada is not None:
                imprimir_banner()  # Folio, el proyecto y cómo pedir ayuda
            else:
                entrada = input
        if entrada is input or self.entrada is not None:
            print(t("chat.welcome"))
        try:
            while True:
                try:
                    linea = entrada("> ").strip()
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    print(t("chat.cancelled"))
                    continue
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
        try:
            partes = shlex.split(linea[1:], posix=True) if linea[1:].strip() else []
        except ValueError as e:
            print(t("chat.invalid_command", error=e))
            return
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
            codigo = main(partes)
            if codigo == 130:
                print(t("chat.cancelled"))
        except SystemExit:
            pass  # argparse: --help o argumentos inválidos ya se informaron

    def _ayuda(self) -> None:
        print(t("chat.commands"))
        for nombre, clave in PROPIOS.items():
            print(f"  {nombre:14} {t(clave)}")
        print(f"  {'/<command>':14} {t('chat.cmd_any')}")
        from ipsis.recursos.instalacion import INSTALAR

        print(t("terminal.install", command=INSTALAR))
        print(t("terminal.update"))
        print(t("terminal.no_activation"))

    def _preguntar(self, pregunta: str) -> None:
        from ipsis.aplicacion.consulta import MotorNoListo, diagnosticar_pregunta
        from ipsis.cli.comandos.consulta import imprimir_diagnostico

        try:
            from ipsis.cli.progreso import actividad

            motor = self._motor()
            with actividad("query"):
                d = diagnosticar_pregunta(pregunta, motor)
        except KeyboardInterrupt:
            print(t("chat.cancelled"))
            self._cerrar_motor()
            return
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
        from ipsis.cli.terminal import imprimir_respuesta

        imprimir_respuesta(d.estado, d.respuesta, d.evidencias)


__all__ = ["ComandoAyuda", "ComandoChat", "PROPIOS"]
