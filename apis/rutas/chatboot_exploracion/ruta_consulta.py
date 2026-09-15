from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.ruta_consulta import RutaConsultaEntrada, RutaConsultaSalida
from servicios.chatboot_exploracion.ruta_consulta import consultar_rutas

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/ruta-consulta", response_model=RutaConsultaSalida)
def api_ruta_consulta(
    payload: RutaConsultaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return consultar_rutas(db, payload)
