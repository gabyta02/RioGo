"""
Script de carga de datos turísticos desde Excel a PostgreSQL (RiobambaGo).

Uso en producción (desde el host, con postgres-apis publicado en 127.0.0.1:5432):
    pip install pandas openpyxl psycopg2-binary
    python base_datos/initdb/cargar_datos.py

Los valores por defecto se leen de base_datos/.env (POSTGRES_*).
Si el host es postgres-apis y el script corre fuera de Docker, se usa 127.0.0.1.

Opciones:
    --excel        Ruta al .xlsx  (default: initdb/plantilla_recoleccion_sitios_turismo_v2.xlsx)
    --host         Host BD        (default: POSTGRES_HOST o 127.0.0.1)
    --port         Puerto BD      (default: POSTGRES_PORT o 5432)
    --db           Base de datos  (default: POSTGRES_DB o riobambago)
    --user         Usuario BD     (default: POSTGRES_USER)
    --password     Contraseña BD  (default: POSTGRES_PASSWORD)
    --env-file     Ruta al .env   (default: base_datos/.env)
    --dry-run      Valida el Excel sin ejecutar ningún INSERT en la base de datos.
    --skip-errors  Omite filas con error y continúa en lugar de abortar.
    --init-db      Ejecuta 01-extensions.sql si faltan tablas requeridas.
    --no-limpiar   No vacía turismo.* antes de insertar (por defecto se trunca).

Compatibilidad confirmada con 01-extensions.sql (schemas turismo/gis/chatbot):
    parroquia · plataforma · categoria · subcategoria · sitio
    direccion · contacto · horario · horario_detalle
    multimedia · rango_precio · tarifa_acceso

Notas de compatibilidad:
    - La hoja CONTACTOS conserva la columna tipo_contacto, pero el SQL actual
      define turismo.contacto(nombre, contenido). El script guarda tipo_contacto
      en la columna nombre.
    - La hoja ACTIVIDADES existe en la plantilla, pero 01-extensions.sql actual
      no define una tabla turismo.actividad; por eso se omite durante la carga.
    - Las tablas RAG actuales son turismo.sitio_documento, turismo.chunk_fuente
      y turismo.chunk. Ya no se usa turismo.sitio_documento_chunk.
"""

import argparse
import json
import logging
import re
import sys
import unicodedata
import warnings
from datetime import time
from pathlib import Path
from typing import Optional
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

import pandas as pd

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:  # Permite ejecutar --dry-run aunque psycopg2 no esté instalado.
    psycopg2 = None
    execute_values = None

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DATOS_DIR = SCRIPT_DIR.parent
DEFAULT_ENV_FILE = BASE_DATOS_DIR / ".env"
DEFAULT_EXCEL = SCRIPT_DIR / "plantilla_recoleccion_sitios_turismo_v2.xlsx"
DEFAULT_INIT_SQL = SCRIPT_DIR / "01-extensions.sql"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("carga_turismo")

warnings.filterwarnings(
    "ignore",
    message="Data Validation extension is not supported.*",
    category=UserWarning,
    module="openpyxl",
)

# ---------------------------------------------------------------------------
# Configuración de conexión (base_datos/.env)
# ---------------------------------------------------------------------------

def leer_env(env_path: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not env_path.exists():
        return valores
    for linea in env_path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip()
    return valores


def resolver_host(host: str) -> str:
    if host in {"postgres-apis", "localhost"} and not Path("/.dockerenv").exists():
        return "127.0.0.1"
    return host


def defaults_desde_env(env: dict[str, str]) -> dict:
    host = env.get("POSTGRES_HOST", "127.0.0.1")
    port = int(env.get("POSTGRES_PORT", "5432"))
    db = env.get("POSTGRES_DB", "riobambago")
    user = env.get("POSTGRES_USER", "riobambago")
    password = env.get("POSTGRES_PASSWORD", "")

    database_url = env.get("DATABASE_URL", "")
    if database_url:
        parsed = urlparse(database_url.replace("postgresql+psycopg2://", "postgresql://", 1))
        if parsed.hostname:
            host = parsed.hostname
        if parsed.port:
            port = parsed.port
        if parsed.path and parsed.path != "/":
            db = parsed.path.lstrip("/")
        if parsed.username:
            user = parsed.username
        if parsed.password:
            password = parsed.password

    return {
        "host": resolver_host(host),
        "port": port,
        "db": db,
        "user": user,
        "password": password,
    }


def voyage_config_desde_env(env: dict[str, str]) -> dict[str, str]:
    return {
        "api_key": env.get("VOYAGE_API_KEY", "").strip(),
        "model": env.get("MODELO_VOYAGE", "voyage-4-lite").strip() or "voyage-4-lite",
    }


# ---------------------------------------------------------------------------
# Constantes alineadas a los ENUMs del 01-extensions.sql
# ---------------------------------------------------------------------------

def normalizar_clave(valor) -> str:
    """Normaliza texto para comparar valores del Excel sin depender de tildes o mayúsculas."""
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"\s+", " ", texto)
    return texto


BOOL_MAP = {
    "si": True, "sí": True, "s": True, "true": True, "1": True, "x": True,
    "no": False, "n": False, "false": False, "0": False,
}

# turismo.tipo_sitio_t
TIPO_SITIO_MAP = {
    "servicio turistico": "servicio_turistico",
    "servicios turisticos": "servicio_turistico",
    "atractivo turistico": "atractivo_turistico",
    "atractivos turisticos": "atractivo_turistico",
    "operador turistico": "operadora_turistica",
    "operadora turistica": "operadora_turistica",
    "operacion e intermediacion": "operadora_turistica",
}

# turismo.contacto.nombre
# La plantilla mantiene la columna tipo_contacto; en el SQL actual se guarda en
# turismo.contacto.nombre. Estos alias normalizan valores frecuentes sin exigir
# un ENUM inexistente.
CONTACTO_NOMBRE_MAP = {
    "telefono": "telefono",
    "teléfono": "telefono",
    "celular": "telefono",
    "whatsapp": "whatsapp",
    "email": "email",
    "correo": "email",
    "correo electronico": "email",
    "correo electrónico": "email",
    "web": "web",
    "pagina web": "web",
    "página web": "web",
    "facebook": "facebook",
    "instagram": "instagram",
    "tiktok": "tiktok",
    "otro": "otro",
}

# turismo.etiqueta_precio_t
ETIQUETA_PRECIO_VALIDAS = {"economico", "medio", "alto", "desconocido"}
VOYAGE_EMBEDDINGS_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_BATCH_SIZE = 64


# ---------------------------------------------------------------------------
# Helpers de conversión
# ---------------------------------------------------------------------------

