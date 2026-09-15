"""Compatibilidad: usar servicios.chatboot_exploracion.gis_consulta."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("servicios.chatboot_exploracion.gis_consulta")
