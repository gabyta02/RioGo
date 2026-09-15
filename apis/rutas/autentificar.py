"""Compatibilidad: usar rutas.autenticacion.autentificar."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("rutas.autenticacion.autentificar")
