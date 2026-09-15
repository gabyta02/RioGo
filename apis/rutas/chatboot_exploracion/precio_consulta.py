from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.precio_consulta import PrecioConsultaEntrada, PrecioConsultaSalida
from servicios.chatboot_exploracion.precio_consulta import consultar_sitios_por_precio

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/precio-consulta", response_model=PrecioConsultaSalida)
def api_precio_consulta(
    payload: PrecioConsultaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return consultar_sitios_por_precio(db, payload)
