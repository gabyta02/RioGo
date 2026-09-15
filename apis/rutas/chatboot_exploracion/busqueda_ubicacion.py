from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.busqueda_ubicacion import (
    BusquedaUbicacionEntrada,
    BusquedaUbicacionSalida,
)
from servicios.chatboot_exploracion.busqueda_ubicacion import buscar_por_ubicacion

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/busqueda-ubicacion", response_model=BusquedaUbicacionSalida)
def api_busqueda_ubicacion(
    payload: BusquedaUbicacionEntrada,
    db: Session = Depends(obtener_sesion),
):
    return buscar_por_ubicacion(db, payload)
