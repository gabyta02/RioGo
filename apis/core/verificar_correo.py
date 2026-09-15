"""Compatibilidad: usar core.autenticacion.verificar_correo."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.autenticacion.verificar_correo")
