from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import requerir_usuario_autenticado
from esquemas.favoritos_user import (
    FavoritoAccionRespuesta,
    FavoritoEstadoRespuesta,
    FavoritosListaRespuesta,
)
from servicios.favoritos_user import (
    agregar_favorito,
    eliminar_favorito,
    listar_favoritos,
    verificar_estado_favorito,
)

router = APIRouter(
    prefix="/favoritos",
    tags=["Favoritos"],
)


@router.get("", response_model=FavoritosListaRespuesta)
def api_listar_favoritos(
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
):
    id_usuario = usuario["id_usuario"]
    return listar_favoritos(db, id_usuario)


@router.post("/{id_sitio}", response_model=FavoritoAccionRespuesta)
def api_agregar_favorito(
    id_sitio: int,
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
):
    id_usuario = usuario["id_usuario"]
    return agregar_favorito(db, id_usuario, id_sitio)


@router.delete("/{id_sitio}", response_model=FavoritoAccionRespuesta)
def api_eliminar_favorito(
    id_sitio: int,
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
):
    id_usuario = usuario["id_usuario"]
    return eliminar_favorito(db, id_usuario, id_sitio)


@router.get("/{id_sitio}/estado", response_model=FavoritoEstadoRespuesta)
def api_verificar_estado_favorito(
    id_sitio: int,
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_usuario_autenticado),
):
    id_usuario = usuario["id_usuario"]
    es_favorito = verificar_estado_favorito(db, id_usuario, id_sitio)
    return {
        "id_sitio": id_sitio,
        "es_favorito": es_favorito,
    }
