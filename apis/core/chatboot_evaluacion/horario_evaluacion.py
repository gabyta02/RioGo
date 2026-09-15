from __future__ import annotations

from datetime import datetime, time as dt_time
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.filtro_sitios import agregar_filtro_ids

TZ_GUAYAQUIL = ZoneInfo("America/Guayaquil")

TipoHorario = Literal[
    "instantaneo",
    "punto_tiempo",
    "bloque_tiempo",
    "relacional",
    "dias_solamente",
]
ComparadorHorario = Literal["", "igual", "dentro_de", "mayor_que", "menor_que"]


def ahora_local() -> datetime:
    return datetime.now(TZ_GUAYAQUIL)


def parsear_hora(hora_texto: str) -> dt_time | None:
    texto = hora_texto.strip()
    for formato in ("%H:%M", "%H:%M:%S", "%H"):
        try:
            return datetime.strptime(texto, formato).time()
        except ValueError:
            continue
    return None


def resolver_dia_semana(valor: int | None) -> int | None:
    if valor is None:
        return None
    return valor if 1 <= valor <= 7 else None


def resolver_dias_excluidos(excluir_dias: list[int]) -> list[int]:
    dias: list[int] = []
    for item in excluir_dias:
        dia = resolver_dia_semana(item)
        if dia and dia not in dias:
            dias.append(dia)
    return dias


def mapear_comparador_legacy(comparador: ComparadorHorario) -> str | None:
    if comparador in {"", "igual", "dentro_de"}:
        return None
    if comparador == "mayor_que":
        return "despues_de"
    if comparador == "menor_que":
        return "antes_de"
    return None


def mapear_tipo_legacy(tipo: TipoHorario) -> str:
    return {
        "instantaneo": "abierto_ahora",
        "punto_tiempo": "abierto_en_hora",
        "bloque_tiempo": "abierto_en_rango",
        "relacional": "abierto_en_hora",
        "dias_solamente": "atiende_dia",
    }[tipo]


def obtener_horarios_sitios(
    db: Session,
    ids_consulta: list[int],
) -> dict[int, dict[str, Any]]:
    filtros_sql: list[str] = []
    params: dict[str, Any] = {}
    agregar_filtro_ids(filtros_sql, params, ids_consulta)
    alcance_sql = ""
    if filtros_sql:
        alcance_sql = " AND " + " AND ".join(filtros_sql)

    rows = db.execute(
        text(
            f"""
            SELECT
                s.id_sitio,
                COALESCE(h.abierto_24h, FALSE) AS abierto_24h,
                h.comentario AS comentario,
                hd.dia_semana,
                hd.hora_inicio,
                hd.hora_fin
            FROM turismo.sitio s
            LEFT JOIN turismo.horario h
                ON h.id_sitio = s.id_sitio AND h.activo = TRUE
            LEFT JOIN turismo.horario_detalle hd
                ON hd.id_horario = h.id_horario AND hd.activo = TRUE
            WHERE s.activo = TRUE
              {alcance_sql}
            ORDER BY s.id_sitio ASC, hd.dia_semana ASC, hd.hora_inicio ASC
            """
        ),
        params,
    ).mappings().all()

    sitios: dict[int, dict[str, Any]] = {}
    for row in rows:
        id_sitio = int(row["id_sitio"])
        if id_sitio not in sitios:
            sitios[id_sitio] = {
                "id_sitio": id_sitio,
                "abierto_24h": bool(row["abierto_24h"]),
                "comentario": (row["comentario"] or "").strip() or None,
                "detalles": [],
            }
        if row["dia_semana"] is not None:
            sitios[id_sitio]["detalles"].append(
                {
                    "dia_semana": int(row["dia_semana"]),
                    "hora_inicio": row["hora_inicio"],
                    "hora_fin": row["hora_fin"],
                }
            )
    return sitios


def _sitio_atiende_dia(sitio: dict[str, Any], dia: int) -> bool:
    if sitio["abierto_24h"]:
        return True
    return any(detalle["dia_semana"] == dia for detalle in sitio["detalles"])


def _detalles_dia(sitio: dict[str, Any], dia: int) -> list[dict[str, Any]]:
    return [detalle for detalle in sitio["detalles"] if detalle["dia_semana"] == dia]


def _hora_en_rango(hora: dt_time, inicio: dt_time, fin: dt_time) -> bool:
    return inicio <= hora <= fin


def _rangos_se_solapan(
    inicio_a: dt_time,
    fin_a: dt_time,
    inicio_b: dt_time,
    fin_b: dt_time,
) -> bool:
    return inicio_a < fin_b and fin_a > inicio_b