def to_bool(val, col: str, row_idx: int) -> Optional[bool]:
    if pd.isna(val):
        return None
    s = normalizar_clave(val)
    if s not in BOOL_MAP:
        log.warning("Fila %d – columna '%s': valor booleano desconocido '%s', se usará NULL", row_idx, col, val)
        return None
    return BOOL_MAP[s]


def to_str(val) -> Optional[str]:
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None


def to_str_limit(val, max_len: int, col: str, row_idx: int) -> Optional[str]:
    """Convierte a texto y recorta si supera el límite VARCHAR de la BD."""
    s = to_str(val)
    if s is None:
        return None
    if len(s) > max_len:
        log.warning(
            "Fila %d – columna '%s': texto de %d caracteres supera VARCHAR(%d); se recorta.",
            row_idx, col, len(s), max_len,
        )
        return s[:max_len]
    return s


def chunked(seq, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def to_int(val, col: str, row_idx: int) -> Optional[int]:
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        log.warning("Fila %d – columna '%s': no es entero ('%s'), se usará NULL", row_idx, col, val)
        return None


def to_float(val, col: str, row_idx: int) -> Optional[float]:
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        log.warning("Fila %d – columna '%s': no es número ('%s'), se usará NULL", row_idx, col, val)
        return None


def to_time(val, col: str, row_idx: int) -> Optional[str]:
    """
    Devuelve HH:MM:SS como string para psycopg2.

    Maneja los formatos más comunes que aparecen al leer horas desde Excel:
      - 14:00
      - 14:00:00
      - 1900-01-01 14:00:00
      - 1899-12-30 14:00:00
      - fracciones de día de Excel como 0.5833333333
    """
    if pd.isna(val):
        return None

    if isinstance(val, time):
        return val.strftime("%H:%M:%S")

    s = str(val).strip()
    if not s:
        return None

    # Algunos Excel guardan las horas como fecha ficticia + hora.
    # Ejemplo: "1900-01-01 00:00:00". En ese caso extraemos solo la parte HH:MM:SS.
    match = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?", s)
    if match:
        h = int(match.group(1))
        m = int(match.group(2))
        sec_raw = match.group(3)
        sec = int(float(sec_raw)) if sec_raw is not None else 0

        if 0 <= h <= 23 and 0 <= m <= 59 and 0 <= sec <= 59:
            return f"{h:02d}:{m:02d}:{sec:02d}"

        log.warning(
            "Fila %d – columna '%s': hora fuera de rango '%s', se usará NULL",
            row_idx, col, val,
        )
        return None

    # Si llega como fracción de día de Excel, por ejemplo 0.5 = 12:00:00.
    try:
        numero = float(s.replace(",", "."))
        if 0 <= numero < 1:
            total_segundos = int(round(numero * 24 * 60 * 60))
            if total_segundos >= 24 * 60 * 60:
                total_segundos = 24 * 60 * 60 - 1
            h = total_segundos // 3600
            m = (total_segundos % 3600) // 60
            sec = total_segundos % 60
            return f"{h:02d}:{m:02d}:{sec:02d}"
    except ValueError:
        pass

    log.warning("Fila %d – columna '%s': hora inválida '%s', se usará NULL", row_idx, col, val)
    return None


def time_key(hora: str) -> tuple[int, int, int]:
    """Convierte HH:MM:SS en una tupla comparable."""
    h, m, s = hora.split(":")
    return int(h), int(m), int(s)


def siguiente_dia_semana(dia: int) -> int:
    """Convierte 7 → 1 y el resto al día siguiente."""
    return 1 if dia == 7 else dia + 1


def read_sheet(sheets: dict, name: str) -> pd.DataFrame:
    df = sheets.get(name, pd.DataFrame())
    df.columns = [c.strip().lower() for c in df.columns]
    return df


TABLAS_REQUERIDAS = [
    "parroquia", "plataforma", "categoria", "subcategoria", "sitio",
    "direccion", "contacto", "horario", "horario_detalle",
    "multimedia", "rango_precio", "tarifa_acceso",
]


def tablas_turismo_existentes(cur) -> set:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'turismo'
          AND table_type = 'BASE TABLE'
        """
    )
    return {row[0] for row in cur.fetchall()}


def mover_seccion_sql(sql_texto: str, inicio_patron: str, fin_patron: str, destino_patron: str) -> str:
    """Mueve una sección completa de un SQL antes de un marcador destino."""
    inicio = re.search(inicio_patron, sql_texto, flags=re.IGNORECASE)
    fin = re.search(fin_patron, sql_texto, flags=re.IGNORECASE)
    destino = re.search(destino_patron, sql_texto, flags=re.IGNORECASE)

    if not inicio or not fin or not destino:
        return sql_texto
    if not (inicio.start() < fin.start()):
        return sql_texto

    seccion = sql_texto[inicio.start():fin.start()].strip() + "\n\n"
    restante = sql_texto[:inicio.start()] + sql_texto[fin.start():]

    destino_restante = re.search(destino_patron, restante, flags=re.IGNORECASE)
    if not destino_restante:
        return sql_texto

    return restante[:destino_restante.start()] + seccion + restante[destino_restante.start():]


def limpiar_init_sql(sql_texto: str) -> str:
    """
    Limpia detalles del SQL que pueden fallar cuando se ejecuta desde el script.

    - Omite ALTER DATABASE … SET timezone porque el contenedor ya define la zona horaria.
    - Quita el trigger temprano trg_eliminar_chunks_ruta si aparece antes de crear
      gis.rutas_turistica. En el archivo SQL subido el trigger vuelve a declararse
      correctamente después de crear la tabla, por lo que esta eliminación evita que
      --init-db falle en una base vacía.
    - Mueve la sección TRAZABILIDAD después de crear chatbot.usuario, porque las
      tablas trazabilidad.inicio_sesion y trazabilidad.accion tienen FK hacia
      chatbot.usuario. En PostgreSQL, la tabla referenciada debe existir antes.
    """
    lineas_limpias = []
    for linea in sql_texto.splitlines():
        if re.match(r"\s*ALTER\s+DATABASE\s+\S+\s+SET\s+timezone\s+TO\s+", linea, re.IGNORECASE):
            continue
        lineas_limpias.append(linea)

    sql_limpio = "\n".join(lineas_limpias)

    # La sección de trazabilidad aparece antes de chatbot.usuario en el SQL subido.
    # Se mueve justo antes de la sección CHATBOT, es decir, después de USUARIOS Y PERMISOS.
    sql_limpio = mover_seccion_sql(
        sql_limpio,
        inicio_patron=r"--\s*=+\s*\n--\s*TRAZABILIDAD\s*\n--\s*=+",
        fin_patron=r"--\s*=+\s*\n--\s*USUARIOS\s+Y\s+PERMISOS\s*\n--\s*=+",
        destino_patron=r"--\s*=+\s*\n--\s*CHATBOT\s*\n--\s*=+",
    )

    tabla_ruta_pos = re.search(
        r"CREATE\s+TABLE\s+gis\.rutas_turistica\s*\(",
        sql_limpio,
        flags=re.IGNORECASE,
    )
    trigger_patron = re.compile(
        r"\s*CREATE\s+TRIGGER\s+trg_eliminar_chunks_ruta\s+"
        r"BEFORE\s+DELETE\s+ON\s+gis\.rutas_turistica\s+"
        r"FOR\s+EACH\s+ROW\s+"
        r"EXECUTE\s+FUNCTION\s+turismo\.fn_eliminar_chunks_ruta\s*\(\s*\)\s*;",
        flags=re.IGNORECASE | re.DOTALL,
    )

    if tabla_ruta_pos:
        partes = []
        ultimo = 0
        for match in trigger_patron.finditer(sql_limpio):
            if match.start() < tabla_ruta_pos.start():
                partes.append(sql_limpio[ultimo:match.start()])
                ultimo = match.end()
        partes.append(sql_limpio[ultimo:])
        sql_limpio = "".join(partes)

    return sql_limpio

def ejecutar_init_sql(cur, init_sql_path: str):
    ruta = Path(init_sql_path)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de inicialización: {ruta}. "
            "Crea init/01-init.sql o pasa la ruta con --init-sql."
        )

    log.info("Inicializando estructura de base desde: %s", ruta)
    sql_texto = ruta.read_text(encoding="utf-8")
    sql_texto = limpiar_init_sql(sql_texto)
    cur.execute(sql_texto)


def validar_esquema_requerido(cur, init_db: bool, init_sql_path: str):
    existentes = tablas_turismo_existentes(cur)
    faltantes = [tabla for tabla in TABLAS_REQUERIDAS if tabla not in existentes]

    if not faltantes:
        log.info("Esquema validado: tablas requeridas encontradas.")
        return

    if init_db:
        log.warning("Faltan tablas en schema turismo: %s", ", ".join(faltantes))
        ejecutar_init_sql(cur, init_sql_path)
        existentes = tablas_turismo_existentes(cur)
        faltantes = [tabla for tabla in TABLAS_REQUERIDAS if tabla not in existentes]
        if not faltantes:
            log.info("Esquema inicializado correctamente.")
            return

    raise RuntimeError(
        "La base de datos no tiene creada la estructura requerida. "
        f"Faltan tablas: {', '.join(faltantes)}. "
        "Reinicia el volumen de Docker (postgres-apis) o vuelve a correr con --init-db."
    )


def limpiar_datos_turismo(cur) -> None:
    """
    Vacía las tablas que carga este script y sus dependientes directos.

    Se arma dinámicamente para ser compatible con el 01-extensions.sql actual:
    ya no existe turismo.sitio_documento_chunk ni turismo.trazabilidad, y las
    tablas RAG vigentes son sitio_documento, chunk_fuente y chunk.
    """
    log.info("Limpiando datos existentes en schema turismo…")

    tablas_objetivo = [
        ("turismo", "chunk"),
        ("turismo", "chunk_fuente"),
        ("turismo", "sitio_documento"),
        ("turismo", "noticia"),
        ("turismo", "tarifa_acceso"),
        ("turismo", "rango_precio"),
        ("turismo", "multimedia"),
        ("turismo", "horario_detalle"),
        ("turismo", "horario"),
        ("turismo", "contacto"),
        ("turismo", "direccion"),
        ("turismo", "sitio"),
        ("turismo", "subcategoria"),
        ("turismo", "categoria"),
        ("turismo", "plataforma"),
        ("turismo", "parroquia"),
    ]

    cur.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('turismo')
          AND table_type = 'BASE TABLE'
        """
    )
    existentes = {(schema, tabla) for schema, tabla in cur.fetchall()}
    tablas_truncar = [
        f"{schema}.{tabla}"
        for schema, tabla in tablas_objetivo
        if (schema, tabla) in existentes
    ]

    if not tablas_truncar:
        log.info("No se encontraron tablas de turismo para limpiar.")
        return

    cur.execute(
        "TRUNCATE TABLE " + ", ".join(tablas_truncar) + " RESTART IDENTITY CASCADE"
    )
    log.info("Schema turismo vaciado: %d tablas truncadas.", len(tablas_truncar))


