"""Compatibilidad: usar core.infra.filtro_sitios."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.infra.filtro_sitios")
