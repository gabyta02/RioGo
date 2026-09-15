from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload, selectinload

from core.chatboot_evaluacion.chunk_sitio_evaluacion import (
    MAX_CHUNKS_SALIDA,
    ChunkSitioEvaluado,
    buscar_chunks_en_sitio,
)
from core.chatboot_evaluacion.horario_compacto import construir_horario_compacto
from core.chatboot_evaluacion.precio_compacto import construir_texto_precio_resumen
from core.embeddings.embeddings import generar_embeddings
from esquemas.chatboot_especifico.chatboot_pregunta_directa import (
    AtributosSitioCompacto,
    ChunksDocumentoEntrada,
    ChunksDocumentoExito,
    ChunkDocumentoItem,
    ComoLlegarExito,
    ContactoCompacto,
    CriterioSeleccionDocumento,
    FichaSitioCompactaExito,
    FichaSitioFallo,
    HorarioCompacto,
    IdSitioEntrada,
    ImagenSitioItem,
    MultimediaSitioExito,
    PrecioCompacto,
    RutaDocumentoExito,
    TarifaCompacta,
    UbicacionSitio,
)
from modelos.sitios_turismo import Horario, Sitio


def _nombre_catalogo(relacion) -> str | None:
    if relacion is None or not getattr(relacion, "activo", True):
        return None
    return str(relacion.nombre)


def _opciones_ficha_compacta():
    return (
        joinedload(Sitio.categoria),
        joinedload(Sitio.subcategoria),
        joinedload(Sitio.parroquia),
        joinedload(Sitio.plataforma),
        joinedload(Sitio.horario).selectinload(Horario.detalles),
        joinedload(Sitio.precio),
        selectinload(Sitio.tarifas),
        selectinload(Sitio.contactos),
    )


def _obtener_sitio_activo(db: Session, id_sitio: int) -> Sitio | None:
    return (
        db.query(Sitio)
        .filter(Sitio.id_sitio == id_sitio, Sitio.activo.is_(True))
        .first()
    )


def _obtener_sitio_ficha(db: Session, id_sitio: int) -> Sitio | None:
    return (
        db.query(Sitio)
        .options(*_opciones_ficha_compacta())
        .filter(Sitio.id_sitio == id_sitio, Sitio.activo.is_(True))
        .first()
    )


def _construir_precio_compacto(sitio: Sitio) -> PrecioCompacto:
    tarifas_activas = [
        TarifaCompacta(
            condicion=tarifa.condicion,
            precio=float(tarifa.precio),
        )
        for tarifa in sitio.tarifas
        if getattr(tarifa, "activo", True)
    ]
    return PrecioCompacto(
        texto=construir_texto_precio_resumen(sitio),
        precio_min=sitio.precio.precio_min if sitio.precio else None,
        precio_max=sitio.precio.precio_max if sitio.precio else None,
        etiqueta_precio=(
            str(sitio.precio.etiqueta_precio)
            if sitio.precio and sitio.precio.etiqueta_precio
            else None
        ),
        tarifas=tarifas_activas,
    )


def _construir_atributos(sitio: Sitio) -> AtributosSitioCompacto:
    return AtributosSitioCompacto(
        es_gratuito=sitio.es_gratuito,
        parqueadero=sitio.parqueadero,
        tiene_wifi=sitio.tiene_wifi,
        accesibilidad=sitio.accesibilidad,
        permite_mascotas=sitio.permite_mascotas,
    )


def _construir_contactos(sitio: Sitio) -> list[ContactoCompacto]:
    return [
        ContactoCompacto(nombre=contacto.nombre, contenido=contacto.contenido)
        for contacto in sitio.contactos
        if getattr(contacto, "activo", True)
    ]


def _normalizar_mensajes_chunk(mensaje_chunk: str | list[str]) -> list[str]:
    if isinstance(mensaje_chunk, str):
        candidatos = [mensaje_chunk]
    else:
        candidatos = list(mensaje_chunk)

    mensajes: list[str] = []
    for item in candidatos:
        texto = str(item or "").strip()
        if texto:
            mensajes.append(texto)
    return mensajes


