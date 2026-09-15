from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion as obtener_db
from esquemas.sitio_turismo import (
    CargaCacheSitiosSalida,
    CategoriaSalida,
    SitioCacheActualizadoSalida,
    SitioCacheEliminadoSalida,
    SitioSalida,
    SubcategoriaSalida,
)
from servicios.sitios_turismo import (
    actualizar_sitio_cache,
    cargar_cache_sitios,
    eliminar_sitio_cache,
    listar_sitios_resumen,
    obtener_categorias,
    obtener_subcategorias,
)

router = APIRouter(
    prefix="/sitios",
    tags=["Sitios"],
)


@router.get("/categorias", response_model=List[CategoriaSalida])
def api_obtener_categorias(db: Session = Depends(obtener_db)):
    return obtener_categorias(db)

@router.get("/subcategorias", response_model=List[SubcategoriaSalida])
def api_obtener_subcategorias(
    id_categoria: int,
    db: Session = Depends(obtener_db)
):
    return obtener_subcategorias(db, id_categoria)


@router.post("/cache/cargar", response_model=CargaCacheSitiosSalida)
def api_cargar_cache_sitios(db: Session = Depends(obtener_db)):
    return cargar_cache_sitios(db)


@router.put("/cache/{id_sitio}", response_model=SitioCacheActualizadoSalida)
def api_actualizar_sitio_cache(
    id_sitio: int,
    db: Session = Depends(obtener_db),
):
    sitio = actualizar_sitio_cache(db, id_sitio)

    if not sitio:
        raise HTTPException(status_code=404, detail="Sitio no encontrado")

    return sitio


@router.delete("/cache/{id_sitio}", response_model=SitioCacheEliminadoSalida)
def api_eliminar_sitio_cache(id_sitio: int):
    return eliminar_sitio_cache(id_sitio)

@router.get("/", response_model=List[SitioSalida])
def api_listar_sitios(
    id_categoria: Optional[int] = Query(None),
    id_subcategoria: Optional[int] = Query(None),
    nombre: Optional[str] = Query(None),
    db: Session = Depends(obtener_db),
):
    return listar_sitios_resumen(
        db=db,
        id_categoria=id_categoria,
        id_subcategoria=id_subcategoria,
        nombre=nombre,
    )
