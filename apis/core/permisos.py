"""Compatibilidad: usar core.autenticacion.permisos."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.autenticacion.permisos")
