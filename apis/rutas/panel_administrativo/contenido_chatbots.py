from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.infra.conexion import obtener_sesion
from core.autenticacion.dependencias import obtener_actor, requerir_permiso, requerir_usuario_panel
from core.infra.trazabilidad import ActorTrazabilidad
from esquemas.panel_administrativo.chunks_descripcion import (
    ChunkDescripcionRegenerarRequest,
    ChunkDescripcionRegenerarResponse,
)
from esquemas.panel_administrativo.contenido_chatbots import (
    DocumentoChatbotCreate,
    DocumentoChatbotContenidoUpdate,
    DocumentoChatbotContenidoResponse,
    DocumentoChatbotResponse,
    DocumentoChatbotUpdate,
    EntidadChatbotResponse,
    RepositorioChatbotCreate,
    RepositorioChatbotResponse,
    RepositorioChatbotUpdate,
    TipoOrigen,
)
from servicios.panel_administrativo.chunks_descripcion import regenerar_chunk_descripcion
from servicios.panel_administrativo.contenido_chatbots import (
    actualizar_documento_chatbot,
    agregar_contenido_documento_chatbot,
    buscar_entidades_para_contenido,
    crear_documento_chatbot,
    crear_repositorio_chatbot,
    eliminar_documento_chatbot,
    eliminar_repositorio_chatbot,
    listar_repositorios_chatbot,
    obtener_contenido_documento_chatbot,
    renombrar_repositorio_chatbot,
)

router = APIRouter(
    prefix="/admin/contenido-chatbots",
    tags=["Contenido chatbots admin"],
    dependencies=[Depends(requerir_usuario_panel)],
)

_permiso_ver = Depends(requerir_permiso("chatbot_content", "ver"))
_permiso_crear = Depends(requerir_permiso("chatbot_content", "crear"))
_permiso_actualizar = Depends(requerir_permiso("chatbot_content", "actualizar"))
_permiso_eliminar = Depends(requerir_permiso("chatbot_content", "eliminar"))
_permiso_exportar = Depends(requerir_permiso("chatbot_content", "exportar"))


@router.get("/entidades", response_model=list[EntidadChatbotResponse], dependencies=[_permiso_ver])
def entidades_para_contenido_chatbot(
    q: str | None = None,
    tipo: TipoOrigen | Literal["all"] = "all",
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "ver")),
):
    return buscar_entidades_para_contenido(db, q, tipo, limit, usuario)


@router.get("/repositorios", response_model=list[RepositorioChatbotResponse], dependencies=[_permiso_ver])
def repositorios_contenido_chatbot(
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "ver")),
):
    return listar_repositorios_chatbot(db, usuario)


@router.post(
    "/repositorios",
    response_model=RepositorioChatbotResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_permiso_crear],
)
def crear_repositorio_contenido_chatbot(
    datos: RepositorioChatbotCreate,
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "crear")),
):
    return crear_repositorio_chatbot(db, datos, usuario)


@router.patch("/repositorios/{slug}", response_model=RepositorioChatbotResponse, dependencies=[_permiso_actualizar])
def renombrar_repositorio_contenido_chatbot(
    slug: str,
    datos: RepositorioChatbotUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "actualizar")),
):
    return renombrar_repositorio_chatbot(db, slug, datos, actor, usuario)


@router.delete("/repositorios/{slug}", response_model=RepositorioChatbotResponse, dependencies=[_permiso_eliminar])
def eliminar_repositorio_contenido_chatbot(
    slug: str,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "eliminar")),
):
    return eliminar_repositorio_chatbot(db, slug, actor, usuario)


@router.post(
    "/repositorios/{slug}/documentos",
    response_model=RepositorioChatbotResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_permiso_crear],
)
def crear_documento_contenido_chatbot(
    slug: str,
    datos: DocumentoChatbotCreate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "crear")),
):
    return crear_documento_chatbot(db, slug, datos, actor, usuario)


@router.patch("/documentos/{id_documento}", response_model=DocumentoChatbotResponse, dependencies=[_permiso_actualizar])
def actualizar_documento_contenido_chatbot(
    id_documento: int,
    datos: DocumentoChatbotUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "actualizar")),
):
    return actualizar_documento_chatbot(db, id_documento, datos, actor, usuario)


@router.get(
    "/documentos/{id_documento}/contenido",
    response_model=DocumentoChatbotContenidoResponse,
    dependencies=[_permiso_ver],
)
def obtener_contenido_documento_contenido_chatbot(
    id_documento: int,
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "ver")),
):
    return obtener_contenido_documento_chatbot(db, id_documento, usuario)


@router.put("/documentos/{id_documento}/contenido", response_model=DocumentoChatbotResponse, dependencies=[_permiso_actualizar])
def agregar_contenido_documento_contenido_chatbot(
    id_documento: int,
    datos: DocumentoChatbotContenidoUpdate,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "actualizar")),
):
    return agregar_contenido_documento_chatbot(db, id_documento, datos, actor, usuario)


@router.post("/chunks/descripcion", response_model=ChunkDescripcionRegenerarResponse, dependencies=[_permiso_exportar])
def regenerar_chunk_descripcion_contenido_chatbot(
    datos: ChunkDescripcionRegenerarRequest,
    db: Session = Depends(obtener_sesion),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "exportar")),
):
    return regenerar_chunk_descripcion(db, datos.origen, datos.id_vinculo, usuario)


@router.delete("/documentos/{id_documento}", response_model=DocumentoChatbotResponse, dependencies=[_permiso_eliminar])
def eliminar_documento_contenido_chatbot(
    id_documento: int,
    db: Session = Depends(obtener_sesion),
    actor: ActorTrazabilidad = Depends(obtener_actor),
    usuario: dict = Depends(requerir_permiso("chatbot_content", "eliminar")),
):
    return eliminar_documento_chatbot(db, id_documento, actor, usuario)
