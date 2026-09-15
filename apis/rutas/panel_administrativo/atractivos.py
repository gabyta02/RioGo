from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import obtener_actor, requerir_permiso, requerir_permiso_cualquiera, requerir_usuario_panel
from core.infra.trazabilidad import ActorTrazabilidad
from esquemas.panel_administrativo.atractivos import (
    CatalogoSimpleResponse,
    CategoriaCreate,
    CategoriaDetalleResponse,
    CategoriaResponse,
    CategoriaUpdate,
    EstadoActivoUpdate,
    EstadoAtractivo,
    PrecioFiltro,
    ServicioFiltro,
    ImagenSubidaResponse,
    SitioCreate,
    SitioDetalleResponse,
    SitioResponse,
    SitiosListResponse,
    SubcategoriaCreate,
    SubcategoriaResponse,
    SubcategoriaUpdate,
)
from servicios.panel_administrativo.atractivos import (
    actualizar_categoria,
    actualizar_sitio,
    actualizar_subcategoria,
    cambiar_estado_categoria,
    cambiar_estado_sitio,
    cambiar_estado_subcategoria,
    crear_categoria,
    crear_sitio,
    crear_subcategoria,
    eliminar_categoria,
    eliminar_sitio,
    eliminar_subcategoria,
    guardar_imagenes,
    listar_categorias,
    listar_categorias_detalle,
    listar_parroquias,
    listar_plataformas,
    listar_sitios,
    listar_subcategorias,
    obtener_sitio_detalle,
)

router = APIRouter(
    prefix="/admin/atractivos",
    tags=["Atractivos admin"],
    dependencies=[Depends(requerir_usuario_panel)],
)

_permiso_attractions_ver = Depends(requerir_permiso("attractions", "ver"))
_permiso_attractions_crear = Depends(requerir_permiso("attractions", "crear"))
_permiso_attractions_actualizar = Depends(requerir_permiso("attractions", "actualizar"))
_permiso_attractions_eliminar = Depends(requerir_permiso("attractions", "eliminar"))
_permiso_categories_ver = Depends(requerir_permiso("categories", "ver"))
_permiso_categories_crear = Depends(requerir_permiso("categories", "crear"))
_permiso_categories_actualizar = Depends(requerir_permiso("categories", "actualizar"))
_permiso_categories_eliminar = Depends(requerir_permiso("categories", "eliminar"))
_permiso_catalogo_lectura = Depends(
    requerir_permiso_cualquiera(("attractions", "ver"), ("categories", "ver"))
)


@router.get("", response_model=SitiosListResponse, dependencies=[_permiso_attractions_ver])
def sitios_turisticos(
    q: str | None = None,
    id_categoria: int | None = Query(default=None, ge=1),
    id_subcategoria: int | None = Query(default=None, ge=1),
    estado: EstadoAtractivo = "all",
    servicio: ServicioFiltro = "all",
    precio: PrecioFiltro = "all",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("attractions", "ver")),
):
    return listar_sitios(
        db,
        q,
        id_categoria,
        id_subcategoria,
        estado,
        servicio,
        precio,
        page,
        page_size,
        usuario,
    )


