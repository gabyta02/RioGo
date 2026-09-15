from typing import Any


def normalizar_ids_consulta(ids: list[int]) -> list[int]:
    vistos: set[int] = set()
    resultado: list[int] = []
    for item in ids:
        id_sitio = int(item)
        if id_sitio <= 0 or id_sitio in vistos:
            continue
        vistos.add(id_sitio)
        resultado.append(id_sitio)
    return sorted(resultado)


def agregar_filtro_ids(
    filtros_sql: list[str],
    params: dict[str, Any],
    ids_consulta: list[int],
) -> list[int]:
    ids_validos = normalizar_ids_consulta(ids_consulta)
    if ids_validos:
        filtros_sql.append("s.id_sitio = ANY(:ids_consulta)")
        params["ids_consulta"] = ids_validos
    return ids_validos


def intersectar_ids(
    ids_sitio: list[int],
    ids_consulta: list[int],
) -> list[int]:
    ids_validos = normalizar_ids_consulta(ids_consulta)
    if not ids_validos:
        return sorted(set(ids_sitio))
    permitidos = set(ids_validos)
    return sorted(id_sitio for id_sitio in ids_sitio if id_sitio in permitidos)
