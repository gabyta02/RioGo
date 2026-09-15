#!/usr/bin/env python3
"""Reorganiza apis en subcarpetas por dominio con shims de compatibilidad."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CORE_MOVES: dict[str, str] = {
    "conexion.py": "infra/conexion.py",
    "redis_cliente.py": "infra/redis_cliente.py",
    "trazabilidad.py": "infra/trazabilidad.py",
    "texto_limpieza.py": "infra/texto_limpieza.py",
    "busqueda_texto.py": "infra/busqueda_texto.py",
    "catalogo_trgm.py": "infra/catalogo_trgm.py",
    "filtro_sitios.py": "infra/filtro_sitios.py",
    "tokens.py": "autenticacion/tokens.py",
    "renovacion_tokens.py": "autenticacion/renovacion_tokens.py",
    "dependencias.py": "autenticacion/dependencias.py",
    "permisos.py": "autenticacion/permisos.py",
    "roles.py": "autenticacion/roles.py",
    "actividad_sesion.py": "autenticacion/actividad_sesion.py",
    "encriptacion.py": "autenticacion/encriptacion.py",
    "verificar_correo.py": "autenticacion/verificar_correo.py",
    "enviar_correo.py": "autenticacion/enviar_correo.py",
    "embeddings.py": "embeddings/embeddings.py",
    "semantica_evaluacion.py": "embeddings/semantica_evaluacion.py",
    "horario_evaluacion.py": "chatboot_evaluacion/horario_evaluacion.py",
    "horario_compacto.py": "chatboot_evaluacion/horario_compacto.py",
    "precio_evaluacion.py": "chatboot_evaluacion/precio_evaluacion.py",
    "tarifa_evaluacion.py": "chatboot_evaluacion/tarifa_evaluacion.py",
    "gis_evaluacion.py": "chatboot_evaluacion/gis_evaluacion.py",
    "ruta_evaluacion.py": "chatboot_evaluacion/ruta_evaluacion.py",
    "atributos_evaluacion.py": "chatboot_evaluacion/atributos_evaluacion.py",
    "chunk_sitio_evaluacion.py": "chatboot_evaluacion/chunk_sitio_evaluacion.py",
}

DOMAIN_MODULES: dict[str, list[str]] = {
    "autenticacion": ["autentificar"],
    "panel_administrativo": [
        "dashboard",
        "atractivos",
        "rutas_turisticas",
        "contenido_chatbots",
        "noticias",
        "registro_acciones",
        "cuentas_admin",
        "chunks_descripcion",
    ],
    "app_movil": [
        "sitio_turismo",
        "sitio_ficha",
        "sitios_turismo",
        "favoritos_user",
        "noticias_usuario",
        "rutas_movil_turismo",
        "historial_usuario",
        "historial_usuario_service",
        "rutas_buses",
    ],
    "chatboot_exploracion": [
        "busqueda_referencia",
        "contacto_busqueda",
        "horario_consulta",
        "precio_consulta",
        "tarifa_acceso_consulta",
        "atributos_booleanos_consulta",
        "gis_consulta",
        "ruta_consulta",
        "busqueda_semantica_consulta",
        "historial_exploracion",
        "estado_busqueda",
        "exploracion_fallback",
    ],
    "chatboot_especifico": [
        "pregunta_directa",
        "chatboot_pregunta_directa",
        "historial_pregunta_directa",
    ],
    "compartido": ["comprobar_archivos"],
}

CORE_IMPORT_REWRITES = [
    (r"from core\.conexion\b", "from core.infra.conexion"),
    (r"from core\.redis_cliente\b", "from core.infra.redis_cliente"),
    (r"from core\.trazabilidad\b", "from core.infra.trazabilidad"),
    (r"from core\.texto_limpieza\b", "from core.infra.texto_limpieza"),
    (r"from core\.busqueda_texto\b", "from core.infra.busqueda_texto"),
    (r"from core\.catalogo_trgm\b", "from core.infra.catalogo_trgm"),
    (r"from core\.filtro_sitios\b", "from core.infra.filtro_sitios"),
    (r"from core\.tokens\b", "from core.autenticacion.tokens"),
    (r"from core\.renovacion_tokens\b", "from core.autenticacion.renovacion_tokens"),
    (r"from core\.dependencias\b", "from core.autenticacion.dependencias"),
    (r"from core\.permisos\b", "from core.autenticacion.permisos"),
    (r"from core\.roles\b", "from core.autenticacion.roles"),
    (r"from core\.actividad_sesion\b", "from core.autenticacion.actividad_sesion"),
    (r"from core\.encriptacion\b", "from core.autenticacion.encriptacion"),
    (r"from core\.verificar_correo\b", "from core.autenticacion.verificar_correo"),
    (r"from core\.enviar_correo\b", "from core.autenticacion.enviar_correo"),
    (r"from core\.embeddings\b", "from core.embeddings.embeddings"),
    (r"from core\.semantica_evaluacion\b", "from core.embeddings.semantica_evaluacion"),
    (r"from core\.horario_evaluacion\b", "from core.chatboot_evaluacion.horario_evaluacion"),
    (r"from core\.horario_compacto\b", "from core.chatboot_evaluacion.horario_compacto"),
    (r"from core\.precio_evaluacion\b", "from core.chatboot_evaluacion.precio_evaluacion"),
    (r"from core\.tarifa_evaluacion\b", "from core.chatboot_evaluacion.tarifa_evaluacion"),
    (r"from core\.gis_evaluacion\b", "from core.chatboot_evaluacion.gis_evaluacion"),
    (r"from core\.ruta_evaluacion\b", "from core.chatboot_evaluacion.ruta_evaluacion"),
    (r"from core\.atributos_evaluacion\b", "from core.chatboot_evaluacion.atributos_evaluacion"),
    (r"from core\.chunk_sitio_evaluacion\b", "from core.chatboot_evaluacion.chunk_sitio_evaluacion"),
]

LAYER_IMPORT_REWRITES: list[tuple[str, str]] = []
for layer in ("rutas", "servicios", "esquemas"):
    for domain, modules in DOMAIN_MODULES.items():
        for module in modules:
            old = rf"from {layer}\.{module}\b"
            new = f"from {layer}.{domain}.{module}"
            LAYER_IMPORT_REWRITES.append((old, new))


def _ensure_init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    init = path / "__init__.py"
    if not init.exists():
        init.write_text('"""Paquete de dominio."""\n', encoding="utf-8")


def _shim_content(module: str) -> str:
    return (
        f'"""Compatibilidad: usar {module}."""\n'
        "import sys\n"
        "from importlib import import_module\n\n"
        f'sys.modules[__name__] = import_module("{module}")\n'
    )


def _rewrite_imports(content: str) -> str:
    for pattern, replacement in CORE_IMPORT_REWRITES + LAYER_IMPORT_REWRITES:
        content = re.sub(pattern, replacement, content)
    return content


def _move_core() -> None:
    core = ROOT / "core"
    for old_name, new_rel in CORE_MOVES.items():
        src = core / old_name
        dst = core / new_rel
        if not src.exists():
            if dst.exists():
                shim = core / old_name
                if not shim.exists():
                    module = "core." + new_rel.replace("/", ".").replace(".py", "")
                    shim.write_text(_shim_content(module), encoding="utf-8")
                continue
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            src.unlink()
            continue
        shutil.move(str(src), str(dst))
        content = dst.read_text(encoding="utf-8")
        dst.write_text(_rewrite_imports(content), encoding="utf-8")
        shim = core / old_name
        module = "core." + new_rel.replace("/", ".").replace(".py", "")
        shim.write_text(_shim_content(module), encoding="utf-8")
    for sub in ("infra", "autenticacion", "embeddings", "chatboot_evaluacion"):
        _ensure_init(core / sub)


def _move_layer(layer: str) -> None:
    base = ROOT / layer
    for domain, modules in DOMAIN_MODULES.items():
        domain_dir = base / domain
        _ensure_init(domain_dir)
        for module in modules:
            src = base / f"{module}.py"
            dst = domain_dir / f"{module}.py"
            if not src.exists():
                if dst.exists():
                    shim = base / f"{module}.py"
                    if not shim.exists():
                        module_path = f"{layer}.{domain}.{module}"
                        shim.write_text(_shim_content(module_path), encoding="utf-8")
                continue
            if dst.exists():
                src.unlink()
                continue
            shutil.move(str(src), str(dst))
            content = dst.read_text(encoding="utf-8")
            dst.write_text(_rewrite_imports(content), encoding="utf-8")
            shim = base / f"{module}.py"
            module_path = f"{layer}.{domain}.{module}"
            shim.write_text(_shim_content(module_path), encoding="utf-8")


def _fix_env_paths() -> None:
    autenticacion_files = list((ROOT / "core" / "autenticacion").glob("*.py"))
    for path in autenticacion_files:
        text = path.read_text(encoding="utf-8")
        if 'parents[1] / ".env"' in text:
            path.write_text(text.replace('parents[1] / ".env"', 'parents[2] / ".env"'), encoding="utf-8")
    tokens = ROOT / "core" / "autenticacion" / "tokens.py"
    if tokens.exists():
        text = tokens.read_text(encoding="utf-8")
        text = text.replace("parents[1]", "parents[2]")
        tokens.write_text(text, encoding="utf-8")


def main() -> None:
    _move_core()
    for layer in ("esquemas", "servicios", "rutas"):
        _move_layer(layer)
    _fix_env_paths()
    print("Reorganizacion completada.")


if __name__ == "__main__":
    main()
