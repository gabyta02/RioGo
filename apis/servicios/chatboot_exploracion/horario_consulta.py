from datetime import time as dt_time

from sqlalchemy.orm import Session

from core.chatboot_evaluacion.horario_evaluacion import (
    ahora_local,
    filtrar_sitios_por_horario,
    obtener_horarios_sitios,
    parsear_hora,
    resolver_dia_semana,
)
from esquemas.chatboot_exploracion.horario_consulta import (
    CandidatoHorarioItem,
    HorarioConsultaEntrada,
    HorarioConsultaExito,
    HorarioConsultaFallo,
    HorarioConsultaSinSitios,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda


_NOMBRES_DIA = {
    1: "Lun",
    2: "Mar",
    3: "Mié",
    4: "Jue",
    5: "Vie",
    6: "Sáb",
    7: "Dom",
}


def _formatear_hora(valor: dt_time | None) -> str:
    return valor.strftime("%H:%M") if valor else ""


def _horario_texto_sitio(sitio: dict) -> str:
    if sitio.get("abierto_24h"):
        return "Abierto 24 horas"
    detalles = sitio.get("detalles") or []
    if not detalles:
        return "No disponible"
    partes: list[str] = []
    for detalle in detalles[:6]:
        dia = _NOMBRES_DIA.get(detalle.get("dia_semana"), f"Día {detalle.get('dia_semana')}")
        partes.append(
            f"{dia}: {_formatear_hora(detalle.get('hora_inicio'))}-{_formatear_hora(detalle.get('hora_fin'))}"
        )
    if len(detalles) > 6:
        partes.append("...")
    return " | ".join(partes)


def _comentario_horario_sitio(sitio: dict) -> str | None:
    comentario = str(sitio.get("comentario") or "").strip()
    return comentario or None


def _comentario_indica_reservacion(sitio: dict) -> bool:
    comentario = str(sitio.get("comentario") or "").casefold()
    return "reserv" in comentario


def _ids_disponibilidad_condicional(
    sitios_map: dict[int, dict],
    ids_sitio: list[int],
    ids_consulta: list[int],
) -> list[int]:
    if not ids_consulta:
        return []
    ids_confirmados = set(ids_sitio)
    ids_base = set(ids_consulta)
    return sorted(
        int(id_sitio)
        for id_sitio, sitio in sitios_map.items()
        if id_sitio in ids_base
        and id_sitio not in ids_confirmados
        and _comentario_indica_reservacion(sitio)
    )


def _evidencia_horario(
    sitios_map: dict[int, dict],
    ids_sitio: list[int],
    *,
    dias_semana: list[int],
    hora: dt_time | None,
    ids_condicionales: list[int] | None = None,
) -> list[CandidatoHorarioItem]:
    condicionales = set(ids_condicionales or [])
    return [
        CandidatoHorarioItem(
            id_sitio=id_sitio,
            abierto_24h=bool((sitios_map.get(id_sitio) or {}).get("abierto_24h")),
            horario_texto=_horario_texto_sitio(sitios_map.get(id_sitio) or {}),
            comentario=_comentario_horario_sitio(sitios_map.get(id_sitio) or {}),
            cumplimiento_condicional=id_sitio in condicionales,
            dias_semana_resueltos=dias_semana,
            hora_consultada=_formatear_hora(hora) or None,
            criterio_cumplido=True,
        )
        for id_sitio in ids_sitio
    ]


def _resolver_parametros_horario(
    payload: HorarioConsultaEntrada,
) -> tuple[
    int | None,
    list[int],
    dt_time | None,
    dt_time | None,
    dt_time | None,
    str | None,
]:
    dia_semana = resolver_dia_semana(payload.dia_semana)
    dias_semana = _resolver_dias_semana(payload.dias_semana, dia_semana)
    hora = parsear_hora(payload.hora) if payload.hora else None
    rango_inicio, rango_fin = _resolver_rango_hora(payload)
    dia_semana, dias_semana, hora = _aplicar_defaults_temporales(
        payload,
        dia_semana,
        dias_semana,
        hora,
    )
    error = _validar_parametros_temporales(
        payload,
        dias_semana,
        hora,
        rango_inicio,
        rango_fin,
    )
    if error:
        return dia_semana, dias_semana, hora, rango_inicio, rango_fin, error

    return dia_semana, dias_semana, hora, rango_inicio, rango_fin, None


def _resolver_rango_hora(
    payload: HorarioConsultaEntrada,
) -> tuple[dt_time | None, dt_time | None]:
    if not payload.rango_hora:
        return None, None
    return parsear_hora(payload.rango_hora[0]), parsear_hora(payload.rango_hora[1])


def _aplicar_defaults_temporales(
    payload: HorarioConsultaEntrada,
    dia_semana: int | None,
    dias_semana: list[int],
    hora: dt_time | None,
) -> tuple[int | None, list[int], dt_time | None]:
    if payload.tipo == "instantaneo":
        dia_semana = dia_semana or ahora_local().isoweekday()
        return dia_semana, [dia_semana], hora or ahora_local().time()

    if payload.tipo in {"punto_tiempo", "relacional", "bloque_tiempo"} and not dias_semana:
        dia_semana = dia_semana or ahora_local().isoweekday()
        dias_semana = [dia_semana]

    return dia_semana, dias_semana, hora


def _validar_parametros_temporales(
    payload: HorarioConsultaEntrada,
    dias_semana: list[int],
    hora: dt_time | None,
    rango_inicio: dt_time | None,
    rango_fin: dt_time | None,
) -> str | None:
    if payload.tipo == "punto_tiempo" and hora is None:
        return "El tipo 'punto_tiempo' requiere una hora válida (HH:MM)."

    if payload.tipo == "relacional":
        if hora is None:
            return "El tipo 'relacional' requiere una hora válida (HH:MM)."
        if payload.comparador not in {"mayor_que", "menor_que"}:
            return "El tipo 'relacional' requiere comparador 'mayor_que' o 'menor_que'."

    if payload.tipo == "bloque_tiempo" and (rango_inicio is None or rango_fin is None):
        return "El tipo 'bloque_tiempo' requiere rango_hora con dos valores HH:MM."

    if payload.tipo == "dias_solamente" and not dias_semana:
        return "El tipo 'dias_solamente' requiere dia_semana (1-7) o dias_semana."

    return None


def _resolver_dias_semana(
    dias_semana: list[int] | None,
    dia_semana: int | None,
) -> list[int]:
    dias: list[int] = []
    for dia in dias_semana or []:
        dia_resuelto = resolver_dia_semana(dia)
        if dia_resuelto and dia_resuelto not in dias:
            dias.append(dia_resuelto)
    if not dias and dia_semana is not None:
        dias.append(dia_semana)
    return dias


def consultar_sitios_por_horario(
    db: Session,
    payload: HorarioConsultaEntrada,
) -> HorarioConsultaExito | HorarioConsultaSinSitios | HorarioConsultaFallo:
    valor_estado = payload.model_dump(mode="json")
    dia_semana, dias_semana, hora, rango_inicio, rango_fin, error = _resolver_parametros_horario(
        payload
    )
    if error:
        return HorarioConsultaFallo(
            fallo=error,
            estado_busqueda=construir_estado_busqueda(
                nombre="horario",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=error,
            ),
        )

    sitios_map = obtener_horarios_sitios(db, payload.ids_consulta)
    ids_sitio = filtrar_sitios_por_horario(
        sitios_map,
        payload.tipo,
        dia_semana,
        hora,
        rango_inicio,
        rango_fin,
        payload.comparador,
        payload.excluir_dias,
        dias_semana=dias_semana,
    )
    ids_condicionales = _ids_disponibilidad_condicional(
        sitios_map,
        ids_sitio,
        payload.ids_consulta,
    )
    ids_respuesta = sorted(set(ids_sitio) | set(ids_condicionales))
    candidatos = _evidencia_horario(
        sitios_map,
        ids_respuesta,
        dias_semana=dias_semana,
        hora=hora,
        ids_condicionales=ids_condicionales,
    )

    if not ids_respuesta:
        mensaje = "Ningún sitio cumple con el filtro de horario indicado."
        return HorarioConsultaSinSitios(
            sin_sitios=mensaje,
            candidatos=[],
            estado_busqueda=construir_estado_busqueda(
                nombre="horario",
                estado="no_cumplido",
                valor={
                    **valor_estado,
                    "dias_semana_resueltos": dias_semana,
                },
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    return HorarioConsultaExito(
        ids_sitio=ids_respuesta,
        candidatos=candidatos,
        estado_busqueda=construir_estado_busqueda(
            nombre="horario",
            estado="cumplido",
            valor={
                **valor_estado,
                "dias_semana_resueltos": dias_semana,
            },
            ids_entrada=payload.ids_consulta,
            ids_salida=ids_respuesta,
            detalle="Se filtraron sitios por disponibilidad horaria.",
        ),
    )
