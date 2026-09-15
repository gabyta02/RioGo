ROLES_PANEL = frozenset({"super-admin", "admin"})


def rol_desde_cargo(cargo_nombre: str | None) -> str:
    nombre = (cargo_nombre or "").strip().lower()
    if nombre in ("super admin", "super administrador"):
        return "super-admin"
    if nombre == "usuario":
        return "usuario"
    return "admin"


def es_rol_panel(rol: str | None) -> bool:
    return bool(rol and rol in ROLES_PANEL)
