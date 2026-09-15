"""Compatibilidad: usar core.infra.busqueda_texto."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.infra.busqueda_texto")
