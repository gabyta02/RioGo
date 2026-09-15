"""Compatibilidad: usar core.autenticacion.encriptacion."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.autenticacion.encriptacion")