def _cumple_abierto_ahora(
    sitio: dict[str, Any],
    dia_semana: int | None,
    hora: dt_time | None,
) -> bool:
    if sitio["abierto_24h"]:
        return True
    dia = dia_semana or ahora_local().isoweekday()
    hora_actual = hora or ahora_local().time()
    return any(
        _hora_en_rango(hora_actual, detalle["hora_inicio"], detalle["hora_fin"])
        for detalle in _detalles_dia(sitio, dia)
    )


def _cumple_abierto_en_hora(
    sitio: dict[str, Any],
    dia_semana: int | None,
    hora: dt_time | None,
    comparador: str | None,
) -> bool:
    if dia_semana is None or hora is None:
        return False
    if sitio["abierto_24h"]:
        return True

    for detalle in _detalles_dia(sitio, dia_semana):
        inicio = detalle["hora_inicio"]
        fin = detalle["hora_fin"]
        if comparador == "antes_de" and inicio <= hora:
            return True
        if comparador == "despues_de" and fin >= hora:
            return True
        if comparador not in {"antes_de", "despues_de"} and _hora_en_rango(hora, inicio, fin):
            return True
    return False


def _cumple_abierto_en_rango(
    sitio: dict[str, Any],
    dia_semana: int | None,
    rango_inicio: dt_time | None,
    rango_fin: dt_time | None,
) -> bool:
    if dia_semana is None or rango_inicio is None or rango_fin is None:
        return False
    if sitio["abierto_24h"]:
        return True

    return any(
        _rangos_se_solapan(
            detalle["hora_inicio"],
            detalle["hora_fin"],
            rango_inicio,
            rango_fin,
        )
        for detalle in _detalles_dia(sitio, dia_semana)
    )


def _sitio_cumple_filtro_horario(
    sitio: dict[str, Any],
    tipo: str,
    dia_semana: int | None,
    hora: dt_time | None,
    rango_inicio: dt_time | None,
    rango_fin: dt_time | None,
    comparador: str | None,
) -> bool:
    if tipo == "abierto_ahora":
        return _cumple_abierto_ahora(sitio, dia_semana, hora)

    if tipo == "atiende_dia":
        if dia_semana is None:
            return False
        return _sitio_atiende_dia(sitio, dia_semana)

    if tipo == "abierto_en_hora":
        return _cumple_abierto_en_hora(sitio, dia_semana, hora, comparador)

    if tipo == "abierto_en_rango":
        return _cumple_abierto_en_rango(sitio, dia_semana, rango_inicio, rango_fin)

    return False


def _sitio_cumple_en_algun_dia(
    sitio: dict[str, Any],
    tipo: str,
    dias_semana: list[int],
    hora: dt_time | None,
    rango_inicio: dt_time | None,
    rango_fin: dt_time | None,
    comparador: str | None,
) -> bool:
    if not dias_semana:
        return _sitio_cumple_filtro_horario(
            sitio,
            tipo,
            None,
            hora,
            rango_inicio,
            rango_fin,
            comparador,
        )

    return any(
        _sitio_cumple_filtro_horario(
            sitio,
            tipo,
            dia,
            hora,
            rango_inicio,
            rango_fin,
            comparador,
        )
        for dia in dias_semana
    )


def sitio_excluido_por_dias(sitio: dict[str, Any], dias_excluidos: list[int]) -> bool:
    if not dias_excluidos:
        return False
    return any(_sitio_atiende_dia(sitio, dia) for dia in dias_excluidos)


def filtrar_sitios_por_horario(
    sitios_map: dict[int, dict[str, Any]],
    tipo: TipoHorario,
    dia_semana: int | None,
    hora: dt_time | None,
    rango_inicio: dt_time | None,
    rango_fin: dt_time | None,
    comparador: ComparadorHorario,
    excluir_dias: list[int],
    dias_semana: list[int] | None = None,
) -> list[int]:
    tipo_legacy = mapear_tipo_legacy(tipo)
    comparador_legacy = mapear_comparador_legacy(comparador)
    dias_excluidos = resolver_dias_excluidos(excluir_dias)
    dias_a_evaluar = dias_semana or ([dia_semana] if dia_semana is not None else [])
    ids_coincidentes: list[int] = []

    for sitio in sitios_map.values():
        if sitio_excluido_por_dias(sitio, dias_excluidos):
            continue
        if not _sitio_cumple_en_algun_dia(
            sitio,
            tipo_legacy,
            dias_a_evaluar,
            hora,
            rango_inicio,
            rango_fin,
            comparador_legacy,
        ):
            continue
        ids_coincidentes.append(int(sitio["id_sitio"]))

    return sorted(ids_coincidentes)
