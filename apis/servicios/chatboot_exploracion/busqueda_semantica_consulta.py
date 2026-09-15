from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.embeddings.embeddings import generar_embedding
from core.infra.filtro_sitios import normalizar_ids_consulta
from core.embeddings.semantica_evaluacion import (
    CandidatoSemanticoEvaluado,
    buscar_sitios_por_semantica,
)
from esquemas.chatboot_exploracion.busqueda_semantica_consulta import (
    BusquedaSemanticaConsultaEntrada,
    BusquedaSemanticaExito,
    BusquedaSemanticaFallo,
    BusquedaSemanticaSinSitios,
    CandidatoSemanticoItem,
    RetroalimentacionSemantica,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda

_MENSAJE_ENCONTRADO_ALCANCE = (
    "Se encontraron sitios relevantes dentro del filtro previo "
    "(categoría o referencia sugerida)."
)
_MENSAJE_FALLBACK_GLOBAL = (
    "No se encontraron coincidencias suficientes en el filtro previo; "
    "se amplió la búsqueda a todo el catálogo turístico."
)
_MENSAJE_GLOBAL_SIN_FILTRO = (
    "Búsqueda realizada en todo el catálogo (sin filtro previo)."
)
_MENSAJE_SIN_COINCIDENCIAS = (
    "No encontramos lugares que coincidan claramente con la búsqueda; "
    "se entregan candidatos relacionados para evaluación."
)
_MENSAJE_SIN_COINCIDENCIAS_GLOBAL = (
    "No encontramos lugares que coincidan claramente con la búsqueda; "
    "se entregan candidatos relacionados para evaluación."
)


def _estado_busqueda_para_ids(
    ids_sitio: list[int],
    candidatos_eval: list[CandidatoSemanticoEvaluado],
) -> str:
    if not ids_sitio:
        return "no_cumplido"
    ids_set = set(ids_sitio)
    if any(
        candidato.supera_umbral and candidato.id_sitio in ids_set
        for candidato in candidatos_eval
    ):
        return "cumplido"
    return "aproximado"


def _serializar_candidatos(
    candidatos: list[CandidatoSemanticoEvaluado],
) -> list[CandidatoSemanticoItem]:
    return [
        CandidatoSemanticoItem(
            id_sitio=item.id_sitio,
            nombre=item.nombre,
            score_semantico=item.score_semantico,
            score_final=item.score_final,
            boost_keywords=item.boost_keywords,
            keywords_match=item.keywords_match,
            supera_umbral=item.supera_umbral,
            motivo=item.motivo,
            id_chunk=item.id_chunk,
            contenido_chunk=item.contenido_chunk,
        )
        for item in candidatos
    ]


def _retroalimentacion_encontrado_alcance(ids_entrada: list[int]) -> RetroalimentacionSemantica:
    return RetroalimentacionSemantica(
        codigo="encontrado_en_alcance_previo",
        alcance_busqueda="ids_consulta",
        fallback_global_aplicado=False,
        ids_consulta_entrada=ids_entrada,
        mensaje=_MENSAJE_ENCONTRADO_ALCANCE,
    )


def _retroalimentacion_fallback_global(ids_entrada: list[int]) -> RetroalimentacionSemantica:
    return RetroalimentacionSemantica(
        codigo="busqueda_global_por_sin_coincidencias_en_alcance",
        alcance_busqueda="global",
        fallback_global_aplicado=True,
        ids_consulta_entrada=ids_entrada,
        mensaje=_MENSAJE_FALLBACK_GLOBAL,
    )


def _retroalimentacion_global_sin_filtro() -> RetroalimentacionSemantica:
    return RetroalimentacionSemantica(
        codigo="busqueda_global_sin_filtro_previo",
        alcance_busqueda="global",
        fallback_global_aplicado=False,
        ids_consulta_entrada=[],
        mensaje=_MENSAJE_GLOBAL_SIN_FILTRO,
    )


def _retroalimentacion_sin_coincidencias(
    *,
    ids_entrada: list[int],
    fallback_aplicado: bool,
) -> RetroalimentacionSemantica:
    if fallback_aplicado:
        return RetroalimentacionSemantica(
            codigo="sin_coincidencias_en_alcance_y_global",
            alcance_busqueda="global",
            fallback_global_aplicado=True,
            ids_consulta_entrada=ids_entrada,
            mensaje=_MENSAJE_SIN_COINCIDENCIAS,
        )
    return RetroalimentacionSemantica(
        codigo="sin_coincidencias_en_alcance_y_global",
        alcance_busqueda="global",
        fallback_global_aplicado=False,
        ids_consulta_entrada=[],
        mensaje=_MENSAJE_SIN_COINCIDENCIAS_GLOBAL,
    )


def _ejecutar_busqueda(
    db: Session,
    *,
    embedding: str,
    keywords: list[str],
    ids_consulta: list[int],
    excluir_terminos: list[str],
) -> tuple[list[int], list[CandidatoSemanticoEvaluado]]:
    return buscar_sitios_por_semantica(
        db,
        embedding=embedding,
        keywords=keywords,
        ids_consulta=ids_consulta,
        excluir_terminos=excluir_terminos,
    )


def consultar_sitios_por_busqueda_semantica(
    db: Session,
    payload: BusquedaSemanticaConsultaEntrada,
) -> BusquedaSemanticaExito | BusquedaSemanticaSinSitios | BusquedaSemanticaFallo:
    valor_estado = payload.model_dump(mode="json")
    texto = payload.texto_embeddings.strip()
    if not texto:
        mensaje = "El texto de búsqueda semántica no puede estar vacío."
        return BusquedaSemanticaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="busqueda_semantica",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    try:
        embedding = generar_embedding(texto, input_type="query")
    except HTTPException as exc:
        detalle = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return BusquedaSemanticaFallo(
            fallo=detalle,
            estado_busqueda=construir_estado_busqueda(
                nombre="busqueda_semantica",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=detalle,
            ),
        )
    except Exception as exc:
        mensaje = f"No se pudo generar el embedding para la búsqueda semántica: {exc}"
        return BusquedaSemanticaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="busqueda_semantica",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    if not embedding:
        mensaje = "No se pudo generar el embedding para la búsqueda semántica."
        return BusquedaSemanticaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="busqueda_semantica",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    ids_entrada = normalizar_ids_consulta(payload.ids_consulta)
    params_busqueda = {
        "embedding": embedding,
        "keywords": payload.keywords,
        "excluir_terminos": payload.excluir_terminos,
    }

    try:
        if ids_entrada:
            ids_sitio, candidatos_eval = _ejecutar_busqueda(
                db,
                ids_consulta=ids_entrada,
                **params_busqueda,
            )
            candidatos = _serializar_candidatos(candidatos_eval)
            if ids_sitio:
                retro = _retroalimentacion_encontrado_alcance(ids_entrada)
                return BusquedaSemanticaExito(
                    ids_sitio=ids_sitio,
                    candidatos=candidatos,
                    retroalimentacion=retro,
                    estado_busqueda=construir_estado_busqueda(
                        nombre="busqueda_semantica",
                        estado="cumplido",
                        valor=valor_estado,
                        ids_entrada=ids_entrada,
                        ids_salida=ids_sitio,
                        detalle=retro.mensaje,
                        retroalimentacion=retro,
                    ),
                )

            ids_sitio, candidatos_eval = _ejecutar_busqueda(
                db,
                ids_consulta=[],
                **params_busqueda,
            )
            candidatos = _serializar_candidatos(candidatos_eval)
            retroalimentacion = _retroalimentacion_fallback_global(ids_entrada)
            if not ids_sitio:
                retro_sin = _retroalimentacion_sin_coincidencias(
                    ids_entrada=ids_entrada,
                    fallback_aplicado=True,
                )
                return BusquedaSemanticaSinSitios(
                    sin_sitios=_MENSAJE_SIN_COINCIDENCIAS,
                    candidatos=candidatos,
                    retroalimentacion=retro_sin,
                    estado_busqueda=construir_estado_busqueda(
                        nombre="busqueda_semantica",
                        estado="no_cumplido",
                        valor=valor_estado,
                        ids_entrada=ids_entrada,
                        detalle=retro_sin.mensaje,
                        retroalimentacion=retro_sin,
                    ),
                )
            return BusquedaSemanticaExito(
                ids_sitio=ids_sitio,
                candidatos=candidatos,
                retroalimentacion=retroalimentacion,
                estado_busqueda=construir_estado_busqueda(
                    nombre="busqueda_semantica",
                    estado="aproximado",
                    valor=valor_estado,
                    ids_entrada=ids_entrada,
                    ids_salida=ids_sitio,
                    detalle=retroalimentacion.mensaje,
                    retroalimentacion=retroalimentacion,
                ),
            )

        ids_sitio, candidatos_eval = _ejecutar_busqueda(
            db,
            ids_consulta=[],
            **params_busqueda,
        )
        candidatos = _serializar_candidatos(candidatos_eval)
        retroalimentacion = _retroalimentacion_global_sin_filtro()
        if not ids_sitio:
            retro_sin = _retroalimentacion_sin_coincidencias(
                ids_entrada=[],
                fallback_aplicado=False,
            )
            return BusquedaSemanticaSinSitios(
                sin_sitios=_MENSAJE_SIN_COINCIDENCIAS_GLOBAL,
                candidatos=candidatos,
                retroalimentacion=retro_sin,
                estado_busqueda=construir_estado_busqueda(
                    nombre="busqueda_semantica",
                    estado="no_cumplido",
                    valor=valor_estado,
                    ids_entrada=[],
                    detalle=retro_sin.mensaje,
                    retroalimentacion=retro_sin,
                ),
            )
        return BusquedaSemanticaExito(
            ids_sitio=ids_sitio,
            candidatos=candidatos,
            retroalimentacion=retroalimentacion,
            estado_busqueda=construir_estado_busqueda(
                nombre="busqueda_semantica",
                estado=_estado_busqueda_para_ids(ids_sitio, candidatos_eval),
                valor=valor_estado,
                ids_entrada=[],
                ids_salida=ids_sitio,
                detalle=retroalimentacion.mensaje,
                retroalimentacion=retroalimentacion,
            ),
        )
    except Exception as exc:
        mensaje = f"Error al ejecutar la búsqueda semántica: {exc}"
        return BusquedaSemanticaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="busqueda_semantica",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )
