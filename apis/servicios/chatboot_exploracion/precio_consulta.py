from sqlalchemy.orm import Session

from core.chatboot_evaluacion.precio_evaluacion import (
    filtrar_sitios_por_precio,
    mapear_operador,
    normalizar_etiqueta,
    normalizar_etiquetas_excluidas,
    obtener_datos_precio_sitios,
    rango_cumple_filtro,
    sitio_cumple_es_gratuito,
)
from esquemas.chatboot_exploracion.precio_consulta import (
    CandidatoPrecioItem,
    PrecioConsultaEntrada,
    PrecioConsultaExito,
    PrecioConsultaFallo,
    PrecioConsultaSinSitios,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda


def _evidencia_precio(
    sitios_datos: dict[int, dict],
    ids_sitio: list[int],
    *,
    es_gratuito: bool | None,
    etiqueta: str | None,
    precio_numero: float | None,
    operador,
) -> list[CandidatoPrecioItem]:
    salida: list[CandidatoPrecioItem] = []
    for id_sitio in ids_sitio:
        datos = sitios_datos.get(id_sitio) or {}
        rangos = datos.get("rangos") or []
        criterio_gratis = (
            True
            if es_gratuito is None
            else sitio_cumple_es_gratuito(datos.get("es_gratuito"), es_gratuito)
        )
        rango_elegido = None
        for rango in rangos:
            if rango_cumple_filtro(
                rango["precio_min"],
                rango["precio_max"],
                rango.get("etiqueta_precio"),
                etiqueta,
                precio_numero,
                operador,
            ):
                rango_elegido = rango
                break
        criterio_rango = not (etiqueta is not None or precio_numero is not None) or rango_elegido is not None
        salida.append(
            CandidatoPrecioItem(
                id_sitio=id_sitio,
                es_gratuito=datos.get("es_gratuito"),
                precio_min=(rango_elegido or {}).get("precio_min"),
                precio_max=(rango_elegido or {}).get("precio_max"),
                etiqueta_precio=(rango_elegido or {}).get("etiqueta_precio"),
                criterio_cumplido=criterio_gratis and criterio_rango,
            )
        )
    return salida


def consultar_sitios_por_precio(
    db: Session,
    payload: PrecioConsultaEntrada,
) -> PrecioConsultaExito | PrecioConsultaSinSitios | PrecioConsultaFallo:
    valor_estado = payload.model_dump(mode="json")
    etiqueta = normalizar_etiqueta(payload.etiqueta) if payload.etiqueta else None
    if payload.etiqueta and etiqueta is None:
        mensaje = (
            f"No se pudo resolver la etiqueta '{payload.etiqueta}'. "
            "Valores válidos: economico, medio, alto."
        )
        return PrecioConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="precio",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    tiene_filtro = (
        payload.es_gratuito is not None
        or etiqueta is not None
        or payload.precio_numero is not None
    )
    if not tiene_filtro:
        mensaje = "Debe indicar es_gratuito, precio_numero o etiqueta."
        return PrecioConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="precio",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    operador = None
    if payload.precio_numero is not None:
        operador = mapear_operador(payload.operador)
        if operador is None:
            mensaje = "operador inválido. Use '', '=', '<', '<=', '>' o '>='."
            return PrecioConsultaFallo(
                fallo=mensaje,
                estado_busqueda=construir_estado_busqueda(
                    nombre="precio",
                    estado="error",
                    valor=valor_estado,
                    ids_entrada=payload.ids_consulta,
                    detalle=mensaje,
                ),
            )

    etiquetas_excluidas = normalizar_etiquetas_excluidas(payload.excluir_etiquetas)
    sitios_datos = obtener_datos_precio_sitios(db, payload.ids_consulta)
    ids_sitio = filtrar_sitios_por_precio(
        sitios_datos,
        payload.es_gratuito,
        etiqueta,
        payload.precio_numero,
        operador,
        etiquetas_excluidas,
    )
    candidatos = _evidencia_precio(
        sitios_datos,
        ids_sitio,
        es_gratuito=payload.es_gratuito,
        etiqueta=etiqueta,
        precio_numero=payload.precio_numero,
        operador=operador,
    )

    if not ids_sitio:
        mensaje = "Ningún sitio cumple con el filtro de precio indicado."
        return PrecioConsultaSinSitios(
            sin_sitios=mensaje,
            candidatos=[],
            estado_busqueda=construir_estado_busqueda(
                nombre="precio",
                estado="no_cumplido",
                valor={**valor_estado, "etiqueta_normalizada": etiqueta},
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    return PrecioConsultaExito(
        ids_sitio=ids_sitio,
        candidatos=candidatos,
        estado_busqueda=construir_estado_busqueda(
            nombre="precio",
            estado="cumplido",
            valor={**valor_estado, "etiqueta_normalizada": etiqueta},
            ids_entrada=payload.ids_consulta,
            ids_salida=ids_sitio,
            detalle="Se filtraron sitios por precio o gratuidad del servicio.",
        ),
    )
