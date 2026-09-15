from sqlalchemy.orm import Session

from core.infra.filtro_sitios import normalizar_ids_consulta
from core.chatboot_evaluacion.gis_evaluacion import (
    CandidatoGisEvaluado,
    ResultadoGisEvaluacion,
    filtrar_rutas_por_gis,
    filtrar_sitios_por_gis,
    formatear_distancia_aproximada,
)
from esquemas.chatboot_exploracion.gis_consulta import (
    CandidatoGisRutaItem,
    CandidatoGisSitioItem,
    GisConsultaEntrada,
    GisConsultaExitoRutas,
    GisConsultaExitoSitios,
    GisConsultaFallo,
    GisConsultaSinRutas,
    GisConsultaSinSitios,
    RetroalimentacionGis,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda


def _validar_origen(
    payload: GisConsultaEntrada,
) -> GisConsultaFallo | None:
    if payload.usar_ubicacion_usuario and (
        payload.ubicacion_usuario is None
        or payload.ubicacion_usuario.coordenadas() is None
    ):
        mensaje = (
            "Cuando usar_ubicacion_usuario es true, "
            "debe enviar ubicacion_usuario con lat y lon."
        )
        return GisConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="gis",
                estado="error",
                valor=payload.model_dump(mode="json"),
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    if not payload.usar_ubicacion_usuario and not payload.punto_referencia.strip():
        mensaje = "Debe indicar usar_ubicacion_usuario o un punto_referencia."
        return GisConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="gis",
                estado="error",
                valor=payload.model_dump(mode="json"),
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    return None


def _describir_radio(metros: float) -> str:
    return formatear_distancia_aproximada(metros)


def _mensaje_exito_progresivo(radio_metros: float) -> str:
    return (
        f"Se encontraron resultados dentro de aproximadamente "
        f"{_describir_radio(radio_metros)}."
    )


def _mensaje_exito_fijo(radio_metros: float) -> str:
    return (
        f"Se encontraron resultados dentro del radio indicado "
        f"({_describir_radio(radio_metros)})."
    )


def _mensaje_sin_coincidencias(
    *,
    modo_busqueda: str,
    radios_intentados: list[float],
) -> str:
    if modo_busqueda == "progresivo" and radios_intentados:
        radios_texto = ", ".join(_describir_radio(r) for r in radios_intentados)
        return (
            f"No se encontraron resultados dentro de los radios probados "
            f"({radios_texto})."
        )
    if radios_intentados:
        return (
            f"No se encontraron resultados dentro del radio indicado "
            f"({_describir_radio(radios_intentados[-1])})."
        )
    return "No se encontraron resultados dentro del filtro de cercanía indicado."


def _construir_retroalimentacion(
    resultado: ResultadoGisEvaluacion,
) -> RetroalimentacionGis:
    if resultado.ids and resultado.radio_aplicado_metros is not None:
        if resultado.modo_busqueda == "progresivo":
            return RetroalimentacionGis(
                codigo="encontrado_en_radio_progresivo",
                modo_busqueda="progresivo",
                radio_aplicado_metros=resultado.radio_aplicado_metros,
                radios_intentados_metros=resultado.radios_intentados_metros,
                mensaje=_mensaje_exito_progresivo(resultado.radio_aplicado_metros),
            )
        return RetroalimentacionGis(
            codigo="encontrado_en_radio_fijo",
            modo_busqueda="fijo",
            radio_aplicado_metros=resultado.radio_aplicado_metros,
            radios_intentados_metros=resultado.radios_intentados_metros,
            mensaje=_mensaje_exito_fijo(resultado.radio_aplicado_metros),
        )

    return RetroalimentacionGis(
        codigo="sin_coincidencias_en_radios",
        modo_busqueda=resultado.modo_busqueda,
        radio_aplicado_metros=None,
        radios_intentados_metros=resultado.radios_intentados_metros,
        mensaje=_mensaje_sin_coincidencias(
            modo_busqueda=resultado.modo_busqueda,
            radios_intentados=resultado.radios_intentados_metros,
        ),
    )


def _serializar_candidatos_sitio(
    candidatos: list[CandidatoGisEvaluado],
) -> list[CandidatoGisSitioItem]:
    return [
        CandidatoGisSitioItem(
            id_sitio=item.id_entidad,
            nombre=item.nombre,
            distancia_metros=item.distancia_metros,
            distancia_aproximada=formatear_distancia_aproximada(item.distancia_metros),
        )
        for item in candidatos
    ]


def _serializar_candidatos_ruta(
    candidatos: list[CandidatoGisEvaluado],
) -> list[CandidatoGisRutaItem]:
    return [
        CandidatoGisRutaItem(
            id_ruta=item.id_entidad,
            titulo=item.nombre,
            distancia_metros=item.distancia_metros,
            distancia_aproximada=formatear_distancia_aproximada(item.distancia_metros),
        )
        for item in candidatos
    ]


def consultar_sitios_por_gis(
    db: Session,
    payload: GisConsultaEntrada,
) -> (
    GisConsultaExitoSitios
    | GisConsultaExitoRutas
    | GisConsultaSinSitios
    | GisConsultaSinRutas
    | GisConsultaFallo
):
    valor_estado = payload.model_dump(mode="json")
    if not normalizar_ids_consulta(payload.ids_consulta):
        entidad = "rutas" if payload.entidad == "ruta" else "sitios"
        mensaje = (
            f"GIS requiere candidatos previos del pipeline "
            f"(ids_consulta no vacío para {entidad})."
        )
        return GisConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="gis",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    error_origen = _validar_origen(payload)
    if error_origen is not None:
        return error_origen

    unidad = payload.unidad or None
    ubicacion = (
        payload.ubicacion_usuario.coordenadas()
        if payload.ubicacion_usuario
        else None
    )

    if payload.entidad == "ruta":
        resultado = filtrar_rutas_por_gis(
            db,
            usar_ubicacion_usuario=payload.usar_ubicacion_usuario,
            ubicacion_usuario=ubicacion,
            punto_referencia=payload.punto_referencia or None,
            distancia=payload.distancia,
            unidad=unidad,
            ids_rutas=payload.ids_consulta,
            zonas_excluidas=payload.excluir_zonas,
        )
        retroalimentacion = _construir_retroalimentacion(resultado)
        candidatos = _serializar_candidatos_ruta(resultado.candidatos)

        if not resultado.ids:
            return GisConsultaSinRutas(
                sin_rutas=retroalimentacion.mensaje,
                candidatos=candidatos,
                retroalimentacion=retroalimentacion,
                estado_busqueda=construir_estado_busqueda(
                    nombre="gis",
                    estado="no_cumplido",
                    valor=valor_estado,
                    ids_entrada=payload.ids_consulta,
                    detalle=retroalimentacion.mensaje,
                    retroalimentacion=retroalimentacion,
                ),
            )
        return GisConsultaExitoRutas(
            ids_ruta=resultado.ids,
            candidatos=candidatos,
            retroalimentacion=retroalimentacion,
            estado_busqueda=construir_estado_busqueda(
                nombre="gis",
                estado="cumplido",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                ids_salida=resultado.ids,
                detalle=retroalimentacion.mensaje,
                retroalimentacion=retroalimentacion,
            ),
        )

    resultado = filtrar_sitios_por_gis(
        db,
        usar_ubicacion_usuario=payload.usar_ubicacion_usuario,
        ubicacion_usuario=ubicacion,
        punto_referencia=payload.punto_referencia or None,
        distancia=payload.distancia,
        unidad=unidad,
        ids_consulta=payload.ids_consulta,
        zonas_excluidas=payload.excluir_zonas,
    )
    retroalimentacion = _construir_retroalimentacion(resultado)
    candidatos = _serializar_candidatos_sitio(resultado.candidatos)

    if not resultado.ids:
        return GisConsultaSinSitios(
            sin_sitios=retroalimentacion.mensaje,
            candidatos=candidatos,
            retroalimentacion=retroalimentacion,
            estado_busqueda=construir_estado_busqueda(
                nombre="gis",
                estado="no_cumplido",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=retroalimentacion.mensaje,
                retroalimentacion=retroalimentacion,
            ),
        )

    return GisConsultaExitoSitios(
        ids_sitio=resultado.ids,
        candidatos=candidatos,
        retroalimentacion=retroalimentacion,
        estado_busqueda=construir_estado_busqueda(
            nombre="gis",
            estado="cumplido",
            valor=valor_estado,
            ids_entrada=payload.ids_consulta,
            ids_salida=resultado.ids,
            detalle=retroalimentacion.mensaje,
            retroalimentacion=retroalimentacion,
        ),
    )
