from pydantic import BaseModel, Field

from esquemas.panel_administrativo.contenido_chatbots import TipoOrigen


class ChunkDescripcionRegenerarRequest(BaseModel):
    origen: TipoOrigen
    id_vinculo: int = Field(ge=1)


class ChunkDescripcionRegenerarResponse(BaseModel):
    origen: TipoOrigen
    id_vinculo: int
    id_fuente: int | None = None
    total_chunks: int = 0
    contenido: str = ""
