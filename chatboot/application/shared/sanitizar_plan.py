from __future__ import annotations

from copy import deepcopy
from typing import Any

EXPLORACION_HERRAMIENTAS = {
    "busqueda_referencia",
    "busqueda_ubicacion",
    "busqueda_ubicacion_consulta",
    "contactos",
    "contacto_busqueda",
    "horario",
    "horario_consulta",
    "precio",
    "precio_consulta",
    "tarifa_acceso",
    "tarifa_acceso_consulta",
    "atributos_booleanos",
    "atributos_booleanos_consulta",
    "ruta",
    "ruta_consulta",
    "gis",
    "gis_consulta",
    "busqueda_semantica",
    "busqueda_semantica_consulta",
    "conversacional",
    "fallback",
    "pregunta_directa",
    "pregunta-directa",
}

PREGUNTA_HERRAMIENTAS = {
    "conversacional",
    "documento_sitio",
    "ficha_sitio",
    "chuck_documento",
    "chunk_documento",
    "multimedia",
    "como_llegar",
    "fallback",
}

PREGUNTA_PERMITE_PARAMETROS_VACIOS = {
    "documento_sitio",
    "ficha_sitio",
    "multimedia",
    "como_llegar",
}

FALLBACK_EXPLORACION = {
    "orden": 1,
    "herramienta": {
        "nombre": "fallback",
        "parametros": {},
    },
}

FALLBACK_PREGUNTA = {
    "orden": 1,
    "herramienta": {
        "nombre": "fallback",
        "parametros": {
            "respuesta_sugerida": (
                "No encontré una herramienta clara para responder esa pregunta "
                "sobre este sitio."
            ),
        },
    },
}

PROXIMIDAD_TEXTUAL_METROS = {
    "corta": 150,
    "media": 500,
    "larga": 1000,
}



