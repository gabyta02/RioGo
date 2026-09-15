import re
import secrets
import string
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.correo import EnviarCorreoError, enviar_correo
from core.autenticacion.encriptacion import encriptar_texto
from core.infra.trazabilidad import ActorTrazabilidad, registrar_evento_actor
from core.autenticacion.permisos import PERMISOS_SITIO_DUENO, reemplazar_sitios_usuario
from esquemas.panel_administrativo.atractivos import EstadoAtractivo, SitiosListResponse
from esquemas.panel_administrativo.cuentas_admin import (
    CargoCreate,
    CargoResponse,
    CargoUpdate,
    CuentaAdminCreate,
    CuentaAdminDetalleResponse,
    CuentaAdminEstadoUpdate,
    CuentaAdminListItem,
    CuentaAdminListResponse,
    CuentaAdminUpdate,
    PermisoResponse,
    SitioAsignadoItem,
)
from servicios.panel_administrativo.atractivos import _sitio_select_sql, listar_sitios
from servicios.panel_administrativo.contenido_chatbots import (
    asegurar_repositorio_sitio_chatbot,
)

ACCIONES_PERMISO = ("ver", "crear", "actualizar", "eliminar", "exportar")
ROLES_CUENTA_ADMIN = frozenset({"admin", "super-admin"})
MODULOS_ALCANCE_SITIO_DUENO = frozenset(PERMISOS_SITIO_DUENO.keys())
MODULOS_EXCLUIDOS_ADMIN = frozenset({"admin_accounts"})
MODULOS_DUENO_GLOBAL = frozenset({"dashboard", "analytics"})
_USUARIO_CATALOGO_GLOBAL = {"rol": "super-admin", "id_usuario": 0}


def _normalizar_nombre_cargo(nombre: str | None) -> str:
    texto = unicodedata.normalize("NFD", nombre or "")
    texto = "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")
    return texto.strip().lower()


def _es_cargo_dueno(nombre: str | None) -> bool:
    return _normalizar_nombre_cargo(nombre) == "dueno"


def _tipo_cargo(nombre: str | None) -> str:
    nombre_norm = _normalizar_nombre_cargo(nombre)
    if nombre_norm in ("super admin", "super administrador"):
        return "super_admin"
    if nombre_norm == "dueno":
        return "dueno"
    if nombre_norm == "usuario":
        return "usuario"
    return "admin"


def _filtrar_permisos_por_cargo(db: Session, codigos: list[str], cargo: dict) -> list[str]:
    tipo = _tipo_cargo(cargo.get("nombre"))
    if tipo == "super_admin":
        return [
            codigo
            for codigo in _catalogo_modulos(db)
            if codigo not in MODULOS_EXCLUIDOS_ADMIN
        ]
    if tipo == "dueno":
        return [codigo for codigo in codigos if codigo in MODULOS_DUENO_GLOBAL]
    if tipo == "usuario":
        return []
    return [codigo for codigo in codigos if codigo not in MODULOS_EXCLUIDOS_ADMIN]


def _filtrar_permisos_globales_dueno(codigos: list[str], es_dueno: bool) -> list[str]:
    if not es_dueno:
        return codigos
    return [codigo for codigo in codigos if codigo in MODULOS_DUENO_GLOBAL]


def _datos_cuenta_afectados(cuenta: dict, cambios: dict) -> tuple[dict, dict]:
    anteriores: dict = {}
    nuevos: dict = {}
    for campo, valor in cambios.items():
        if campo not in {
            "nombre_completo",
            "email",
            "id_cargo",
            "activo",
            "permisos",
        }:
            continue
        anteriores[campo] = cuenta.get(campo)
        nuevos[campo] = valor
    return anteriores, nuevos


def _catalogo_modulos(db: Session) -> list[str]:
    return list(
        db.execute(
            text(
                """
                SELECT codigo
                FROM conversacion.modulo
                WHERE activo = TRUE
                ORDER BY codigo
                """
            )
        ).scalars().all()
    )


def _generar_password_temporal() -> str:
    alfabeto = string.ascii_letters + string.digits
    sufijo = "".join(secrets.choice(alfabeto) for _ in range(10))
    return f"RbGo-{sufijo}"


