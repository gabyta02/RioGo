from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.tarifa_acceso_consulta import (
    TarifaAccesoConsultaEntrada,
    TarifaAccesoConsultaSalida,
)
from servicios.chatboot_exploracion.tarifa_acceso_consulta import consultar_sitios_por_tarifa_acceso

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/tarifa-acceso-consulta", response_model=TarifaAccesoConsultaSalida)
def api_tarifa_acceso_consulta(
    payload: TarifaAccesoConsultaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return consultar_sitios_por_tarifa_acceso(db, payload)