def sanitizar_plan_exploracion(
    plan: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    return _sanitizar_plan(
        plan,
        canal="exploracion",
        herramientas_validas=EXPLORACION_HERRAMIENTAS,
        fallback=FALLBACK_EXPLORACION,
    )


def sanitizar_plan_pregunta(
    plan: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    plan_sanitizado, errores = _sanitizar_plan(
        plan,
        canal="pregunta_directa",
        herramientas_validas=PREGUNTA_HERRAMIENTAS,
        fallback=FALLBACK_PREGUNTA,
    )
    if plan_sanitizado is None:
        return None, errores

    errores_reglas = _validar_reglas_pregunta(plan_sanitizado)
    if errores_reglas:
        return None, [*errores, *errores_reglas]
    return plan_sanitizado, errores


def _sanitizar_plan(
    plan: dict[str, Any],
    *,
    canal: str,
    herramientas_validas: set[str],
    fallback: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not isinstance(plan.get("consultas"), list):
        return None, [
            {
                "tipo": "estructura_invalida",
                "detalle": "El plan debe incluir la clave consultas como lista",
            }
        ]

    errores: list[dict[str, Any]] = []
    consultas_sanitizadas: list[dict[str, Any]] = []

    for indice_consulta, consulta in enumerate(plan["consultas"], start=1):
        if not isinstance(consulta, dict):
            errores.append(
                _error(
                    "estructura_invalida",
                    f"La consulta {indice_consulta} debe ser un objeto",
                    indice_consulta,
                )
            )
            consultas_sanitizadas.append(_consulta_fallback(fallback))
            continue

        pasos = consulta.get("ejecucion_herramienta")
        if not isinstance(pasos, list):
            errores.append(
                _error(
                    "estructura_invalida",
                    (
                        f"La consulta {indice_consulta} debe incluir "
                        "ejecucion_herramienta como lista"
                    ),
                    indice_consulta,
                )
            )
            consultas_sanitizadas.append(_consulta_fallback(fallback))
            continue

        pasos_sanitizados: list[dict[str, Any]] = []
        for indice_paso, paso in enumerate(pasos, start=1):
            paso_sanitizado, error = _sanitizar_paso(
                paso,
                canal=canal,
                herramientas_validas=herramientas_validas,
                indice_consulta=indice_consulta,
                indice_paso=indice_paso,
            )
            if error:
                errores.append(error)
            if paso_sanitizado is not None:
                pasos_sanitizados.append(paso_sanitizado)

        if not pasos_sanitizados:
            errores.append(
                _error(
                    "consulta_sin_herramientas",
                    (
                        f"La consulta {indice_consulta} quedó sin herramientas "
                        "útiles; se usó fallback"
                    ),
                    indice_consulta,
                )
            )
            consultas_sanitizadas.append(_consulta_fallback(fallback))
            continue

        consultas_sanitizadas.append(
            {
                "ejecucion_herramienta": _reordenar_pasos(pasos_sanitizados),
            }
        )

    if not consultas_sanitizadas:
        consultas_sanitizadas.append(_consulta_fallback(fallback))

    plan_sanitizado = dict(plan)
    plan_sanitizado["consultas"] = consultas_sanitizadas
    return plan_sanitizado, errores


def _sanitizar_paso(
    paso: Any,
    *,
    canal: str,
    herramientas_validas: set[str],
    indice_consulta: int,
    indice_paso: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(paso, dict):
        return None, _error(
            "estructura_invalida",
            f"El paso {indice_paso} de la consulta {indice_consulta} debe ser un objeto",
            indice_consulta,
            indice_paso,
        )

    herramienta = paso.get("herramienta")
    if not isinstance(herramienta, dict):
        return None, _error(
            "estructura_invalida",
            f"El paso {indice_paso} de la consulta {indice_consulta} debe incluir herramienta",
            indice_consulta,
            indice_paso,
        )

    nombre = str(herramienta.get("nombre") or "").strip()
    parametros = herramienta.get("parametros")
    parametros = parametros if isinstance(parametros, dict) else {}

    if nombre not in herramientas_validas:
        return None, _error(
            "herramienta_invalida",
            f"Herramienta no soportada: {nombre or '<vacía>'}",
            indice_consulta,
            indice_paso,
            nombre,
        )

    parametros_limpios = _normalizar_parametros_exploracion(
        nombre,
        _limpiar_parametros(parametros),
    )
    if not _herramienta_tiene_valor(canal, nombre, parametros_limpios):
        return None, _error(
            "herramienta_sin_valor",
            f"La herramienta {nombre} no incluye valores útiles",
            indice_consulta,
            indice_paso,
            nombre,
        )

    return {
        "orden": int(paso.get("orden") or indice_paso),
        "herramienta": {
            "nombre": nombre,
            "parametros": parametros_limpios,
        },
    }, None


def _herramienta_tiene_valor(canal: str, nombre: str, parametros: dict[str, Any]) -> bool:
    if canal == "pregunta_directa":
        return _herramienta_pregunta_tiene_valor(nombre, parametros)
    return _herramienta_exploracion_tiene_valor(nombre, parametros)


def _herramienta_exploracion_tiene_valor(nombre: str, parametros: dict[str, Any]) -> bool:
    if nombre in {"busqueda_semantica", "busqueda_semantica_consulta"}:
        return _texto(parametros.get("texto_embeddings")) != ""
    if nombre in {"gis", "gis_consulta", "busqueda_ubicacion", "busqueda_ubicacion_consulta"}:
        return (
            parametros.get("usar_ubicacion_usuario") is True
            or parametros.get("distancia") is not None
            or _texto(parametros.get("punto_referencia")) != ""
            or _texto(parametros.get("referencia_ubicacion")) != ""
        )
    if nombre in {"conversacional"}:
        return _texto(parametros.get("tipo")) != ""
    if nombre in {"fallback"}:
        return True
    if nombre in {"pregunta_directa", "pregunta-directa"}:
        return _texto(parametros.get("nombre_entidad")) != ""
    return _dict_tiene_valor(parametros)


def _normalizar_parametros_exploracion(
    nombre: str,
    parametros: dict[str, Any],
) -> dict[str, Any]:
    if nombre not in {
        "gis",
        "gis_consulta",
        "busqueda_ubicacion",
        "busqueda_ubicacion_consulta",
    }:
        return parametros

    salida = dict(parametros)
    proximidad = _texto(salida.get("proximidad_textual")).lower()
    if proximidad not in PROXIMIDAD_TEXTUAL_METROS:
        if "proximidad_textual" in salida:
            salida["proximidad_textual"] = ""
        return salida

    salida["proximidad_textual"] = proximidad
    if salida.get("distancia") is None:
        salida["distancia"] = PROXIMIDAD_TEXTUAL_METROS[proximidad]
        salida["unidad"] = "m"
    return salida


def _herramienta_pregunta_tiene_valor(nombre: str, parametros: dict[str, Any]) -> bool:
    if nombre in PREGUNTA_PERMITE_PARAMETROS_VACIOS:
        return True
    if nombre in {"chuck_documento", "chunk_documento"}:
        return _dict_tiene_valor(
            {
                "texto_embeddings": parametros.get("texto_embeddings")
                or parametros.get("mensaje_chunk"),
                "keywords": parametros.get("keywords"),
            }
        )
    if nombre == "fallback":
        return True
    if nombre == "conversacional":
        return _texto(parametros.get("tipo")) != ""
    return _dict_tiene_valor(parametros)


def _validar_reglas_pregunta(plan: dict[str, Any]) -> list[dict[str, Any]]:
    errores: list[dict[str, Any]] = []
    for indice_consulta, consulta in enumerate(plan.get("consultas") or [], start=1):
        pasos = consulta.get("ejecucion_herramienta") or []
        nombres = [
            str((paso.get("herramienta") or {}).get("nombre") or "").strip()
            for paso in pasos
            if isinstance(paso, dict)
        ]
        if "documento_sitio" in nombres and "ficha_sitio" in nombres:
            errores.append(
                _error(
                    "regla_prompt_invalida",
                    (
                        f"La consulta {indice_consulta} no debe combinar "
                        "documento_sitio con ficha_sitio"
                    ),
                    indice_consulta,
                )
            )
        if "ficha_sitio" in nombres:
            indice_ficha = nombres.index("ficha_sitio")
            if "chuck_documento" not in nombres[indice_ficha + 1 :]:
                errores.append(
                    _error(
                        "regla_prompt_invalida",
                        (
                            f"La consulta {indice_consulta} usa ficha_sitio "
                            "sin chuck_documento posterior"
                        ),
                        indice_consulta,
                    )
                )
    return errores


def _limpiar_parametros(parametros: dict[str, Any]) -> dict[str, Any]:
    salida: dict[str, Any] = {}
    for clave, valor in parametros.items():
        limpio = _limpiar_valor(valor)
        salida[clave] = limpio
    return salida


def _limpiar_valor(valor: Any) -> Any:
    if isinstance(valor, str):
        return valor.strip()
    if isinstance(valor, list):
        return [
            item
            for item in (_limpiar_valor(item) for item in valor)
            if _valor_util(item)
        ]
    if isinstance(valor, dict):
        return _limpiar_parametros(valor)
    return valor


def _dict_tiene_valor(parametros: dict[str, Any]) -> bool:
    return any(_valor_util(valor) for valor in parametros.values())


def _valor_util(valor: Any) -> bool:
    if isinstance(valor, bool):
        return bool(valor)
    if valor is None:
        return False
    if isinstance(valor, str):
        return valor.strip() != ""
    if isinstance(valor, list):
        return any(_valor_util(item) for item in valor)
    if isinstance(valor, dict):
        return _dict_tiene_valor(valor)
    return True


def _lista_con_texto(valor: Any) -> bool:
    return isinstance(valor, list) and any(_texto(item) for item in valor)


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _reordenar_pasos(pasos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordenados = sorted(pasos, key=lambda paso: int(paso.get("orden") or 0))
    for indice, paso in enumerate(ordenados, start=1):
        paso["orden"] = indice
    return ordenados


def _consulta_fallback(fallback: dict[str, Any]) -> dict[str, Any]:
    return {"ejecucion_herramienta": [deepcopy(fallback)]}


def _error(
    tipo: str,
    detalle: str,
    indice_consulta: int,
    indice_paso: int | None = None,
    herramienta: str | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "tipo": tipo,
        "detalle": detalle,
        "consulta": indice_consulta,
    }
    if indice_paso is not None:
        error["paso"] = indice_paso
    if herramienta is not None:
        error["herramienta"] = herramienta
    return error
