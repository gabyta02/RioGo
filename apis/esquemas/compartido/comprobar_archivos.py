from pydantic import BaseModel


class ComprobarArchivosSalida(BaseModel):
    id_sitio: int
    tiene_documentos: bool
