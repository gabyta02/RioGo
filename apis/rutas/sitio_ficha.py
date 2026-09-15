from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion as obtener_db
from esquemas.sitio_ficha import SitioDetalleAppSalida
from servicios.sitio_ficha import obtener_sitio_por_id


router = APIRouter(
    prefix="/ficha_sitio",
    tags=["Ficha sitio"],
)


@router.get("/{id_sitio}", response_model=SitioDetalleAppSalida)
def api_obtener_ficha_sitio(id_sitio: int, db: Session = Depends(obtener_db)):
    sitio = obtener_sitio_por_id(db, id_sitio)

    if not sitio:
        raise HTTPException(status_code=404, detail="Sitio no encontrado")

    return sitio