def generar_embeddings_voyage(textos: list[str], voyage_cfg: dict[str, str]) -> list[str]:
    if not textos:
        return []

    api_key = voyage_cfg.get("api_key", "").strip()
    modelo = voyage_cfg.get("model", "voyage-4-lite").strip() or "voyage-4-lite"
    if not api_key:
        raise RuntimeError(
            "VOYAGE_API_KEY no esta configurada en base_datos/.env; no se pueden generar embeddings."
        )

    embeddings: list[str] = []
    for lote in chunked(textos, VOYAGE_BATCH_SIZE):
        payload = json.dumps(
            {
                "input": lote,
                "model": modelo,
                "input_type": "document",
                "truncation": True,
                "output_dimension": 1024,
            }
        ).encode("utf-8")
        req = urllib_request.Request(
            VOYAGE_EMBEDDINGS_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            detalle = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Voyage devolvio HTTP {exc.code} al generar embeddings: {detalle}"
            ) from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(
                f"No se pudo conectar con Voyage para generar embeddings: {exc.reason}"
            ) from exc

        try:
            for item in data["data"]:
                vector = item["embedding"]
                embeddings.append("[" + ",".join(str(float(value)) for value in vector) + "]")
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Respuesta invalida de Voyage al generar embeddings.") from exc

    if len(embeddings) != len(textos):
        raise RuntimeError(
            f"Voyage devolvio {len(embeddings)} embeddings para {len(textos)} textos."
        )
    return embeddings


# ---------------------------------------------------------------------------
# Carga por tabla
# ---------------------------------------------------------------------------