def _enviar_password_cuenta_admin(
    email: str,
    nombre_completo: str,
    username: str,
    password_temporal: str,
) -> None:
    enviar_correo(
        "cuenta_admin_creada",
        email,
        {
            "nombre_completo": nombre_completo,
            "username": username,
            "password_temporal": password_temporal,
        },
    )


def _mapear_cuenta_list_item(fila: dict) -> CuentaAdminListItem:
    nombre_completo = fila["nombre_completo"] or fila["username"]
    return CuentaAdminListItem(
        id_usuario=fila["id_usuario"],
        nombre_completo=nombre_completo,
        email=fila["email"],
        username=fila["username"],
        id_cargo=fila.get("id_cargo"),
        cargo_nombre=fila.get("cargo_nombre"),
        activo=fila["activo"],
        ultimo_acceso_en=fila.get("ultimo_acceso_en"),
        iniciales=_iniciales(fila.get("nombre_completo"), fila["username"]),
    )


def _iniciales(nombre: str | None, username: str) -> str:
    if nombre:
        partes = [parte for parte in re.split(r"\s+", nombre.strip()) if parte]
        if len(partes) >= 2:
            return f"{partes[0][0]}{partes[1][0]}".upper()
        if partes:
            return partes[0][:2].upper()
    return username[:2].upper()


def _username_desde_email(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    local = re.sub(r"[^a-z0-9._-]", "", local)
    return local[:80] or "admin"


def _username_normalizado(username: str) -> str:
    normalizado = username.strip().lower()
    normalizado = re.sub(r"[^a-z0-9._-]", "", normalizado)
    return normalizado[:80]


def _existe_username(db: Session, username: str) -> bool:
    return bool(
        db.execute(
            text(
                """
                SELECT 1
                FROM conversacion.usuario
                WHERE username = :username
                """
            ),
            {"username": username},
        ).first()
    )


def _generar_username_disponible(db: Session, base: str) -> str:
    base_normalizada = _username_normalizado(base) or "admin"
    for indice in range(0, 100):
        sufijo = "" if indice == 0 else f"-{indice}"
        username = f"{base_normalizada[:80 - len(sufijo)]}{sufijo}"
        if not _existe_username(db, username):
            return username

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="No se pudo generar un username disponible para esta cuenta",
    )


def _obtener_usuario_por_email(db: Session, email: str) -> dict | None:
    fila = db.execute(
        text(
            """
            SELECT u.id_usuario, u.username, u.email, u.id_cargo, c.nombre AS cargo_nombre
            FROM conversacion.usuario u
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE u.email = :email
            """
        ),
        {"email": email},
    ).mappings().first()
    return dict(fila) if fila else None


def _validar_cargo(db: Session, id_cargo: int) -> dict:
    cargo = db.execute(
        text(
            """
            SELECT id_cargo, nombre, activo
            FROM conversacion.cargo
            WHERE id_cargo = :id_cargo
            """
        ),
        {"id_cargo": id_cargo},
    ).mappings().first()
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo no encontrado",
        )
    return dict(cargo)


def _mapear_codigos_a_ids(db: Session, codigos: list[str]) -> list[int]:
    if not codigos:
        return []

    filas = db.execute(
        text(
            """
            SELECT id_modulo, codigo
            FROM conversacion.modulo
            WHERE codigo = ANY(:codigos) AND activo = TRUE
            """
        ),
        {"codigos": codigos},
    ).mappings().all()

    encontrados = {fila["codigo"] for fila in filas}
    faltantes = sorted(set(codigos) - encontrados)
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Permisos invalidos: {', '.join(faltantes)}",
        )

    return [int(fila["id_modulo"]) for fila in filas]


def _permisos_cargo(db: Session, id_cargo: int) -> list[str]:
    return list(
        db.execute(
            text(
                """
                SELECT DISTINCT m.codigo
                FROM conversacion.cargo_permiso cp
                JOIN conversacion.modulo m ON m.id_modulo = cp.id_modulo
                WHERE cp.id_cargo = :id_cargo AND m.activo = TRUE
                ORDER BY m.codigo
                """
            ),
            {"id_cargo": id_cargo},
        ).scalars().all()
    )


