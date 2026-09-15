from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.horario_consulta import HorarioConsultaEntrada, HorarioConsultaSalida
from servicios.chatboot_exploracion.horario_consulta import consultar_sitios_por_horario

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/horario-consulta", response_model=HorarioConsultaSalida)
def api_horario_consulta(
    payload: HorarioConsultaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return consultar_sitios_por_horario(db, payload)
