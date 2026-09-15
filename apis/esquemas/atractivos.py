"""Compatibilidad: usar esquemas.panel_administrativo.atractivos."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("esquemas.panel_administrativo.atractivos")
