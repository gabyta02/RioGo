from typing import Any

from sqlalchemy.orm import Session

from esquemas.chatboot_exploracion.busqueda_referencia import BusquedaReferenciaEntrada
from esquemas.chatboot_exploracion.busqueda_ubicacion import (
    BusquedaUbicacionEntrada,
    BusquedaUbicacionFallo,
    BusquedaUbicacionSalida,
)
from esquemas.chatboot_exploracion.gis_consulta import GisConsultaEntrada
from servicios.chatboot_exploracion.busqueda_referencia import buscar_sitios_por_referencia
from servicios.chatboot_exploracion.gis_consulta import consultar_sitios_por_gis
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda


def _tipo_busqueda_resuelto(payload: BusquedaUbicacionEntrada) -> str:
    if payload.tipo_busqueda:
        return payload.tipo_busqueda
    if payload.usar_ubicacion_usuario or payload.distancia is not None:
        return "cercania"
    if payload.referencia_ubicacion.strip():
        return "zona_textual"
    return ""


def _renombrar_estado_busqueda(respuesta: Any, payload: BusquedaUbicacionEntrada) -> Any:
    estado = getattr(respuesta, "estado_busqueda", None)
    if estado is None:
        return respuesta

    estado.estado = estado.estado
    for filtro in estado.filtros:
        filtro.nombre = "busqueda_ubicacion"
        filtro.valor = payload.model_dump(mode="json")
    return respuesta


def _fallo(mensaje: str, payload: BusquedaUbicacionEntrada) -> BusquedaUbicacionFallo:
    valor = payload.model_dump(mode="json")
    return BusquedaUbicacionFallo(
        fallo=mensaje,
        estado_busqueda=construir_estado_busqueda(
            nombre="busqueda_ubicacion",
            estado="error",
            valor=valor,
            ids_entrada=payload.ids_consulta,
            detalle=mensaje,
        ),
    )


def buscar_por_ubicacion(
    db: Session,
    payload: BusquedaUbicacionEntrada,
) -> BusquedaUbicacionSalida:
    tipo = _tipo_busqueda_resuelto(payload)
    referencia = payload.referencia_ubicacion.strip()

    if tipo == "zona_textual":
        if not referencia:
            return _fallo("Debe indicar referencia_ubicacion para zona_textual.", payload)
        respuesta = buscar_sitios_por_referencia(
            db,
            BusquedaReferenciaEntrada(
                direccion_referencia=referencia,
                ids_consulta=payload.ids_consulta,
            ),
        )
        return _renombrar_estado_busqueda(respuesta, payload)

    if tipo == "cercania":
        respuesta = consultar_sitios_por_gis(
            db,
            GisConsultaEntrada(
                entidad=payload.entidad,
                usar_ubicacion_usuario=payload.usar_ubicacion_usuario,
                distancia=payload.distancia,
                unidad=payload.unidad,
                punto_referencia=referencia,
                excluir_zonas=payload.excluir_zonas,
                ubicacion_usuario=payload.ubicacion_usuario,
                ids_consulta=payload.ids_consulta,
            ),
        )
        return _renombrar_estado_busqueda(respuesta, payload)

    return _fallo(
        "Debe indicar tipo_busqueda, referencia_ubicacion, distancia o ubicación de usuario.",
        payload,
    )
