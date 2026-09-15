"""Compatibilidad: usar core.autenticacion.tokens."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.autenticacion.tokens")
