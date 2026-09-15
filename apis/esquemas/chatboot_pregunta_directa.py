"""Compatibilidad: usar esquemas.chatboot_especifico.chatboot_pregunta_directa."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("esquemas.chatboot_especifico.chatboot_pregunta_directa")
