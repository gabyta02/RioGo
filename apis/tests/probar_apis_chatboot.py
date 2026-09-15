#!/usr/bin/env python3
"""Probador interactivo de APIs chatboot (H1–H10).

Uso (desde la raíz del repo):
  cd apis && .venv/bin/python tests/probar_apis_chatboot.py

Si ya estás dentro de apis/:
  .venv/bin/python tests/probar_apis_chatboot.py

Herramientas (--herramienta):
  semantica, ubicacion, referencia, contacto, horario, precio, tarifa, atributos, gis, ruta

Prueba rápida:
  .venv/bin/python tests/probar_apis_chatboot.py --herramienta semantica --caso 1
  .venv/bin/python tests/probar_apis_chatboot.py --herramienta referencia --caso 1
  .venv/bin/python tests/probar_apis_chatboot.py --herramienta horario --caso 1
  .venv/bin/python tests/probar_apis_chatboot.py --herramienta ruta --caso 1

Pipelines:
  .venv/bin/python tests/probar_apis_chatboot.py --verificar
  .venv/bin/python tests/probar_apis_chatboot.py --verificar-pipeline
  .venv/bin/python tests/probar_apis_chatboot.py --verificar-pipeline-gis
  .venv/bin/python tests/probar_apis_chatboot.py --verificar-pipeline-ruta-gis
  .venv/bin/python tests/probar_apis_chatboot.py --verificar-pipeline-semantica
  .venv/bin/python tests/probar_apis_chatboot.py --verificar-fallback-semantica

Documentación: apis/docs/chatboot_arquitectura_api.md
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

APIS_DIR = Path(__file__).resolve().parents[1]
if str(APIS_DIR) not in sys.path:
    sys.path.insert(0, str(APIS_DIR))

load_dotenv(APIS_DIR / ".env")

APIS_BASE_URL = os.getenv("APIS_BASE_URL", "http://localhost").rstrip("/")

HERRAMIENTAS: dict[str, dict[str, Any]] = {
    "ubicacion": {
        "nombre": "busqueda_ubicacion",
        "endpoint": "/api/v1/chatboot/herramientas/busqueda-ubicacion",
        "casos": {
            "1": {
                "entidad": "sitio",
                "tipo_busqueda": "cercania",
                "referencia_ubicacion": "mercado la condamine",
                "usar_ubicacion_usuario": False,
                "distancia": None,
                "unidad": "",
                "excluir_zonas": [],
                "ids_consulta": [],
            },
            "2": {
                "entidad": "sitio",
                "tipo_busqueda": "cercania",
                "referencia_ubicacion": "",
                "usar_ubicacion_usuario": True,
                "distancia": 400,
                "unidad": "m",
                "excluir_zonas": [],
                "ubicacion_usuario": {"lat": -1.6736, "lon": -78.6473},
                "ids_consulta": [],
            },
            "3": {
                "entidad": "sitio",
                "tipo_busqueda": "zona_textual",
                "referencia_ubicacion": "Leopoldo Ormaza y Agustín Cascante",
                "usar_ubicacion_usuario": None,
                "distancia": None,
                "unidad": "",
                "excluir_zonas": [],
                "ids_consulta": [],
            },
        },
    },
    "referencia": {
        "nombre": "busqueda_referencia",
        "endpoint": "/api/v1/chatboot/herramientas/busqueda-referencia",
        "casos": {
            "1": {"direccion_referencia": "jose veloz y morona", "ids_consulta": []},
            "2": {"direccion_referencia": "Av. Jose Veloz y Morona"},
            "3": {"direccion_referencia": "cordovez espejo"},
            "4": {"direccion_referencia": "RIOBAMBA"},
            "5": {"direccion_referencia": "PLATAFORMA N"},
            "6": {"direccion_referencia": "zzz inexistente xyz"},
        },
    },
    "contacto": {
        "nombre": "contacto_busqueda",
        "endpoint": "/api/v1/chatboot/herramientas/contacto-busqueda",
        "casos": {
            "1": {
                "contacto_sugerido": "whatsapp",
                "excluir_contactos": [],
                "ids_consulta": [],
            },
            "2": {"contacto_sugerido": "telefono", "excluir_contactos": []},
            "3": {"contacto_sugerido": "teléfono", "excluir_contactos": []},
            "4": {"contacto_sugerido": "email", "excluir_contactos": []},
            "5": {
                "contacto_sugerido": "whatsapp",
                "excluir_contactos": ["telefono"],
            },
            "6": {"contacto_sugerido": "zzz_inexistente", "excluir_contactos": []},
        },
    },
    "horario": {
        "nombre": "horario_consulta",
        "endpoint": "/api/v1/chatboot/herramientas/horario-consulta",
        "casos": {
            "1": {
                "tipo": "instantaneo",
                "dia_semana": None,
                "hora": None,
                "rango_hora": None,
                "comparador": "",
                "excluir_dias": [],
                "ids_consulta": [],
            },
            "2": {
                "tipo": "punto_tiempo",
                "dia_semana": None,
                "hora": "12:00",
                "rango_hora": None,
                "comparador": "igual",
                "excluir_dias": [],
                "ids_consulta": [],
            },
            "3": {
                "tipo": "bloque_tiempo",
                "dia_semana": None,
                "hora": None,
                "rango_hora": ["06:00", "11:59"],
                "comparador": "dentro_de",
                "excluir_dias": [],
                "ids_consulta": [],
            },
            "4": {
                "tipo": "dias_solamente",
                "dia_semana": 6,
                "hora": None,
                "rango_hora": None,
                "comparador": "",
                "excluir_dias": [],
                "ids_consulta": [],
            },
            "5": {
                "tipo": "relacional",
                "dia_semana": None,
                "hora": "18:00",
                "rango_hora": None,
                "comparador": "mayor_que",
                "excluir_dias": [],
                "ids_consulta": [],
            },
            "6": {
                "tipo": "instantaneo",
                "dia_semana": None,
                "hora": None,
                "rango_hora": None,
                "comparador": "",
                "excluir_dias": [],
                "ids_consulta": [999],
            },
            "7": {
                "tipo": "relacional",
                "dia_semana": None,
                "hora": None,
                "rango_hora": None,
                "comparador": "mayor_que",
                "excluir_dias": [],
                "ids_consulta": [],
            },
        },
    },
    "precio": {
        "nombre": "precio_consulta",
        "endpoint": "/api/v1/chatboot/herramientas/precio-consulta",
        "casos": {
            "1": {
                "es_gratuito": True,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "",
                "excluir_etiquetas": [],
                "ids_consulta": [],
            },
            "2": {
                "es_gratuito": None,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "economico",
                "excluir_etiquetas": [],
                "ids_consulta": [],
            },
            "3": {
                "es_gratuito": None,
                "precio_numero": 10,
                "operador": "<=",
                "etiqueta": "",
                "excluir_etiquetas": [],
                "ids_consulta": [],
            },
            "4": {
                "es_gratuito": None,
                "precio_numero": 5,
                "operador": "=",
                "etiqueta": "",
                "excluir_etiquetas": [],
                "ids_consulta": [],
            },
            "5": {
                "es_gratuito": None,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "moderado",
                "excluir_etiquetas": ["alto"],
                "ids_consulta": [],
            },
            "6": {
                "es_gratuito": False,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "",
                "excluir_etiquetas": [],
                "ids_consulta": [],
            },
            "7": {
                "es_gratuito": None,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "",
                "excluir_etiquetas": [],
                "ids_consulta": [],
            },
        },
    },
    "tarifa": {
        "nombre": "tarifa_acceso_consulta",
        "endpoint": "/api/v1/chatboot/herramientas/tarifa-acceso-consulta",
        "casos": {
            "1": {
                "entrada_gratuita": True,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "",
                "condicion": "",
                "excluir_condiciones": [],
                "ids_consulta": [],
            },
            "2": {
                "entrada_gratuita": None,
                "precio_numero": 5,
                "operador": "<=",
                "etiqueta": "",
                "condicion": "estudiante",
                "excluir_condiciones": [],
                "ids_consulta": [],
            },
            "3": {
                "entrada_gratuita": False,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "",
                "condicion": "",
                "excluir_condiciones": [],
                "ids_consulta": [],
            },
            "4": {
                "entrada_gratuita": None,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "economico",
                "condicion": "",
                "excluir_condiciones": [],
                "ids_consulta": [],
            },
            "5": {
                "entrada_gratuita": None,
                "precio_numero": None,
                "operador": "",
                "etiqueta": "",
                "condicion": "",
                "excluir_condiciones": [],
                "ids_consulta": [],
            },
        },
    },
    "atributos": {
        "nombre": "atributos_booleanos_consulta",
        "endpoint": "/api/v1/chatboot/herramientas/atributos-booleanos-consulta",
        "casos": {
            "1": {
                "tiene_wifi": True,
                "permite_mascotas": None,
                "accesibilidad": None,
                "parqueadero": None,
                "es_gratuito": None,
                "excluir": [],
                "ids_consulta": [],
            },
            "2": {
                "tiene_wifi": None,
                "permite_mascotas": None,
                "accesibilidad": None,
                "parqueadero": None,
                "es_gratuito": True,
                "excluir": [],
                "ids_consulta": [],
            },
            "3": {
                "tiene_wifi": None,
                "permite_mascotas": None,
                "accesibilidad": None,
                "parqueadero": None,
                "es_gratuito": None,
                "excluir": ["parqueadero"],
                "ids_consulta": [],
            },
            "4": {
                "tiene_wifi": None,
                "permite_mascotas": None,
                "accesibilidad": None,
                "parqueadero": None,
                "es_gratuito": None,
                "excluir": [],
                "ids_consulta": [],
            },
        },
    },
    "gis": {
        "nombre": "gis_consulta",
        "endpoint": "/api/v1/chatboot/herramientas/gis-consulta",
        "casos": {
            "1": {
                "entidad": "sitio",
                "usar_ubicacion_usuario": False,
                "distancia": None,
                "unidad": "",
                "punto_referencia": "Museo",
                "excluir_zonas": [],
                "ubicacion_usuario": None,
                "ids_consulta": [],
            },
            "2": {
                "entidad": "sitio",
                "usar_ubicacion_usuario": True,
                "distancia": None,
                "unidad": "",
                "punto_referencia": "",
                "excluir_zonas": [],
                "ubicacion_usuario": {"lat": -1.6736, "lon": -78.6473},
                "ids_consulta": [],
            },
            "3": {
                "entidad": "sitio",
                "usar_ubicacion_usuario": False,
                "distancia": 1,
                "unidad": "km",
                "punto_referencia": "Riobamba",
                "excluir_zonas": [],
                "ubicacion_usuario": None,
                "ids_consulta": [],
            },
            "4": {
                "entidad": "sitio",
                "usar_ubicacion_usuario": False,
                "distancia": None,
                "unidad": "",
                "punto_referencia": "",
                "excluir_zonas": [],
                "ubicacion_usuario": None,
                "ids_consulta": [1, 2, 3],
            },
            "5": {
                "entidad": "ruta",
                "usar_ubicacion_usuario": True,
                "distancia": None,
                "unidad": "",
                "punto_referencia": "",
                "excluir_zonas": [],
                "ubicacion_usuario": {"lat": -1.6736, "lon": -78.6473},
                "ids_consulta": [],
            },
        },
    },
    "ruta": {
        "nombre": "ruta_consulta",
        "endpoint": "/api/v1/chatboot/herramientas/ruta-consulta",
        "casos": {
            "1": {
                "tipo_ruta": "senderismo",
                "excluir_tipos": [],
                "ids_consulta": [],
            },
            "2": {
                "tipo_ruta": "ciclismo",
                "excluir_tipos": [],
                "ids_consulta": [],
            },
            "3": {
                "tipo_ruta": "senderismo",
                "excluir_tipos": ["ciclismo"],
                "ids_consulta": [],
            },
            "4": {
                "tipo_ruta": "tipo_invalido",
                "excluir_tipos": [],
                "ids_consulta": [],
            },
            "5": {
                "tipo_ruta": "transporte publico",
                "excluir_tipos": [],
                "ids_consulta": [],
            },
            "6": {
                "tipo_ruta": "otro",
                "excluir_tipos": [],
                "ids_consulta": [],
            },
        },
    },
    "semantica": {
        "nombre": "busqueda_semantica_consulta",
        "endpoint": "/api/v1/chatboot/herramientas/busqueda-semantica-consulta",
        "casos": {
            "1": {
                "texto_embeddings": "museo con exposiciones de arte colonial",
                "keywords": ["arte colonial", "colonial"],
                "excluir_terminos": [],
                "ids_consulta": [],
            },
            "2": {
                "texto_embeddings": "hostal con vista al chimborazo",
                "keywords": ["chimborazo", "vista"],
                "excluir_terminos": [],
                "ids_consulta": [],
            },
            "3": {
                "texto_embeddings": "museo con arte colonial",
                "keywords": ["arte colonial"],
                "excluir_terminos": ["iglesia"],
                "ids_consulta": [],
            },
            "4": {
                "texto_embeddings": "",
                "keywords": [],
                "excluir_terminos": [],
                "ids_consulta": [],
            },
            "5": {
                "texto_embeddings": "museo con arte colonial",
                "keywords": ["colonial"],
                "excluir_terminos": [],
                "ids_consulta": [1, 2, 3],
            },
            "6": {
                "texto_embeddings": "restaurante vegano con menú sin gluten",
                "keywords": ["vegano", "sin gluten"],
                "excluir_terminos": [],
                "ids_consulta": [1, 2, 3],
            },
        },
    },
}

CASOS_PREDEFINIDOS = HERRAMIENTAS["semantica"]["casos"]
ENDPOINT = HERRAMIENTAS["semantica"]["endpoint"]


def llamar_api(
    payload: dict[str, Any],
    endpoint: str | None = None,
) -> tuple[int, dict[str, Any]]:
    path = endpoint or ENDPOINT
    url = f"{APIS_BASE_URL}{path}"
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ConnectionError(
            f"No se pudo conectar a {url}. "
            f"¿Está levantado nginx/apis? Prueba APIS_BASE_URL=http://localhost "
            f"o dentro del contenedor: docker exec riobambago-apis python tests/probar_apis_chatboot.py"
        ) from exc
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}
    return response.status_code, body


def llamar_api_get(path: str, params: dict[str, Any] | None = None) -> tuple[int, Any]:
    url = f"{APIS_BASE_URL}{path}"
    try:
        response = requests.get(
            url,
            params=params,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ConnectionError(
            f"No se pudo conectar a {url}. Verifica APIS_BASE_URL ({APIS_BASE_URL})."
        ) from exc
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return response.status_code, body


def listar_catalogo() -> None:
    status, categorias = llamar_api_get("/api/v1/sitios/categorias")
    if status != 200 or not isinstance(categorias, list):
        print(f"\n✗ No se pudo obtener catálogo (HTTP {status}): {categorias}")
        return

    print("\n--- Catálogo activo ---")
    for cat in categorias:
        id_cat = cat.get("id_categoria")
        nombre_cat = cat.get("nombre")
        print(f"\n[{id_cat}] {nombre_cat}")
        st, subcategorias = llamar_api_get(
            "/api/v1/sitios/subcategorias",
            {"id_categoria": id_cat},
        )
        if st == 200 and isinstance(subcategorias, list):
            for sub in subcategorias:
                print(f"  - [{sub.get('id_subcategoria')}] {sub.get('nombre')}")
    print()


def _parsear_lista(texto: str) -> list[str]:
    texto = texto.strip()
    if not texto:
        return []
    if texto.startswith("["):
        try:
            parsed = json.loads(texto)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in texto.split(",") if part.strip()]


def consulta_personalizada() -> None:
    print("\nIngresa listas separadas por coma o JSON (vacío = [])")
    categorias = _parsear_lista(
        input("categorias_sugeridas: ").strip()
    )
    subcategorias = _parsear_lista(
        input("subcategorias_sugeridas: ").strip()
    )
    excluir = _parsear_lista(input("excluir_categorias: ").strip())
    payload = {
        "categorias_sugeridas": categorias,
        "subcategorias_sugeridas": subcategorias,
        "excluir_categorias": excluir,
    }
    _ejecutar_y_mostrar(payload)


def _ejecutar_y_mostrar(
    payload: dict[str, Any],
    endpoint: str | None = None,
) -> None:
    print("\n--- Request ---")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        status, body = llamar_api(payload, endpoint=endpoint)
    except ConnectionError as exc:
        print(f"\n✗ {exc}")
        return
    print(f"\n--- Response HTTP {status} ---")
    print(json.dumps(body, ensure_ascii=False, indent=2))

    if "ids_sitio" in body:
        total = len(body["ids_sitio"])
        print(f"\n✓ {total} sitio(s) encontrado(s)")
        retro = body.get("retroalimentacion")
        if retro:
            print(f"  Retroalimentación: {retro.get('codigo')} — {retro.get('mensaje')}")
        candidatos = body.get("candidatos", [])
        if candidatos and candidatos[0].get("distancia_aproximada"):
            c0 = candidatos[0]
            print(
                f"  Ejemplo distancia: {c0.get('nombre', '')} "
                f"a ~{c0.get('distancia_aproximada')}"
            )
    elif "ids_ruta" in body:
        total = len(body["ids_ruta"])
        print(f"\n✓ {total} ruta(s) encontrada(s)")
        retro = body.get("retroalimentacion")
        if retro:
            print(f"  Retroalimentación: {retro.get('codigo')} — {retro.get('mensaje')}")
    elif "sin_sitios" in body:
        print(f"\n○ Sin sitios: {body['sin_sitios']}")
        retro = body.get("retroalimentacion")
        if retro:
            print(f"  Retroalimentación: {retro.get('codigo')} — {retro.get('mensaje')}")
    elif "sin_rutas" in body:
        print(f"\n○ Sin rutas: {body['sin_rutas']}")
        retro = body.get("retroalimentacion")
        if retro:
            print(f"  Retroalimentación: {retro.get('codigo')} — {retro.get('mensaje')}")
    elif "candidatos" in body:
        total = len(body.get("ids_sitio", []))
        debug = len(body["candidatos"])
        if total:
            print(f"\n✓ {total} sitio(s) semántico(s), {debug} candidato(s) debug")
        else:
            print(f"\n○ Sin sitios semánticos, {debug} candidato(s) debug")
    elif "fallo" in body:
        print(f"\n✗ Fallo: {body['fallo']}")
    elif "detail" in body:
        print(f"\n✗ Error validación: {body['detail']}")


def verificar_multiples_filtros() -> bool:
    """Comprueba unión OR de varias categorías y subcategorías vía HTTP."""
    endpoint = HERRAMIENTAS["categoria"]["endpoint"]

    def obtener_ids(payload: dict[str, list[str]]) -> set[int]:
        status, body = llamar_api(payload, endpoint=endpoint)
        if status != 200:
            raise AssertionError(f"HTTP {status}: {body}")
        if "ids_sitio" not in body:
            raise AssertionError(f"Respuesta inesperada: {body}")
        return set(body["ids_sitio"])

    print(f"Verificando contra {APIS_BASE_URL}{endpoint} ...")

    museo = obtener_ids({"subcategorias_sugeridas": ["Museo"]})
    iglesia = obtener_ids({"subcategorias_sugeridas": ["Iglesia"]})
    ambas_sub = obtener_ids({"subcategorias_sugeridas": ["Museo", "Iglesia"]})
    assert ambas_sub == museo | iglesia, "Subcategorías múltiples deben unir (OR)"

    alojamiento = obtener_ids({"categorias_sugeridas": ["Alojamiento"]})
    naturales = obtener_ids({"categorias_sugeridas": ["Atractivos Naturales"]})
    ambas_cat = obtener_ids(
        {"categorias_sugeridas": ["Alojamiento", "Atractivos Naturales"]}
    )
    assert ambas_cat == alojamiento | naturales, "Categorías múltiples deben unir (OR)"

    mixto = obtener_ids(
        {
            "categorias_sugeridas": ["Alojamiento"],
            "subcategorias_sugeridas": ["Museo", "Iglesia"],
        }
    )
    assert mixto == alojamiento | museo | iglesia, (
        "Categorías + subcategorías deben unir todos los conjuntos (OR)"
    )

    parcial = obtener_ids(
        {
            "categorias_sugeridas": ["Alojamiento", "zzz_inexistente"],
            "subcategorias_sugeridas": ["Museo"],
        }
    )
    assert parcial == alojamiento | museo, (
        "Nombres inválidos se ignoran si al menos uno resuelve"
    )

    print("✓ Múltiples categorías/subcategorías: unión OR verificada")
    print(f"  - Museo ∪ Iglesia = {len(ambas_sub)} sitios")
    print(f"  - 2 categorías = {len(ambas_cat)} sitios")
    print(f"  - Mixto cat+sub = {len(mixto)} sitios")
    return True


def verificar_pipeline_categoria_horario() -> bool:
    """Pipeline: Hotel → abierto ahora (instantaneo con ids_consulta)."""
    ep_cat = HERRAMIENTAS["categoria"]["endpoint"]
    ep_hor = HERRAMIENTAS["horario"]["endpoint"]

    status, body_cat = llamar_api(
        {
            "categorias_sugeridas": [],
            "subcategorias_sugeridas": ["Hotel"],
            "excluir_categorias": [],
            "ids_consulta": [],
        },
        endpoint=ep_cat,
    )
    if status != 200:
        raise AssertionError(f"categoria HTTP {status}: {body_cat}")
    if "ids_sitio" not in body_cat:
        raise AssertionError(f"categoria sin ids_sitio: {body_cat}")

    ids_hotel = body_cat["ids_sitio"]
    print(f"Pipeline: {len(ids_hotel)} hotel(es) candidato(s)")

    status, body_hor = llamar_api(
        {
            "tipo": "instantaneo",
            "dia_semana": None,
            "hora": None,
            "rango_hora": None,
            "comparador": "",
            "excluir_dias": [],
            "ids_consulta": ids_hotel,
        },
        endpoint=ep_hor,
    )
    if status != 200:
        raise AssertionError(f"horario HTTP {status}: {body_hor}")

    if "ids_sitio" in body_hor:
        abiertos = set(body_hor["ids_sitio"])
        assert abiertos <= set(ids_hotel), "horario debe ser subconjunto de ids_consulta"
        print(f"✓ Pipeline categoria→horario: {len(abiertos)} abierto(s) ahora")
    elif "sin_sitios" in body_hor:
        print("✓ Pipeline categoria→horario: sin_sitios (ningún hotel abierto ahora)")
    else:
        raise AssertionError(f"horario respuesta inesperada: {body_hor}")

    return True


def _validar_retroalimentacion_semantica(body: dict[str, Any]) -> None:
    retro = body.get("retroalimentacion")
    if not retro:
        raise AssertionError("Falta retroalimentacion en la respuesta semántica")
    codigo = retro.get("codigo")
    if "ids_sitio" in body:
        if retro.get("alcance_busqueda") == "ids_consulta":
            assert codigo == "encontrado_en_alcance_previo", (
                f"codigo inesperado con alcance ids_consulta: {codigo}"
            )
            assert retro.get("fallback_global_aplicado") is False
        elif retro.get("fallback_global_aplicado"):
            assert codigo == "busqueda_global_por_sin_coincidencias_en_alcance", (
                f"codigo inesperado con fallback: {codigo}"
            )
        else:
            assert codigo == "busqueda_global_sin_filtro_previo", (
                f"codigo inesperado global sin fallback: {codigo}"
            )
    elif "sin_sitios" in body:
        assert codigo == "sin_coincidencias_en_alcance_y_global", (
            f"codigo inesperado sin_sitios: {codigo}"
        )
    assert retro.get("mensaje"), "mensaje de retroalimentacion vacío"


def verificar_pipeline_categoria_semantica() -> bool:
    """Pipeline: Museo → búsqueda semántica con atributo."""
    ep_cat = HERRAMIENTAS["categoria"]["endpoint"]
    ep_sem = HERRAMIENTAS["semantica"]["endpoint"]

    status, body_cat = llamar_api(
        {"subcategorias_sugeridas": ["Museo"], "ids_consulta": []},
        endpoint=ep_cat,
    )
    if status != 200 or "ids_sitio" not in body_cat:
        raise AssertionError(f"categoria HTTP {status}: {body_cat}")

    ids_museo = body_cat["ids_sitio"]
    status, body_sem = llamar_api(
        {
            "texto_embeddings": "museo con arte colonial en exposiciones",
            "keywords": ["arte colonial", "colonial"],
            "excluir_terminos": [],
            "ids_consulta": ids_museo,
        },
        endpoint=ep_sem,
    )
    if status != 200:
        raise AssertionError(f"semantica HTTP {status}: {body_sem}")

    _validar_retroalimentacion_semantica(body_sem)

    if "ids_sitio" in body_sem:
        refinados = set(body_sem["ids_sitio"])
        retro = body_sem["retroalimentacion"]
        if retro["alcance_busqueda"] == "ids_consulta":
            assert refinados <= set(ids_museo), (
                "semántica en alcance previo debe ser subconjunto de ids_consulta"
            )
        print(
            f"✓ Pipeline categoria→semantica: {len(refinados)} sitio(s) "
            f"({retro['codigo']})"
        )
    elif "sin_sitios" in body_sem:
        debug = len(body_sem.get("candidatos", []))
        print(f"✓ Pipeline categoria→semantica: sin_sitios ({debug} candidatos debug)")
    elif "fallo" in body_sem:
        raise AssertionError(f"semantica fallo inesperado: {body_sem['fallo']}")
    else:
        raise AssertionError(f"semantica respuesta inesperada: {body_sem}")
    return True


def verificar_fallback_semantica() -> bool:
    """Fuerza fallback global: categoría Museo + query muy específica."""
    ep_cat = HERRAMIENTAS["categoria"]["endpoint"]
    ep_sem = HERRAMIENTAS["semantica"]["endpoint"]

    status, body_cat = llamar_api(
        {"subcategorias_sugeridas": ["Museo"], "ids_consulta": []},
        endpoint=ep_cat,
    )
    if status != 200 or "ids_sitio" not in body_cat:
        raise AssertionError(f"categoria HTTP {status}: {body_cat}")

    ids_museo = body_cat["ids_sitio"]
    status, body_sem = llamar_api(
        {
            "texto_embeddings": "restaurante vegano con menú sin gluten",
            "keywords": ["vegano", "sin gluten"],
            "excluir_terminos": [],
            "ids_consulta": ids_museo,
        },
        endpoint=ep_sem,
    )
    if status != 200:
        raise AssertionError(f"semantica HTTP {status}: {body_sem}")

    _validar_retroalimentacion_semantica(body_sem)
    retro = body_sem["retroalimentacion"]

    if "ids_sitio" in body_sem:
        assert retro["fallback_global_aplicado"] is True, (
            "Se esperaba fallback global con query fuera de museos"
        )
        assert retro["codigo"] == "busqueda_global_por_sin_coincidencias_en_alcance"
        print(
            f"✓ Fallback semántico: {len(body_sem['ids_sitio'])} sitio(s) globales "
            f"— {retro['mensaje']}"
        )
    elif "sin_sitios" in body_sem:
        assert retro["fallback_global_aplicado"] is True
        print("✓ Fallback semántico: sin_sitios tras ampliar a global")
    else:
        raise AssertionError(f"semantica respuesta inesperada: {body_sem}")
    return True


def verificar_pipeline_ruta_gis() -> bool:
    """Pipeline: senderismo → gis entidad=ruta con ubicación usuario."""
    ep_ruta = HERRAMIENTAS["ruta"]["endpoint"]
    ep_gis = HERRAMIENTAS["gis"]["endpoint"]

    status, body_ruta = llamar_api(
        {"tipo_ruta": "senderismo", "excluir_tipos": [], "ids_consulta": []},
        endpoint=ep_ruta,
    )
    if status != 200 or "ids_ruta" not in body_ruta:
        if "sin_rutas" in body_ruta:
            print("○ Pipeline ruta→gis: sin rutas de senderismo en BD")
            return True
        raise AssertionError(f"ruta HTTP {status}: {body_ruta}")

    ids_ruta = body_ruta["ids_ruta"]
    status, body_gis = llamar_api(
        {
            "entidad": "ruta",
            "usar_ubicacion_usuario": True,
            "distancia": None,
            "unidad": "",
            "punto_referencia": "",
            "excluir_zonas": [],
            "ubicacion_usuario": {"lat": -1.6736, "lon": -78.6473},
            "ids_consulta": ids_ruta,
        },
        endpoint=ep_gis,
    )
    if status != 200:
        raise AssertionError(f"gis HTTP {status}: {body_gis}")

    _validar_retroalimentacion_gis(body_gis)

    if "ids_ruta" in body_gis:
        cercanas = set(body_gis["ids_ruta"])
        assert cercanas <= set(ids_ruta), "gis ruta debe ser subconjunto de ids_consulta"
        retro = body_gis["retroalimentacion"]
        print(
            f"✓ Pipeline ruta→gis: {len(cercanas)} ruta(s) cercana(s) "
            f"({retro['codigo']})"
        )
    elif "sin_rutas" in body_gis:
        print("✓ Pipeline ruta→gis: sin_rutas en radio")
    elif "fallo" in body_gis:
        raise AssertionError(f"gis fallo inesperado: {body_gis['fallo']}")
    else:
        raise AssertionError(f"gis respuesta inesperada: {body_gis}")
    return True


def _validar_retroalimentacion_gis(body: dict[str, Any]) -> None:
    retro = body.get("retroalimentacion")
    if not retro:
        raise AssertionError("Falta retroalimentacion en la respuesta GIS")
    assert retro.get("mensaje"), "mensaje de retroalimentacion GIS vacío"
    assert retro.get("modo_busqueda") in ("progresivo", "fijo")

    if "ids_sitio" in body or "ids_ruta" in body:
        assert retro.get("radio_aplicado_metros") is not None
        assert retro.get("codigo") in (
            "encontrado_en_radio_progresivo",
            "encontrado_en_radio_fijo",
        )
        candidatos = body.get("candidatos", [])
        assert len(candidatos) == len(
            body.get("ids_sitio") or body.get("ids_ruta") or []
        ), "candidatos GIS debe alinear con ids devueltos"
        for item in candidatos:
            assert item.get("distancia_metros") is not None
            assert item.get("distancia_aproximada")
    elif "sin_sitios" in body or "sin_rutas" in body:
        assert retro.get("codigo") == "sin_coincidencias_en_radios"


def verificar_pipeline_categoria_gis() -> bool:
    """Pipeline: Museo → cercanos a punto_referencia Museo."""
    ep_cat = HERRAMIENTAS["categoria"]["endpoint"]
    ep_gis = HERRAMIENTAS["gis"]["endpoint"]

    status, body_cat = llamar_api(
        {
            "categorias_sugeridas": [],
            "subcategorias_sugeridas": ["Museo"],
            "excluir_categorias": [],
            "ids_consulta": [],
        },
        endpoint=ep_cat,
    )
    if status != 200 or "ids_sitio" not in body_cat:
        raise AssertionError(f"categoria falló: {body_cat}")

    ids_museo = body_cat["ids_sitio"]
    print(f"Pipeline GIS: {len(ids_museo)} museo(s) candidato(s)")

    status, body_gis = llamar_api(
        {
            "usar_ubicacion_usuario": False,
            "distancia": None,
            "unidad": "",
            "punto_referencia": "Museo",
            "excluir_zonas": [],
            "ubicacion_usuario": None,
            "ids_consulta": ids_museo,
        },
        endpoint=ep_gis,
    )
    if status != 200:
        raise AssertionError(f"gis HTTP {status}: {body_gis}")

    _validar_retroalimentacion_gis(body_gis)

    if "ids_sitio" in body_gis:
        cercanos = set(body_gis["ids_sitio"])
        assert cercanos <= set(ids_museo), "gis debe ser subconjunto de ids_consulta"
        retro = body_gis["retroalimentacion"]
        print(
            f"✓ Pipeline categoria→gis: {len(cercanos)} sitio(s) cercano(s) "
            f"({retro['codigo']}, radio {retro.get('radio_aplicado_metros')} m)"
        )
    elif "sin_sitios" in body_gis:
        print("✓ Pipeline categoria→gis: sin_sitios en radio")
    elif "fallo" in body_gis:
        raise AssertionError(f"gis fallo inesperado: {body_gis['fallo']}")
    else:
        raise AssertionError(f"gis respuesta inesperada: {body_gis}")

    return True


def consulta_personalizada_referencia() -> None:
    texto = input("\ndireccion_referencia: ").strip()
    _ejecutar_y_mostrar(
        {"direccion_referencia": texto},
        endpoint=HERRAMIENTAS["referencia"]["endpoint"],
    )

def consulta_personalizada_contacto() -> None:
    contacto = input("\ncontacto_sugerido: ").strip()
    excluir = _parsear_lista(input("excluir_contactos: ").strip())
    _ejecutar_y_mostrar(
        {"contacto_sugerido": contacto, "excluir_contactos": excluir},
        endpoint=HERRAMIENTAS["contacto"]["endpoint"],
    )


def consulta_personalizada_horario() -> None:
    tipo = input("\ntipo (instantaneo/punto_tiempo/bloque_tiempo/relacional/dias_solamente): ").strip()
    dia = input("dia_semana (1-7, vacío=null): ").strip()
    hora = input("hora HH:MM (vacío=null): ").strip()
    rango = _parsear_lista(input("rango_hora (dos HH:MM separados por coma): ").strip())
    comparador = input("comparador (vacío/igual/dentro_de/mayor_que/menor_que): ").strip()
    excluir = _parsear_lista(input("excluir_dias (enteros 1-7): ").strip())
    ids = _parsear_lista(input("ids_consulta (enteros): ").strip())
    payload: dict[str, Any] = {
        "tipo": tipo,
        "dia_semana": int(dia) if dia else None,
        "hora": hora or None,
        "rango_hora": rango if len(rango) == 2 else None,
        "comparador": comparador,
        "excluir_dias": [int(x) for x in excluir] if excluir else [],
        "ids_consulta": [int(x) for x in ids] if ids else [],
    }
    _ejecutar_y_mostrar(payload, endpoint=HERRAMIENTAS["horario"]["endpoint"])


def consulta_personalizada_precio() -> None:
    es_gratuito_txt = input("\nes_gratuito (true/false/vacío=null): ").strip().lower()
    es_gratuito: bool | None
    if es_gratuito_txt in {"true", "1", "si", "sí"}:
        es_gratuito = True
    elif es_gratuito_txt in {"false", "0", "no"}:
        es_gratuito = False
    else:
        es_gratuito = None
    precio_txt = input("precio_numero (vacío=null): ").strip()
    precio_numero = float(precio_txt) if precio_txt else None
    operador = input("operador (=, <=, <, >=, >, vacío): ").strip()
    etiqueta = input("etiqueta (economico/medio/alto/vacío): ").strip()
    excluir = _parsear_lista(input("excluir_etiquetas: ").strip())
    ids = _parsear_lista(input("ids_consulta (enteros): ").strip())
    payload: dict[str, Any] = {
        "es_gratuito": es_gratuito,
        "precio_numero": precio_numero,
        "operador": operador,
        "etiqueta": etiqueta,
        "excluir_etiquetas": excluir,
        "ids_consulta": [int(x) for x in ids] if ids else [],
    }
    _ejecutar_y_mostrar(payload, endpoint=HERRAMIENTAS["precio"]["endpoint"])


def consulta_personalizada_tarifa() -> None:
    entrada_txt = input("\nentrada_gratuita (true/false/vacío=null): ").strip().lower()
    entrada_gratuita: bool | None
    if entrada_txt in {"true", "1", "si", "sí"}:
        entrada_gratuita = True
    elif entrada_txt in {"false", "0", "no"}:
        entrada_gratuita = False
    else:
        entrada_gratuita = None
    precio_txt = input("precio_numero (vacío=null): ").strip()
    precio_numero = float(precio_txt) if precio_txt else None
    operador = input("operador (=, <=, <, >=, >, vacío): ").strip()
    etiqueta = input("etiqueta (economico/medio/alto/vacío): ").strip()
    condicion = input("condicion (general/adulto/estudiante/...): ").strip()
    excluir = _parsear_lista(input("excluir_condiciones: ").strip())
    ids = _parsear_lista(input("ids_consulta (enteros): ").strip())
    payload: dict[str, Any] = {
        "entrada_gratuita": entrada_gratuita,
        "precio_numero": precio_numero,
        "operador": operador,
        "etiqueta": etiqueta,
        "condicion": condicion,
        "excluir_condiciones": excluir,
        "ids_consulta": [int(x) for x in ids] if ids else [],
    }
    _ejecutar_y_mostrar(payload, endpoint=HERRAMIENTAS["tarifa"]["endpoint"])


def consulta_personalizada_atributos() -> None:
    def _bool(txt: str) -> bool | None:
        if txt in {"true", "1", "si", "sí"}:
            return True
        if txt in {"false", "0", "no"}:
            return False
        return None

    payload: dict[str, Any] = {
        "tiene_wifi": _bool(input("tiene_wifi (true/false/vacío): ").strip().lower()),
        "permite_mascotas": _bool(
            input("permite_mascotas (true/false/vacío): ").strip().lower()
        ),
        "accesibilidad": _bool(
            input("accesibilidad (true/false/vacío): ").strip().lower()
        ),
        "parqueadero": _bool(input("parqueadero (true/false/vacío): ").strip().lower()),
        "es_gratuito": _bool(input("es_gratuito (true/false/vacío): ").strip().lower()),
        "excluir": _parsear_lista(input("excluir: ").strip()),
        "ids_consulta": [
            int(x)
            for x in _parsear_lista(input("ids_consulta (enteros): ").strip())
        ],
    }
    _ejecutar_y_mostrar(payload, endpoint=HERRAMIENTAS["atributos"]["endpoint"])


def consulta_personalizada_gis() -> None:
    usar_txt = input("\nusar_ubicacion_usuario (true/false/vacío): ").strip().lower()
    usar = True if usar_txt in {"true", "1", "si", "sí"} else False if usar_txt in {"false", "0", "no"} else None
    dist_txt = input("distancia (vacío=null): ").strip()
    distancia = float(dist_txt) if dist_txt else None
    unidad = input("unidad (m/km/vacío): ").strip()
    punto = input("punto_referencia: ").strip()
    excluir = _parsear_lista(input("excluir_zonas: ").strip())
    ids = _parsear_lista(input("ids_consulta (enteros, obligatorio): ").strip())
    lat_txt = input("ubicacion_usuario lat (vacío): ").strip()
    lon_txt = input("ubicacion_usuario lon (vacío): ").strip()
    ubicacion = None
    if lat_txt and lon_txt:
        ubicacion = {"lat": float(lat_txt), "lon": float(lon_txt)}
    payload: dict[str, Any] = {
        "usar_ubicacion_usuario": usar,
        "distancia": distancia,
        "unidad": unidad,
        "punto_referencia": punto,
        "excluir_zonas": excluir,
        "ubicacion_usuario": ubicacion,
        "ids_consulta": [int(x) for x in ids] if ids else [],
    }
    _ejecutar_y_mostrar(payload, endpoint=HERRAMIENTAS["gis"]["endpoint"])


def menu_herramienta(herramienta: str) -> None:
    config = HERRAMIENTAS[herramienta]
    casos = config["casos"]
    endpoint = config["endpoint"]

    while True:
        print(f"\n=== Probador {config['nombre']} ===")
        print(f"Base URL: {APIS_BASE_URL}")

        if herramienta == "categoria":
            print("1. Solo subcategoría (Museo)")
            print("2. Solo categoría (Alojamiento)")
            print("3. Confianza parcial (2 categorías)")
            print("4. Varias subcategorías (Museo + Iglesia)")
            print("5. Subcategoría con exclusión (bar)")
            print("6. Nombre inválido (fallo)")
            print("7. Listas vacías (422)")
            print("10. Múltiples categorías Y subcategorías")
            print("8. Consulta personalizada")
            print("9. Listar catálogo (API)")
        elif herramienta == "referencia":
            print("1. Dirección (jose veloz y morona)")
            print("2. Dirección con Av.")
            print("3. Dirección corta (cordovez espejo)")
            print("4. Parroquia (RIOBAMBA)")
            print("5. Plataforma (PLATAFORMA N)")
            print("6. Sin coincidencias")
            print("8. Consulta personalizada")
        elif herramienta == "contacto":
            print("1. WhatsApp")
            print("2. Teléfono")
            print("3. Teléfono con acento")
            print("4. Email")
            print("5. WhatsApp excluyendo teléfono")
            print("6. Contacto inexistente")
            print("8. Consulta personalizada")
        elif herramienta == "horario":
            print("1. Abierto ahora (instantaneo)")
            print("2. Punto de tiempo (12:00)")
            print("3. Bloque mañana (06:00-11:59)")
            print("4. Solo sábado (dias_solamente)")
            print("5. Relacional después de 18:00")
            print("6. ids_consulta [999] sin horario")
            print("7. Relacional sin hora (fallo)")
            print("8. Consulta personalizada")
        elif herramienta == "precio":
            print("1. Gratuito (es_gratuito=true)")
            print("2. Etiqueta economico")
            print("3. Hasta $10 (operador <=)")
            print("4. Precio exacto $5")
            print("5. Moderado excluyendo alto")
            print("6. No gratuito")
            print("7. Sin criterio (fallo)")
            print("8. Consulta personalizada")
        elif herramienta == "tarifa":
            print("1. Entrada gratuita")
            print("2. Estudiante hasta $5")
            print("3. Entrada de pago")
            print("4. Etiqueta economico")
            print("5. Sin criterio (fallo)")
            print("8. Consulta personalizada")
        elif herramienta == "atributos":
            print("1. Tiene wifi")
            print("2. Es gratuito")
            print("3. Excluir parqueadero")
            print("4. Sin criterio (fallo)")
            print("8. Consulta personalizada")
        elif herramienta == "gis":
            print("1. Cerca de Museo (requiere ids_consulta en pipeline)")
            print("2. Ubicación usuario Riobamba")
            print("3. Radio fijo 1 km desde Riobamba")
            print("4. ids_consulta vacío (fallo)")
            print("5. Rutas cercanas (entidad=ruta, requiere ids_consulta)")
            print("8. Consulta personalizada")
        elif herramienta == "ruta":
            print("1. Senderismo")
            print("2. Ciclismo")
            print("3. Senderismo excluyendo ciclismo")
            print("4. Tipo inválido (fallo)")
            print("5. Transporte público (fallo)")
            print("6. Otro reservado para semántica (fallo)")
            print("8. Consulta personalizada")
        elif herramienta == "semantica":
            print("1. Arte colonial (universo completo)")
            print("2. Vista al Chimborazo")
            print("3. Con excluir_terminos iglesia")
            print("4. texto_embeddings vacío (fallo 422)")
            print("5. Con ids_consulta acotado")
            print("6. Fallback global (ids sin match → catálogo completo)")
            print("8. Consulta personalizada")

        print("0. Volver")

        opcion = input("\nOpción: ").strip()
        if opcion == "0":
            break
        if opcion == "8":
            if herramienta == "categoria":
                consulta_personalizada()
            elif herramienta == "referencia":
                consulta_personalizada_referencia()
            elif herramienta == "contacto":
                consulta_personalizada_contacto()
            elif herramienta == "horario":
                consulta_personalizada_horario()
            elif herramienta == "precio":
                consulta_personalizada_precio()
            elif herramienta == "tarifa":
                consulta_personalizada_tarifa()
            elif herramienta == "atributos":
                consulta_personalizada_atributos()
            elif herramienta == "gis":
                consulta_personalizada_gis()
            continue
        if opcion == "9" and herramienta == "categoria":
            listar_catalogo()
            continue
        if opcion in casos:
            _ejecutar_y_mostrar(casos[opcion], endpoint=endpoint)
            continue
        print("Opción no válida.")


def menu() -> None:
    print(
        "\nTip: ya en apis/ usa solo  .venv/bin/python tests/probar_apis_chatboot.py\n"
        "     Rápido: --herramienta referencia --caso 1\n"
    )
    while True:
        print("\n=== Probador APIs Chatboot ===")
        print("1. busqueda_semantica_consulta")
        print("2. busqueda_ubicacion")
        print("3. busqueda_referencia (legacy)")
        print("4. contacto_busqueda")
        print("5. horario_consulta")
        print("6. precio_consulta")
        print("7. tarifa_acceso_consulta")
        print("8. atributos_booleanos_consulta")
        print("9. gis_consulta (legacy)")
        print("10. ruta_consulta")
        print("0. Salir")
        opcion = input("\nHerramienta: ").strip()
        if opcion == "0":
            break
        if opcion == "1":
            menu_herramienta("semantica")
        elif opcion == "2":
            menu_herramienta("ubicacion")
        elif opcion == "3":
            menu_herramienta("referencia")
        elif opcion == "4":
            menu_herramienta("contacto")
        elif opcion == "5":
            menu_herramienta("horario")
        elif opcion == "6":
            menu_herramienta("precio")
        elif opcion == "7":
            menu_herramienta("tarifa")
        elif opcion == "8":
            menu_herramienta("atributos")
        elif opcion == "9":
            menu_herramienta("gis")
        elif opcion == "10":
            menu_herramienta("ruta")
        else:
            print("Opción no válida.")


def _imprimir_ayuda_casos(herramienta: str | None = None) -> None:
    items = (
        [herramienta]
        if herramienta and herramienta in HERRAMIENTAS
        else list(HERRAMIENTAS.keys())
    )
    for key in items:
        config = HERRAMIENTAS[key]
        print(f"\n-- {config['nombre']} (--herramienta {key}) --")
        for clave, payload in sorted(config["casos"].items(), key=lambda x: int(x[0])):
            print(f"  {clave}: {json.dumps(payload, ensure_ascii=False)}")


if __name__ == "__main__":
    herramienta_cli = "semantica"
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--herramienta" and i + 1 < len(args):
            herramienta_cli = args[i + 1]
            i += 2
            continue
        if args[i] in ("-h", "--help"):
            print(__doc__)
            _imprimir_ayuda_casos()
            sys.exit(0)
        if args[i] == "--verificar":
            try:
                ok = verificar_multiples_filtros()
            except (ConnectionError, AssertionError) as exc:
                print(f"\n✗ {exc}")
                sys.exit(1)
            sys.exit(0 if ok else 1)
        if args[i] == "--verificar-pipeline-semantica":
            try:
                ok = verificar_pipeline_categoria_semantica()
            except (ConnectionError, AssertionError) as exc:
                print(f"\n✗ {exc}")
                sys.exit(1)
            sys.exit(0 if ok else 1)
        if args[i] == "--verificar-fallback-semantica":
            try:
                ok = verificar_fallback_semantica()
            except (ConnectionError, AssertionError) as exc:
                print(f"\n✗ {exc}")
                sys.exit(1)
            sys.exit(0 if ok else 1)
        if args[i] == "--verificar-pipeline-ruta-gis":
            try:
                ok = verificar_pipeline_ruta_gis()
            except (ConnectionError, AssertionError) as exc:
                print(f"\n✗ {exc}")
                sys.exit(1)
            sys.exit(0 if ok else 1)
        if args[i] == "--verificar-pipeline-gis":
            try:
                ok = verificar_pipeline_categoria_gis()
            except (ConnectionError, AssertionError) as exc:
                print(f"\n✗ {exc}")
                sys.exit(1)
            sys.exit(0 if ok else 1)
        if args[i] == "--verificar-pipeline":
            try:
                ok = verificar_pipeline_categoria_horario()
            except (ConnectionError, AssertionError) as exc:
                print(f"\n✗ {exc}")
                sys.exit(1)
            sys.exit(0 if ok else 1)
        if args[i] == "--caso" and i + 1 < len(args):
            caso = args[i + 1]
            if herramienta_cli not in HERRAMIENTAS:
                print(f"✗ Herramienta '{herramienta_cli}' no existe.")
                _imprimir_ayuda_casos()
                sys.exit(1)
            casos = HERRAMIENTAS[herramienta_cli]["casos"]
            if caso not in casos:
                print(f"✗ Caso '{caso}' no existe para {herramienta_cli}.")
                _imprimir_ayuda_casos(herramienta_cli)
                sys.exit(1)
            _ejecutar_y_mostrar(
                casos[caso],
                endpoint=HERRAMIENTAS[herramienta_cli]["endpoint"],
            )
            sys.exit(0)
        print(f"✗ Argumento desconocido: {args[i]}")
        sys.exit(1)
    menu()
