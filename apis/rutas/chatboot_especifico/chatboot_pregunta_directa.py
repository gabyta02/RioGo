from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from esquemas.chatboot_especifico.chatboot_pregunta_directa import (
    ChunksDocumentoEntrada,
    ChunksDocumentoSalida,
    ComoLlegarSalida,
    FichaSitioSalida,
    IdSitioEntrada,
    MultimediaSitioSalida,
    RutaDocumentoSalida,
)
from servicios.chatboot_especifico.chatboot_pregunta_directa import (
    buscar_chunks_documento,
    obtener_como_llegar,
    obtener_ficha_sitio_compacta,
    obtener_multimedia_sitio,
    obtener_ruta_documento,
)

router = APIRouter(
    prefix="/chatboot/pregunta-directa",
    tags=["Chatboot pregunta directa"],
)


@router.post("/ficha-sitio", response_model=FichaSitioSalida)
def api_ficha_sitio_pregunta_directa(
    payload: IdSitioEntrada,
    db: Session = Depends(obtener_sesion),
):
    return obtener_ficha_sitio_compacta(db, payload)


@router.post("/multimedia", response_model=MultimediaSitioSalida)
def api_multimedia_pregunta_directa(
    payload: IdSitioEntrada,
    db: Session = Depends(obtener_sesion),
):
    return obtener_multimedia_sitio(db, payload)


@router.post("/chunks-documento", response_model=ChunksDocumentoSalida)
def api_chunks_documento_pregunta_directa(
    payload: ChunksDocumentoEntrada,
    db: Session = Depends(obtener_sesion),
):
    return buscar_chunks_documento(db, payload)


@router.post("/como-llegar", response_model=ComoLlegarSalida)
def api_como_llegar_pregunta_directa(
    payload: IdSitioEntrada,
    db: Session = Depends(obtener_sesion),
):
    return obtener_como_llegar(db, payload)


@router.post("/ruta-documento", response_model=RutaDocumentoSalida)
def api_ruta_documento_pregunta_directa(
    payload: IdSitioEntrada,
    db: Session = Depends(obtener_sesion),
):
    return obtener_ruta_documento(db, payload)
