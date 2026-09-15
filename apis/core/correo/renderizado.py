from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.correo.configuracion import PLANTILLAS_DIR

_environment: Environment | None = None


def _obtener_entorno() -> Environment:
    global _environment
    if _environment is None:
        _environment = Environment(
            loader=FileSystemLoader(str(PLANTILLAS_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )
    return _environment


def renderizar_plantilla(nombre: str, contexto: dict[str, Any]) -> str:
    plantilla = _obtener_entorno().get_template(nombre)
    return plantilla.render(**contexto)


def renderizar_correo(
    plantilla_base: str,
    contexto: dict[str, Any],
) -> tuple[str, str]:
    html = renderizar_plantilla(f"{plantilla_base}.html", contexto)
    texto = renderizar_plantilla(f"{plantilla_base}.txt", contexto)
    return html, texto
