from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import requerir_usuario_autenticado
from esquemas.historial_usuario import (
    ConversacionDetalleRespuesta,
    ConversacionesListaRespuesta,
)
from servicios.historial_usuario_service import (
    listar_conversaciones,
    obtener_mensajes,
)


router = APIRouter(
    prefix="/historial",
    tags=["Historial"],
)


@router.get("/conversaciones", response_model=ConversacionesListaRespuesta)
def api_listar_conversaciones(
    tipo: Literal["general", "sitio", "detalle", "todos"] = "todos",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
):
    return listar_conversaciones(
        db,
        int(usuario["id_usuario"]),
        tipo,
        limit,
        offset,
    )


@router.get(
    "/conversaciones/{id_conversacion}/mensajes",
    response_model=ConversacionDetalleRespuesta,
)
def api_obtener_mensajes(
    id_conversacion: int,
    tipo: Literal["general", "detalle", "sitio"] | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
):
    detalle = obtener_mensajes(
        db,
        int(usuario["id_usuario"]),
        id_conversacion,
        tipo,
        limit,
        offset,
    )
    if detalle is None:
        raise HTTPException(
            status_code=404, detail="Conversacion no encontrada"
        )
    return detalle