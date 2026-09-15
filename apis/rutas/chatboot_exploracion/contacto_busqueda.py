from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.contacto_busqueda import (
    ContactoBusquedaEntrada,
    ContactoBusquedaSalida,
)
from servicios.chatboot_exploracion.contacto_busqueda import buscar_sitios_por_contacto

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/contacto-busqueda", response_model=ContactoBusquedaSalida)
def api_contacto_busqueda(
    payload: ContactoBusquedaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return buscar_sitios_por_contacto(db, payload)