@router.post(
    "",
    response_model=SitioResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_permiso_attractions_crear],
)
def crear_atractivo_turistico(
    datos: SitioCreate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return crear_sitio(db, datos, actor)


@router.post(
    "/imagenes",
    response_model=list[ImagenSubidaResponse],
    dependencies=[_permiso_attractions_crear],
)
def subir_imagenes_atractivo(
    nombre_sitio: str = Form(min_length=2),
    archivos: list[UploadFile] = File(...),
):
    return guardar_imagenes(nombre_sitio, archivos)


@router.get("/categorias", response_model=list[CategoriaResponse], dependencies=[_permiso_catalogo_lectura])
def categorias_turisticas(
    incluir_inactivas: bool = False,
    db: Session = Depends(obtener_sesion),
):
    return listar_categorias(db, incluir_inactivas)


@router.get(
    "/categorias/detalle",
    response_model=list[CategoriaDetalleResponse],
    dependencies=[_permiso_categories_ver],
)
def categorias_turisticas_detalle(
    incluir_inactivas: bool = True,
    db: Session = Depends(obtener_sesion),
):
    return listar_categorias_detalle(db, incluir_inactivas)


@router.post(
    "/categorias",
    response_model=CategoriaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_permiso_categories_crear],
)
def crear_categoria_turistica(
    datos: CategoriaCreate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return crear_categoria(db, datos, actor)


@router.patch("/categorias/{id_categoria}", response_model=CategoriaResponse, dependencies=[_permiso_categories_actualizar])
def actualizar_categoria_turistica(
    id_categoria: int,
    datos: CategoriaUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return actualizar_categoria(db, id_categoria, datos, actor)


@router.patch(
    "/categorias/{id_categoria}/estado",
    response_model=CategoriaResponse,
    dependencies=[_permiso_categories_actualizar],
)
def actualizar_estado_categoria_turistica(
    id_categoria: int,
    datos: EstadoActivoUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return cambiar_estado_categoria(db, id_categoria, datos.activo, actor)


@router.delete("/categorias/{id_categoria}", response_model=CategoriaResponse, dependencies=[_permiso_categories_eliminar])
def eliminar_categoria_turistica(
    id_categoria: int,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return eliminar_categoria(db, id_categoria, actor)


@router.get("/subcategorias", response_model=list[SubcategoriaResponse], dependencies=[_permiso_catalogo_lectura])
def subcategorias_turisticas(
    id_categoria: int | None = Query(default=None, ge=1),
    incluir_inactivas: bool = False,
    db: Session = Depends(obtener_sesion),
):
    return listar_subcategorias(db, id_categoria, incluir_inactivas)


@router.post(
    "/subcategorias",
    response_model=SubcategoriaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_permiso_categories_crear],
)
def crear_subcategoria_turistica(
    datos: SubcategoriaCreate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return crear_subcategoria(db, datos, actor)


@router.patch("/subcategorias/{id_subcategoria}", response_model=SubcategoriaResponse, dependencies=[_permiso_categories_actualizar])
def actualizar_subcategoria_turistica(
    id_subcategoria: int,
    datos: SubcategoriaUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return actualizar_subcategoria(db, id_subcategoria, datos, actor)


@router.patch(
    "/subcategorias/{id_subcategoria}/estado",
    response_model=SubcategoriaResponse,
    dependencies=[_permiso_categories_actualizar],
)
def actualizar_estado_subcategoria_turistica(
    id_subcategoria: int,
    datos: EstadoActivoUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return cambiar_estado_subcategoria(db, id_subcategoria, datos.activo, actor)


@router.delete("/subcategorias/{id_subcategoria}", response_model=SubcategoriaResponse, dependencies=[_permiso_categories_eliminar])
def eliminar_subcategoria_turistica(
    id_subcategoria: int,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return eliminar_subcategoria(db, id_subcategoria, actor)


@router.get("/parroquias", response_model=list[CatalogoSimpleResponse], dependencies=[_permiso_attractions_ver])
def parroquias_turisticas(db: Session = Depends(obtener_sesion)):
    return listar_parroquias(db)


@router.get("/plataformas", response_model=list[CatalogoSimpleResponse], dependencies=[_permiso_attractions_ver])
def plataformas_turisticas(
    id_parroquia: int | None = Query(default=None, ge=1),
    db: Session = Depends(obtener_sesion),
):
    return listar_plataformas(db, id_parroquia)


@router.get("/{id_sitio}", response_model=SitioDetalleResponse, dependencies=[_permiso_attractions_ver])
def detalle_atractivo_turistico(
    id_sitio: int,
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("attractions", "ver")),
):
    return obtener_sitio_detalle(db, id_sitio, usuario)


@router.put("/{id_sitio}", response_model=SitioResponse, dependencies=[_permiso_attractions_actualizar])
def actualizar_atractivo_turistico(
    id_sitio: int,
    datos: SitioCreate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
    usuario: dict = Depends(requerir_permiso("attractions", "actualizar")),
):
    return actualizar_sitio(db, id_sitio, datos, actor, usuario)


@router.patch("/{id_sitio}/estado", response_model=SitioResponse, dependencies=[_permiso_attractions_actualizar])
def actualizar_estado_atractivo_turistico(
    id_sitio: int,
    datos: EstadoActivoUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
    usuario: dict = Depends(requerir_permiso("attractions", "actualizar")),
):
    return cambiar_estado_sitio(db, id_sitio, datos.activo, actor, usuario)


@router.delete("/{id_sitio}", response_model=SitioResponse, dependencies=[_permiso_attractions_eliminar])
def eliminar_atractivo_turistico(
    id_sitio: int,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
    usuario: dict = Depends(requerir_permiso("attractions", "eliminar")),
):
    return eliminar_sitio(db, id_sitio, actor, usuario)
