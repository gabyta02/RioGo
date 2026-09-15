from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.busqueda_referencia import (
    BusquedaReferenciaEntrada,
    BusquedaReferenciaSalida,
)
from esquemas.chatboot_exploracion.busqueda_ubicacion import BusquedaUbicacionEntrada
from servicios.chatboot_exploracion.busqueda_ubicacion import buscar_por_ubicacion

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/busqueda-referencia", response_model=BusquedaReferenciaSalida)
def api_busqueda_referencia(
    payload: BusquedaReferenciaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return buscar_por_ubicacion(
        db,
        BusquedaUbicacionEntrada(
            tipo_busqueda="zona_textual",
            referencia_ubicacion=payload.direccion_referencia,
            ids_consulta=payload.ids_consulta,
        ),
    )
