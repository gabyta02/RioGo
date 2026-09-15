from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import obtener_actor, requerir_permiso, requerir_usuario_panel
from core.infra.trazabilidad import ActorTrazabilidad
from esquemas.panel_administrativo.rutas_turisticas import (
    EstadoRuta,
    EstadoRutaUpdate,
    ImagenRutaResponse,
    RutaGeometriaResponse,
    RutaGeometriaUpdate,
    RutaCreate,
    RutaResponse,
    RutasListResponse,
    RutaUpdate,
    SitioRutaResponse,
    TipoRuta,
)
from servicios.panel_administrativo.rutas_turisticas import (
    actualizar_ruta,
    buscar_sitios_para_ruta,
    cambiar_estado_ruta,
    crear_ruta,
    eliminar_ruta,
    guardar_geometria_ruta,
    guardar_imagen_ruta,
    listar_rutas,
    obtener_geometria_ruta,
)

router = APIRouter(
    prefix="/admin/rutas-turisticas",
    tags=["Rutas turisticas admin"],
    dependencies=[Depends(requerir_usuario_panel)],
)

_permiso_ver = Depends(requerir_permiso("routes", "ver"))
_permiso_crear = Depends(requerir_permiso("routes", "crear"))
_permiso_actualizar = Depends(requerir_permiso("routes", "actualizar"))
_permiso_eliminar = Depends(requerir_permiso("routes", "eliminar"))


@router.get("", response_model=RutasListResponse, dependencies=[_permiso_ver])
def rutas_turisticas(
    q: str | None = None,
    tipo_ruta: TipoRuta | None = None,
    estado: EstadoRuta = "all",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(obtener_sesion),
):
    return listar_rutas(db, q, tipo_ruta, estado, page, page_size)


@router.post(
    "",
    response_model=RutaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_permiso_crear],
)
def crear_ruta_turistica(
    datos: RutaCreate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return crear_ruta(db, datos, actor)


@router.post(
    "/imagen",
    response_model=ImagenRutaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_permiso_crear],
)
def subir_imagen_ruta(
    titulo_ruta: str = Form(...),
    archivo: UploadFile = File(...),
):
    return guardar_imagen_ruta(titulo_ruta, archivo)


@router.get("/sitios", response_model=list[SitioRutaResponse], dependencies=[_permiso_ver])
def sitios_para_ruta(
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(obtener_sesion),
):
    return buscar_sitios_para_ruta(db, q, limit)


@router.get(
    "/{id_ruta}/geometria",
    response_model=RutaGeometriaResponse,
    dependencies=[_permiso_ver],
)
def detalle_geometria_ruta(id_ruta: int, db: Session = Depends(obtener_sesion)):
    return obtener_geometria_ruta(db, id_ruta)


@router.put(
    "/{id_ruta}/geometria",
    response_model=RutaGeometriaResponse,
    dependencies=[_permiso_actualizar],
)
def actualizar_geometria_ruta(
    id_ruta: int,
    datos: RutaGeometriaUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return guardar_geometria_ruta(db, id_ruta, datos, actor)


@router.patch("/{id_ruta}", response_model=RutaResponse, dependencies=[_permiso_actualizar])
def actualizar_ruta_turistica(
    id_ruta: int,
    datos: RutaUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return actualizar_ruta(db, id_ruta, datos, actor)


@router.patch(
    "/{id_ruta}/estado",
    response_model=RutaResponse,
    dependencies=[_permiso_actualizar],
)
def actualizar_estado_ruta_turistica(
    id_ruta: int,
    datos: EstadoRutaUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return cambiar_estado_ruta(db, id_ruta, datos.activo, actor)


@router.delete("/{id_ruta}", response_model=RutaResponse, dependencies=[_permiso_eliminar])
def eliminar_ruta_turistica(
    id_ruta: int,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return eliminar_ruta(db, id_ruta, actor)
