from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import ResultadoHerramienta, TipoIds, construir_estado

REPO_ROOT = Path(__file__).resolve().parents[5]
MAX_DOCUMENTO_CHARS = 12000


async def ejecutar(
    *,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    id_sitio = _resolver_id_sitio(state)
    if id_sitio is None:
        return (
            construir_estado(
                "documento_sitio",
                orden,
                "error",
                payload={"fallo": "Falta id_sitio para documento_sitio."},
                nota="Falta id_sitio para documento_sitio.",
            ),
            tipo_ids,
        )

    ruta_payload: dict[str, Any] = {}
    try:
        ruta_payload = await cliente.post("/ruta-documento", {"id_sitio": id_sitio})
    except Exception as exc:
        ruta_payload = {"fallo": str(exc)}

    contenido, rutas_intentadas = _leer_documento(ruta_payload.get("ruta_archivo"))
    if contenido:
        payload = {
            **ruta_payload,
            "id_sitio": id_sitio,
            "contenido_markdown": contenido,
            "ruta_resuelta": rutas_intentadas[0] if rutas_intentadas else "",
        }
        return (
            construir_estado(
                "documento_sitio",
                orden,
                "ok",
                ids=[id_sitio],
                payload=payload,
                nota="Documento principal del sitio cargado.",
            ),
            "sitio",
        )

    fallback = await _buscar_chunks_generales(id_sitio, state, cliente)
    if fallback.get("chunks"):
        return (
            construir_estado(
                "documento_sitio",
                orden,
                "ok",
                ids=[id_sitio],
                payload={
                    "id_sitio": id_sitio,
                    "fallback_chunks": True,
                    "ruta_documento": ruta_payload,
                    **fallback,
                },
                nota="Documento no disponible; se usaron chunks del sitio.",
            ),
            "sitio",
        )

    fallo = ruta_payload.get("fallo") or "No hay documento disponible para este sitio."
    return (
        construir_estado(
            "documento_sitio",
            orden,
            "sin_resultados",
            payload={
                "fallo": fallo,
                "ruta_documento": ruta_payload,
                "rutas_intentadas": rutas_intentadas,
                "fallback_chunks": fallback,
            },
            nota=str(fallo),
        ),
        tipo_ids,
    )


async def _buscar_chunks_generales(
    id_sitio: int,
    state: dict[str, Any],
    cliente: Any,
) -> dict[str, Any]:
    nombre = str(state.get("nombre_sitio") or "este sitio").strip()
    try:
        return await cliente.post(
            "/chunks-documento",
            {
                "id_sitio": id_sitio,
                "mensaje_chunk": f"información general de {nombre}",
                "keywords": [nombre],
            },
        )
    except Exception as exc:
        return {"fallo": str(exc)}


def _leer_documento(ruta_archivo: Any) -> tuple[str, list[str]]:
    ruta = str(ruta_archivo or "").strip()
    if not ruta:
        return "", []

    candidatos = _resolver_rutas_candidatas(ruta)
    rutas_intentadas: list[str] = []
    for path in candidatos:
        rutas_intentadas.append(str(path))
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8")[:MAX_DOCUMENTO_CHARS], [
                    str(path),
                    *[str(item) for item in candidatos if item != path],
                ]
        except OSError:
            continue
    return "", rutas_intentadas


def _resolver_rutas_candidatas(ruta: str) -> list[Path]:
    path = Path(ruta)
    if path.is_absolute():
        return [path]

    roots = [
        Path(os.getenv("RIOBAMBAGO_ROOT", "")),
        Path.cwd(),
        REPO_ROOT,
        REPO_ROOT / "chatboot",
    ]
    candidatos: list[Path] = []
    vistos: set[str] = set()
    for root in roots:
        if not str(root):
            continue
        candidato = (root / path).resolve()
        clave = str(candidato)
        if clave in vistos:
            continue
        vistos.add(clave)
        candidatos.append(candidato)
    return candidatos


def _resolver_id_sitio(state: dict[str, Any]) -> int | None:
    try:
        id_sitio = int(state.get("id_sitio"))
    except (TypeError, ValueError):
        return None
    return id_sitio if id_sitio > 0 else None
