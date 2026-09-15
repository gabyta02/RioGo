"""Compatibilidad: usar core.chatboot_evaluacion.precio_evaluacion."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.chatboot_evaluacion.precio_evaluacion")
