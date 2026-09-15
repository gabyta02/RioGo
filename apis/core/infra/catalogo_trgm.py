import re
import unicodedata

from sqlalchemy import text
from sqlalchemy.orm import Session

UMBRAL_CATALOGO = 0.40

_TRANSLATE_ACENTOS_SQL = (
    "translate(lower({campo}), "
    "'áéíóúüñàèìòùâêîôûãõç', "
    "'aeiouunaeiouaeiouaoc')"
)


def normalizar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.strip().lower())


def sin_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(caracter for caracter in normalizado if not unicodedata.combining(caracter))


def _sql_ascii(campo: str) -> str:
    return _TRANSLATE_ACENTOS_SQL.format(campo=campo)


def _sql_score_trgm(campo: str) -> str:
    ascii_campo = _sql_ascii(campo)
    return f"""GREATEST(
        similarity({ascii_campo}, :texto_ascii),
        similarity({ascii_campo}, :limpio_ascii),
        word_similarity({ascii_campo}, :texto_ascii),
        word_similarity({ascii_campo}, :limpio_ascii)
    )"""


def sql_score_trgm(campo: str) -> str:
    return _sql_score_trgm(campo)


def params_texto_busqueda(texto: str, texto_limpio: str) -> dict[str, str]:
    texto_ascii = sin_acentos(normalizar_texto(texto))
    limpio_ascii = sin_acentos(normalizar_texto(texto_limpio)) or texto_ascii
    return {
        "texto_ascii": texto_ascii,
        "limpio_ascii": limpio_ascii,
    }


def normalizar_excluir(excluir: list[str]) -> list[str]:
    return [normalizar_texto(item) for item in excluir if item and item.strip()]


def resolver_id_categoria(
    db: Session,
    nombre: str,
) -> tuple[int | None, str | None]:
    texto_ascii = sin_acentos(normalizar_texto(nombre))
    row = db.execute(
        text(
            f"""
            SELECT
                id_categoria,
                nombre,
                {_sql_score_trgm("nombre")} AS score
            FROM turismo.categoria
            WHERE activo = TRUE
              AND {_sql_score_trgm("nombre")} > :umbral_catalogo
            ORDER BY score DESC
            LIMIT 1
            """
        ),
        {
            "texto_ascii": texto_ascii,
            "limpio_ascii": texto_ascii,
            "umbral_catalogo": UMBRAL_CATALOGO,
        },
    ).mappings().first()
    if not row:
        return None, None
    return int(row["id_categoria"]), row["nombre"]


def resolver_id_subcategoria(
    db: Session,
    nombre: str,
    id_categoria: int | None = None,
) -> tuple[int | None, str | None]:
    texto_ascii = sin_acentos(normalizar_texto(nombre))
    filtro_categoria = ""
    params: dict[str, object] = {
        "texto_ascii": texto_ascii,
        "limpio_ascii": texto_ascii,
        "umbral_catalogo": UMBRAL_CATALOGO,
    }
    if id_categoria is not None:
        filtro_categoria = "AND id_categoria = :id_categoria"
        params["id_categoria"] = id_categoria

    row = db.execute(
        text(
            f"""
            SELECT
                id_subcategoria,
                nombre,
                {_sql_score_trgm("nombre")} AS score
            FROM turismo.subcategoria
            WHERE activo = TRUE
              AND {_sql_score_trgm("nombre")} > :umbral_catalogo
              {filtro_categoria}
            ORDER BY score DESC
            LIMIT 1
            """
        ),
        params,
    ).mappings().first()
    if not row:
        return None, None
    return int(row["id_subcategoria"]), row["nombre"]