def cargar_parroquias(cur, df: pd.DataFrame, dry_run: bool, skip_errors: bool) -> dict:
    """Retorna mapeo  codigo_parroquia → id_parroquia (BD)."""
    mapping = {}
    rows = []
    for i, row in df.iterrows():
        nombre = to_str_limit(row.get("nombre"), 100, "nombre", i)
        activo = to_bool(row.get("activo"), "activo", i)
        if not nombre:
            log.warning("PARROQUIAS fila %d: nombre vacío, se omite.", i)
            continue
        rows.append((nombre, activo if activo is not None else True))

    if dry_run:
        log.info("[DRY-RUN] PARROQUIAS: %d filas listas para insertar.", len(rows))
        for idx, (r_nombre, _) in enumerate(rows, start=1):
            for i, row in df.iterrows():
                if to_str(row.get("nombre")) == r_nombre:
                    cod = row.get("codigo_parroquia")
                    if not pd.isna(cod):
                        mapping[int(float(cod))] = idx
        return mapping

    for (nombre, activo) in rows:
        cur.execute(
            "INSERT INTO turismo.parroquia (nombre, activo) VALUES (%s, %s) RETURNING id_parroquia",
            (nombre, activo),
        )
        new_id = cur.fetchone()[0]
        for i, row in df.iterrows():
            if to_str(row.get("nombre")) == nombre:
                cod = row.get("codigo_parroquia")
                if not pd.isna(cod):
                    mapping[int(float(cod))] = new_id
    log.info("PARROQUIAS: %d registros insertados.", len(mapping))
    return mapping


def cargar_plataformas(cur, df: pd.DataFrame, map_parroquia: dict,
                       dry_run: bool, skip_errors: bool) -> dict:
    mapping = {}
    rows = []
    for i, row in df.iterrows():
        codigo = to_int(row.get("codigo_plataforma"), "codigo_plataforma", i)
        cod_par = to_int(row.get("codigo_parroquia"), "codigo_parroquia", i)
        nombre = to_str_limit(row.get("nombre"), 100, "nombre", i)
        activo = to_bool(row.get("activo"), "activo", i)

        if not nombre or cod_par is None:
            log.warning("PLATAFORMAS fila %d: datos incompletos, se omite.", i)
            continue
        id_parroquia = map_parroquia.get(cod_par)
        if id_parroquia is None:
            log.warning("PLATAFORMAS fila %d: codigo_parroquia=%s no encontrado.", i, cod_par)
            continue
        rows.append((codigo, id_parroquia, nombre, activo if activo is not None else True))

    if dry_run:
        log.info("[DRY-RUN] PLATAFORMAS: %d filas listas para insertar.", len(rows))
        for idx, (codigo, *_) in enumerate(rows, start=1):
            mapping[codigo] = idx
        return mapping

    for (codigo, id_parroquia, nombre, activo) in rows:
        cur.execute(
            "INSERT INTO turismo.plataforma (id_parroquia, nombre, activo) VALUES (%s,%s,%s) RETURNING id_plataforma",
            (id_parroquia, nombre, activo),
        )
        mapping[codigo] = cur.fetchone()[0]
    log.info("PLATAFORMAS: %d registros insertados.", len(mapping))
    return mapping


def cargar_categorias(cur, df: pd.DataFrame, dry_run: bool, skip_errors: bool) -> dict:
    mapping = {}
    rows = []
    for i, row in df.iterrows():
        codigo = to_int(row.get("codigo_categoria"), "codigo_categoria", i)
        nombre = to_str_limit(row.get("nombre"), 100, "nombre", i)
        activo = to_bool(row.get("activo"), "activo", i)
        if codigo is None or not nombre:
            continue
        rows.append((codigo, nombre, activo if activo is not None else True))

    if dry_run:
        log.info("[DRY-RUN] CATEGORIAS: %d filas listas para insertar.", len(rows))
        for idx, (codigo, *_) in enumerate(rows, start=1):
            mapping[codigo] = idx
        return mapping

    for (codigo, nombre, activo) in rows:
        cur.execute(
            "INSERT INTO turismo.categoria (nombre, activo) VALUES (%s,%s) RETURNING id_categoria",
            (nombre, activo),
        )
        mapping[codigo] = cur.fetchone()[0]
    log.info("CATEGORIAS: %d registros insertados.", len(mapping))
    return mapping


def cargar_subcategorias(cur, df: pd.DataFrame, map_categoria: dict,
                         dry_run: bool, skip_errors: bool) -> dict:
    mapping = {}
    rows = []
    for i, row in df.iterrows():
        codigo = to_int(row.get("codigo_subcategoria"), "codigo_subcategoria", i)
        cod_cat = to_int(row.get("codigo_categoria"), "codigo_categoria", i)
        nombre = to_str_limit(row.get("nombre"), 100, "nombre", i)
        activo = to_bool(row.get("activo"), "activo", i)

        if codigo is None or not nombre or cod_cat is None:
            continue
        id_cat = map_categoria.get(cod_cat)
        if id_cat is None:
            log.warning("SUBCATEGORIAS fila %d: codigo_categoria=%s no encontrado.", i, cod_cat)
            continue
        rows.append((codigo, id_cat, nombre, activo if activo is not None else True))

    if dry_run:
        log.info("[DRY-RUN] SUBCATEGORIAS: %d filas listas para insertar.", len(rows))
        for idx, (codigo, *_) in enumerate(rows, start=1):
            mapping[codigo] = idx
        return mapping

    for (codigo, id_cat, nombre, activo) in rows:
        cur.execute(
            "INSERT INTO turismo.subcategoria (id_categoria, nombre, activo) VALUES (%s,%s,%s) RETURNING id_subcategoria",
            (id_cat, nombre, activo),
        )
        mapping[codigo] = cur.fetchone()[0]
    log.info("SUBCATEGORIAS: %d registros insertados.", len(mapping))
    return mapping


