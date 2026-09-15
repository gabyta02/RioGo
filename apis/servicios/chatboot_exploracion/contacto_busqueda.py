from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.catalogo_trgm import normalizar_texto, params_texto_busqueda, sql_score_trgm
from core.infra.filtro_sitios import normalizar_ids_consulta
from esquemas.chatboot_exploracion.contacto_busqueda import (
    ContactoBusquedaEntrada,
    ContactoBusquedaExito,
    ContactoBusquedaFallo,
    ContactoBusquedaSinSitios,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda

UMBRAL_CONTACTO = 0.90


def _ids_con_contacto(
    db: Session,
    texto: str,
    ids_consulta: list[int] | None = None,
) -> list[int]:
    params = params_texto_busqueda(texto, texto)
    score_nombre = sql_score_trgm("c.nombre")
    filtro_ids = ""
    query_params: dict[str, object] = {**params, "umbral": UMBRAL_CONTACTO}
    if ids_consulta:
        filtro_ids = " AND s.id_sitio = ANY(:ids_consulta)"
        query_params["ids_consulta"] = ids_consulta
    rows = db.execute(
        text(
            f"""
            SELECT DISTINCT c.id_sitio
            FROM turismo.contacto c
            JOIN turismo.sitio s ON s.id_sitio = c.id_sitio
            WHERE c.activo = TRUE
              AND s.activo = TRUE
              {filtro_ids}
              AND {score_nombre} >= :umbral
            ORDER BY c.id_sitio
            """
        ),
        query_params,
    ).scalars().all()
    return [int(item) for item in rows]


def buscar_sitios_por_contacto(
    db: Session,
    payload: ContactoBusquedaEntrada,
) -> ContactoBusquedaExito | ContactoBusquedaSinSitios | ContactoBusquedaFallo:
    valor_estado = payload.model_dump(mode="json")
    texto = normalizar_texto(payload.contacto_sugerido)
    if not texto:
        mensaje = "El contacto sugerido no puede estar vacío."
        return ContactoBusquedaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="contactos",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    ids_filtro = normalizar_ids_consulta(payload.ids_consulta) or None
    ids_sitio = _ids_con_contacto(db, texto, ids_filtro)

    if payload.excluir_contactos:
        excluidos: set[int] = set()
        for termino in payload.excluir_contactos:
            excluidos.update(_ids_con_contacto(db, termino, ids_filtro))
        ids_sitio = [id_sitio for id_sitio in ids_sitio if id_sitio not in excluidos]

    if not ids_sitio:
        mensaje = f"Ningún sitio tiene un contacto que coincida con '{texto}'."
        return ContactoBusquedaSinSitios(
            sin_sitios=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="contactos",
                estado="no_cumplido",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    return ContactoBusquedaExito(
        ids_sitio=ids_sitio,
        estado_busqueda=construir_estado_busqueda(
            nombre="contactos",
            estado="cumplido",
            valor=valor_estado,
            ids_entrada=payload.ids_consulta,
            ids_salida=ids_sitio,
            detalle=f"Se filtraron sitios con contacto relacionado con '{texto}'.",
        ),
    )
