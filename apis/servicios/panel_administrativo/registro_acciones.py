import json
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.trazabilidad import preparar_datos_auditoria
from esquemas.panel_administrativo.registro_acciones import (
    FiltroAccion,
    ModuloRegistro,
    ResultadoInicioSesion,
    RegistroAccionDetalleResponse,
    RegistroAccionItem,
    RegistroAccionesCatalogosResponse,
    RegistroAccionesListResponse,
    TipoAccionVisual,
    VistaRegistro,
)

MODULO_POR_TABLA: dict[str, str] = {
    "sitio": "attractions",
    "categoria": "categories",
    "subcategoria": "categories",
    "rutas_turistica": "routes",
    "noticia": "noticias",
    "sitio_documento": "chatbot_content",
    "usuario": "admin_accounts",
    "usuario_permiso": "admin_accounts",
    "cargo": "admin_accounts",
}

MODULO_LABELS: dict[str, str] = {
    "attractions": "Atractivos turísticos",
    "categories": "Categorías",
    "routes": "Rutas",
    "noticias": "Noticias",
    "chatbot_content": "Contenido chatbots",
    "admin_accounts": "Cuentas administrativas",
    "sistema": "Sistema",
}

ACCION_LABELS: dict[str, tuple[TipoAccionVisual, str]] = {
    "INSERT": ("creacion", "Creación"),
    "DELETE": ("eliminacion", "Eliminación"),
    "creacion_cuenta": ("creacion", "Creación cuenta"),
    "actualizacion_cuenta": ("actualizacion", "Actualización cuenta"),
    "inactivacion_cuenta": ("desactivacion", "Desactivación"),
    "eliminacion_cuenta": ("eliminacion", "Eliminación"),
    "cambio_username": ("actualizacion", "Actualización"),
    "cambio_email": ("actualizacion", "Actualización"),
    "cambio_password": ("actualizacion", "Actualización"),
    "cambio_2fa": ("actualizacion", "Actualización 2FA"),
    "cambio_foto_perfil": ("actualizacion", "Foto de perfil"),
    "registro_usuario": ("creacion", "Creación"),
    "login": ("sesion", "Inicio de sesión"),
}

REFERENCIA_SQL: dict[tuple[str, str], tuple[str, str]] = {
    ("turismo", "sitio"): ("turismo.sitio", "nombre"),
    ("turismo", "categoria"): ("turismo.categoria", "nombre"),
    ("turismo", "subcategoria"): ("turismo.subcategoria", "nombre"),
    ("gis", "rutas_turistica"): ("gis.rutas_turistica", "titulo"),
    ("turismo", "noticia"): ("turismo.noticia", "titulo"),
    ("turismo", "sitio_documento"): ("turismo.sitio_documento", "COALESCE(titulo, repositorio_nombre)"),
    ("conversacion", "usuario"): ("conversacion.usuario", "COALESCE(nombre_completo, username)"),
    ("conversacion", "cargo"): ("conversacion.cargo", "nombre"),
}

