"""Compatibilidad: usar core.infra.texto_limpieza."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.infra.texto_limpieza")
