from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import requerir_permiso, requerir_usuario_panel
from esquemas.panel_administrativo.registro_acciones import (
    FiltroAccion,
    ModuloRegistro,
    ResultadoInicioSesion,
    RegistroAccionDetalleResponse,
    RegistroAccionesCatalogosResponse,
    RegistroAccionesListResponse,
    VistaRegistro,
)
from servicios.panel_administrativo.registro_acciones import (
    listar_registro_acciones,
    obtener_catalogos_registro_acciones,
    obtener_registro_accion,
)

router = APIRouter(
    prefix="/admin/registro-acciones",
    tags=["Registro de acciones admin"],
    dependencies=[Depends(requerir_usuario_panel), Depends(requerir_permiso("action_log"))],
)


@router.get("", response_model=RegistroAccionesListResponse)
def registro_acciones_admin(
    q: str | None = None,
    usuario: str | None = None,
    vista: VistaRegistro = "acciones",
    modulo: ModuloRegistro = "all",
    accion: FiltroAccion = "all",
    resultado: ResultadoInicioSesion = "all",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(obtener_sesion),
):
    return listar_registro_acciones(
        db,
        q,
        usuario,
        vista,
        modulo,
        accion,
        resultado,
        fecha_inicio,
        fecha_fin,
        page,
        page_size,
    )


@router.get("/catalogos", response_model=RegistroAccionesCatalogosResponse)
def catalogos_registro_acciones(db: Session = Depends(obtener_sesion)):
    return obtener_catalogos_registro_acciones(db)


@router.get("/{id_evento}", response_model=RegistroAccionDetalleResponse)
def detalle_registro_accion(
    id_evento: int,
    vista: VistaRegistro = "acciones",
    db: Session = Depends(obtener_sesion),
):
    return obtener_registro_accion(db, id_evento, vista)
