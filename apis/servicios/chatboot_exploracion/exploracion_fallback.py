from __future__ import annotations

import random
import re
from typing import Any, Callable

FILTROS_RESTRINGENTES = frozenset({
    "precio",
    "tarifa_acceso",
    "horario",
    "contactos",
    "campos_parametrizados",
    "busqueda_aproximada",
})

CATEGORIAS_EXPLORACION = [
    "Alojamiento",
    "Alimentos y Bebidas",
    "Comunitario",
    "Transporte Turistico",
    "Aguas Termales",
    "Sala de Recepciones",
    "Discoteca",
    "Bar",
    "Guianza Turística",
    "Operación e intermediación",
    "Atractivos Naturales",
    "Manifestaciones Culturales",
]

MAX_SUGERENCIAS_EXPLORACION = 6

PALABRAS_CATEGORIA: dict[str, str] = {
    "hostal": "Alojamiento",
    "hotel": "Alojamiento",
    "alojamiento": "Alojamiento",
    "hospedaje": "Alojamiento",
    "museo": "Manifestaciones Culturales",
    "iglesia": "Manifestaciones Culturales",
    "templo": "Manifestaciones Culturales",
    "restaurante": "Alimentos y Bebidas",
    "comida": "Alimentos y Bebidas",
    "laguna": "Atractivos Naturales",
    "mirador": "Atractivos Naturales",
    "montaña": "Atractivos Naturales",
    "montana": "Atractivos Naturales",
    "termal": "Aguas Termales",
    "aguas termales": "Aguas Termales",
}

ETIQUETAS_PRECIO_TEXTO = {
    "economico": "económicos",
    "economica": "económicas",
    "medio": "de precio medio",
    "alto": "de precio alto",
}


def _normalizar(texto: str | None) -> str:
    return str(texto or "").strip().lower()


def tiene_criterio_busqueda_aproximada(params: dict[str, Any]) -> bool:
    return bool(_normalizar(params.get("direccion_referencia")))


def debe_aplicar_recomendacion_calida(
    nombre_herr: str,
    params: dict[str, Any],
    ids_antes_del_paso: list[int],
    ids_despues_del_paso: list[int],
    tiene_criterio_filtro: Callable[[str, dict[str, Any]], bool],
) -> bool:
    if nombre_herr not in FILTROS_RESTRINGENTES:
        return False
    if not ids_antes_del_paso or ids_despues_del_paso:
        return False
    if nombre_herr == "busqueda_aproximada":
        return tiene_criterio_busqueda_aproximada(params)
    return tiene_criterio_filtro(nombre_herr, params)


def _referencia_tipo_sitio(
    subcategoria: str | None,
    categoria: str | None = None,
) -> str:
    if subcategoria and str(subcategoria).strip():
        nombre = str(subcategoria).strip().lower()
        femeninos = {
            "laguna",
            "montaña",
            "montana",
            "cascada",
            "quebrada",
            "iglesia",
            "hostería",
            "hosteria",
            "cafeteria",
            "discoteca",
            "gastronomía",
            "gastronomia",
        }
        if nombre in femeninos or nombre.endswith("a"):
            return f"las opciones de {nombre}"
        return f"los {nombre}s"

    if categoria and str(categoria).strip():
        cat = str(categoria).strip().lower()
        if cat == "alojamiento":
            return "las opciones de hospedaje"
        if cat.endswith("a") or cat.endswith("ión") or cat.endswith("ion"):
            return f"las opciones de {cat}"
        return f"los sitios de {cat}"

    return "las opciones registradas"


def _mensaje_precio(
    params: dict[str, Any],
    subcategoria: str | None,
    categoria: str | None,
) -> str:
    etiqueta = _normalizar(params.get("etiqueta"))
    etiqueta_texto = ETIQUETAS_PRECIO_TEXTO.get(etiqueta, etiqueta or "ese criterio de precio")
    referencia = _referencia_tipo_sitio(subcategoria, categoria)

    if etiqueta in {"economico", "economica"} and _normalizar(categoria) == "alojamiento":
        return (
            "No encontré alojamientos registrados específicamente como económicos, "
            "pero te muestro las opciones de hospedaje que tengo disponibles en "
            "Riobamba para que puedas revisar sus precios."
        )

    return (
        f"No encontré sitios con precio {etiqueta_texto}, "
        f"pero te muestro {referencia} disponibles en Riobamba para que puedas revisar."
    )


