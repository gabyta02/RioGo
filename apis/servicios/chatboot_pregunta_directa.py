"""Compatibilidad: usar servicios.chatboot_especifico.chatboot_pregunta_directa."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("servicios.chatboot_especifico.chatboot_pregunta_directa")
