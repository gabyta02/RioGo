"""Compatibilidad: usar core.infra.catalogo_trgm."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.infra.catalogo_trgm")