def _serializar_chunks(candidatos: list[ChunkSitioEvaluado]) -> list[ChunkDocumentoItem]:
    return [
        ChunkDocumentoItem(
            id_chunk=item.id_chunk,
            contenido=item.contenido,
            score_semantico=item.score_semantico,
            score_final=item.score_final,
            keywords_match=item.keywords_match,
        )
        for item in candidatos[:MAX_CHUNKS_SALIDA]
    ]


def obtener_ficha_sitio_compacta(
    db: Session,
    payload: IdSitioEntrada,
) -> FichaSitioCompactaExito | FichaSitioFallo:
    sitio = _obtener_sitio_ficha(db, payload.id_sitio)
    if not sitio:
        return FichaSitioFallo(fallo="Sitio no encontrado.")

    horario_data = construir_horario_compacto(sitio.horario)
    return FichaSitioCompactaExito(
        id_sitio=sitio.id_sitio,
        nombre=sitio.nombre,
        categoria=sitio.categoria.nombre if sitio.categoria else "Sin categoría",
        subcategoria=(
            sitio.subcategoria.nombre if sitio.subcategoria else "Sin subcategoría"
        ),
        parroquia=_nombre_catalogo(sitio.parroquia),
        plataforma=_nombre_catalogo(sitio.plataforma),
        horario=HorarioCompacto(**horario_data),
        contactos=_construir_contactos(sitio),
        precio=_construir_precio_compacto(sitio),
        atributos=_construir_atributos(sitio),
    )


def obtener_multimedia_sitio(
    db: Session,
    payload: IdSitioEntrada,
) -> MultimediaSitioExito | FichaSitioFallo:
    sitio = _obtener_sitio_activo(db, payload.id_sitio)
    if not sitio:
        return FichaSitioFallo(fallo="Sitio no encontrado.")

    filas = db.execute(
        text(
            """
            SELECT url, es_principal
            FROM turismo.multimedia
            WHERE id_sitio = :id_sitio
              AND activo = TRUE
            ORDER BY es_principal DESC NULLS LAST, id_multimedia ASC
            """
        ),
        {"id_sitio": payload.id_sitio},
    ).mappings().all()

    imagenes = [
        ImagenSitioItem(
            url=normalizar_url_imagen(str(fila["url"])),
            es_principal=bool(fila["es_principal"]),
        )
        for fila in filas
    ]
    return MultimediaSitioExito(id_sitio=payload.id_sitio, imagenes=imagenes)


def buscar_chunks_documento(
    db: Session,
    payload: ChunksDocumentoEntrada,
) -> ChunksDocumentoExito | FichaSitioFallo:
    sitio = _obtener_sitio_activo(db, payload.id_sitio)
    if not sitio:
        return FichaSitioFallo(fallo="Sitio no encontrado.")

    mensajes = _normalizar_mensajes_chunk(payload.mensaje_chunk)
    if not mensajes:
        return FichaSitioFallo(fallo="mensaje_chunk vacío.")

    vectores = generar_embeddings(mensajes, input_type="query")
    embeddings = [vector for vector in vectores if vector]

    if not embeddings:
        return FichaSitioFallo(fallo="No se pudo generar embedding para mensaje_chunk.")

    candidatos = buscar_chunks_en_sitio(
        db,
        id_sitio=payload.id_sitio,
        embeddings=embeddings,
        keywords=payload.keywords,
    )

    if not candidatos:
        return ChunksDocumentoExito(
            estado="chunk_baja_precision",
            id_sitio=payload.id_sitio,
            score_maximo=0.0,
            chunks=[],
        )

    hay_validos = any(item.supera_umbral for item in candidatos)
    score_maximo = candidatos[0].score_final
    return ChunksDocumentoExito(
        estado="ok" if hay_validos else "chunk_baja_precision",
        id_sitio=payload.id_sitio,
        score_maximo=score_maximo,
        chunks=_serializar_chunks(candidatos),
    )


