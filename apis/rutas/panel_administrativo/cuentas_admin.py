from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import obtener_actor, requerir_super_admin
from core.infra.trazabilidad import ActorTrazabilidad
from esquemas.panel_administrativo.cuentas_admin import (
    CargoCreate,
    CargoResponse,
    CargoUpdate,
    CuentaAdminCreate,
    CuentaAdminDetalleResponse,
    CuentaAdminEstadoUpdate,
    CuentaAdminListResponse,
    CuentaAdminUpdate,
    PermisoResponse,
    SitiosAsignadosResponse,
    SitiosAsignadosUpdate,
)
from esquemas.panel_administrativo.atractivos import EstadoAtractivo, SitiosListResponse
from servicios.panel_administrativo.cuentas_admin import (
    actualizar_cargo,
    actualizar_cuenta_admin,
    actualizar_sitios_cuenta,
    cambiar_estado_cuenta_admin,
    crear_cargo,
    crear_cuenta_admin,
    eliminar_cargo,
    eliminar_cuenta_admin,
    listar_cargos,
    listar_cuentas_admin,
    listar_permisos,
    listar_sitios_catalogo_cuenta,
    obtener_cargo,
    obtener_cuenta_admin,
    obtener_sitios_cuenta_detalle,
)

router_cuentas = APIRouter(
    prefix="/admin/cuentas",
    tags=["Cuentas administrativas"],
    dependencies=[Depends(requerir_super_admin)],
)

router_cargos = APIRouter(
    prefix="/admin/cargos",
    tags=["Cargos administrativos"],
    dependencies=[Depends(requerir_super_admin)],
)

router_permisos = APIRouter(
    prefix="/admin/permisos",
    tags=["Permisos del panel"],
    dependencies=[Depends(requerir_super_admin)],
)


@router_permisos.get("", response_model=list[PermisoResponse])
def permisos_panel(db: Session = Depends(obtener_sesion)):
    return listar_permisos(db)


@router_cargos.get("", response_model=list[CargoResponse])
def cargos_panel(
    incluir_inactivos: bool = False,
    db: Session = Depends(obtener_sesion),
):
    return listar_cargos(db, incluir_inactivos)


@router_cargos.get("/{id_cargo}", response_model=CargoResponse)
def cargo_panel(id_cargo: int, db: Session = Depends(obtener_sesion)):
    return obtener_cargo(db, id_cargo)


@router_cargos.post("", response_model=CargoResponse, status_code=status.HTTP_201_CREATED)
def crear_cargo_panel(
    datos: CargoCreate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return crear_cargo(db, datos, actor)


@router_cargos.patch("/{id_cargo}", response_model=CargoResponse)
def actualizar_cargo_panel(
    id_cargo: int,
    datos: CargoUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return actualizar_cargo(db, id_cargo, datos, actor)


@router_cargos.delete("/{id_cargo}", response_model=CargoResponse)
def eliminar_cargo_panel(
    id_cargo: int,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return eliminar_cargo(db, id_cargo, actor)


@router_cuentas.get("", response_model=CuentaAdminListResponse)
def cuentas_admin(
    q: str | None = None,
    id_cargo: int | None = Query(default=None, ge=1),
    activo: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(obtener_sesion),
):
    return listar_cuentas_admin(
        db,
        q=q,
        id_cargo=id_cargo,
        activo=activo,
        page=page,
        page_size=page_size,
    )


@router_cuentas.get("/catalogo/sitios", response_model=SitiosListResponse)
def catalogo_sitios_cuenta(
    q: str | None = None,
    estado: EstadoAtractivo = "activo",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(obtener_sesion),
):
    return listar_sitios_catalogo_cuenta(db, q, estado, page, page_size)


@router_cuentas.get("/{id_usuario}/sitios", response_model=SitiosAsignadosResponse)
def sitios_cuenta_admin(id_usuario: int, db: Session = Depends(obtener_sesion)):
    sitios, items = obtener_sitios_cuenta_detalle(db, id_usuario)
    return SitiosAsignadosResponse(sitios=sitios, items=items)


@router_cuentas.put("/{id_usuario}/sitios", response_model=SitiosAsignadosResponse)
def actualizar_sitios_cuenta_admin(
    id_usuario: int,
    datos: SitiosAsignadosUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    sitios = actualizar_sitios_cuenta(db, id_usuario, datos.sitios, actor)
    _, items = obtener_sitios_cuenta_detalle(db, id_usuario)
    return SitiosAsignadosResponse(sitios=sitios, items=items)


@router_cuentas.get("/{id_usuario}", response_model=CuentaAdminDetalleResponse)
def cuenta_admin(id_usuario: int, db: Session = Depends(obtener_sesion)):
    return obtener_cuenta_admin(db, id_usuario)


@router_cuentas.post("", response_model=CuentaAdminDetalleResponse, status_code=status.HTTP_201_CREATED)
def crear_cuenta_admin_panel(
    datos: CuentaAdminCreate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return crear_cuenta_admin(db, datos, actor)


@router_cuentas.patch("/{id_usuario}", response_model=CuentaAdminDetalleResponse)
def actualizar_cuenta_admin_panel(
    id_usuario: int,
    datos: CuentaAdminUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return actualizar_cuenta_admin(db, id_usuario, datos, actor)


@router_cuentas.patch("/{id_usuario}/estado", response_model=CuentaAdminDetalleResponse)
def cambiar_estado_cuenta_admin_panel(
    id_usuario: int,
    datos: CuentaAdminEstadoUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return cambiar_estado_cuenta_admin(db, id_usuario, datos, actor)


@router_cuentas.delete("/{id_usuario}", status_code=status.HTTP_200_OK)
def eliminar_cuenta_admin_panel(
    id_usuario: int,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
):
    return eliminar_cuenta_admin(db, id_usuario, actor)