def cargar_sitios(cur, df: pd.DataFrame, map_parroquia: dict, map_plataforma: dict,
                  map_categoria: dict, map_subcategoria: dict,
                  dry_run: bool, skip_errors: bool) -> dict:
    """
    Inserta en turismo.sitio.
    La columna ubicacion usa GEOGRAPHY(POINT,4326) → se pasa como WKT con SRID.
    Con --skip-errors se usa un SAVEPOINT real por fila para poder hacer rollback
    sin abortar la transacción completa.
    """
    mapping = {}
    ok = 0
    for i, row in df.iterrows():
        codigo = to_int(row.get("codigo_sitio"), "codigo_sitio", i)
        if codigo is None:
            continue

        tipo_raw = to_str(row.get("tipo")) or ""
        tipo = TIPO_SITIO_MAP.get(normalizar_clave(tipo_raw), "desconocido")
        if tipo == "desconocido":
            log.warning(
                "SITIOS fila %d (codigo=%s): tipo '%s' no reconocido → 'desconocido'.",
                i, codigo, tipo_raw,
            )

        cod_cat = to_int(row.get("codigo_categoria"), "codigo_categoria", i)
        id_cat = map_categoria.get(cod_cat)
        if id_cat is None:
            log.warning(
                "SITIOS fila %d (codigo=%s): codigo_categoria=%s inválido, se omite.",
                i, codigo, cod_cat,
            )
            continue

        cod_par = to_int(row.get("codigo_parroquia"), "codigo_parroquia", i)
        cod_pla = to_int(row.get("codigo_plataforma"), "codigo_plataforma", i)
        cod_sub = to_int(row.get("codigo_subcategoria"), "codigo_subcategoria", i)

        id_parroquia    = map_parroquia.get(cod_par)   if cod_par else None
        id_plataforma   = map_plataforma.get(cod_pla)  if cod_pla else None
        id_subcategoria = map_subcategoria.get(cod_sub) if cod_sub else None

        lat = to_float(row.get("latitud"),  "latitud",  i)
        lon = to_float(row.get("longitud"), "longitud", i)
        # GEOGRAPHY acepta WKT con SRID mediante ST_GeogFromText o el cast ::geography
        ubicacion = f"SRID=4326;POINT({lon} {lat})" if lat is not None and lon is not None else None

        activo_val = row.get("activo", pd.NA)
        activo = to_bool(activo_val, "activo", i) if not pd.isna(activo_val) else True

        params = (
            id_parroquia,
            id_plataforma,
            id_cat,
            id_subcategoria,
            tipo,
            to_str_limit(row.get("nombre"), 180, "nombre", i),
            to_str_limit(row.get("descripcion_corta"), 350, "descripcion_corta", i),
            ubicacion,
            to_bool(row.get("es_gratuito"),      "es_gratuito",      i),
            to_bool(row.get("permite_mascotas"),  "permite_mascotas",  i),
            to_bool(row.get("parqueadero"),        "parqueadero",        i),
            to_bool(row.get("tiene_wifi"),         "tiene_wifi",         i),
            to_bool(row.get("accesibilidad"),      "accesibilidad",      i),
            activo,
        )

        if dry_run:
            mapping[codigo] = codigo  # placeholder
            ok += 1
            continue

        # SAVEPOINT real: permite continuar la transacción si skip_errors=True
        if skip_errors:
            cur.execute("SAVEPOINT sp_sitio")
        try:
            cur.execute(
                """
                INSERT INTO turismo.sitio
                    (id_parroquia, id_plataforma, id_categoria, id_subcategoria,
                     tipo, nombre, descripcion_corta, ubicacion,
                     es_gratuito, permite_mascotas, parqueadero, tiene_wifi,
                     accesibilidad, activo)
                VALUES (%s,%s,%s,%s,
                        %s::turismo.tipo_sitio_t,
                        %s,%s,%s::geography,
                        %s,%s,%s,%s,%s,%s)
                RETURNING id_sitio
                """,
                params,
            )
            mapping[codigo] = cur.fetchone()[0]
            ok += 1
            if skip_errors:
                cur.execute("RELEASE SAVEPOINT sp_sitio")
        except Exception as exc:
            if skip_errors:
                log.error("SITIOS fila %d (codigo=%s): %s – se omite.", i, codigo, exc)
                cur.execute("ROLLBACK TO SAVEPOINT sp_sitio")
                cur.execute("RELEASE SAVEPOINT sp_sitio")
            else:
                raise

    if dry_run:
        log.info("[DRY-RUN] SITIOS: %d filas listas para insertar.", ok)
    else:
        log.info("SITIOS: %d registros insertados.", ok)
    return mapping


def cargar_direcciones(cur, df: pd.DataFrame, map_sitio: dict,
                       dry_run: bool, skip_errors: bool):
    """
    turismo.direccion tiene UNIQUE(id_sitio): un sitio → una dirección.
    Se usa INSERT … ON CONFLICT DO NOTHING para tolerar duplicados en el Excel.
    """
    rows = []
    for i, row in df.iterrows():
        cod = to_int(row.get("codigo_sitio"), "codigo_sitio", i)
        id_sitio = map_sitio.get(cod)
        dir_texto = to_str_limit(row.get("direccion_texto"), 200, "direccion_texto", i)
        if id_sitio is None or not dir_texto:
            continue
        rows.append((id_sitio, dir_texto, to_str_limit(row.get("referencia_adicional"), 200, "referencia_adicional", i)))

    if dry_run:
        log.info("[DRY-RUN] DIRECCIONES: %d filas listas para insertar.", len(rows))
        return

    execute_values(
        cur,
        """
        INSERT INTO turismo.direccion (id_sitio, direccion_texto, referencia_adicional)
        VALUES %s
        ON CONFLICT (id_sitio) DO NOTHING
        """,
        rows,
    )
    log.info("DIRECCIONES: %d registros insertados.", len(rows))


def cargar_contactos(cur, df: pd.DataFrame, map_sitio: dict,
                     dry_run: bool, skip_errors: bool):
    """
    Inserta contactos según el SQL actual.

    La plantilla tiene tipo_contacto, pero turismo.contacto ya no tiene columna tipo
    ni ENUM turismo.tipo_contacto_t. Se guarda ese dato normalizado en nombre.
    """
    rows = []
    for i, row in df.iterrows():
        cod = to_int(row.get("codigo_sitio"), "codigo_sitio", i)
        id_sitio = map_sitio.get(cod)

        tipo_original = to_str(row.get("tipo_contacto"))
        tipo_clave = normalizar_clave(tipo_original)
        nombre = CONTACTO_NOMBRE_MAP.get(tipo_clave)
        if nombre is None:
            nombre = to_str_limit(tipo_original, 100, "tipo_contacto", i) or "otro"
            log.warning(
                "CONTACTOS fila %d: tipo_contacto '%s' no está en el mapa; se guardará como nombre='%s'.",
                i, tipo_original, nombre,
            )

        contenido = to_str_limit(row.get("contenido"), 300, "contenido", i)
        activo = to_bool(row.get("activo"), "activo", i)

        if id_sitio is None or not contenido:
            continue
        rows.append((id_sitio, nombre, contenido, activo if activo is not None else True))

    if dry_run:
        log.info("[DRY-RUN] CONTACTOS: %d filas listas para insertar.", len(rows))
        return

    execute_values(
        cur,
        """
        INSERT INTO turismo.contacto (id_sitio, nombre, contenido, activo)
        VALUES %s
        """,
        rows,
    )
    log.info("CONTACTOS: %d registros insertados.", len(rows))


