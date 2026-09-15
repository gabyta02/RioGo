#!/usr/bin/env python3
"""Regenera shims de compatibilidad (incluye nombres privados)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SHIM_BODY = '''\
"""Compatibilidad: usar {module}."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("{module}")
'''

CORE_MOVES = {
    "conexion.py": "core.infra.conexion",
    "redis_cliente.py": "core.infra.redis_cliente",
    "trazabilidad.py": "core.infra.trazabilidad",
    "texto_limpieza.py": "core.infra.texto_limpieza",
    "busqueda_texto.py": "core.infra.busqueda_texto",
    "catalogo_trgm.py": "core.infra.catalogo_trgm",
    "filtro_sitios.py": "core.infra.filtro_sitios",
    "tokens.py": "core.autenticacion.tokens",
    "renovacion_tokens.py": "core.autenticacion.renovacion_tokens",
    "dependencias.py": "core.autenticacion.dependencias",
    "permisos.py": "core.autenticacion.permisos",
    "roles.py": "core.autenticacion.roles",
    "actividad_sesion.py": "core.autenticacion.actividad_sesion",
    "encriptacion.py": "core.autenticacion.encriptacion",
    "verificar_correo.py": "core.autenticacion.verificar_correo",
    "enviar_correo.py": "core.autenticacion.enviar_correo",
    "embeddings.py": "core.embeddings.embeddings",
    "semantica_evaluacion.py": "core.embeddings.semantica_evaluacion",
    "horario_evaluacion.py": "core.chatboot_evaluacion.horario_evaluacion",
    "horario_compacto.py": "core.chatboot_evaluacion.horario_compacto",
    "precio_evaluacion.py": "core.chatboot_evaluacion.precio_evaluacion",
    "tarifa_evaluacion.py": "core.chatboot_evaluacion.tarifa_evaluacion",
    "gis_evaluacion.py": "core.chatboot_evaluacion.gis_evaluacion",
    "ruta_evaluacion.py": "core.chatboot_evaluacion.ruta_evaluacion",
    "atributos_evaluacion.py": "core.chatboot_evaluacion.atributos_evaluacion",
    "chunk_sitio_evaluacion.py": "core.chatboot_evaluacion.chunk_sitio_evaluacion",
}

DOMAIN_MODULES = {
    "autenticacion": ["autentificar"],
    "panel_administrativo": [
        "dashboard", "atractivos", "rutas_turisticas", "contenido_chatbots",
        "noticias", "registro_acciones", "cuentas_admin", "chunks_descripcion",
    ],
    "app_movil": [
        "sitio_turismo", "sitio_ficha", "sitios_turismo", "favoritos_user",
        "noticias_usuario", "rutas_movil_turismo", "historial_usuario",
        "historial_usuario_service", "rutas_buses",
    ],
    "chatboot_exploracion": [
        "busqueda_referencia", "contacto_busqueda",
        "horario_consulta", "precio_consulta", "tarifa_acceso_consulta",
        "atributos_booleanos_consulta", "gis_consulta", "ruta_consulta",
        "busqueda_semantica_consulta", "historial_exploracion",
        "estado_busqueda", "exploracion_fallback",
    ],
    "chatboot_especifico": [
        "pregunta_directa", "chatboot_pregunta_directa",
        "historial_pregunta_directa",
    ],
    "compartido": ["comprobar_archivos"],
}


def _write_shim(path: Path, module: str) -> None:
    path.write_text(SHIM_BODY.format(module=module), encoding="utf-8")


def _fix_core() -> int:
    count = 0
    for old_name, module in CORE_MOVES.items():
        rel = module.replace("core.", "").replace(".", "/") + ".py"
        dst = ROOT / "core" / rel
        if not dst.exists():
            continue
        _write_shim(ROOT / "core" / old_name, module)
        count += 1
    return count


def _fix_layer(layer: str) -> int:
    count = 0
    base = ROOT / layer
    for domain, modules in DOMAIN_MODULES.items():
        for module in modules:
            dst = base / domain / f"{module}.py"
            shim = base / f"{module}.py"
            if not dst.exists():
                continue
            _write_shim(shim, f"{layer}.{domain}.{module}")
            count += 1
    return count


def _fix_orphan_shims(layer: str) -> int:
    """Shims cuyo destino se infiere del docstring existente."""
    count = 0
    base = ROOT / layer
    pattern = re.compile(r'Compatibilidad: usar ([\w.]+)\.')
    for shim in base.glob("*.py"):
        if (base / shim.stem).is_dir():
            continue
        text = shim.read_text(encoding="utf-8")
        match = pattern.search(text)
        if match:
            _write_shim(shim, match.group(1))
            count += 1
    return count


def main() -> None:
    n = _fix_core()
    print(f"core shims: {n}")
    for layer in ("esquemas", "servicios", "rutas"):
        n = _fix_layer(layer)
        print(f"{layer} shims: {n}")


if __name__ == "__main__":
    main()
