"""Compatibilidad: usar core.autenticacion.enviar_correo."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.autenticacion.enviar_correo")
