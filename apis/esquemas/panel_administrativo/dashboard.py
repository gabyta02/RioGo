from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Periodo = Literal["all", "today", "week", "month", "year", "custom"]
Metric = Literal["usuarios", "atractivos", "preguntas", "favoritos", "noticias", "rutas"]
Estado = Literal["activo", "inactivo", "publicado", "borrador", "all"]
TipoChatbot = Literal["general", "sitio", "all"]
CanalChatbot = Literal["exploracion", "pregunta_directa", "all"]
AgruparPor = Literal["hour", "day", "week", "month", "year"]
CompararPor = Literal["none", "tipo_chatbot", "categoria", "subcategoria", "estado"]
Dimension = Literal["tipo_chatbot", "categoria", "subcategoria", "estado", "sitio"]
RankingTipo = Literal[
    "sitios_consultados",
    "sitios_favoritos",
    "categorias_buscadas",
    "subcategorias_buscadas",
    "rutas_consultadas",
]
OrdenConsultas = Literal["fecha_desc", "fecha_asc"]


class ValorVariacion(BaseModel):
    valor: int
    variacion: float


class DashboardResumenResponse(BaseModel):
    usuarios_registrados: ValorVariacion
    atractivos_activos: ValorVariacion
    preguntas_chatbots: ValorVariacion
    favoritos_guardados: ValorVariacion
    noticias_activas: ValorVariacion
    rutas_activas: ValorVariacion


class DashboardMetricResponse(BaseModel):
    metric: Metric
    periodo: Periodo
    valor: int


class PuntoSerie(BaseModel):
    label: str
    fecha: str
    valor: int


class SerieDashboard(BaseModel):
    name: str
    key: str
    data: list[PuntoSerie]


class DashboardSeriesResponse(BaseModel):
    metric: Metric
    periodo: Periodo
    agrupar_por: AgruparPor
    comparar_por: CompararPor
    series: list[SerieDashboard]


class DistribucionItem(BaseModel):
    label: str
    key: str
    valor: int


class DashboardDistribucionResponse(BaseModel):
    metric: Literal["usuarios", "preguntas", "favoritos", "atractivos", "noticias", "rutas"]
    dimension: Dimension
    periodo: Periodo
    items: list[DistribucionItem]


class RankingItem(BaseModel):
    posicion: int
    id: int | None = None
    nombre: str
    valor: int


class DashboardRankingResponse(BaseModel):
    tipo: RankingTipo
    periodo: Periodo
    limit: int
    items: list[RankingItem]


class ConsultaDashboardItem(BaseModel):
    id_mensaje: int
    pregunta: str
    tipo_chatbot: Literal["general", "sitio"]
    categoria: str | None = None
    subcategoria: str | None = None
    id_sitio: int | None = None
    sitio: str | None = None
    fecha: datetime


class DashboardConsultasResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ConsultaDashboardItem]


class SemanticaResumenItem(BaseModel):
    label: str | None = None
    valor: int


class SemanticaResumen(BaseModel):
    consultas_totales: int
    total_preguntas_usuario: int = 0
    total_mensajes_historial: int = 0
    preguntas_con_embedding: int = 0
    preguntas_sin_embedding: int = 0
    preguntas_analizadas: int = 0
    categoria_mas_frecuente: SemanticaResumenItem
    entidad_mas_relacionada: SemanticaResumenItem


class ConsultaSemanticaItem(BaseModel):
    id_mensaje: int
    pregunta: str
    categoria: str | None = None
    subcategoria: str | None = None
    entidad: str | None = None
    tipo_chatbot: Literal["general", "sitio"]
    canal: Literal["exploracion", "pregunta_directa"]
    fecha: datetime


class PreguntaRelacionadaSemanticaItem(BaseModel):
    pregunta: str
    total_consultas: int
    categoria: str | None = None
    subcategoria: str | None = None
    entidad: str | None = None
    tipo_chatbot: Literal["general", "sitio", "mixto"]
    canal: Literal["exploracion", "pregunta_directa", "mixto"]
    ultima_fecha: datetime


class GrupoSemanticoItem(BaseModel):
    id_grupo: int
    consulta_representativa: str
    total_consultas: int
    categoria: str | None = None
    subcategoria: str | None = None
    entidad: str | None = None
    tipo_chatbot: Literal["general", "sitio", "mixto"]
    canal: Literal["exploracion", "pregunta_directa", "mixto"]
    similitud_promedio: float
    ultima_fecha: datetime
    preguntas_relacionadas: list[PreguntaRelacionadaSemanticaItem]
    consultas: list[ConsultaSemanticaItem]


class DashboardSemanticaResponse(BaseModel):
    periodo: Periodo
    total_grupos: int
    total_consultas_agrupadas: int
    resumen: SemanticaResumen
    grupos: list[GrupoSemanticoItem]


class DashboardFiltros(BaseModel):
    periodo: Periodo = "month"
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    estado: Estado = "all"
    tipo_chatbot: TipoChatbot = "all"
    categoria: str | None = None
    subcategoria: str | None = None
    id_sitio: int | None = Field(default=None, ge=1)