def _permisos_usuario(db: Session, id_usuario: int) -> list[str]:
    return list(
        db.execute(
            text(
                """
                SELECT DISTINCT m.codigo
                FROM conversacion.usuario_permiso up
                JOIN conversacion.modulo m ON m.id_modulo = up.id_modulo
                WHERE up.id_usuario = :id_usuario
                  AND up.id_sitio IS NULL
                  AND m.activo = TRUE
                ORDER BY m.codigo
                """
            ),
            {"id_usuario": id_usuario},
        ).scalars().all()
    )


def _reemplazar_usuario_permiso(db: Session, id_usuario: int, codigos: list[str]) -> None:
    db.execute(
        text(
            """
            DELETE FROM conversacion.usuario_permiso
            WHERE id_usuario = :id_usuario
              AND id_sitio IS NULL
            """
        ),
        {"id_usuario": id_usuario},
    )
    for id_modulo in _mapear_codigos_a_ids(db, codigos):
        for accion in ACCIONES_PERMISO:
            db.execute(
                text(
                    """
                    INSERT INTO conversacion.usuario_permiso
                        (id_usuario, id_modulo, accion, id_sitio)
                    VALUES (
                        :id_usuario,
                        :id_modulo,
                        CAST(:accion AS conversacion.accion_t),
                        NULL
                    )
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"id_usuario": id_usuario, "id_modulo": id_modulo, "accion": accion},
            )


def _reemplazar_cargo_permiso(db: Session, id_cargo: int, codigos: list[str]) -> None:
    db.execute(
        text("DELETE FROM conversacion.cargo_permiso WHERE id_cargo = :id_cargo"),
        {"id_cargo": id_cargo},
    )
    for id_modulo in _mapear_codigos_a_ids(db, codigos):
        for accion in ACCIONES_PERMISO:
            db.execute(
                text(
                    """
                    INSERT INTO conversacion.cargo_permiso (id_cargo, id_modulo, accion)
                    VALUES (:id_cargo, :id_modulo, CAST(:accion AS conversacion.accion_t))
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"id_cargo": id_cargo, "id_modulo": id_modulo, "accion": accion},
            )


def _obtener_cuenta_admin(db: Session, id_usuario: int) -> dict:
    cuenta = db.execute(
        text(
            """
            SELECT u.id_usuario, u.nombre_completo, u.email, u.username,
                   u.id_cargo, c.nombre AS cargo_nombre, u.activo,
                   u.ultimo_acceso_en,
                   CASE
                       WHEN LOWER(COALESCE(c.nombre, '')) IN ('super admin', 'super administrador') THEN 'super-admin'
                       WHEN LOWER(COALESCE(c.nombre, '')) = 'usuario' THEN 'usuario'
                       ELSE 'admin'
                   END AS rol
            FROM conversacion.usuario u
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE u.id_usuario = :id_usuario
            """
        ),
        {"id_usuario": id_usuario},
    ).mappings().first()

    if not cuenta or cuenta["rol"] not in ROLES_CUENTA_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta administrativa no encontrada",
        )
    return dict(cuenta)


def listar_permisos(db: Session) -> list[PermisoResponse]:
    filas = db.execute(
        text(
            """
            SELECT id_modulo AS id_permiso, codigo, nombre, activo
            FROM conversacion.modulo
            WHERE activo = TRUE
            ORDER BY id_modulo
            """
        )
    ).mappings().all()
    return [PermisoResponse(**dict(fila)) for fila in filas]


def listar_cargos(db: Session, incluir_inactivos: bool = False) -> list[CargoResponse]:
    consulta = """
        SELECT id_cargo, nombre, activo
        FROM conversacion.cargo
        WHERE LOWER(nombre) <> 'usuario'
    """
    if not incluir_inactivos:
        consulta += " AND activo = TRUE"
    consulta += " ORDER BY nombre"

    filas = db.execute(text(consulta)).mappings().all()
    return [
        CargoResponse(
            **dict(fila),
            permisos=_permisos_cargo(db, int(fila["id_cargo"])),
        )
        for fila in filas
    ]


