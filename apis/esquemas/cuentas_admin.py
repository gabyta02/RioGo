"""Compatibilidad: usar esquemas.panel_administrativo.cuentas_admin."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("esquemas.panel_administrativo.cuentas_admin")
