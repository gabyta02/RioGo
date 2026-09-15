from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.compartido.comprobar_archivos import ComprobarArchivosSalida
from servicios.compartido.comprobar_archivos import comprobar_archivos_sitio

router = APIRouter(prefix="/comprobar_archivos", tags=["Comprobar archivos"])


@router.get("/{id_sitio}", response_model=ComprobarArchivosSalida)
def api_comprobar_archivos_sitio(
    id_sitio: int,
    db: Session = Depends(obtener_sesion),
):
    tiene_documentos = comprobar_archivos_sitio(db, id_sitio)

    if tiene_documentos is None:
        raise HTTPException(status_code=404, detail="Sitio no encontrado")

    return {
        "id_sitio": id_sitio,
        "tiene_documentos": tiene_documentos,
    }