def construir_mensaje_recomendacion(
    nombre_herr: str,
    params: dict[str, Any],
    *,
    subcategoria: str | None = None,
    categoria: str | None = None,
) -> str:
    if nombre_herr in ("precio", "tarifa_acceso"):
        return _mensaje_precio(params, subcategoria, categoria)

    referencia = _referencia_tipo_sitio(subcategoria, categoria)

    if nombre_herr == "busqueda_aproximada":
        zona = str(params.get("direccion_referencia") or "esa zona").strip()
        return (
            f"No encontré sitios exactamente en '{zona}', "
            f"pero te muestro {referencia} que tengo registradas en Riobamba."
        )

    if nombre_herr == "horario":
        return (
            f"No encontré sitios que cumplan con el horario indicado, "
            f"pero te muestro {referencia} para que puedas revisar sus horarios."
        )

    if nombre_herr == "contactos":
        contacto = str(params.get("contacto_sugerido") or "contacto").strip()
        return (
            f"No encontré sitios con {contacto} disponible, "
            f"pero te muestro {referencia} para que puedas revisar."
        )

    if nombre_herr == "campos_parametrizados":
        return (
            f"No encontré sitios que cumplan con esas características, "
            f"pero te muestro {referencia} disponibles en Riobamba."
        )

    return (
        f"No encontré opciones que cumplan exactamente con ese filtro, "
        f"pero te muestro {referencia} por si te interesa explorar."
    )


def marcar_recomendacion_en_campos(
    campos_rama: dict[int, dict[str, Any]],
    ids_restaurados: list[int],
    nombre_herr: str,
    mensaje: str,
) -> None:
    for id_sitio in ids_restaurados:
        campos_rama[id_sitio]["recomendacion_fallback"] = True
        campos_rama[id_sitio]["filtro_fallido"] = nombre_herr
        campos_rama[id_sitio]["recomendacion_turistica"] = mensaje


def _inferir_categorias_desde_herramientas(
    herramientas: list[Any],
) -> list[str]:
    inferidas: list[str] = []

    for paso in herramientas:
        params = dict(getattr(paso, "parametros", {}) or {})
        categoria = params.get("categoria")
        if categoria and str(categoria).strip() in CATEGORIAS_EXPLORACION:
            inferidas.append(str(categoria).strip())

        textos: list[str] = []
        texto_embeddings = params.get("texto_embeddings")
        if texto_embeddings:
            textos.append(str(texto_embeddings))
        for frase in params.get("posibles_match") or []:
            textos.append(str(frase))

        texto_unido = " ".join(textos).lower()
        for palabra, categoria_mapa in PALABRAS_CATEGORIA.items():
            if re.search(rf"\b{re.escape(palabra)}\b", texto_unido):
                inferidas.append(categoria_mapa)

    vistos: set[str] = set()
    resultado: list[str] = []
    for categoria in inferidas:
        if categoria not in vistos:
            vistos.add(categoria)
            resultado.append(categoria)
    return resultado


def generar_fallback_frio(herramientas: list[Any]) -> list[str]:
    inferidas = _inferir_categorias_desde_herramientas(herramientas)
    sugerencias: list[str] = list(inferidas)

    restantes = [c for c in CATEGORIAS_EXPLORACION if c not in sugerencias]
    if len(sugerencias) < MAX_SUGERENCIAS_EXPLORACION and restantes:
        muestra = random.sample(
            restantes,
            min(MAX_SUGERENCIAS_EXPLORACION - len(sugerencias), len(restantes)),
        )
        sugerencias.extend(muestra)

    return sugerencias[:MAX_SUGERENCIAS_EXPLORACION]


MENSAJE_FALLBACK_FRIO = (
    "No encontré sitios que coincidan con tu búsqueda. "
    "¿Te gustaría explorar alguna de estas categorías?"
)
