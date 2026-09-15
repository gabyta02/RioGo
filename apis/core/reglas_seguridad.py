import os
import time
from dataclasses import dataclass, field
from threading import Lock

from fastapi import HTTPException, status

MAX_CORREOS_DISTINTOS_POR_IP = int(
    os.getenv("REGLAS_SEGURIDAD_MAX_CORREOS_DISTINTOS_IP", "5")
)
VENTANA_CORREOS_DISTINTOS_SEGUNDOS = int(
    os.getenv("REGLAS_SEGURIDAD_VENTANA_CORREOS_DISTINTOS_SEGUNDOS", "300")
)
BLOQUEO_CORREOS_DISTINTOS_SEGUNDOS = int(
    os.getenv("REGLAS_SEGURIDAD_BLOQUEO_CORREOS_DISTINTOS_SEGUNDOS", "900")
)


@dataclass(slots=True)
class _RegistroReglaCorreos:
    intentos: list[tuple[float, str]] = field(default_factory=list)
    bloqueado_hasta: float = 0.0


_lock = Lock()
_registros_correos_distintos: dict[str, _RegistroReglaCorreos] = {}


def _clave(regla: str, ip: str) -> str:
    return f"{regla}:{ip}"


def limpiar_reglas_seguridad_memoria() -> None:
    with _lock:
        _registros_correos_distintos.clear()


def validar_correos_distintos_por_ip(
    *,
    regla: str,
    ip: str,
    email: str,
    max_correos: int = MAX_CORREOS_DISTINTOS_POR_IP,
    ventana_segundos: int = VENTANA_CORREOS_DISTINTOS_SEGUNDOS,
    bloqueo_segundos: int = BLOQUEO_CORREOS_DISTINTOS_SEGUNDOS,
) -> None:
    ahora = time.time()
    email_normalizado = email.strip().lower()
    clave = _clave(regla, ip)

    with _lock:
        registro = _registros_correos_distintos.setdefault(clave, _RegistroReglaCorreos())

        if registro.bloqueado_hasta > ahora:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Intenta nuevamente mas tarde.",
            )

        desde = ahora - ventana_segundos
        registro.intentos = [
            (marca_tiempo, correo)
            for marca_tiempo, correo in registro.intentos
            if marca_tiempo >= desde
        ]
        registro.intentos.append((ahora, email_normalizado))

        correos_distintos = {correo for _marca_tiempo, correo in registro.intentos}
        if len(correos_distintos) > max_correos:
            registro.bloqueado_hasta = ahora + bloqueo_segundos
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Intenta nuevamente mas tarde.",
            )
