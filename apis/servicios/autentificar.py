"""Compatibilidad: usar servicios.autenticacion.autentificar."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("servicios.autenticacion.autentificar")