def obtener_cargo(db: Session, id_cargo: int) -> CargoResponse:
    cargo = _validar_cargo(db, id_cargo)
    return CargoResponse(
        **cargo,
        permisos=_permisos_cargo(db, id_cargo),
    )


def crear_cargo(db: Session, datos: CargoCreate, actor: ActorTrazabilidad) -> CargoResponse:
    existe = db.execute(
        text("SELECT 1 FROM conversacion.cargo WHERE nombre = :nombre"),
        {"nombre": datos.nombre},
    ).first()
    if existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un cargo con ese nombre",
        )

    fila = db.execute(
        text(
            """
            INSERT INTO conversacion.cargo (nombre, activo)
            VALUES (:nombre, :activo)
            RETURNING id_cargo, nombre, activo
            """
        ),
        {"nombre": datos.nombre, "activo": datos.activo},
    ).mappings().one()

    id_cargo = int(fila["id_cargo"])
    _reemplazar_cargo_permiso(db, id_cargo, datos.permisos)

    registrar_evento_actor(
        db,
        actor,
        accion="INSERT",
        esquema_modificado="conversacion",
        tabla_modificada="cargo",
        entidad_modificada=id_cargo,
        datos_nuevos={"nombre": datos.nombre, "permisos": datos.permisos},
    )
    db.commit()
    return obtener_cargo(db, id_cargo)


def actualizar_cargo(
    db: Session,
    id_cargo: int,
    datos: CargoUpdate,
    actor: ActorTrazabilidad,
) -> CargoResponse:
    cargo = _validar_cargo(db, id_cargo)

    if datos.nombre and datos.nombre != cargo["nombre"]:
        existe = db.execute(
            text(
                """
                SELECT 1
                FROM conversacion.cargo
                WHERE nombre = :nombre AND id_cargo <> :id_cargo
                """
            ),
            {"nombre": datos.nombre, "id_cargo": id_cargo},
        ).first()
        if existe:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un cargo con ese nombre",
            )

    db.execute(
        text(
            """
            UPDATE conversacion.cargo
            SET nombre = COALESCE(:nombre, nombre),
                activo = COALESCE(:activo, activo)
            WHERE id_cargo = :id_cargo
            """
        ),
        {
            "id_cargo": id_cargo,
            "nombre": datos.nombre,
            "activo": datos.activo,
        },
    )

    if datos.permisos is not None:
        _reemplazar_cargo_permiso(db, id_cargo, datos.permisos)

    registrar_evento_actor(
        db,
        actor,
        accion="UPDATE",
        esquema_modificado="conversacion",
        tabla_modificada="cargo",
        entidad_modificada=id_cargo,
        datos_anteriores=cargo,
        datos_nuevos=datos.model_dump(exclude_unset=True),
        referencia=datos.nombre or cargo["nombre"],
    )
    db.commit()
    return obtener_cargo(db, id_cargo)


def eliminar_cargo(db: Session, id_cargo: int, actor: ActorTrazabilidad) -> CargoResponse:
    cargo = obtener_cargo(db, id_cargo)
    en_uso = db.execute(
        text(
            """
            SELECT 1
            FROM conversacion.usuario
            WHERE id_cargo = :id_cargo
            LIMIT 1
            """
        ),
        {"id_cargo": id_cargo},
    ).first()
    if en_uso:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar un cargo asignado a cuentas",
        )

    db.execute(
        text("DELETE FROM conversacion.cargo WHERE id_cargo = :id_cargo"),
        {"id_cargo": id_cargo},
    )
    registrar_evento_actor(
        db,
        actor,
        accion="DELETE",
        esquema_modificado="conversacion",
        tabla_modificada="cargo",
        entidad_modificada=id_cargo,
        datos_anteriores=cargo.model_dump(),
        referencia=cargo.nombre,
    )
    db.commit()
    return cargo


