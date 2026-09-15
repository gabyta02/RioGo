"""Compatibilidad: usar esquemas.compartido.comprobar_archivos."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("esquemas.compartido.comprobar_archivos")