def obtener_como_llegar(
    db: Session,
    payload: IdSitioEntrada,
) -> ComoLlegarExito | FichaSitioFallo:
    fila = db.execute(
        text(
            """
            SELECT
                s.id_sitio,
                s.nombre,
                ST_Y(s.ubicacion::geometry) AS lat,
                ST_X(s.ubicacion::geometry) AS lon
            FROM turismo.sitio s
            WHERE s.id_sitio = :id_sitio
              AND s.activo = TRUE
              AND s.ubicacion IS NOT NULL
            """
        ),
        {"id_sitio": payload.id_sitio},
    ).mappings().first()

    if not fila:
        sitio = _obtener_sitio_activo(db, payload.id_sitio)
        if not sitio:
            return FichaSitioFallo(fallo="Sitio no encontrado.")
        return FichaSitioFallo(fallo="El sitio no tiene ubicación registrada.")

    return ComoLlegarExito(
        id_sitio=int(fila["id_sitio"]),
        nombre=str(fila["nombre"]),
        ubicacion=UbicacionSitio(
            lat=float(fila["lat"]),
            lon=float(fila["lon"]),
        ),
    )


def _tamano_archivo(ruta_archivo: str | None) -> int:
    if not ruta_archivo:
        return -1
    path = Path(ruta_archivo)
    if not path.is_file():
        return -1
    return path.stat().st_size


def _seleccionar_documento_principal(
    documentos: list[dict],
) -> tuple[dict, CriterioSeleccionDocumento]:
    if len(documentos) == 1:
        return documentos[0], "unico"

    con_archivo = [
        doc
        for doc in documentos
        if _tamano_archivo(doc.get("ruta_archivo")) >= 0
    ]
    if con_archivo:
        elegido = max(
            con_archivo,
            key=lambda doc: _tamano_archivo(doc.get("ruta_archivo")),
        )
        return elegido, "archivo_mayor"

    con_secciones = [doc for doc in documentos if int(doc.get("total_secciones") or 0) > 0]
    if con_secciones:
        elegido = max(con_secciones, key=lambda doc: int(doc["total_secciones"]))
        return elegido, "mas_secciones"

    elegido = max(documentos, key=lambda doc: int(doc["id_documento"]))
    return elegido, "mas_reciente"


def obtener_ruta_documento(
    db: Session,
    payload: IdSitioEntrada,
) -> RutaDocumentoExito | FichaSitioFallo:
    sitio = _obtener_sitio_activo(db, payload.id_sitio)
    if not sitio:
        return FichaSitioFallo(fallo="Sitio no encontrado.")

    filas = db.execute(
        text(
            """
            SELECT
                d.id_documento,
                d.titulo,
                d.ruta_archivo,
                COUNT(c.id_chunk)::INT AS total_secciones
            FROM turismo.sitio_documento d
            LEFT JOIN turismo.chunk_fuente cf ON cf.id_documento = d.id_documento
            LEFT JOIN turismo.chunk c ON c.id_fuente = cf.id_fuente
            WHERE d.origen = 'sitio'
              AND d.id_vinculo = :id_sitio
              AND d.activo = TRUE
              AND d.ruta_archivo IS NOT NULL
              AND btrim(d.ruta_archivo) <> ''
            GROUP BY d.id_documento, d.titulo, d.ruta_archivo
            ORDER BY d.id_documento DESC
            """
        ),
        {"id_sitio": payload.id_sitio},
    ).mappings().all()

    if not filas:
        return FichaSitioFallo(fallo="No hay documento activo para este sitio.")

    documentos = [dict(fila) for fila in filas]
    elegido, criterio = _seleccionar_documento_principal(documentos)

    return RutaDocumentoExito(
        id_sitio=payload.id_sitio,
        id_documento=int(elegido["id_documento"]),
        titulo=str(elegido["titulo"]),
        ruta_archivo=str(elegido["ruta_archivo"]),
        total_documentos=len(documentos),
        criterio_seleccion=criterio,
    )
