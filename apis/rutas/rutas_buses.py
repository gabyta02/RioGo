from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion as obtener_db
from esquemas.rutas_buses import LeyendaRutaBusSalida, RutaBusSalida
from servicios.rutas_buses import (
    listar_rutas_buses,
    obtener_leyenda_rutas_buses,
    obtener_ruta_bus_por_id,
)

router = APIRouter(
    prefix="/rutas-buses",
    tags=["Rutas de Buses"],
)


@router.get("/leyenda", response_model=list[LeyendaRutaBusSalida])
def api_leyenda_rutas_buses(db: Session = Depends(obtener_db)):
    return obtener_leyenda_rutas_buses(db)


@router.get("/{id_ruta}", response_model=RutaBusSalida)
def api_obtener_ruta_bus(id_ruta: int, db: Session = Depends(obtener_db)):
    ruta = obtener_ruta_bus_por_id(db, id_ruta)
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta de bus no encontrada")
    return ruta


@router.get("/", response_model=list[RutaBusSalida])
def api_listar_rutas_buses(
    estado: Optional[str] = Query(None),
    linea_bus: Optional[str] = Query(None),
    db: Session = Depends(obtener_db),
):
    return listar_rutas_buses(db, estado, linea_bus)