def cargar_horarios(cur, df_hor: pd.DataFrame, df_det: pd.DataFrame,
                    map_sitio: dict, dry_run: bool, skip_errors: bool):
    map_horario = {}  # codigo_sitio → id_horario

    # ── Cabeceras de horario ──────────────────────────────────────────────
    rows_hor = []
    for i, row in df_hor.iterrows():
        cod = to_int(row.get("codigo_sitio"), "codigo_sitio", i)
        id_sitio = map_sitio.get(cod)
        if id_sitio is None:
            continue
        abierto = to_bool(row.get("abierto_24h"), "abierto_24h", i)
        activo = to_bool(row.get("activo"), "activo", i)
        comentario = to_str_limit(row.get("comentario"), 200, "comentario", i)
        rows_hor.append((cod, id_sitio, abierto or False, comentario, activo if activo is not None else True))

    if dry_run:
        log.info("[DRY-RUN] HORARIOS: %d filas listas.", len(rows_hor))
        for (cod, *_) in rows_hor:
            map_horario[cod] = cod
    else:
        for (cod, id_sitio, abierto, comentario, activo) in rows_hor:
            cur.execute(
                "INSERT INTO turismo.horario (id_sitio, abierto_24h, comentario, activo) "
                "VALUES (%s,%s,%s,%s) RETURNING id_horario",
                (id_sitio, abierto, comentario, activo),
            )
            map_horario[cod] = cur.fetchone()[0]
        log.info("HORARIOS: %d registros insertados.", len(map_horario))

    # ── Detalle de horario ────────────────────────────────────────────────
    # Validaciones adicionales del CHECK del SQL:
    #   dia_semana BETWEEN 1 AND 7
    #   hora_inicio < hora_fin
    rows_det = []
    for i, row in df_det.iterrows():
        cod = to_int(row.get("codigo_sitio"), "codigo_sitio", i)
        id_horario = map_horario.get(cod)
        if id_horario is None:
            continue
        dia = to_int(row.get("dia_semana"), "dia_semana", i)
        h_ini = to_time(row.get("hora_inicio"), "hora_inicio", i)
        h_fin = to_time(row.get("hora_fin"),    "hora_fin",    i)
        activo = to_bool(row.get("activo"), "activo", i)

        if dia is None or h_ini is None or h_fin is None:
            log.warning("HORARIO_DETALLE fila %d: datos incompletos, se omite.", i)
            continue
        if not (1 <= dia <= 7):
            log.warning("HORARIO_DETALLE fila %d: dia_semana=%s fuera de rango [1-7], se omite.", i, dia)
            continue
        activo_final = activo if activo is not None else True

        # Si hora_inicio >= hora_fin, el horario cruza la medianoche.
        # Ejemplo: lunes 22:00 → 04:00 realmente significa:
        # lunes 22:00 → 23:59:59 y martes 00:00 → 04:00.
        # Esto evita violar el CHECK de la tabla, que exige hora_inicio < hora_fin.
        if time_key(h_ini) >= time_key(h_fin):
            if h_ini == h_fin:
                log.warning(
                    "HORARIO_DETALLE fila %d: hora_inicio=%s y hora_fin=%s son iguales; "
                    "si es 24 horas, usa abierto_24h=SI en la hoja HORARIOS. Se omite.",
                    i, h_ini, h_fin,
                )
                continue

            log.warning(
                "HORARIO_DETALLE fila %d: horario nocturno detectado %s-%s; "
                "se divide en día %s %s-23:59:59 y día %s 00:00:00-%s.",
                i, h_ini, h_fin, dia, h_ini, siguiente_dia_semana(dia), h_fin,
            )

            if time_key(h_ini) < time_key("23:59:59"):
                rows_det.append((id_horario, dia, h_ini, "23:59:59", activo_final))

            if time_key("00:00:00") < time_key(h_fin):
                rows_det.append((id_horario, siguiente_dia_semana(dia), "00:00:00", h_fin, activo_final))

            continue

        rows_det.append((id_horario, dia, h_ini, h_fin, activo_final))

    if dry_run:
        log.info("[DRY-RUN] HORARIO_DETALLE: %d filas listas.", len(rows_det))
        return

    execute_values(
        cur,
        "INSERT INTO turismo.horario_detalle (id_horario, dia_semana, hora_inicio, hora_fin, activo) VALUES %s",
        rows_det,
    )
    log.info("HORARIO_DETALLE: %d registros insertados.", len(rows_det))


def cargar_multimedia(cur, df: pd.DataFrame, map_sitio: dict,
                      dry_run: bool, skip_errors: bool):
    """
    El trigger trg_un_solo_principal_media garantiza un solo principal por sitio.
    Se usa SAVEPOINT por fila para no abortar la TX completa ante conflictos
    en el índice uq_multimedia_principal_por_sitio.
    """
    rows = []
    for i, row in df.iterrows():
        cod = to_int(row.get("codigo_sitio"), "codigo_sitio", i)
        id_sitio = map_sitio.get(cod)
        url = to_str(row.get("url"))
        principal = to_bool(row.get("es_principal"), "es_principal", i)
        activo = to_bool(row.get("activo"), "activo", i)
        if id_sitio is None or not url:
            continue
        rows.append((id_sitio, url, principal or False, activo if activo is not None else True))

    if dry_run:
        log.info("[DRY-RUN] MULTIMEDIA: %d filas listas.", len(rows))
        return

    inserted = 0
    for r in rows:
        cur.execute("SAVEPOINT sp_multimedia")
        try:
            cur.execute(
                "INSERT INTO turismo.multimedia (id_sitio, url, es_principal, activo) VALUES (%s,%s,%s,%s)",
                r,
            )
            cur.execute("RELEASE SAVEPOINT sp_multimedia")
            inserted += 1
        except Exception as exc:
            cur.execute("ROLLBACK TO SAVEPOINT sp_multimedia")
            cur.execute("RELEASE SAVEPOINT sp_multimedia")
            if skip_errors:
                log.error("MULTIMEDIA sitio=%s url=%s: %s – se omite.", r[0], r[1], exc)
            else:
                raise
    log.info("MULTIMEDIA: %d registros insertados.", inserted)


