from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_especifico.historial_pregunta_directa import (
    HistorialPreguntaDirectaEntrada,
    HistorialPreguntaDirectaSalida,
)
from servicios.chatboot_especifico.historial_pregunta_directa import guardar_historial_pregunta_directa

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post(
    "/historial-pregunta-directa",
    response_model=HistorialPreguntaDirectaSalida,
)
def api_historial_pregunta_directa(
    payload: HistorialPreguntaDirectaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return guardar_historial_pregunta_directa(db, payload)
