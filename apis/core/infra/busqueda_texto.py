import re

from rapidfuzz import fuzz

from core.infra.catalogo_trgm import normalizar_texto, sin_acentos

PALABRAS_VIA = frozenset({
    "calle",
    "calles",
    "avenida",
    "avenidas",
    "av",
    "ave",
    "pasaje",
    "pasajes",
    "pj",
    "via",
    "ruta",
    "rutas",
    "blvd",
    "boulevard",
    "boulevar",
})

UMBRAL_TRGM_REFERENCIA = 0.60
UMBRAL_FINAL_REFERENCIA = 0.90
TOP_CANDIDATOS_REFERENCIA = 10
PALABRAS_PRIORIZA_DIRECCION = 3


def quitar_prefijos_via(texto: str) -> str:
    palabras = [
        palabra
        for palabra in normalizar_texto(texto).split()
        if sin_acentos(palabra.rstrip(".")) not in PALABRAS_VIA
    ]
    return " ".join(palabras)


def contar_palabras(texto: str) -> int:
    return len(texto.split()) if texto else 0


def score_comparacion(consulta: str, destino: str) -> float:
    consulta_norm = sin_acentos(normalizar_texto(consulta))
    destino_norm = sin_acentos(normalizar_texto(destino))
    if not consulta_norm or not destino_norm:
        return 0.0
    return round(
        max(
            fuzz.ratio(consulta_norm, destino_norm),
            fuzz.token_sort_ratio(consulta_norm, destino_norm),
        )
        / 100.0,
        4,
    )


def score_trigram_local(texto: str | None, keyword: str) -> float:
    """Aproxima GREATEST(similarity, word_similarity) de pg_trgm sin round-trip a BD."""
    contenido = str(texto or "").strip()
    if not contenido or not keyword.strip():
        return 0.0
    consulta_norm = sin_acentos(normalizar_texto(keyword))
    destino_norm = sin_acentos(normalizar_texto(contenido))
    return round(
        max(
            fuzz.ratio(consulta_norm, destino_norm),
            fuzz.partial_ratio(consulta_norm, destino_norm),
            fuzz.token_sort_ratio(consulta_norm, destino_norm),
        )
        / 100.0,
        4,
    )


_STOPWORDS_KEYWORD = frozenset({
    "a",
    "al",
    "de",
    "del",
    "en",
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "y",
    "o",
    "por",
    "para",
    "con",
    "sin",
    "e",
})


def _palabras_significativas(texto: str) -> list[str]:
    return [
        palabra
        for palabra in re.findall(r"\w+", texto)
        if palabra and palabra not in _STOPWORDS_KEYWORD
    ]


def _similitud_palabras(palabra_kw: str, palabra_dest: str) -> float:
    if palabra_kw == palabra_dest:
        return 1.0
    if len(palabra_kw) >= 4 and (
        palabra_dest == f"{palabra_kw}s" or palabra_kw == f"{palabra_dest}s"
    ):
        return 1.0
    score = fuzz.ratio(palabra_kw, palabra_dest) / 100.0
    if (
        score >= 0.90
        and len(palabra_kw) >= 6
        and len(palabra_dest) >= 6
        and abs(len(palabra_kw) - len(palabra_dest)) <= 2
    ):
        return round(score, 4)
    return score if score >= 0.95 else 0.0


def _frase_exacta_en_texto(consulta_norm: str, destino_norm: str) -> bool:
    palabras = _palabras_significativas(consulta_norm)
    if not palabras:
        return False
    patron = r"\b" + r"\s+".join(re.escape(palabra) for palabra in palabras) + r"\b"
    return re.search(patron, destino_norm) is not None


def score_keyword_en_texto(texto: str | None, keyword: str) -> float:
    """Compara un keyword con palabras del texto (aproxima pg_trgm word_similarity).

    Evita falsos positivos de partial_ratio sobre cadenas largas: solo puntúa si el
    keyword coincide con una palabra del destino o la frase aparece como subcadena.
    """
    contenido = str(texto or "").strip()
    keyword = str(keyword or "").strip()
    if not contenido or not keyword:
        return 0.0

    consulta_norm = sin_acentos(normalizar_texto(keyword))
    destino_norm = sin_acentos(normalizar_texto(contenido))
    if not consulta_norm or not destino_norm:
        return 0.0

    if _frase_exacta_en_texto(consulta_norm, destino_norm):
        return 1.0

    palabras_kw = _palabras_significativas(consulta_norm)
    palabras_dest = _palabras_significativas(destino_norm)
    if not palabras_kw or not palabras_dest:
        return 0.0

    if len(palabras_kw) == 1:
        palabra_kw = palabras_kw[0]
        return round(
            max(_similitud_palabras(palabra_kw, palabra) for palabra in palabras_dest),
            4,
        )

    mejores: list[float] = []
    for palabra_kw in palabras_kw:
        mejores.append(
            max(_similitud_palabras(palabra_kw, palabra) for palabra in palabras_dest)
        )
    if all(score >= 0.95 for score in mejores):
        return round(min(mejores), 4)
    return 0.0


def mejor_score_direccion(
    consulta_limpia: str,
    direccion: str,
    referencia: str | None,
) -> float:
    direccion_limpia = quitar_prefijos_via(direccion)
    score_dir = score_comparacion(consulta_limpia, direccion_limpia)
    if referencia and referencia.strip():
        score_ref = score_comparacion(consulta_limpia, quitar_prefijos_via(referencia))
        return max(score_dir, score_ref)
    return score_dir
