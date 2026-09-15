from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.rutas_movil_turismo import (
    RutaMovilTurismo,
    RutasMovilTurismoResponse,
)
from servicios.rutas_movil_turismo import (
    listar_rutas_movil_turismo,
    obtener_ruta_movil_turismo_por_id,
)

router = APIRouter(
    prefix="/rutas-movil-turismo",
    tags=["Rutas turísticas móvil"],
)


@router.get("", response_model=RutasMovilTurismoResponse)
def api_listar_rutas_movil_turismo(db: Session = Depends(obtener_sesion)):
    """Lista todas las rutas turísticas activas"""
    return listar_rutas_movil_turismo(db)


@router.get("/{id_ruta}", response_model=RutaMovilTurismo)
def api_obtener_ruta_movil_turismo(
    id_ruta: int,
    db: Session = Depends(obtener_sesion),
):
    """Obtiene el detalle de una ruta turística"""
    return obtener_ruta_movil_turismo_por_id(db, id_ruta)
