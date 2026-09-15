#!/usr/bin/env python3
"""Genera shims de compatibilidad faltantes en core/."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CORE_MOVES = {
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


def main() -> None:
    core = ROOT / "core"
    for old_name, new_rel in CORE_MOVES.items():
        dst = core / new_rel
        shim = core / old_name
        if not dst.exists():
            print(f"FALTA destino: {dst}")
            continue
        module = "core." + new_rel.replace("/", ".").replace(".py", "")
        shim.write_text(
            f'"""Compatibilidad: usar {module}."""\n'
            "import sys\n"
            "from importlib import import_module\n\n"
            f'sys.modules[__name__] = import_module("{module}")\n',
            encoding="utf-8",
        )
        print(f"shim: {old_name}")


if __name__ == "__main__":
    main()
