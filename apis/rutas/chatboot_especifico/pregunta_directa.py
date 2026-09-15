from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_especifico.pregunta_directa import PreguntaDirectaEntrada, PreguntaDirectaSalida
from servicios.chatboot_especifico.pregunta_directa import resolver_sitio_pregunta_directa

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/pregunta-directa", response_model=PreguntaDirectaSalida)
def api_pregunta_directa(
    payload: PreguntaDirectaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return resolver_sitio_pregunta_directa(db, payload)
