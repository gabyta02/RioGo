from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.panel_administrativo.noticias import (
    NoticiasUsuarioEstadoResponse,
    NoticiasUsuarioListResponse,
)
from servicios.panel_administrativo.noticias import (
    listar_noticias_usuario,
    obtener_estado_noticias_usuario,
)

router = APIRouter(
    prefix="/noticias",
    tags=["Noticias usuario"],
)


@router.get("/usuario", response_model=NoticiasUsuarioListResponse)
def api_listar_noticias_usuario(db: Session = Depends(obtener_sesion)):
    """Lista noticias activas y vigentes para la app movil."""
    return listar_noticias_usuario(db)

@router.get(
    "/usuario/estado",
    response_model=NoticiasUsuarioEstadoResponse,
)
def api_obtener_estado_noticias_usuario(
    db: Session = Depends(obtener_sesion),
):
    return obtener_estado_noticias_usuario(db)