def listar_cuentas_admin(
    db: Session,
    *,
    q: str | None = None,
    id_cargo: int | None = None,
    activo: bool | None = None,
    page: int = 1,
    page_size: int = 10,
) -> CuentaAdminListResponse:
    filtros = ["LOWER(COALESCE(c.nombre, '')) <> 'usuario'"]
    parametros: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if q:
        filtros.append(
            "(u.nombre_completo ILIKE :q OR u.email ILIKE :q OR u.username ILIKE :q)"
        )
        parametros["q"] = f"%{q.strip()}%"

    if id_cargo is not None:
        filtros.append("u.id_cargo = :id_cargo")
        parametros["id_cargo"] = id_cargo

    if activo is not None:
        filtros.append("u.activo = :activo")
        parametros["activo"] = activo

    where_sql = " AND ".join(filtros)
    total = db.execute(
        text(
            f"""
            SELECT COUNT(*)
            FROM conversacion.usuario u
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE {where_sql}
            """
        ),
        parametros,
    ).scalar()

    filas = db.execute(
        text(
            f"""
            SELECT u.id_usuario, u.nombre_completo, u.email, u.username,
                   u.id_cargo, c.nombre AS cargo_nombre, u.activo, u.ultimo_acceso_en
            FROM conversacion.usuario u
            LEFT JOIN conversacion.cargo c ON c.id_cargo = u.id_cargo
            WHERE {where_sql}
            ORDER BY u.nombre_completo NULLS LAST, u.username
            LIMIT :limit OFFSET :offset
            """
        ),
        parametros,
    ).mappings().all()

    items = [_mapear_cuenta_list_item(dict(fila)) for fila in filas]

    return CuentaAdminListResponse(
        items=items,
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


def obtener_cuenta_admin(db: Session, id_usuario: int) -> CuentaAdminDetalleResponse:
    cuenta = _obtener_cuenta_admin(db, id_usuario)
    base = _mapear_cuenta_list_item(cuenta)
    return CuentaAdminDetalleResponse(
        **base.model_dump(),
        permisos=_permisos_usuario(db, id_usuario),
    )


def crear_cuenta_admin(
    db: Session,
    datos: CuentaAdminCreate,
    actor: ActorTrazabilidad,
) -> CuentaAdminDetalleResponse:
    cargo = _validar_cargo(db, datos.id_cargo)
    email = str(datos.email).strip()

    usuario_email = _obtener_usuario_por_email(db, email)
    if usuario_email:
        if _tipo_cargo(usuario_email.get("cargo_nombre")) == "usuario":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ese email ya esta registrado como usuario",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya esta registrado",
        )

    if datos.username:
        username = _username_normalizado(datos.username)
        if len(username) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El username debe tener al menos 3 caracteres validos",
            )
        if _existe_username(db, username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El username ya esta registrado",
            )
    else:
        username = _generar_username_disponible(db, _username_desde_email(email))

    password_temporal = _generar_password_temporal()
    fila = db.execute(
        text(
            """
            INSERT INTO conversacion.usuario (
                id_cargo, nombre_completo, username, password, email, activo
            )
            VALUES (
                :id_cargo, :nombre_completo, :username, :password, :email, :activo
            )
            RETURNING id_usuario
            """
        ),
        {
            "id_cargo": datos.id_cargo,
            "nombre_completo": datos.nombre_completo,
            "username": username,
            "password": encriptar_texto(password_temporal),
            "email": email,
            "activo": datos.activo,
        },
    ).mappings().one()

    id_usuario = int(fila["id_usuario"])
    permisos = _filtrar_permisos_por_cargo(db, datos.permisos, cargo)
    _reemplazar_usuario_permiso(db, id_usuario, permisos)

    registrar_evento_actor(
        db,
        actor,
        accion="creacion_cuenta_admin",
        esquema_modificado="conversacion",
        tabla_modificada="usuario",
        entidad_modificada=id_usuario,
        datos_nuevos={
            "nombre_completo": datos.nombre_completo,
            "email": email,
            "id_cargo": datos.id_cargo,
            "permisos": datos.permisos,
        },
    )

    try:
        _enviar_password_cuenta_admin(
            email,
            datos.nombre_completo,
            username,
            password_temporal,
        )
    except EnviarCorreoError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    db.commit()
    return obtener_cuenta_admin(db, id_usuario)


