from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.atributos_booleanos_consulta import (
    AtributosBooleanosConsultaEntrada,
    AtributosBooleanosConsultaSalida,
)
from servicios.chatboot_exploracion.atributos_booleanos_consulta import consultar_sitios_por_atributos

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post(
    "/atributos-booleanos-consulta",
    response_model=AtributosBooleanosConsultaSalida,
)
def api_atributos_booleanos_consulta(
    payload: AtributosBooleanosConsultaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return consultar_sitios_por_atributos(db, payload)
