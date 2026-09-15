from sqlalchemy import text
from sqlalchemy.orm import Session

from core.infra.catalogo_trgm import normalizar_texto, sin_acentos
from core.infra.filtro_sitios import agregar_filtro_ids
from esquemas.chatboot_especifico.pregunta_directa import (
    PreguntaDirectaEntrada,
    PreguntaDirectaExito,
    PreguntaDirectaFallo,
    PreguntaDirectaSinSitios,
)
from servicios.chatboot_exploracion.estado_busqueda import construir_estado_busqueda

UMBRAL_PREGUNTA_DIRECTA = 0.90
UMBRAL_SUGERENCIA_PREGUNTA_DIRECTA = 0.50
MAX_SUGERENCIAS_PREGUNTA_DIRECTA = 5

_SQL_NORMALIZAR_NOMBRE = (
    "translate(lower(trim(s.nombre)), "
    "'áéíóúüñàèìòùâêîôûãõç', "
    "'aeiouunaeiouaeiouaoc')"
)


def resolver_sitio_pregunta_directa(
    db: Session,
    payload: PreguntaDirectaEntrada,
) -> PreguntaDirectaExito | PreguntaDirectaSinSitios | PreguntaDirectaFallo:
    valor_estado = payload.model_dump(mode="json")
    nombre_entidad = normalizar_texto(payload.nombre_entidad or "")
    if not nombre_entidad:
        mensaje = "Debe enviar nombre_entidad."
        return PreguntaDirectaFallo(
            fallo=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="pregunta_directa",
                estado="error",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    nombre_ascii = sin_acentos(nombre_entidad)
    filtros_sql = ["s.activo = TRUE"]
    params: dict[str, object] = {
        "nombre_entidad": nombre_ascii,
        "umbral": UMBRAL_SUGERENCIA_PREGUNTA_DIRECTA,
    }
    agregar_filtro_ids(filtros_sql, params, payload.ids_consulta)

    score_sql = f"similarity({_SQL_NORMALIZAR_NOMBRE}, :nombre_entidad)"
    query = f"""
        SELECT
            s.id_sitio,
            s.nombre,
            {score_sql} AS score
        FROM turismo.sitio s
        WHERE {' AND '.join(filtros_sql)}
          AND {score_sql} >= :umbral
        ORDER BY score DESC, s.id_sitio ASC
        LIMIT {MAX_SUGERENCIAS_PREGUNTA_DIRECTA}
    """

    rows = list(db.execute(text(query), params).mappings())
    if not rows:
        mensaje = "No encontré sitios registrados parecidos a ese nombre."
        return PreguntaDirectaSinSitios(
            sin_sitios=mensaje,
            estado_busqueda=construir_estado_busqueda(
                nombre="pregunta_directa",
                estado="no_cumplido",
                valor=valor_estado,
                ids_entrada=payload.ids_consulta,
                detalle=mensaje,
            ),
        )

    row = rows[0]
    id_sitio = int(row["id_sitio"])
    nombre = str(row["nombre"])
    score = float(row["score"])
    if score < UMBRAL_PREGUNTA_DIRECTA:
        sugerencias = [
            PreguntaDirectaExito(
                ids_sitio=[int(item["id_sitio"])],
                id_sitio=int(item["id_sitio"]),
                nombre=str(item["nombre"]),
                score=float(item["score"]),
                mensaje="Coincidencia aproximada registrada.",
                estado_busqueda=None,
            )
            for item in rows
        ]
        mensaje = "Encontré sitios parecidos, pero necesito que confirmes a cuál te refieres."
        return PreguntaDirectaSinSitios(
            sin_sitios=mensaje,
            sugerencias=sugerencias,
            estado_busqueda=construir_estado_busqueda(
                nombre="pregunta_directa",
                estado="no_cumplido",
                valor={
                    **valor_estado,
                    "score": score,
                    "umbral_resolucion": UMBRAL_PREGUNTA_DIRECTA,
                    "umbral_sugerencia": UMBRAL_SUGERENCIA_PREGUNTA_DIRECTA,
                    "sugerencias": [
                        {
                            "id_sitio": sugerencia.id_sitio,
                            "nombre": sugerencia.nombre,
                            "score": sugerencia.score,
                        }
                        for sugerencia in sugerencias
                    ],
                },
                ids_entrada=payload.ids_consulta,
                ids_salida=[sugerencia.id_sitio for sugerencia in sugerencias],
                detalle=mensaje,
            ),
        )

    return PreguntaDirectaExito(
        ids_sitio=[id_sitio],
        id_sitio=id_sitio,
        nombre=nombre,
        score=score,
        mensaje="Sitio encontrado en la base de datos.",
        estado_busqueda=construir_estado_busqueda(
            nombre="pregunta_directa",
            estado="cumplido",
            valor={**valor_estado, "score": score, "nombre_resuelto": nombre},
            ids_entrada=payload.ids_consulta,
            ids_salida=[id_sitio],
            detalle="Se resolvió una entidad turística registrada.",
        ),
    )
