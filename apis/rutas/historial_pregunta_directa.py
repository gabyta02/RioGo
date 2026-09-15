"""Compatibilidad: usar rutas.chatboot_especifico.historial_pregunta_directa."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("rutas.chatboot_especifico.historial_pregunta_directa")