def actualizar_cuenta_admin(
    db: Session,
    id_usuario: int,
    datos: CuentaAdminUpdate,
    actor: ActorTrazabilidad,
) -> CuentaAdminDetalleResponse:
    cuenta = _obtener_cuenta_admin(db, id_usuario)

    if datos.id_cargo is not None:
        _validar_cargo(db, datos.id_cargo)

    if datos.email:
        existe = db.execute(
            text(
                """
                SELECT 1
                FROM conversacion.usuario
                WHERE email = :email AND id_usuario <> :id_usuario
                """
            ),
            {"email": str(datos.email), "id_usuario": id_usuario},
        ).first()
        if existe:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El email ya esta registrado",
            )

    db.execute(
        text(
            """
            UPDATE conversacion.usuario
            SET nombre_completo = COALESCE(:nombre_completo, nombre_completo),
                email = COALESCE(:email, email),
                id_cargo = COALESCE(:id_cargo, id_cargo),
                activo = COALESCE(:activo, activo),
                token = CASE WHEN :activo IS FALSE THEN NULL ELSE token END
            WHERE id_usuario = :id_usuario
            """
        ),
        {
            "id_usuario": id_usuario,
            "nombre_completo": datos.nombre_completo,
            "email": str(datos.email) if datos.email else None,
            "id_cargo": datos.id_cargo,
            "activo": datos.activo,
        },
    )

    if datos.permisos is not None:
        id_cargo_final = datos.id_cargo if datos.id_cargo is not None else cuenta["id_cargo"]
        cargo = _validar_cargo(db, int(id_cargo_final))
        permisos = _filtrar_permisos_por_cargo(db, datos.permisos, cargo)
        _reemplazar_usuario_permiso(db, id_usuario, permisos)

    cambios = datos.model_dump(exclude_unset=True)
    datos_anteriores, datos_nuevos = _datos_cuenta_afectados(cuenta, cambios)

    registrar_evento_actor(
        db,
        actor,
        accion="actualizacion_cuenta_admin",
        esquema_modificado="conversacion",
        tabla_modificada="usuario",
        entidad_modificada=id_usuario,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        referencia=datos_nuevos.get("nombre_completo") or cuenta.get("nombre_completo") or cuenta.get("username"),
    )
    db.commit()
    return obtener_cuenta_admin(db, id_usuario)


def cambiar_estado_cuenta_admin(
    db: Session,
    id_usuario: int,
    datos: CuentaAdminEstadoUpdate,
    actor: ActorTrazabilidad,
) -> CuentaAdminDetalleResponse:
    if actor.id_usuario is not None and id_usuario == actor.id_usuario and not datos.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes inactivar tu propia cuenta",
        )

    cuenta = _obtener_cuenta_admin(db, id_usuario)
    db.execute(
        text(
            """
            UPDATE conversacion.usuario
            SET activo = :activo,
                token = CASE WHEN :activo = FALSE THEN NULL ELSE token END
            WHERE id_usuario = :id_usuario
            """
        ),
        {"id_usuario": id_usuario, "activo": datos.activo},
    )

    registrar_evento_actor(
        db,
        actor,
        accion="inactivacion_cuenta_admin" if not datos.activo else "actualizacion_cuenta_admin",
        esquema_modificado="conversacion",
        tabla_modificada="usuario",
        entidad_modificada=id_usuario,
        datos_anteriores={"activo": cuenta["activo"]},
        datos_nuevos={"activo": datos.activo},
        referencia=cuenta.get("nombre_completo") or cuenta.get("username"),
    )
    db.commit()
    return obtener_cuenta_admin(db, id_usuario)


def eliminar_cuenta_admin(
    db: Session,
    id_usuario: int,
    actor: ActorTrazabilidad,
) -> dict[str, str]:
    if actor.id_usuario is not None and id_usuario == actor.id_usuario:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propia cuenta",
        )

    cuenta = obtener_cuenta_admin(db, id_usuario)
    db.execute(
        text("DELETE FROM conversacion.usuario WHERE id_usuario = :id_usuario"),
        {"id_usuario": id_usuario},
    )

    registrar_evento_actor(
        db,
        actor,
        accion="eliminacion_cuenta_admin",
        esquema_modificado="conversacion",
        tabla_modificada="usuario",
        entidad_modificada=id_usuario,
        datos_anteriores=cuenta.model_dump(),
        referencia=cuenta.nombre_completo or cuenta.username,
    )
    db.commit()
    return {"mensaje": "Cuenta administrativa eliminada correctamente"}


