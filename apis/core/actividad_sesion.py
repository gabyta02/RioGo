"""Compatibilidad: usar core.autenticacion.actividad_sesion."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.autenticacion.actividad_sesion")
