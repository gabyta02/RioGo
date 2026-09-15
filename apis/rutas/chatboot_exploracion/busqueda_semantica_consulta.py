from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.busqueda_semantica_consulta import (
    BusquedaSemanticaConsultaEntrada,
    BusquedaSemanticaConsultaSalida,
)
from servicios.chatboot_exploracion.busqueda_semantica_consulta import consultar_sitios_por_busqueda_semantica

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post(
    "/busqueda-semantica-consulta",
    response_model=BusquedaSemanticaConsultaSalida,
)
def api_busqueda_semantica_consulta(
    payload: BusquedaSemanticaConsultaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return consultar_sitios_por_busqueda_semantica(db, payload)