def cargar_rango_precio(cur, df: pd.DataFrame, map_sitio: dict,
                        dry_run: bool, skip_errors: bool):
    """
    CHECK precio_min <= precio_max se valida en Python antes de insertar
    para dar un mensaje más claro que el error de PostgreSQL.
    etiqueta_precio → turismo.etiqueta_precio_t (ENUM).
    """
    rows = []
    for i, row in df.iterrows():
        cod = to_int(row.get("codigo_sitio"), "codigo_sitio", i)
        id_sitio = map_sitio.get(cod)
        p_min = to_float(row.get("precio_min"), "precio_min", i)
        p_max = to_float(row.get("precio_max"), "precio_max", i)
        etiqueta = (to_str(row.get("etiqueta_precio")) or "desconocido").lower()
        activo = to_bool(row.get("activo"), "activo", i)

        if id_sitio is None or p_min is None or p_max is None:
            continue
        if p_min > p_max:
            log.warning(
                "RANGO_PRECIO fila %d: precio_min(%.2f) > precio_max(%.2f), se omite.",
                i, p_min, p_max,
            )
            continue
        if etiqueta not in ETIQUETA_PRECIO_VALIDAS:
            log.warning("RANGO_PRECIO fila %d: etiqueta '%s' inválida → 'desconocido'.", i, etiqueta)
            etiqueta = "desconocido"
        rows.append((id_sitio, p_min, p_max, etiqueta, activo if activo is not None else True))

    if dry_run:
        log.info("[DRY-RUN] RANGO_PRECIO: %d filas listas.", len(rows))
        return

    execute_values(
        cur,
        """
        INSERT INTO turismo.rango_precio (id_sitio, precio_min, precio_max, etiqueta_precio, activo)
        VALUES %s
        """,
        rows,
        template="(%s, %s, %s, %s::turismo.etiqueta_precio_t, %s)",
    )
    log.info("RANGO_PRECIO: %d registros insertados.", len(rows))


def cargar_tarifa_acceso(cur, df: pd.DataFrame, map_sitio: dict,
                         dry_run: bool, skip_errors: bool):
    rows = []
    for i, row in df.iterrows():
        cod = to_int(row.get("codigo_sitio"), "codigo_sitio", i)
        id_sitio = map_sitio.get(cod)
        precio = to_float(row.get("precio"), "precio", i)
        condicion = to_str_limit(row.get("condicion"), 150, "condicion", i)
        activo = to_bool(row.get("activo"), "activo", i)
        if id_sitio is None or precio is None:
            continue
        if precio < 0:
            log.warning("TARIFA_ACCESO fila %d: precio negativo (%.2f), se omite.", i, precio)
            continue
        rows.append((id_sitio, precio, condicion, activo if activo is not None else True))

    if dry_run:
        log.info("[DRY-RUN] TARIFA_ACCESO: %d filas listas.", len(rows))
        return

    execute_values(
        cur,
        "INSERT INTO turismo.tarifa_acceso (id_sitio, precio, condicion, activo) VALUES %s",
        rows,
    )
    log.info("TARIFA_ACCESO: %d registros insertados.", len(rows))


def construir_texto_chunk_descripcion(nombre: str | None, descripcion: str | None) -> str | None:
    nombre_limpio = (nombre or "").strip()
    descripcion_limpia = (descripcion or "").strip()
    if not descripcion_limpia:
        return None
    if nombre_limpio:
        return f"{nombre_limpio}\n\n{descripcion_limpia}"
    return descripcion_limpia


