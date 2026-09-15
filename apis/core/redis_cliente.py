"""Compatibilidad: usar core.infra.redis_cliente."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.infra.redis_cliente")