ID_COLUMNAS: dict[str, str] = {
    "sitio": "id_sitio",
    "categoria": "id_categoria",
    "subcategoria": "id_subcategoria",
    "rutas_turistica": "id_ruta",
    "noticia": "id_noticia",
    "sitio_documento": "id_documento",
    "usuario": "id_usuario",
    "cargo": "id_cargo",
}


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _parse_json(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _iniciales(nombre: str | None, username: str) -> str:
    fuente = (nombre or username or "??").strip()
    partes = [part for part in fuente.replace(".", " ").split() if part]
    if len(partes) >= 2:
        return f"{partes[0][0]}{partes[1][0]}".upper()
    return fuente[:2].upper()


def _modulo_desde_tabla(tabla: str, accion: str) -> str:
    if accion in {
        "login",
        "registro_usuario",
        "cambio_username",
        "cambio_email",
        "cambio_password",
        "cambio_2fa",
        "cambio_foto_perfil",
        "eliminacion_cuenta",
    }:
        return "sistema"
    return MODULO_POR_TABLA.get(tabla, "sistema")


def _clasificar_update(datos_nuevos: dict[str, Any] | None, datos_anteriores: dict[str, Any] | None) -> tuple[TipoAccionVisual, str]:
    nuevos = datos_nuevos or {}
    anteriores = datos_anteriores or {}
    if nuevos.get("activo") is False and anteriores.get("activo") is not False:
        return "desactivacion", "Desactivación"
    if nuevos.get("activa") is False and anteriores.get("activa") is not False:
        return "desactivacion", "Desactivación"
    if nuevos.get("activo") is True and anteriores.get("activo") is False:
        return "actualizacion", "Activación"
    if nuevos.get("activa") is True and anteriores.get("activa") is False:
        return "actualizacion", "Activación"
    if nuevos.get("geometria"):
        return "edicion", "Edición"
    if len(nuevos) == 1 and ("activo" in nuevos or "activa" in nuevos):
        return "actualizacion", "Actualización"
    return "edicion", "Edición"


def _clasificar_accion(accion: str, datos_nuevos: dict[str, Any] | None, datos_anteriores: dict[str, Any] | None) -> tuple[TipoAccionVisual, str]:
    if accion in ACCION_LABELS:
        return ACCION_LABELS[accion]
    if accion == "UPDATE":
        return _clasificar_update(datos_nuevos, datos_anteriores)
    return "otro", accion.replace("_", " ").title()


def _formatear_direccion(ip: str | None) -> str:
    if not ip or ip == "0.0.0.0":
        return "—"
    return str(ip)


def _datos_detalle(row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    return preparar_datos_auditoria(
        row["accion"],
        _parse_json(row.get("datos_anteriores")),
        _parse_json(row.get("datos_nuevos")),
    )


def _referencia_desde_datos(tabla: str, *datos: dict[str, Any] | None) -> str | None:
    claves_por_tabla = {
        "sitio": ("nombre",),
        "categoria": ("nombre",),
        "subcategoria": ("nombre",),
        "rutas_turistica": ("titulo",),
        "noticia": ("titulo",),
        "sitio_documento": ("titulo", "repositorio_nombre", "nombre"),
        "usuario": ("nombre_completo", "username", "email"),
        "cargo": ("nombre",),
    }
    for item in datos:
        if not item:
            continue
        for clave in claves_por_tabla.get(tabla, ()):
            valor = item.get(clave)
            if valor:
                return str(valor)
    return None


def _referencia_fallback(db: Session, row: dict[str, Any], anterior: dict[str, Any] | None, nuevo: dict[str, Any] | None) -> str | None:
    referencia = row.get("referencia")
    if referencia:
        return str(referencia)

    tabla = row["tabla_modificada"]
    referencia_datos = _referencia_desde_datos(tabla, nuevo, anterior)
    if referencia_datos:
        return referencia_datos

    entidad = row.get("entidad_modificada")
    if entidad is None:
        return None
    sql_info = REFERENCIA_SQL.get((row["esquema_modificado"], tabla))
    id_columna = ID_COLUMNAS.get(tabla)
    if not sql_info or not id_columna:
        return None

    tabla_sql, expresion = sql_info
    return db.execute(
        text(f"SELECT {expresion} AS referencia FROM {tabla_sql} WHERE {id_columna}::TEXT = :id_registro"),
        {"id_registro": str(entidad)},
    ).scalar()


def _construir_item(row: dict[str, Any]) -> RegistroAccionItem:
    datos_nuevos = _parse_json(row.get("datos_nuevos"))
    datos_anteriores = _parse_json(row.get("datos_anteriores"))
    accion_tipo, accion_label = _clasificar_accion(row["accion"], datos_nuevos, datos_anteriores)
    modulo = _modulo_desde_tabla(row["tabla_modificada"], row["accion"])
    administrador = row.get("nombre_completo") or row["usuario"]

    return RegistroAccionItem(
        id_evento=int(row["id_evento"]),
        administrador=administrador,
        username=row["usuario"],
        iniciales=_iniciales(row.get("nombre_completo"), row["usuario"]),
        accion=row["accion"],
        accion_label=accion_label,
        accion_tipo=accion_tipo,
        modulo=modulo,
        modulo_label=MODULO_LABELS.get(modulo, "Sistema"),
        direccion=_formatear_direccion(row.get("direccion")),
        fecha_modificacion=row["fecha_modificacion"],
    )


def _filtros_acciones_sql(
    q: str | None,
    usuario: str | None,
    modulo: ModuloRegistro,
    fecha_inicio: date | None,
    fecha_fin: date | None,
) -> tuple[str, dict[str, Any]]:
    filtros: list[str] = []
    params: dict[str, Any] = {}

    if q:
        filtros.append(
            """
            (
                t.username ILIKE :q
                OR COALESCE(u.nombre_completo, '') ILIKE :q
                OR COALESCE(t.id_registro, '') ILIKE :q
                OR COALESCE(host(t.ip), '') ILIKE :q
                OR COALESCE(t.tabla_modificada, '') ILIKE :q
                OR COALESCE(t.referencia, '') ILIKE :q
                OR COALESCE(t.datos_nuevos::TEXT, '') ILIKE :q
                OR COALESCE(t.datos_anteriores::TEXT, '') ILIKE :q
            )
            """
        )
        params["q"] = f"%{q.strip()}%"

    if usuario:
        filtros.append("t.username = :usuario")
        params["usuario"] = usuario
    if fecha_inicio:
        filtros.append("t.creado_en >= :fecha_inicio")
        params["fecha_inicio"] = fecha_inicio
    if fecha_fin:
        filtros.append("t.creado_en < (:fecha_fin + INTERVAL '1 day')")
        params["fecha_fin"] = fecha_fin
    if modulo != "all":
        tablas = [tabla for tabla, codigo in MODULO_POR_TABLA.items() if codigo == modulo]
        if modulo == "sistema":
            filtros.append(
                """
                t.accion IN ('registro_usuario', 'cambio_username', 'cambio_email', 'cambio_password', 'cambio_2fa', 'cambio_foto_perfil', 'eliminacion_cuenta')
                """
            )
        elif tablas:
            filtros.append("t.tabla_modificada = ANY(:tablas_modulo)")
            params["tablas_modulo"] = tablas

    where_sql = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    return where_sql, params


def _sql_filtro_accion_visual(accion: FiltroAccion) -> str:
    if accion == "all":
        return ""
    if accion == "creacion":
        return " AND t.accion IN ('INSERT', 'creacion_cuenta', 'registro_usuario')"
    if accion == "eliminacion":
        return " AND t.accion IN ('DELETE', 'eliminacion_cuenta')"
    if accion == "sesion":
        return " AND FALSE"
    if accion == "desactivacion":
        return """
            AND (
                t.accion = 'inactivacion_cuenta'
                OR (
                    t.accion = 'UPDATE'
                    AND (
                        (t.datos_nuevos->>'activo')::boolean IS FALSE
                        OR (t.datos_nuevos->>'activa')::boolean IS FALSE
                    )
                )
            )
        """
    if accion == "actualizacion":
        return """
            AND (
                t.accion IN ('actualizacion_cuenta', 'cambio_username', 'cambio_email', 'cambio_password', 'cambio_2fa', 'cambio_foto_perfil')
                OR (
                    t.accion = 'UPDATE'
                    AND NOT (COALESCE(t.datos_nuevos, '{}'::jsonb) ? 'geometria')
                )
            )
        """
    if accion == "edicion":
        return """
            AND (
                t.accion = 'UPDATE'
                AND COALESCE(t.datos_nuevos, '{}'::jsonb) ? 'geometria'
            )
        """
    return ""


def _listar_acciones(
    db: Session,
    q: str | None,
    usuario: str | None,
    modulo: ModuloRegistro,
    accion: FiltroAccion,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    page: int,
    page_size: int,
) -> RegistroAccionesListResponse:
    where_sql, params = _filtros_acciones_sql(q, usuario, modulo, fecha_inicio, fecha_fin)
    accion_sql = _sql_filtro_accion_visual(accion)
    if accion_sql:
        where_sql = f"{where_sql} {accion_sql}" if where_sql else f"WHERE TRUE {accion_sql}"

    count_sql = f"""
        SELECT COUNT(*)
        FROM trazabilidad.accion t
        LEFT JOIN conversacion.usuario u ON u.id_usuario = t.id_usuario
        {where_sql}
    """
    total = int(db.execute(text(count_sql), params).scalar() or 0)
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    rows = db.execute(
        text(
            f"""
            SELECT
                t.id_evento,
                t.username AS usuario,
                u.nombre_completo,
                t.accion::TEXT AS accion,
                t.tabla_modificada,
                t.id_registro AS entidad_modificada,
                host(t.ip) AS direccion,
                t.datos_anteriores,
                t.datos_nuevos,
                t.creado_en AS fecha_modificacion
            FROM trazabilidad.accion t
            LEFT JOIN conversacion.usuario u ON u.id_usuario = t.id_usuario
            {where_sql}
            ORDER BY t.creado_en DESC, t.id_evento DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    return RegistroAccionesListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[_construir_item(dict(row)) for row in rows],
    )


def _filtros_inicios_sql(
    q: str | None,
    usuario: str | None,
    resultado: ResultadoInicioSesion,
    fecha_inicio: date | None,
    fecha_fin: date | None,
) -> tuple[str, dict[str, Any]]:
    filtros: list[str] = []
    params: dict[str, Any] = {}
    if q:
        filtros.append(
            """
            (
                s.username ILIKE :q
                OR COALESCE(u.nombre_completo, '') ILIKE :q
                OR COALESCE(host(s.ip), '') ILIKE :q
                OR COALESCE(s.user_agent, '') ILIKE :q
                OR COALESCE(s.detalle, '') ILIKE :q
            )
            """
        )
        params["q"] = f"%{q.strip()}%"
    if usuario:
        filtros.append("s.username = :usuario")
        params["usuario"] = usuario
    if resultado != "all":
        filtros.append("s.resultado = CAST(:resultado AS trazabilidad.resultado_t)")
        params["resultado"] = resultado
    if fecha_inicio:
        filtros.append("s.creado_en >= :fecha_inicio")
        params["fecha_inicio"] = fecha_inicio
    if fecha_fin:
        filtros.append("s.creado_en < (:fecha_fin + INTERVAL '1 day')")
        params["fecha_fin"] = fecha_fin
    where_sql = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    return where_sql, params


def _listar_inicios_sesion(
    db: Session,
    q: str | None,
    usuario: str | None,
    resultado: ResultadoInicioSesion,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    page: int,
    page_size: int,
) -> RegistroAccionesListResponse:
    where_sql, params = _filtros_inicios_sql(q, usuario, resultado, fecha_inicio, fecha_fin)
    total = int(
        db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM trazabilidad.inicio_sesion s
                LEFT JOIN conversacion.usuario u ON u.id_usuario = s.id_usuario
                {where_sql}
                """
            ),
            params,
        ).scalar()
        or 0
    )
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    rows = db.execute(
        text(
            f"""
            SELECT
                s.id_evento,
                s.username AS usuario,
                u.nombre_completo,
                'login' AS accion,
                'inicio_sesion' AS tabla_modificada,
                host(s.ip) AS direccion,
                NULL::JSONB AS datos_anteriores,
                jsonb_build_object('resultado', s.resultado::TEXT, 'detalle', s.detalle) AS datos_nuevos,
                s.creado_en AS fecha_modificacion
            FROM trazabilidad.inicio_sesion s
            LEFT JOIN conversacion.usuario u ON u.id_usuario = s.id_usuario
            {where_sql}
            ORDER BY s.creado_en DESC, s.id_evento DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    return RegistroAccionesListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[_construir_item(dict(row)) for row in rows],
    )


def listar_registro_acciones(
    db: Session,
    q: str | None,
    usuario: str | None,
    vista: VistaRegistro,
    modulo: ModuloRegistro,
    accion: FiltroAccion,
    resultado: ResultadoInicioSesion,
    fecha_inicio: date | None,
    fecha_fin: date | None,
    page: int,
    page_size: int,
) -> RegistroAccionesListResponse:
    if vista == "inicios_sesion":
        return _listar_inicios_sesion(db, q, usuario, resultado, fecha_inicio, fecha_fin, page, page_size)
    return _listar_acciones(db, q, usuario, modulo, accion, fecha_inicio, fecha_fin, page, page_size)


def _obtener_accion(db: Session, id_evento: int) -> RegistroAccionDetalleResponse:
    row = db.execute(
        text(
            """
            SELECT
                t.id_evento,
                t.username AS usuario,
                u.nombre_completo,
                t.accion::TEXT AS accion,
                t.esquema_modificado,
                t.tabla_modificada,
                t.id_registro AS entidad_modificada,
                t.referencia,
                host(t.ip) AS direccion,
                t.datos_anteriores,
                t.datos_nuevos,
                t.creado_en AS fecha_modificacion
            FROM trazabilidad.accion t
            LEFT JOIN conversacion.usuario u ON u.id_usuario = t.id_usuario
            WHERE t.id_evento = :id_evento
            """
        ),
        {"id_evento": id_evento},
    ).mappings().first()
    if not row:
        raise _not_found("El registro de accion no existe")

    row_dict = dict(row)
    datos_anteriores, datos_nuevos = _datos_detalle(row_dict)
    row_dict["datos_anteriores"] = datos_anteriores
    row_dict["datos_nuevos"] = datos_nuevos
    item = _construir_item(row_dict)
    return RegistroAccionDetalleResponse(
        **item.model_dump(),
        esquema_modificado=row["esquema_modificado"],
        tabla_modificada=row["tabla_modificada"],
        entidad_modificada=row.get("entidad_modificada"),
        referencia=_referencia_fallback(db, row_dict, datos_anteriores, datos_nuevos),
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
    )


def _obtener_inicio_sesion(db: Session, id_evento: int) -> RegistroAccionDetalleResponse:
    row = db.execute(
        text(
            """
            SELECT
                s.id_evento,
                s.username AS usuario,
                u.nombre_completo,
                host(s.ip) AS direccion,
                s.user_agent,
                s.resultado::TEXT AS resultado,
                s.detalle,
                s.creado_en AS fecha_modificacion
            FROM trazabilidad.inicio_sesion s
            LEFT JOIN conversacion.usuario u ON u.id_usuario = s.id_usuario
            WHERE s.id_evento = :id_evento
            """
        ),
        {"id_evento": id_evento},
    ).mappings().first()
    if not row:
        raise _not_found("El inicio de sesion no existe")

    row_dict = {
        "id_evento": row["id_evento"],
        "usuario": row["usuario"],
        "nombre_completo": row["nombre_completo"],
        "accion": "login",
        "tabla_modificada": "inicio_sesion",
        "direccion": row["direccion"],
        "datos_anteriores": None,
        "datos_nuevos": {"resultado": row["resultado"], "detalle": row["detalle"], "user_agent": row["user_agent"]},
        "fecha_modificacion": row["fecha_modificacion"],
    }
    item = _construir_item(row_dict)
    return RegistroAccionDetalleResponse(
        **item.model_dump(),
        esquema_modificado="trazabilidad",
        tabla_modificada="inicio_sesion",
        entidad_modificada=str(row["id_evento"]),
        referencia=row["resultado"],
        datos_anteriores=None,
        datos_nuevos=None,
        resultado=row["resultado"],
        detalle=row["detalle"],
        user_agent=row["user_agent"],
    )


def obtener_registro_accion(db: Session, id_evento: int, vista: VistaRegistro) -> RegistroAccionDetalleResponse:
    if vista == "inicios_sesion":
        return _obtener_inicio_sesion(db, id_evento)
    return _obtener_accion(db, id_evento)


def obtener_catalogos_registro_acciones(db: Session) -> RegistroAccionesCatalogosResponse:
    administradores = db.execute(
        text(
            """
            SELECT DISTINCT usuario
            FROM (
                SELECT username AS usuario
                FROM trazabilidad.accion
                UNION
                SELECT username AS usuario
                FROM trazabilidad.inicio_sesion
            ) administradores
            WHERE usuario IS NOT NULL AND usuario <> ''
            ORDER BY usuario ASC
            """
        )
    ).scalars().all()
    modulos = [
        {"value": key, "label": label}
        for key, label in MODULO_LABELS.items()
        if key != "sistema"
    ]
    modulos.append({"value": "sistema", "label": MODULO_LABELS["sistema"]})
    return RegistroAccionesCatalogosResponse(
        administradores=list(administradores),
        modulos=modulos,
    )
