from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.historial_exploracion import (
    HistorialExploracionEntrada,
    HistorialExploracionSalida,
)
from servicios.chatboot_exploracion.historial_exploracion import guardar_historial_exploracion

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/historial-exploracion", response_model=HistorialExploracionSalida)
def api_historial_exploracion(
    payload: HistorialExploracionEntrada,
    db: Session = Depends(obtener_sesion),
):
    return guardar_historial_exploracion(db, payload)

