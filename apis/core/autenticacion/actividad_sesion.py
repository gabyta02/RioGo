import json
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from core.infra.redis_cliente import ejecutar_redis

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

ADMIN_INACTIVIDAD_MINUTOS = int(os.getenv("ADMIN_INACTIVIDAD_MINUTOS", "30"))

_actividad_memoria: dict[str, tuple[float, dict]] = {}


def segundos_inactividad_admin() -> int:
    return ADMIN_INACTIVIDAD_MINUTOS * 60


def _clave_admin_sesion(admin_sesion_id: str) -> str:
    return f"admin_session:{admin_sesion_id}"


def crear_sesion_admin(id_usuario: int, id_sesion: str) -> str:
    admin_sesion_id = uuid.uuid4().hex
    clave = _clave_admin_sesion(admin_sesion_id)
    ttl = segundos_inactividad_admin()
    payload = {
        "id_usuario": int(id_usuario),
        "id_sesion": str(id_sesion),
        "creado_en": int(time.time()),
    }

    def _en_redis(redis):
        redis.setex(clave, ttl, json.dumps(payload))

    def _en_memoria():
        _actividad_memoria[clave] = (time.time() + ttl, payload)

    ejecutar_redis(_en_redis, fallback=_en_memoria)
    return admin_sesion_id


def validar_sesion_admin(admin_sesion_id: str | None, id_usuario: int, id_sesion: str) -> bool:
    if not admin_sesion_id:
        return False
    clave = _clave_admin_sesion(admin_sesion_id)

    def _payload_valido(payload: dict | None) -> bool:
        return bool(
            payload
            and int(payload.get("id_usuario", 0)) == int(id_usuario)
            and str(payload.get("id_sesion")) == str(id_sesion)
        )

    def _en_redis(redis):
        raw = redis.get(clave)
        return _payload_valido(json.loads(raw) if raw else None)

    def _en_memoria():
        item = _actividad_memoria.get(clave)
        if not item:
            return False
        expira_en, payload = item
        if expira_en <= time.time():
            _actividad_memoria.pop(clave, None)
            return False
        return _payload_valido(payload)

    return ejecutar_redis(_en_redis, fallback=_en_memoria)


def renovar_sesion_admin(admin_sesion_id: str | None, id_usuario: int, id_sesion: str) -> bool:
    if not validar_sesion_admin(admin_sesion_id, id_usuario, id_sesion):
        return False
    clave = _clave_admin_sesion(str(admin_sesion_id))
    ttl = segundos_inactividad_admin()

    def _en_redis(redis):
        return bool(redis.expire(clave, ttl))

    def _en_memoria():
        expira_en, payload = _actividad_memoria[clave]
        _actividad_memoria[clave] = (time.time() + ttl, payload)
        return expira_en > time.time()

    return ejecutar_redis(_en_redis, fallback=_en_memoria)


def limpiar_sesion_admin(admin_sesion_id: str | None) -> None:
    if not admin_sesion_id:
        return
    clave = _clave_admin_sesion(admin_sesion_id)

    def _en_redis(redis):
        redis.delete(clave)

    def _en_memoria():
        _actividad_memoria.pop(clave, None)

    ejecutar_redis(_en_redis, fallback=_en_memoria)


def limpiar_sesiones_admin_usuario(id_usuario: int) -> None:
    prefijo = "admin_session:"

    def _en_redis(redis):
        for clave in redis.scan_iter(f"{prefijo}*"):
            raw = redis.get(clave)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if int(payload.get("id_usuario", 0)) == int(id_usuario):
                redis.delete(clave)

    def _en_memoria():
        for clave, (_expira_en, payload) in list(_actividad_memoria.items()):
            if clave.startswith(prefijo) and int(payload.get("id_usuario", 0)) == int(id_usuario):
                _actividad_memoria.pop(clave, None)

    ejecutar_redis(_en_redis, fallback=_en_memoria)


def expirar_sesion_admin_por_inactividad(
    db: Session,
    id_usuario: int,
    id_sesion: str | None = None,
    admin_sesion_id: str | None = None,
) -> None:
    from core.autenticacion.renovacion_tokens import revocar_sesion_refresh

    if id_sesion:
        revocar_sesion_refresh(db, id_sesion)
    else:
        from core.autenticacion.renovacion_tokens import revocar_sesiones_usuario

        revocar_sesiones_usuario(db, id_usuario)
    limpiar_sesion_admin(admin_sesion_id)
