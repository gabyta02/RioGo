from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_exploracion.busqueda_ubicacion import BusquedaUbicacionEntrada
from esquemas.chatboot_exploracion.gis_consulta import GisConsultaEntrada, GisConsultaSalida
from servicios.chatboot_exploracion.busqueda_ubicacion import buscar_por_ubicacion

router = APIRouter(
    prefix="/chatboot/herramientas",
    tags=["Chatboot herramientas"],
)


@router.post("/gis-consulta", response_model=GisConsultaSalida)
def api_gis_consulta(
    payload: GisConsultaEntrada,
    db: Session = Depends(obtener_sesion),
):
    return buscar_por_ubicacion(
        db,
        BusquedaUbicacionEntrada(
            entidad=payload.entidad,
            tipo_busqueda="cercania",
            referencia_ubicacion=payload.punto_referencia,
            usar_ubicacion_usuario=payload.usar_ubicacion_usuario,
            distancia=payload.distancia,
            unidad=payload.unidad,
            excluir_zonas=payload.excluir_zonas,
            ubicacion_usuario=payload.ubicacion_usuario,
            ids_consulta=payload.ids_consulta,
        ),
    )
