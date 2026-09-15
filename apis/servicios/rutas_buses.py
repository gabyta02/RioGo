import json
import hashlib

from sqlalchemy import text
from sqlalchemy.orm import Session

from modelos.rutas_buses import RutaBus


PALETA_COLORES = [
    "#E53935",
    "#1E88E5",
    "#43A047",
    "#FB8C00",
    "#8E24AA",
    "#00ACC1",
    "#FDD835",
    "#6D4C41",
    "#3949AB",
    "#C2185B",
    "#7CB342",
    "#546E7A",
    "#F4511E",
    "#5E35B1",
    "#00897B",
    "#D81B60",
    "#039BE5",
    "#AFB42B",
]


def _generar_hash_djb2(cadena: str) -> int:
    hash_val = 5381
    for char in cadena:
        hash_val = ((hash_val << 5) + hash_val) + ord(char)
    return hash_val


def calcular_color(linea_bus: str | None, nombre: str | None) -> str:
    texto = linea_bus if linea_bus else nombre
    if not texto:
        return PALETA_COLORES[0]
    texto_normalizado = texto.strip()
    if not texto_normalizado:
        return PALETA_COLORES[0]
    hash_val = _generar_hash_djb2(texto_normalizado)
    indice = hash_val % len(PALETA_COLORES)
    return PALETA_COLORES[indice]


def _transformar_ruta(row) -> dict:
    fila = dict(row._mapping)
    geometry_json = fila.get("geometry")
    if geometry_json:
        fila["geometry"] = json.loads(geometry_json)
    else:
        fila["geometry"] = None
    linea = fila.get("linea_bus")
    nombre = fila.get("nombre")
    fila["color"] = calcular_color(linea, nombre)
    return fila


def listar_rutas_buses(
    db: Session,
    estado: str | None = None,
    linea_bus: str | None = None,
) -> list[dict]:
    params = {}
    condiciones = []

    if estado:
        condiciones.append("estado ILIKE :estado")
        params["estado"] = f"%{estado}%"
    if linea_bus:
        condiciones.append("linea_bus ILIKE :linea_bus")
        params["linea_bus"] = f"%{linea_bus}%"

    where_clause = " AND ".join(condiciones) if condiciones else "1=1"

    query = text(f"""
        SELECT
            id_ruta,
            nombre,
            estado,
            distancia_recorrido,
            linea_bus,
            ST_AsGeoJSON(geom) AS geometry
        FROM gis.ruta_bus
        WHERE {where_clause}
        ORDER BY id_ruta
    """)

    rows = db.execute(query, params).fetchall()
    return [_transformar_ruta(row) for row in rows]


def obtener_ruta_bus_por_id(db: Session, id_ruta: int) -> dict | None:
    query = text("""
        SELECT
            id_ruta,
            nombre,
            estado,
            distancia_recorrido,
            linea_bus,
            ST_AsGeoJSON(geom) AS geometry
        FROM gis.ruta_bus
        WHERE id_ruta = :id_ruta
    """)

    row = db.execute(query, {"id_ruta": id_ruta}).first()

    if not row:
        return None

    return _transformar_ruta(row)


def obtener_leyenda_rutas_buses(db: Session) -> list[dict]:
    query = text("""
        SELECT
            linea_bus,
            nombre,
            COUNT(*) AS cantidad_rutas
        FROM gis.ruta_bus
        WHERE linea_bus IS NOT NULL AND linea_bus != ''
        GROUP BY linea_bus, nombre
        ORDER BY linea_bus
    """)

    rows = db.execute(query).fetchall()

    resultado = []
    for row in rows:
        fila = dict(row._mapping)
        linea = fila.get("linea_bus") or ""
        nombre = fila.get("nombre")
        color = calcular_color(linea, nombre)
        resultado.append({
            "linea_bus": linea,
            "color": color,
            "cantidad_rutas": fila["cantidad_rutas"],
        })

    return resultado