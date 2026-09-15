from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import requerir_permiso, requerir_usuario_panel
from core.autenticacion.permisos import obtener_sitios_permitidos
from esquemas.panel_administrativo.dashboard import (
    AgruparPor,
    CanalChatbot,
    CompararPor,
    DashboardConsultasResponse,
    DashboardDistribucionResponse,
    DashboardMetricResponse,
    DashboardRankingResponse,
    DashboardResumenResponse,
    DashboardSemanticaResponse,
    DashboardSeriesResponse,
    Dimension,
    Estado,
    Metric,
    OrdenConsultas,
    Periodo,
    RankingTipo,
    TipoChatbot,
)
from servicios.panel_administrativo.dashboard import (
    obtener_consultas,
    obtener_distribucion,
    obtener_metrica,
    obtener_ranking,
    obtener_resumen,
    obtener_semantica,
    obtener_series,
)

router = APIRouter(
    prefix="/admin/dashboard",
    tags=["Dashboard admin"],
    dependencies=[Depends(requerir_usuario_panel)],
)

_permiso_dashboard = Depends(requerir_permiso("dashboard"))
_permiso_analytics = Depends(requerir_permiso("analytics"))


def _sitios_alcance_dashboard(db: Session, usuario: dict) -> list[int] | None:
    sitios = obtener_sitios_permitidos(db, usuario, "analytics", "ver")
    if sitios:
        return sitios
    if sitios is None:
        return None
    return obtener_sitios_permitidos(db, usuario, "attractions", "ver")


@router.get("/resumen", response_model=DashboardResumenResponse, dependencies=[_permiso_dashboard])
def resumen_dashboard(
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("dashboard")),
):
    sitios = _sitios_alcance_dashboard(db, usuario)
    return obtener_resumen(db, periodo, fecha_inicio, fecha_fin, sitios_permitidos=sitios)


@router.get("/metricas", response_model=DashboardMetricResponse, dependencies=[_permiso_dashboard])
def metricas_dashboard(
    metric: Metric,
    periodo: Periodo = "all",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    estado: Estado = "all",
    tipo_chatbot: TipoChatbot = "all",
    categoria: str | None = None,
    subcategoria: str | None = None,
    id_sitio: int | None = Query(default=None, ge=1),
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("dashboard")),
):
    sitios = _sitios_alcance_dashboard(db, usuario)
    return obtener_metrica(
        db,
        metric,
        periodo,
        fecha_inicio,
        fecha_fin,
        estado,
        tipo_chatbot,
        categoria,
        subcategoria,
        id_sitio,
        sitios_permitidos=sitios,
    )


@router.get("/series", response_model=DashboardSeriesResponse, dependencies=[_permiso_dashboard])
def series_dashboard(
    metric: Metric,
    agrupar_por: AgruparPor,
    periodo: Periodo = "month",
    comparar_por: CompararPor = "none",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    tipo_chatbot: TipoChatbot = "all",
    categoria: str | None = None,
    subcategoria: str | None = None,
    id_sitio: int | None = Query(default=None, ge=1),
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("dashboard")),
):
    sitios = _sitios_alcance_dashboard(db, usuario)
    return obtener_series(
        db,
        metric,
        agrupar_por,
        periodo,
        comparar_por,
        fecha_inicio,
        fecha_fin,
        tipo_chatbot,
        categoria,
        subcategoria,
        id_sitio,
        sitios_permitidos=sitios,
    )


@router.get("/distribucion", response_model=DashboardDistribucionResponse, dependencies=[_permiso_dashboard])
def distribucion_dashboard(
    metric: str,
    dimension: Dimension,
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("dashboard")),
):
    sitios = _sitios_alcance_dashboard(db, usuario)
    return obtener_distribucion(
        db,
        metric,
        dimension,
        periodo,
        fecha_inicio,
        fecha_fin,
        limit,
        sitios_permitidos=sitios,
    )


@router.get("/ranking", response_model=DashboardRankingResponse, dependencies=[_permiso_dashboard])
def ranking_dashboard(
    tipo: RankingTipo,
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    limit: int = Query(default=5, ge=1, le=100),
    categoria: str | None = None,
    subcategoria: str | None = None,
    tipo_chatbot: TipoChatbot = "all",
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("dashboard")),
):
    sitios = _sitios_alcance_dashboard(db, usuario)
    return obtener_ranking(
        db,
        tipo,
        periodo,
        fecha_inicio,
        fecha_fin,
        limit,
        categoria,
        subcategoria,
        tipo_chatbot,
        sitios_permitidos=sitios,
    )


@router.get("/consultas", response_model=DashboardConsultasResponse, dependencies=[_permiso_analytics])
def consultas_dashboard(
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    tipo_chatbot: TipoChatbot = "all",
    categoria: str | None = None,
    subcategoria: str | None = None,
    id_sitio: int | None = Query(default=None, ge=1),
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    orden: OrdenConsultas = "fecha_desc",
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("analytics")),
):
    sitios = _sitios_alcance_dashboard(db, usuario)
    return obtener_consultas(
        db,
        periodo,
        fecha_inicio,
        fecha_fin,
        tipo_chatbot,
        categoria,
        subcategoria,
        id_sitio,
        q,
        page,
        page_size,
        orden,
        sitios_permitidos=sitios,
    )


@router.get("/semantica", response_model=DashboardSemanticaResponse, dependencies=[_permiso_analytics])
def semantica_dashboard(
    periodo: Periodo = "month",
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    categoria: str | None = None,
    subcategoria: str | None = None,
    limit: int = Query(default=30, ge=1, le=200),
    umbral: float = Query(default=0.82, ge=0, le=1),
    canal: CanalChatbot = "all",
    max_consultas_analisis: int = Query(default=10000, ge=1, le=50000),
    min_total_consultas: int = Query(default=20, ge=1, le=50000),
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("analytics")),
):
    sitios = _sitios_alcance_dashboard(db, usuario)
    return obtener_semantica(
        db,
        periodo,
        fecha_inicio,
        fecha_fin,
        categoria,
        subcategoria,
        limit,
        umbral,
        canal,
        max_consultas_analisis,
        min_total_consultas,
        sitios_permitidos=sitios,
    )
