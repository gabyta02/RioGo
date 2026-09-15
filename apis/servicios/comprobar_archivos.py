"""Compatibilidad: usar servicios.compartido.comprobar_archivos."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("servicios.compartido.comprobar_archivos")
