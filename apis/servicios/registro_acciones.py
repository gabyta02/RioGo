"""Compatibilidad: usar servicios.panel_administrativo.registro_acciones."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("servicios.panel_administrativo.registro_acciones")
