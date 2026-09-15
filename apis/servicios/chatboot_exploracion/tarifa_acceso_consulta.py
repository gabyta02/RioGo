from sqlalchemy.orm import Session

from core.chatboot_evaluacion.precio_evaluacion import mapear_operador, normalizar_etiqueta
from core.chatboot_evaluacion.tarifa_evaluacion import (
    condicion_coincide,
    filtrar_sitios_por_tarifa,
    monto_cumple_filtro,
    normalizar_condicion,
    obtener_datos_tarifa_sitios,
    sitio_cumple_entrada_gratuita,
)
from esquemas.chatboot_exploracion.tarifa_acceso_consulta import (
    CandidatoTarifaAccesoItem,
    TarifaAccesoConsultaEntrada,
    TarifaAccesoConsultaExito,
    TarifaAccesoConsultaFallo,
    TarifaAccesoConsultaSinSitios,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda


def _evidencia_tarifa(
    tarifas_por_sitio: dict[int, list[dict]],
    ids_sitio: list[int],
    *,
    entrada_gratuita: bool | None,
    etiqueta: str | None,
    precio_numero: float | None,
    operador,
    condicion: str | None,
) -> list[CandidatoTarifaAccesoItem]:
    salida: list[CandidatoTarifaAccesoItem] = []
    for id_sitio in ids_sitio:
        tarifas = tarifas_por_sitio.get(id_sitio) or []
        tarifas_validas = tarifas
        if condicion:
            tarifas_validas = [
                tarifa
                for tarifa in tarifas_validas
                if condicion_coincide(tarifa.get("condicion") or "", condicion)
            ]
        if etiqueta or precio_numero is not None:
            tarifas_validas = [
                tarifa
                for tarifa in tarifas_validas
                if monto_cumple_filtro(tarifa["precio"], etiqueta, precio_numero, operador)
            ]
        if entrada_gratuita is not None:
            criterio_gratis = sitio_cumple_entrada_gratuita(tarifas, entrada_gratuita)
        else:
            criterio_gratis = True
        tarifa_elegida = min(tarifas_validas, key=lambda item: item["precio"]) if tarifas_validas else None
        salida.append(
            CandidatoTarifaAccesoItem(
                id_sitio=id_sitio,
                precio=(tarifa_elegida or {}).get("precio"),
                condicion=(tarifa_elegida or {}).get("condicion"),
                entrada_gratuita=(
                    any(tarifa["precio"] == 0 for tarifa in tarifas)
                    if tarifas
                    else None
                ),
                criterio_cumplido=criterio_gratis and bool(tarifa_elegida or entrada_gratuita is not None),
            )
        )
    return salida


def consultar_sitios_por_tarifa_acceso(
    db: Session,
    payload: TarifaAccesoConsultaEntrada,
) -> TarifaAccesoConsultaExito | TarifaAccesoConsultaSinSitios | TarifaAccesoConsultaFallo:
    valor_estado = payload.model_dump(mode="json")
    etiqueta = normalizar_etiqueta(payload.etiqueta) if payload.etiqueta else None
    if payload.etiqueta and etiqueta is None:
        mensaje = (
            f"No se pudo resolver la etiqueta '{payload.etiqueta}'. "
            "Valores válidos: economico, medio, alto."
        )
        return TarifaAccesoConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="tarifa_acceso",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    condicion = normalizar_condicion(payload.condicion) if payload.condicion else None

    tiene_filtro = (
        payload.entrada_gratuita is not None
        or etiqueta is not None
        or payload.precio_numero is not None
        or condicion is not None
    )
    if not tiene_filtro:
        mensaje = "Debe indicar entrada_gratuita, precio_numero, etiqueta o condicion."
        return TarifaAccesoConsultaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="tarifa_acceso",
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
            return TarifaAccesoConsultaFallo(
                fallo=mensaje,
                estado_busqueda=construir_estado_busqueda(
                    nombre="tarifa_acceso",
                    estado="error",
                    valor=valor_estado,
                    ids_entrada=payload.ids_consulta,
                    detalle=mensaje,
                ),
            )

    tarifas_por_sitio = obtener_datos_tarifa_sitios(db, payload.ids_consulta)
    ids_sitio = filtrar_sitios_por_tarifa(
        db,
        tarifas_por_sitio,
        payload.entrada_gratuita,
        etiqueta,
        payload.precio_numero,
        operador,
        condicion,
        payload.excluir_condiciones,
    )
    candidatos = _evidencia_tarifa(
        tarifas_por_sitio,
        ids_sitio,
        entrada_gratuita=payload.entrada_gratuita,
        etiqueta=etiqueta,
        precio_numero=payload.precio_numero,
        operador=operador,
        condicion=condicion,
    )

    if not ids_sitio:
        mensaje = "Ningún sitio cumple con el filtro de tarifa de acceso indicado."
        return TarifaAccesoConsultaSinSitios(
            sin_sitios=mensaje,
            candidatos=[],
            estado_busqueda=construir_estado_busqueda(
                nombre="tarifa_acceso",
                estado="no_cumplido",
                valor={
                    **valor_estado,
                    "etiqueta_normalizada": etiqueta,
                    "condicion_normalizada": condicion,
                },
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    return TarifaAccesoConsultaExito(
        ids_sitio=ids_sitio,
        candidatos=candidatos,
        estado_busqueda=construir_estado_busqueda(
            nombre="tarifa_acceso",
            estado="cumplido",
            valor={
                **valor_estado,
                "etiqueta_normalizada": etiqueta,
                "condicion_normalizada": condicion,
            },
            ids_entrada=payload.ids_consulta,
            ids_salida=ids_sitio,
            detalle="Se filtraron sitios por tarifa de acceso.",
        ),
    )
