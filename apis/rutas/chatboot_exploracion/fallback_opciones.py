from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.fallback_opciones import (
    OpcionesFallbackExploracionSalida,
)
from servicios.chatboot_exploracion.fallback_opciones import (
    listar_opciones_fallback_exploracion,
)

router = APIRouter(
    prefix="/chatboot/fallback",
    tags=["Chatboot fallback"],
)


@router.get("/opciones-exploracion", response_model=OpcionesFallbackExploracionSalida)
def api_opciones_fallback_exploracion(
    db: Session = Depends(obtener_sesion),
):
    return listar_opciones_fallback_exploracion(db)