def cargar_chunks_descripcion_sitios(
    cur,
    df_sitios: pd.DataFrame,
    map_sitio: dict,
    voyage_cfg: dict[str, str],
    dry_run: bool,
    skip_errors: bool,
):
    candidatos = []
    vistos: set[int] = set()

    for i, row in df_sitios.iterrows():
        codigo = to_int(row.get("codigo_sitio"), "codigo_sitio", i)
        if codigo is None:
            continue

        id_sitio = map_sitio.get(codigo)
        if id_sitio is None or id_sitio in vistos:
            continue

        contenido = to_str(row.get("descripcion_corta"))
        
        if not contenido:
            continue

        vistos.add(id_sitio)
        candidatos.append((id_sitio, codigo, contenido))

    if dry_run:
        log.info(
            "[DRY-RUN] CHUNKS_DESCRIPCION: %d sitios con descripcion listos para vectorizar.",
            len(candidatos),
        )
        return

    if not candidatos:
        log.info("CHUNKS_DESCRIPCION: no hay descripciones cortas para vectorizar.")
        return

    embeddings = generar_embeddings_voyage(
        [contenido for _, _, contenido in candidatos],
        voyage_cfg,
    )
    insertados = 0

    for (id_sitio, codigo, contenido), embedding in zip(candidatos, embeddings):
        if skip_errors:
            cur.execute("SAVEPOINT sp_chunk_descripcion")
        try:
            cur.execute(
                """
                INSERT INTO turismo.chunk_fuente (tipo_chunk, origen, id_vinculo, id_documento)
                VALUES ('descripcion'::turismo.tipo_chunk_t, 'sitio'::turismo.origen_chunk_t, %s, NULL)
                RETURNING id_fuente
                """,
                (id_sitio,),
            )
            id_fuente = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO turismo.chunk (id_fuente, contenido, embedding)
                VALUES (%s, %s, %s::vector)
                """,
                (id_fuente, contenido, embedding),
            )
            insertados += 1
            if skip_errors:
                cur.execute("RELEASE SAVEPOINT sp_chunk_descripcion")
        except Exception as exc:
            if skip_errors:
                log.error(
                    "CHUNKS_DESCRIPCION sitio=%s codigo=%s: %s – se omite.",
                    id_sitio, codigo, exc,
                )
                cur.execute("ROLLBACK TO SAVEPOINT sp_chunk_descripcion")
                cur.execute("RELEASE SAVEPOINT sp_chunk_descripcion")
                continue
            raise

    log.info(
        "CHUNKS_DESCRIPCION: %d registros insertados en turismo.chunk_fuente/turismo.chunk.",
        insertados,
    )


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Carga plantilla Excel → PostgreSQL (schema turismo)")
    p.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE,
                   help="Archivo .env con POSTGRES_* (default: base_datos/.env)")
    p.add_argument("--excel", type=Path, default=DEFAULT_EXCEL,
                   help="Ruta al archivo .xlsx")
    p.add_argument("--host", default=None, help="Host BD (default: POSTGRES_HOST → 127.0.0.1 fuera de Docker)")
    p.add_argument("--port", default=None, type=int, help="Puerto BD (default: POSTGRES_PORT o 5432)")
    p.add_argument("--db", default=None, help="Base de datos (default: POSTGRES_DB o riobambago)")
    p.add_argument("--user", default=None, help="Usuario BD (default: POSTGRES_USER)")
    p.add_argument("--password", default=None, help="Contraseña BD (default: POSTGRES_PASSWORD)")
    p.add_argument("--dry-run", action="store_true", help="Validar sin insertar en BD")
    p.add_argument("--skip-errors", action="store_true", help="Omitir filas con error y continuar")
    p.add_argument("--init-db", action="store_true",
                   help="Si faltan tablas, ejecuta el SQL de inicialización antes de cargar.")
    p.add_argument("--init-sql", type=Path, default=DEFAULT_INIT_SQL,
                   help="SQL de inicialización (default: initdb/01-extensions.sql)")
    p.add_argument("--no-limpiar", action="store_true",
                   help="No truncar turismo.* antes de cargar.")
    args = p.parse_args()

    env = leer_env(args.env_file)
    args._env = env
    defaults = defaults_desde_env(env)
    if args.host is None:
        args.host = defaults["host"]
    if args.port is None:
        args.port = defaults["port"]
    if args.db is None:
        args.db = defaults["db"]
    if args.user is None:
        args.user = defaults["user"]
    if args.password is None:
        args.password = defaults["password"]

    return args


def main():
    args = parse_args()
    voyage_cfg = voyage_config_desde_env(getattr(args, "_env", {}))

    # ── Leer Excel ──────────────────────────────────────────────────────
    log.info("Leyendo archivo: %s", args.excel)
    try:
        sheets = pd.read_excel(args.excel, sheet_name=None, dtype=str)
    except FileNotFoundError:
        log.error("Archivo no encontrado: %s", args.excel)
        sys.exit(1)

    # Normalizar nombres de hojas a mayúsculas
    sheets = {k.upper(): v for k, v in sheets.items()}

    df_parroquias    = read_sheet(sheets, "PARROQUIAS")
    df_plataformas   = read_sheet(sheets, "PLATAFORMAS")
    df_categorias    = read_sheet(sheets, "CATEGORIAS")
    df_subcategorias = read_sheet(sheets, "SUBCATEGORIAS")
    df_sitios        = read_sheet(sheets, "SITIOS")
    df_direcciones   = read_sheet(sheets, "DIRECCIONES")
    df_contactos     = read_sheet(sheets, "CONTACTOS")
    df_horarios      = read_sheet(sheets, "HORARIOS")
    df_hor_detalle   = read_sheet(sheets, "HORARIO_DETALLE")
    df_multimedia    = read_sheet(sheets, "MULTIMEDIA")
    df_rango_precio  = read_sheet(sheets, "RANGO_PRECIO")
    df_tarifa_acceso = read_sheet(sheets, "TARIFA_ACCESO")
    df_actividades    = read_sheet(sheets, "ACTIVIDADES")

    if not df_actividades.empty:
        log.info(
            "ACTIVIDADES: hoja detectada con %d filas, pero 01-extensions.sql actual "
            "no define turismo.actividad; se omite.",
            len(df_actividades),
        )

    # ── Modo dry-run ────────────────────────────────────────────────────
    if args.dry_run:
        log.info("=== MODO DRY-RUN: no se escribirá nada en la base de datos ===")
        mp  = cargar_parroquias(None, df_parroquias, True, args.skip_errors)
        mpl = cargar_plataformas(None, df_plataformas, mp, True, args.skip_errors)
        mc  = cargar_categorias(None, df_categorias, True, args.skip_errors)
        ms  = cargar_subcategorias(None, df_subcategorias, mc, True, args.skip_errors)
        msi = cargar_sitios(None, df_sitios, mp, mpl, mc, ms, True, args.skip_errors)
        cargar_direcciones(None, df_direcciones, msi, True, args.skip_errors)
        cargar_contactos(None, df_contactos, msi, True, args.skip_errors)
        cargar_horarios(None, df_horarios, df_hor_detalle, msi, True, args.skip_errors)
        cargar_multimedia(None, df_multimedia, msi, True, args.skip_errors)
        cargar_rango_precio(None, df_rango_precio, msi, True, args.skip_errors)
        cargar_tarifa_acceso(None, df_tarifa_acceso, msi, True, args.skip_errors)
        cargar_chunks_descripcion_sitios(None, df_sitios, msi, voyage_cfg, True, args.skip_errors)
        log.info("✅  Dry-run completado sin errores críticos.")
        return

    # ── Conectar a PostgreSQL ─────────────────────────────────────────────
    if psycopg2 is None:
        log.error("No se encontró psycopg2. Instala dependencias con: pip install pandas openpyxl psycopg2-binary")
        sys.exit(1)

    log.info("Conectando a PostgreSQL → %s:%d / db=%s / user=%s",
             args.host, args.port, args.db, args.user)
    try:
        conn = psycopg2.connect(
            host=args.host, port=args.port,
            dbname=args.db, user=args.user, password=args.password,
        )
    except psycopg2.OperationalError as exc:
        log.error("No se pudo conectar a PostgreSQL: %s", exc)
        log.error("¿Está corriendo el contenedor? Prueba: docker compose up -d")
        sys.exit(1)

    conn.autocommit = False
    cur = conn.cursor()

    try:
        validar_esquema_requerido(cur, args.init_db, str(args.init_sql))

        if not args.no_limpiar:
            limpiar_datos_turismo(cur)

        # Catálogos base — orden respeta FKs
        map_parroquia    = cargar_parroquias(cur, df_parroquias, False, args.skip_errors)
        map_plataforma   = cargar_plataformas(cur, df_plataformas, map_parroquia, False, args.skip_errors)
        map_categoria    = cargar_categorias(cur, df_categorias, False, args.skip_errors)
        map_subcategoria = cargar_subcategorias(cur, df_subcategorias, map_categoria, False, args.skip_errors)

        # Sitios (núcleo)
        map_sitio = cargar_sitios(
            cur, df_sitios,
            map_parroquia, map_plataforma, map_categoria, map_subcategoria,
            False, args.skip_errors,
        )

        # Dependientes de sitio
        cargar_direcciones(cur, df_direcciones, map_sitio, False, args.skip_errors)
        cargar_contactos(cur, df_contactos, map_sitio, False, args.skip_errors)
        cargar_horarios(cur, df_horarios, df_hor_detalle, map_sitio, False, args.skip_errors)
        cargar_multimedia(cur, df_multimedia, map_sitio, False, args.skip_errors)
        cargar_rango_precio(cur, df_rango_precio, map_sitio, False, args.skip_errors)
        cargar_tarifa_acceso(cur, df_tarifa_acceso, map_sitio, False, args.skip_errors)
        cargar_chunks_descripcion_sitios(cur, df_sitios, map_sitio, voyage_cfg, False, args.skip_errors)

        conn.commit()
        log.info("✅  Carga completada con éxito.")

    except Exception as exc:
        conn.rollback()
        log.error("❌  Error durante la carga – se revirtió la transacción: %s", exc)
        if "no tiene creada la estructura" in str(exc) or "Faltan tablas" in str(exc):
            log.error("Solución rápida si usas Docker: docker compose down -v && docker compose up -d --build")
            log.error("Alternativa: python cargar_datos.py --init-db")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
