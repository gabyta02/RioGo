from sqlalchemy.orm import Session

from core.chatboot_evaluacion.atributos_evaluacion import filtrar_sitios_por_atributos
from esquemas.chatboot_exploracion.atributos_booleanos_consulta import (
    AtributosBooleanosConsultaEntrada,
    AtributosBooleanosConsultaExito,
    AtributosBooleanosConsultaFallo,
    AtributosBooleanosConsultaSinSitios,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda


def consultar_sitios_por_atributos(
    db: Session,
    payload: AtributosBooleanosConsultaEntrada,
) -> (
    AtributosBooleanosConsultaExito
    | AtributosBooleanosConsultaSinSitios
    | AtributosBooleanosConsultaFallo
):
    valor_estado = payload.model_dump(mode="json")
    tiene_filtro = any(
        valor is not None
        for valor in (
            payload.tiene_wifi,
            payload.permite_mascotas,
            payload.accesibilidad,
            payload.parqueadero,
            payload.es_gratuito,
        )
    ) or bool(payload.excluir)

    if not tiene_filtro:
        mensaje = "Debe indicar al menos un atributo booleano o una exclusión."
        return AtributosBooleanosConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="atributos_booleanos",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    ids_sitio = filtrar_sitios_por_atributos(
        db,
        payload.ids_consulta,
        payload.tiene_wifi,
        payload.permite_mascotas,
        payload.accesibilidad,
        payload.parqueadero,
        payload.es_gratuito,
        payload.excluir,
    )

    if not ids_sitio:
        mensaje = "Ningún sitio cumple con los atributos booleanos indicados."
        return AtributosBooleanosConsultaSinSitios(
            sin_sitios=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="atributos_booleanos",
                estado="no_cumplido",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    return AtributosBooleanosConsultaExito(
        ids_sitio=ids_sitio,
        estado_busqueda=construir_estado_busqueda(
            nombre="atributos_booleanos",
            estado="cumplido",
            valor=valor_estado,
            ids_entrada=payload.ids_consulta,
            ids_salida=ids_sitio,
            detalle="Se filtraron sitios por atributos solicitados.",
        ),
    )
