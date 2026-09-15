from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class PermisoResponse(BaseModel):
    id_permiso: int
    codigo: str
    nombre: str
    activo: bool


class CargoBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    activo: bool = True
    permisos: list[str] = Field(default_factory=list)


class CargoCreate(CargoBase):
    pass


class CargoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    activo: bool | None = None
    permisos: list[str] | None = None


class CargoResponse(BaseModel):
    id_cargo: int
    nombre: str
    activo: bool
    permisos: list[str] = Field(default_factory=list)


class CuentaAdminBase(BaseModel):
    nombre_completo: str = Field(min_length=2, max_length=150)
    email: EmailStr
    id_cargo: int = Field(ge=1)
    activo: bool = True
    permisos: list[str] = Field(default_factory=list)


class CuentaAdminCreate(CuentaAdminBase):
    username: str | None = Field(default=None, min_length=3, max_length=80)


class CuentaAdminUpdate(BaseModel):
    nombre_completo: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    id_cargo: int | None = Field(default=None, ge=1)
    activo: bool | None = None
    permisos: list[str] | None = None


class CuentaAdminEstadoUpdate(BaseModel):
    activo: bool


class CuentaAdminListItem(BaseModel):
    id_usuario: int
    nombre_completo: str
    email: EmailStr
    username: str
    id_cargo: int | None
    cargo_nombre: str | None
    activo: bool
    ultimo_acceso_en: datetime | None
    iniciales: str


class CuentaAdminListResponse(BaseModel):
    items: list[CuentaAdminListItem]
    total: int
    page: int
    page_size: int


class CuentaAdminDetalleResponse(CuentaAdminListItem):
    permisos: list[str] = Field(default_factory=list)


class SitioAsignadoItem(BaseModel):
    id_sitio: int
    nombre: str
    categoria: str
    subcategoria: str | None = None
    activo: bool


class SitiosAsignadosResponse(BaseModel):
    sitios: list[int] = Field(default_factory=list)
    items: list[SitioAsignadoItem] = Field(default_factory=list)


class SitiosAsignadosUpdate(BaseModel):
    sitios: list[int] = Field(default_factory=list)
