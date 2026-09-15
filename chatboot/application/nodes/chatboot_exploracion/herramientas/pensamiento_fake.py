from __future__ import annotations

from typing import Any

from application.shared.empaquetar_mensaje import construir_stream

from .base import ResultadoHerramienta, TipoIds, construir_estado

GUION_BASE = [
    {
        "fase": "entendiendo_consulta",
        "texto": "Estoy entendiendo lo que buscas para orientarte mejor.",
    },
    {
        "fase": "organizando_busqueda",
        "texto": "Estoy organizando la búsqueda con los detalles que mencionaste.",
    },
    {
        "fase": "buscando_opciones",
        "texto": "Estoy buscando opciones turísticas que se acerquen a tu plan.",
    },
    {
        "fase": "comparando_resultados",
        "texto": "Estoy comparando alternativas para quedarme con las más útiles.",
    },
    {
        "fase": "revisando_detalles",
        "texto": "Estoy revisando detalles como ubicación, horarios o características cuando aplican.",
    },
    {
        "fase": "preparando_respuesta",
        "texto": "Estoy preparando una respuesta clara con lo encontrado.",
    },
    {
        "fase": "afinando_respuesta",
        "texto": "Estoy afinando el mensaje para que sea fácil de leer.",
    },
    {
        "fase": "casi_listo",
        "texto": "Ya casi está listo; estoy ordenando las opciones para mostrártelas.",
    },
]

TEXTOS_POR_HERRAMIENTA = {
    "busqueda_referencia": "Estoy revisando opciones relacionadas con la zona o referencia indicada.",
    "busqueda_ubicacion": "Estoy revisando la ubicación o cercanía para filtrar opciones convenientes.",
    "contactos": "Estoy considerando el dato de contacto que mencionaste.",
    "horario": "Estoy revisando disponibilidad horaria cuando la información lo permite.",
    "precio": "Estoy tomando en cuenta el rango de precio solicitado.",
    "tarifa_acceso": "Estoy revisando condiciones de entrada o acceso.",
    "atributos_booleanos": "Estoy considerando servicios y características del lugar.",
    "ruta": "Estoy buscando rutas turísticas relacionadas con tu plan.",
    "gis": "Estoy comparando cercanía para mostrar opciones convenientes.",
    "busqueda_semantica": "Estoy buscando coincidencias por detalles parecidos a lo que escribiste.",
    "conversacional": "Estoy preparando una respuesta breve para ti.",
    "fallback": "Estoy buscando la forma más útil de orientarte.",
}


def construir_guion(plan: dict[str, Any] | None = None) -> list[dict[str, str]]:
    guion = list(GUION_BASE[:3])
    nombres = _extraer_nombres_herramientas(plan)
    for nombre in nombres:
        texto = TEXTOS_POR_HERRAMIENTA.get(nombre)
        if texto:
            guion.append({"fase": f"herramienta_{nombre}", "texto": texto})
    guion.extend(GUION_BASE[3:])
    return _deduplicar_por_texto(guion)


def construir_mensaje_stream(
    *,
    fase: str,
    texto: str,
    indice: int,
    total: int,
) -> dict[str, Any]:
    mensaje = construir_stream(
        {
            "fase": fase,
            "texto": texto,
            "indice": str(indice),
            "total": str(total),
        }
    )
    mensaje["mensaje"]["origen"] = "pensamiento_fake"
    return mensaje


async def ejecutar(
    *,
    orden: int,
    parametros: dict[str, Any],
    ids_consulta: list[int],
    tipo_ids: TipoIds | None,
    state: dict[str, Any],
    cliente: Any,
) -> tuple[ResultadoHerramienta, TipoIds | None]:
    guion = construir_guion(state.get("plan") if isinstance(state, dict) else None)
    payload = {"stream": guion}
    return (
        construir_estado(
            "pensamiento_fake",
            orden,
            "ok",
            payload=payload,
            nota="Guion de progreso generado.",
        ),
        tipo_ids,
    )


def _extraer_nombres_herramientas(plan: dict[str, Any] | None) -> list[str]:
    if not isinstance(plan, dict):
        return []
    consultas = plan.get("consultas")
    if not isinstance(consultas, list):
        return []

    nombres: list[str] = []
    for consulta in consultas:
        if not isinstance(consulta, dict):
            continue
        ejecuciones = consulta.get("ejecucion_herramienta")
        if not isinstance(ejecuciones, list):
            continue
        for ejecucion in sorted(
            [item for item in ejecuciones if isinstance(item, dict)],
            key=lambda item: int(item.get("orden") or 0),
        ):
            herramienta = ejecucion.get("herramienta")
            if not isinstance(herramienta, dict):
                continue
            nombre = str(herramienta.get("nombre") or "").strip()
            if nombre:
                nombres.append(nombre)
    return nombres


def _deduplicar_por_texto(guion: list[dict[str, str]]) -> list[dict[str, str]]:
    salida: list[dict[str, str]] = []
    vistos: set[str] = set()
    for item in guion:
        texto = str(item.get("texto") or "").strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        salida.append(
            {
                "fase": str(item.get("fase") or "progreso"),
                "texto": texto,
            }
        )
    return salida
