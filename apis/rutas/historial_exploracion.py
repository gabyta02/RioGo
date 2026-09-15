"""Compatibilidad: usar rutas.chatboot_exploracion.historial_exploracion."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("rutas.chatboot_exploracion.historial_exploracion")
