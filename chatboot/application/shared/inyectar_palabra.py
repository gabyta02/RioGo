from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz, process

from application.state import PalabraInyectada, SharedFlowState
from infrastructure.config import get_settings

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "inyectar_palabra.json"


@lru_cache(maxsize=1)
def _cargar_data() -> dict[str, Any]:
    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _settings():
    return get_settings().tools.shared.inyectar_palabra


def _stopwords() -> set[str]:
    config = _cargar_data().get("_config", {})
    return {word.casefold() for word in config.get("stopwords", [])}


def _normalizar(texto: str) -> str:
    if not texto:
        return ""
    texto = texto.casefold().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _tokens(texto: str) -> list[str]:
    return _normalizar(texto).split()


@lru_cache(maxsize=1)
def _construir_indice() -> dict[str, list[Any]]:
    data = _cargar_data()
    entries: list[dict[str, str]] = []

    def agregar_entrada(texto_ref: str, palabra: str, significado: str) -> None:
        variante = (texto_ref or "").strip()
        variante_norm = _normalizar(variante)
        if not variante_norm:
            return
        entries.append(
            {
                "variante": variante,
                "variante_norm": variante_norm,
                "palabra": (palabra or "").strip(),
                "significado": (significado or "").strip(),
            }
        )

    for key, bloque in data.items():
        if key.startswith("_") or not isinstance(bloque, dict):
            continue
        for item in bloque.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            palabra = (item.get("palabra") or "").strip()
            significado = (item.get("significado") or "").strip()
            if not palabra:
                continue
            agregar_entrada(palabra, palabra, significado)
            for variante in item.get("variantes", []) or []:
                agregar_entrada(variante, palabra, significado)

    return {
        "entries": entries,
        "variantes_norm": [entry["variante_norm"] for entry in entries],
    }


def _generar_ngrams(texto: str) -> list[str]:
    tokens = _tokens(texto)
    if not tokens:
        return []

    ngramas: list[str] = []
    ventana_maxima = min(_settings().ventana_ngrams_max, len(tokens))
    for longitud in range(1, ventana_maxima + 1):
        for inicio in range(0, len(tokens) - longitud + 1):
            ngramas.append(" ".join(tokens[inicio : inicio + longitud]))
    return ngramas


def _es_ngram_util(ngram: str) -> bool:
    tokens = [token for token in ngram.split() if token]
    if not tokens:
        return False
    if len(tokens) == 1:
        token = tokens[0]
        if token in _stopwords():
            return False
        return len(token) >= 4
    return True


def _puntuar(ngram: str, variante_norm: str) -> int:
    return int(max(fuzz.token_set_ratio(ngram, variante_norm), fuzz.ratio(ngram, variante_norm)))


def _interseccion_tokens(texto_a: str, texto_b: str) -> float:
    stopwords = _stopwords()
    tokens_a = {token for token in texto_a.split() if token and token not in stopwords}
    tokens_b = {token for token in texto_b.split() if token and token not in stopwords}
    if not tokens_a or not tokens_b:
        return 0.0
    interseccion = len(tokens_a & tokens_b)
    base = min(len(tokens_a), len(tokens_b))
    return interseccion / max(1, base)


def _es_correccion_tipografica_segura(ngram: str, variante_norm: str, score: int) -> bool:
    tokens_ngram = ngram.split()
    tokens_variante = variante_norm.split()
    if len(tokens_ngram) != 1 or len(tokens_variante) != 1:
        return False
    if score < _settings().rapidfuzz_score_medio:
        return False
    origen = tokens_ngram[0]
    destino = tokens_variante[0]
    if len(origen) < 6 or len(destino) < 6:
        return False
    return abs(len(origen) - len(destino)) <= 2


def _confianza_por_score(score: int) -> str:
    if score >= _settings().rapidfuzz_score_alto:
        return "alta"
    if score >= _settings().rapidfuzz_score_medio:
        return "media"
    return "baja"


def extraer_palabras_inyectadas(texto: str) -> list[PalabraInyectada]:
    texto_norm = _normalizar(texto)
    if not texto_norm:
        return []

    indice = _construir_indice()
    entries = indice.get("entries", [])
    variantes_norm = indice.get("variantes_norm", [])
    if not entries or not variantes_norm:
        return []

    candidatos: list[PalabraInyectada] = []
    for ngrama in _generar_ngrams(texto_norm):
        if not _es_ngram_util(ngrama):
            continue
        coincidencias = process.extract(
            ngrama,
            variantes_norm,
            scorer=fuzz.WRatio,
            limit=5,
        )
        for variante_norm, score_rapidfuzz, indice_entry in coincidencias:
            if score_rapidfuzz < _settings().rapidfuzz_score_minimo:
                continue
            score_final = _puntuar(ngrama, variante_norm)
            if score_final < _settings().rapidfuzz_score_minimo:
                continue
            es_correccion_tipografica = _es_correccion_tipografica_segura(
                ngrama,
                variante_norm,
                score_final,
            )
            if (
                _interseccion_tokens(ngrama, variante_norm) < 0.5
                and not es_correccion_tipografica
            ):
                continue
            entry = entries[indice_entry]
            termino_normalizado = entry["palabra"].replace("_", " ")
            texto_detectado_norm = _normalizar(ngrama)
            termino_norm = _normalizar(termino_normalizado)
            variante_detectada_norm = _normalizar(entry["variante"])
            correccion_aplicada = (
                es_correccion_tipografica
                or texto_detectado_norm not in {termino_norm, variante_detectada_norm}
            )
            candidatos.append(
                {
                    "texto_detectado": ngrama,
                    "variante": entry["variante"],
                    "palabra": entry["palabra"],
                    "significado": entry.get("significado", ""),
                    "score": score_final,
                    "confianza": _confianza_por_score(score_final),
                    "termino_normalizado": termino_normalizado,
                    "correccion_aplicada": correccion_aplicada,
                    "correccion_sugerida": correccion_aplicada,
                }
            )

    mejores: dict[str, PalabraInyectada] = {}
    for candidato in sorted(candidatos, key=lambda item: item["score"], reverse=True):
        palabra = candidato["palabra"]
        if palabra not in mejores:
            mejores[palabra] = candidato

    return list(mejores.values())[: _settings().max_etiquetas]


def ejecutar_inyectar_palabra(state: SharedFlowState) -> SharedFlowState:
    palabras_inyectadas = extraer_palabras_inyectadas(state.get("mensaje_limpio", ""))
    return {
        **state,
        "palabras_inyectadas": palabras_inyectadas,
    }
