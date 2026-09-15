from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import obtener_actor, requerir_permiso, requerir_usuario_panel
from core.infra.trazabilidad import ActorTrazabilidad
from esquemas.panel_administrativo.noticias import (
    EstadoNoticia,
    EstadoNoticiaUpdate,
    ImagenNoticiaResponse,
    NoticiaCreate,
    NoticiaResponse,
    NoticiasListResponse,
    NoticiaUpdate,
)
from servicios.panel_administrativo.noticias import (
    actualizar_noticia,
    cambiar_estado_noticia,
    crear_noticia,
    eliminar_noticia,
    guardar_imagen_noticia,
    listar_noticias,
    obtener_noticia,
)

router = APIRouter(
    prefix="/admin/noticias",
    tags=["Noticias admin"],
    dependencies=[Depends(requerir_usuario_panel)],
)

_permiso_ver = Depends(requerir_permiso("noticias", "ver"))
_permiso_crear = Depends(requerir_permiso("noticias", "crear"))
_permiso_actualizar = Depends(requerir_permiso("noticias", "actualizar"))
_permiso_eliminar = Depends(requerir_permiso("noticias", "eliminar"))


@router.get("", response_model=NoticiasListResponse, dependencies=[_permiso_ver])
def noticias_admin(
    q: str | None = None,
    estado: EstadoNoticia = "all",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(obtener_sesion),
):
    return listar_noticias(db, q, estado, page, page_size)


@router.post(
    "",
    response_model=NoticiaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_permiso_crear],
)
def crear_noticia_admin(
    datos: NoticiaCreate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return crear_noticia(db, datos, actor)


@router.post(
    "/imagen",
    response_model=ImagenNoticiaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_permiso_crear],
)
def subir_imagen_noticia(
    titulo_noticia: str = Form(...),
    archivo: UploadFile = File(...),
):
    return guardar_imagen_noticia(titulo_noticia, archivo)


@router.get("/{id_noticia}", response_model=NoticiaResponse, dependencies=[_permiso_ver])
def detalle_noticia_admin(id_noticia: int, db: Session = Depends(obtener_sesion)):
    return obtener_noticia(db, id_noticia)


@router.patch("/{id_noticia}", response_model=NoticiaResponse, dependencies=[_permiso_actualizar])
def actualizar_noticia_admin(
    id_noticia: int,
    datos: NoticiaUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return actualizar_noticia(db, id_noticia, datos, actor)


@router.patch(
    "/{id_noticia}/estado",
    response_model=NoticiaResponse,
    dependencies=[_permiso_actualizar],
)
def actualizar_estado_noticia_admin(
    id_noticia: int,
    datos: EstadoNoticiaUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return cambiar_estado_noticia(db, id_noticia, datos.activa, actor)


@router.delete("/{id_noticia}", response_model=NoticiaResponse, dependencies=[_permiso_eliminar])
def eliminar_noticia_admin(
    id_noticia: int,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return eliminar_noticia(db, id_noticia, actor)
