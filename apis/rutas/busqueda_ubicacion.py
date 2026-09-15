"""Compatibilidad: usar rutas.chatboot_exploracion.busqueda_ubicacion."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module("rutas.chatboot_exploracion.busqueda_ubicacion")
