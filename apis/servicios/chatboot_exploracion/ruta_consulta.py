from sqlalchemy.orm import Session

from core.chatboot_evaluacion.ruta_evaluacion import filtrar_rutas_por_tipo
from esquemas.chatboot_exploracion.ruta_consulta import (
    RutaConsultaEntrada,
    RutaConsultaExito,
    RutaConsultaFallo,
    RutaConsultaSinRutas,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda


def consultar_rutas(
    db: Session,
    payload: RutaConsultaEntrada,
) -> RutaConsultaExito | RutaConsultaSinRutas | RutaConsultaFallo:
    valor_estado = payload.model_dump(mode="json")
    ids_ruta, tipo_consultado, tipo_resuelto = filtrar_rutas_por_tipo(
        db,
        tipo_ruta=payload.tipo_ruta,
        excluir_tipos=payload.excluir_tipos,
        ids_consulta=payload.ids_consulta,
    )

    if tipo_resuelto is None:
        mensaje = (
            f"No se pudo resolver el tipo de ruta '{tipo_consultado}'. "
            "Valores válidos: senderismo, ciclismo, caminata_urbana, montanismo."
        )
        return RutaConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="ruta",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    if tipo_resuelto == "Otras":
        mensaje = (
            "El tipo 'otro' no se usa como filtro de rutas. "
            "Para rutas turísticas por nombre, tema o actividad no clasificada, usa busqueda_semantica."
        )
        return RutaConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="ruta",
                estado="error",
                valor={**valor_estado, "tipo_resuelto": tipo_resuelto},
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    if not ids_ruta:
        mensaje = f"No se encontraron rutas de tipo '{tipo_resuelto}'."
        return RutaConsultaSinRutas(
            sin_rutas=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="ruta",
                estado="no_cumplido",
                valor={**valor_estado, "tipo_resuelto": tipo_resuelto},
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    return RutaConsultaExito(
        ids_ruta=ids_ruta,
        estado_busqueda=construir_estado_busqueda(
            nombre="ruta",
            estado="cumplido",
            valor={**valor_estado, "tipo_resuelto": tipo_resuelto},
            ids_entrada=payload.ids_consulta,
            ids_salida=ids_ruta,
            detalle=f"Se filtraron rutas de tipo '{tipo_resuelto}'.",
        ),
    )
