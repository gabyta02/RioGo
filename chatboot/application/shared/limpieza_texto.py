from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

from application.state import SharedFlowState
from infrastructure.config import get_settings

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "limpieza_data.json"


@lru_cache(maxsize=1)
def cargar_limpieza_data() -> dict[str, Any]:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _regex(key: str) -> str:
    return cargar_limpieza_data().get("regex", {}).get(key, "")


def _regex_list(key: str) -> list[str]:
    return list(cargar_limpieza_data().get("regex_lists", {}).get(key, []))


def _list_data(key: str) -> list[str]:
    return list(cargar_limpieza_data().get("lists", {}).get(key, []))


def _dict_data(key: str) -> dict[str, str]:
    return dict(cargar_limpieza_data().get("maps", {}).get(key, {}))


def _responses() -> dict[str, str]:
    return dict(cargar_limpieza_data().get("responses", {}))


def _settings():
    return get_settings().tools.shared.limpieza


def normalizar_espacios(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    lineas = [
        re.sub(_regex("multiple_spaces"), " ", linea).strip()
        for linea in texto.split("\n")
    ]
    texto = "\n".join(lineas)
    limite = _settings().max_saltos_linea_consecutivos
    return re.sub(
        _regex("excessive_newlines_template").format(limit=limite + 1),
        "\n" * limite,
        texto,
    ).strip()


def remover_control_chars(texto: str) -> str:
    permitidos = {"\n", "\r", "\t"}
    return "".join(
        char
        for char in texto
        if char in permitidos or unicodedata.category(char) not in {"Cc", "Cf"}
    )


def reducir_repeticiones(texto: str) -> str:
    limite = _settings().max_repeticion_caracter
    pattern = _regex("repeated_letters_template").format(limit=limite)
    return re.sub(pattern, r"\1" * limite, texto)


def normalizar(texto: str, lowercase: bool = False) -> str:
    if texto is None:
        return ""
    texto = str(texto).strip()
    texto = remover_control_chars(texto)
    texto = reducir_repeticiones(texto)
    texto = normalizar_espacios(texto)
    return texto.lower() if lowercase else texto


def contar_palabras(texto: str) -> int:
    return len((texto or "").split())


def excede_limite_palabras(texto: str) -> bool:
    return contar_palabras(texto) > _settings().max_palabras_mensaje


def expandir_contracciones(texto: str) -> str:
    contracciones = _dict_data("contracciones")
    if not contracciones:
        return texto

    def reemplazar(match: re.Match[str]) -> str:
        token = match.group(0)
        return contracciones.get(token.casefold(), token)

    return re.sub(
        _regex("word_token"),
        reemplazar,
        texto,
        flags=re.IGNORECASE,
    )


def es_palabra_permitida(token: str) -> bool:
    permitidas = {item.casefold() for item in _list_data("palabras_permitidas")}
    return token.casefold() in permitidas


def es_mensaje_unico_corto(texto: str) -> bool:
    tokens = re.findall(_regex("word_token"), texto or "")
    if len(tokens) != 1:
        return False
    token = tokens[0]
    if es_palabra_permitida(token):
        return False
    solo_letras = re.sub(_regex("non_letters"), "", token)
    return 1 <= len(solo_letras) <= 2


def decodificar_texto_seguridad(texto: str) -> str:
    texto_decodificado = str(texto or "")
    for _ in range(2):
        nuevo = unquote(texto_decodificado)
        if nuevo == texto_decodificado:
            break
        texto_decodificado = nuevo
    return unicodedata.normalize("NFKC", texto_decodificado)


def normalizar_seguridad(texto: str) -> tuple[str, str]:
    normalizado = decodificar_texto_seguridad(texto).casefold()
    compacto = re.sub(
        _regex("non_alphanumeric_security"),
        "",
        normalizado,
        flags=re.IGNORECASE,
    )
    return normalizado, compacto


def es_inyeccion_script(texto: str) -> bool:
    normalizado, compacto = normalizar_seguridad(texto)
    if any(
        re.search(pattern, normalizado, flags=re.IGNORECASE | re.DOTALL)
        for pattern in _regex_list("script_patterns")
    ):
        return True
    return any(token in compacto for token in _list_data("script_compact_tokens"))


def es_consulta_sql(texto: str) -> bool:
    normalizado, compacto = normalizar_seguridad(texto)
    if re.search(_regex("sql_primary_keywords"), normalizado) and re.search(
        _regex("sql_secondary_keywords"), normalizado
    ):
        return True
    if any(token in compacto for token in _list_data("sql_compact_tokens")):
        return True
    if re.search(_regex("sql_boolean_condition"), normalizado):
        return True
    if "--" in normalizado and re.search(_regex("sql_comment_keywords"), normalizado):
        return True
    return False


def es_email(texto: str) -> bool:
    return bool(re.search(_regex("email"), (texto or "").strip(), flags=re.UNICODE))


def parece_url(texto: str) -> bool:
    return bool(re.search(_regex("url"), texto or "", flags=re.IGNORECASE))


def es_entrada_numerica_sospechosa(texto: str) -> bool:
    texto = (texto or "").strip()
    if not texto or re.search(_regex("letters"), texto):
        return False
    digitos = re.sub(_regex("non_digits"), "", texto)
    return len(digitos) >= _settings().min_digitos_sin_contexto


def tiene_numero_largo_sin_contexto(texto: str) -> bool:
    texto = (texto or "").strip()
    if not texto:
        return False
    if re.search(_regex("numeric_message"), texto):
        digitos = re.sub(_regex("non_digits"), "", texto)
        return len(digitos) >= _settings().min_digitos_sin_contexto
    return False


def _token_absurdo(token: str) -> bool:
    token_limpio = re.sub(_regex("non_ascii_letters"), "", token.casefold())
    if len(token_limpio) < 5:
        return False
    if re.search(_regex("absurd_sequences"), token_limpio):
        return True
    if re.search(_regex("absurd_repeated_char"), token_limpio):
        return True
    if re.search(_regex("absurd_repeated_pair"), token_limpio):
        return True
    vocales = set(_list_data("vowels"))
    total_vocales = sum(1 for char in token_limpio if char in vocales)
    ratio_vocales = total_vocales / max(len(token_limpio), 1)
    if ratio_vocales < 0.20 or ratio_vocales > 0.90:
        return True
    if re.search(_regex("absurd_consonants"), token_limpio):
        return True
    return False


def evaluar_texto_limpio(texto: str) -> tuple[bool, str | None]:
    texto = (texto or "").strip()
    if not texto:
        return False, "texto_vacio"
    tokens = re.findall(_regex("letters_token"), texto)
    if not tokens:
        return True, None
    absurdos = [token for token in tokens if _token_absurdo(token)]
    if len(tokens) <= 3 and absurdos:
        return False, "patron_absurdo"
    if len(absurdos) >= 2 and len(absurdos) >= max(2, len(tokens) // 2):
        return False, "patron_absurdo"
    return True, None


class ReglaLimpieza:
    def __init__(
        self,
        motivo: str,
        validador: Callable[[str], bool],
        conservar_texto: bool = False,
    ) -> None:
        self.motivo = motivo
        self.validador = validador
        self.conservar_texto = conservar_texto


REGLAS_LIMPIEZA = [
    ReglaLimpieza("limite_palabras", excede_limite_palabras),
    ReglaLimpieza("inyeccion_script", es_inyeccion_script),
    ReglaLimpieza("consulta_sql", es_consulta_sql),
    ReglaLimpieza("email_detectado", es_email),
    ReglaLimpieza("url_detectada", parece_url),
    ReglaLimpieza("mensaje_muy_corto", es_mensaje_unico_corto, conservar_texto=True),
    ReglaLimpieza("enumeracion_numerica", es_entrada_numerica_sospechosa),
    ReglaLimpieza("enumeracion_numerica", tiene_numero_largo_sin_contexto),
]


def construir_resultado_limpieza(
    texto_original: str,
    texto_limpio: str,
    es_basura: bool,
    motivo_basura: str | None,
) -> dict[str, Any]:
    return {
        "texto_original": texto_original,
        "texto_limpio": texto_limpio,
        "es_basura": es_basura,
        "motivo_basura": motivo_basura,
        "mensaje_sistema": obtener_mensaje_limpieza(motivo_basura, es_basura),
    }


def obtener_mensaje_limpieza(
    motivo_basura: str | None,
    es_basura: bool,
) -> str | None:
    if not es_basura:
        return None
    responses = _responses()
    if motivo_basura and responses.get(motivo_basura):
        return responses[motivo_basura]
    return responses.get("default")


def aplicar_reglas_iniciales(
    texto_original: str,
    texto_strip: str,
) -> dict[str, Any] | None:
    if not texto_strip:
        return construir_resultado_limpieza(
            texto_original=texto_original,
            texto_limpio="",
            es_basura=True,
            motivo_basura="texto_vacio",
        )
    for regla in REGLAS_LIMPIEZA:
        if regla.validador(texto_strip):
            texto_limpio = texto_strip if regla.conservar_texto else ""
            return construir_resultado_limpieza(
                texto_original=texto_original,
                texto_limpio=texto_limpio,
                es_basura=True,
                motivo_basura=regla.motivo,
            )
    return None


def limpiar_texto_usuario(texto: str) -> str:
    return normalizar(expandir_contracciones(texto), lowercase=False)


def procesar_limpieza_texto(texto_original: str) -> dict[str, Any]:
    texto_original = str(texto_original or "")
    texto_strip = texto_original.strip()
    resultado_inicial = aplicar_reglas_iniciales(texto_original, texto_strip)
    if resultado_inicial:
        return resultado_inicial

    texto_limpio = limpiar_texto_usuario(texto_strip)
    es_aceptable, motivo = evaluar_texto_limpio(texto_limpio)
    if not es_aceptable:
        return construir_resultado_limpieza(
            texto_original=texto_original,
            texto_limpio=texto_limpio,
            es_basura=True,
            motivo_basura=motivo,
        )

    return construir_resultado_limpieza(
        texto_original=texto_original,
        texto_limpio=texto_limpio,
        es_basura=False,
        motivo_basura=None,
    )


def ejecutar_limpieza_texto(state: SharedFlowState) -> SharedFlowState:
    resultado = procesar_limpieza_texto(state.get("mensaje_original", ""))
    bloqueado = bool(resultado["es_basura"])
    return {
        **state,
        "mensaje_limpio": resultado["texto_limpio"],
        "bloqueado": bloqueado,
        "motivo_bloqueo": resultado["motivo_basura"],
        "mensaje_sistema": resultado["mensaje_sistema"],
        "origen_mensaje_sistema": "limpieza_texto" if bloqueado else None,
    }