def listar_sitios_catalogo_cuenta(
    db: Session,
    q: str | None,
    estado: EstadoAtractivo,
    page: int,
    page_size: int,
) -> SitiosListResponse:
    return listar_sitios(
        db,
        q,
        None,
        None,
        estado,
        "all",
        "all",
        page,
        page_size,
        _USUARIO_CATALOGO_GLOBAL,
    )


def listar_sitios_cuenta(db: Session, id_usuario: int) -> list[int]:
    _obtener_cuenta_admin(db, id_usuario)
    return [
        int(sitio)
        for sitio in db.execute(
            text(
                """
                SELECT DISTINCT id_sitio
                FROM conversacion.usuario_permiso
                WHERE id_usuario = :id_usuario
                  AND id_sitio IS NOT NULL
                ORDER BY id_sitio
                """
            ),
            {"id_usuario": id_usuario},
        ).scalars().all()
    ]


def _mapear_sitio_asignado(row: dict) -> SitioAsignadoItem:
    return SitioAsignadoItem(
        id_sitio=int(row["id_sitio"]),
        nombre=row["nombre"],
        categoria=row["categoria"],
        subcategoria=row.get("subcategoria"),
        activo=bool(row["activo"]),
    )


def obtener_sitios_cuenta_detalle(db: Session, id_usuario: int) -> tuple[list[int], list[SitioAsignadoItem]]:
    sitios = listar_sitios_cuenta(db, id_usuario)
    if not sitios:
        return [], []

    rows = db.execute(
        text(
            f"""
            {_sitio_select_sql()}
            WHERE s.id_sitio = ANY(:sitios)
            ORDER BY s.nombre ASC
            """
        ),
        {"sitios": sitios},
    ).mappings().all()
    items = [_mapear_sitio_asignado(dict(row)) for row in rows]
    return sitios, items


def _validar_sitios_para_asignacion(db: Session, sitios: list[int]) -> None:
    if not sitios:
        return

    filas = db.execute(
        text(
            """
            SELECT id_sitio, activo
            FROM turismo.sitio
            WHERE id_sitio = ANY(:sitios)
            """
        ),
        {"sitios": sitios},
    ).mappings().all()
    encontrados = {int(fila["id_sitio"]): bool(fila["activo"]) for fila in filas}
    faltantes = sorted(set(sitios) - encontrados.keys())
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sitios no encontrados: {', '.join(str(s) for s in faltantes)}",
        )

    inactivos = sorted(sitio_id for sitio_id, activo in encontrados.items() if not activo)
    if inactivos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sitios inactivos no asignables: {', '.join(str(s) for s in inactivos)}",
        )


def _validar_sitios_existen(db: Session, sitios: list[int]) -> None:
    _validar_sitios_para_asignacion(db, sitios)


def actualizar_sitios_cuenta(
    db: Session,
    id_usuario: int,
    sitios: list[int],
    actor: ActorTrazabilidad,
) -> list[int]:
    cuenta = _obtener_cuenta_admin(db, id_usuario)
    sitios_anteriores = listar_sitios_cuenta(db, id_usuario)
    if _es_cargo_dueno(cuenta.get("cargo_nombre")) and not sitios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una cuenta Dueño debe tener al menos un sitio asignado",
        )
    _validar_sitios_para_asignacion(db, sitios)
    reemplazar_sitios_usuario(db, id_usuario, sitios)
    for id_sitio in sitios:
        asegurar_repositorio_sitio_chatbot(db, int(id_sitio))
    registrar_evento_actor(
        db,
        actor,
        accion="actualizacion_sitios_cuenta_admin",
        esquema_modificado="conversacion",
        tabla_modificada="usuario_permiso",
        entidad_modificada=id_usuario,
        datos_anteriores={"sitios": sitios_anteriores},
        datos_nuevos={"sitios": sitios},
        referencia=cuenta.get("nombre_completo") or cuenta.get("username"),
    )
    db.commit()
    return listar_sitios_cuenta(db, id_usuario)
