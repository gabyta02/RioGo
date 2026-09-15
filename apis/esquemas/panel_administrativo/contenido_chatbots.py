from typing import Literal
from pydantic import BaseModel, Field

TipoOrigen = Literal["sitio", "ruta"]


class EntidadChatbotResponse(BaseModel):
    origen: TipoOrigen
    id_vinculo: int
    nombre: str
    descripcion: str | None = None
    activo: bool


class RepositorioChatbotCreate(BaseModel):
    origen: TipoOrigen
    id_vinculo: int = Field(ge=1)


class RepositorioChatbotUpdate(BaseModel):
    nombre: str = Field(min_length=1, max_length=180)


class DocumentoChatbotCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=500)
    descripcion: str = Field(min_length=1, max_length=4000)


class DocumentoChatbotUpdate(BaseModel):
    titulo: str = Field(min_length=1, max_length=500)
    descripcion: str = Field(min_length=1, max_length=4000)


class DocumentoChatbotContenidoUpdate(BaseModel):
    contenido: str = Field(min_length=1)


class DocumentoChatbotContenidoResponse(BaseModel):
    id_documento: int
    contenido: str = ""


class DocumentoChatbotResponse(BaseModel):
    id_documento: int
    origen: TipoOrigen
    id_vinculo: int
    titulo: str
    descripcion: str
    ruta_archivo: str | None = None
    activo: bool
    total_secciones: int = 0


class RepositorioChatbotResponse(BaseModel):
    origen: TipoOrigen
    id_vinculo: int
    nombre: str
    slug: str
    ruta_directorio: str
    total_documentos: int
    documentos: list[DocumentoChatbotResponse] = Field(default_factory=list)
