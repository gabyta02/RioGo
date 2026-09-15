"""Compatibilidad: usar core.embeddings.semantica_evaluacion."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("core.embeddings.semantica_evaluacion")
