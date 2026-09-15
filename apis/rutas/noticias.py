"""Compatibilidad: usar rutas.panel_administrativo.noticias."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("rutas.panel_administrativo.noticias")
