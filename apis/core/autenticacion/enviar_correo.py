"""Compatibilidad: delega al modulo unificado de correo."""

from core.correo.transporte import EnviarCorreoError, enviar_correo_texto

__all__ = ["EnviarCorreoError", "enviar_correo_texto"]
