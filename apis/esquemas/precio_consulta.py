"""Compatibilidad: usar esquemas.chatboot_exploracion.precio_consulta."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("esquemas.chatboot_exploracion.precio_consulta")
