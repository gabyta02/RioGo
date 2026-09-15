from __future__ import annotations

from datetime import datetime, timezone

from servicios.historial_usuario_service import listar_conversaciones, obtener_mensajes


class ResultadoFake:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def mappings(self):
        return self

    def first(self):
        return self.row

    def one(self):
        return self.row

    def all(self):
        return self.rows


class SesionFake:
    def __init__(self, conversaciones, mensajes_explorador=None, mensajes_detalle=None, sitios=None):
        self.conversaciones = conversaciones
        self.mensajes_explorador = mensajes_explorador or {}
        self.mensajes_detalle = mensajes_detalle or {}
        self.sitios = sitios or {}

    def _convs_usuario(self, id_usuario):
        return [c for c in self.conversaciones.values() if c["id_usuario"] == id_usuario]

    def _ultimo_mensaje(self, conv):
        mensajes = self.mensajes_explorador.get(conv["id_conversacion"], []) + self.mensajes_detalle.get(conv["id_conversacion"], [])
        if not mensajes:
            return None
        return max(mensajes, key=lambda item: item["creado_en"])

    def execute(self, query, params):
        query_text = str(query)

        if "SELECT COUNT(*) AS total" in query_text and "FROM conversacion.conversacion c" in query_text:
            id_usuario = params["id_usuario"]
            convs = self._convs_usuario(id_usuario)
            if "EXISTS (SELECT 1 FROM conversacion.mensaje_explorador" in query_text:
                total = sum(1 for c in convs if c["mensajes_explorador"])
            elif "EXISTS (SELECT 1 FROM conversacion.mensaje_detalle" in query_text:
                total = sum(1 for c in convs if c["mensajes_detalle"])
            else:
                total = len(convs)
            return ResultadoFake(row={"total": total})

        if "SELECT 1" in query_text and "FROM conversacion.conversacion" in query_text and "LIMIT 1" in query_text:
            conv = self.conversaciones.get(params["id_conversacion"])
            row = {"1": 1} if conv and conv["id_usuario"] == params["id_usuario"] else None
            return ResultadoFake(row=row)

        if "SELECT id_conversacion, sesion_id, titulo" in query_text:
            conv = self.conversaciones.get(params["id_conversacion"])
            if not conv or conv["id_usuario"] != params["id_usuario"]:
                return ResultadoFake(row=None)
            return ResultadoFake(row={
                "id_conversacion": conv["id_conversacion"],
                "sesion_id": conv["sesion_id"],
                "titulo": conv["titulo"],
            })

        if "SELECT\n            c.id_conversacion" in query_text:
            id_usuario = params["id_usuario"]
            convs = self._convs_usuario(id_usuario)
            if "mensaje_explorador ex" in query_text:
                convs = [c for c in convs if c["mensajes_explorador"]]
            if "mensaje_detalle pd" in query_text:
                convs = [c for c in convs if c["mensajes_detalle"]]
            rows = []
            for conv in convs:
                todos = self.mensajes_explorador.get(conv["id_conversacion"], []) + self.mensajes_detalle.get(conv["id_conversacion"], [])
                creado = min((m["creado_en"] for m in todos), default=None)
                ultimo_en = max((m["creado_en"] for m in todos), default=None)
                rows.append({
                    "id_conversacion": conv["id_conversacion"],
                    "sesion_id": conv["sesion_id"],
                    "titulo": conv["titulo"],
                    "creado_en": creado,
                    "ultimo_mensaje_en": ultimo_en,
                })
            rows = sorted(rows, key=lambda r: (r["ultimo_mensaje_en"] is None, r["ultimo_mensaje_en"]), reverse=True)
            inicio = params["desplazamiento"]
            fin = inicio + params["limite"]
            return ResultadoFake(rows=rows[inicio:fin])

        if "SELECT contenido, rol, creado_en" in query_text and "union_mensajes" in query_text:
            conv = self.conversaciones[params["id_conversacion"]]
            mensajes = self.mensajes_explorador.get(conv["id_conversacion"], []) + self.mensajes_detalle.get(conv["id_conversacion"], [])
            if not mensajes:
                return ResultadoFake(row=None)
            ultimo = max(mensajes, key=lambda item: item["creado_en"])
            return ResultadoFake(row={"contenido": ultimo["contenido"], "rol": ultimo["rol"], "creado_en": ultimo["creado_en"]})

        if "SELECT COUNT(*) FROM conversacion.mensaje_explorador" in query_text and "AS total_explorador" in query_text and "AS total_detalle" in query_text:
            conv = self.conversaciones[params["id_conversacion"]]
            return ResultadoFake(row={
                "total_explorador": len(self.mensajes_explorador.get(conv["id_conversacion"], [])),
                "total_detalle": len(self.mensajes_detalle.get(conv["id_conversacion"], [])),
            })

        if "SELECT entidad_asociada" in query_text and "FROM conversacion.mensaje_detalle" in query_text:
            conv = self.conversaciones[params["id_conversacion"]]
            mensajes = [m for m in self.mensajes_detalle.get(conv["id_conversacion"], []) if m.get("entidad_asociada")]
            if not mensajes:
                return ResultadoFake(row=None)
            ultimo = max(mensajes, key=lambda item: item["creado_en"])
            return ResultadoFake(row={"entidad_asociada": ultimo["entidad_asociada"]})

        if "SELECT s.id_sitio, s.nombre" in query_text and "FROM turismo.sitio s" in query_text:
            return ResultadoFake(row=self.sitios.get(params["nombre_ascii"]))

        if "SELECT id_mensaje_ex AS id_mensaje" in query_text:
            conv = self.conversaciones[params["id_conversacion"]]
            mensajes = sorted(self.mensajes_explorador.get(conv["id_conversacion"], []), key=lambda item: (item["creado_en"], item["id_mensaje"]))
            inicio = params["desplazamiento"]
            fin = inicio + params["limite"]
            rows = []
            for m in mensajes[inicio:fin]:
                rows.append({
                    "id_mensaje": m["id_mensaje"],
                    "client_mensaje_id": m.get("client_mensaje_id"),
                    "rol": m["rol"],
                    "contenido": m["contenido"],
                    "creado_en": m["creado_en"],
                    "categoria": m.get("categoria"),
                    "subcategoria": m.get("subcategoria"),
                })
            return ResultadoFake(rows=rows)

        if "SELECT id_mensaje_pd AS id_mensaje" in query_text:
            conv = self.conversaciones[params["id_conversacion"]]
            mensajes = sorted(self.mensajes_detalle.get(conv["id_conversacion"], []), key=lambda item: (item["creado_en"], item["id_mensaje"]))
            inicio = params["desplazamiento"]
            fin = inicio + params["limite"]
            rows = []
            for m in mensajes[inicio:fin]:
                rows.append({
                    "id_mensaje": m["id_mensaje"],
                    "client_mensaje_id": m.get("client_mensaje_id"),
                    "rol": m["rol"],
                    "contenido": m["contenido"],
                    "creado_en": m["creado_en"],
                    "entidad_asociada": m.get("entidad_asociada"),
                })
            return ResultadoFake(rows=rows)

        return ResultadoFake(row=None)


def _dt(hour, minute=0):
    return datetime(2026, 6, 29, hour, minute, tzinfo=timezone.utc)


def _fake_session():
    conversaciones = {
        10: {
            "id_conversacion": 10,
            "id_usuario": 5,
            "sesion_id": "uuid-sesion-1",
            "titulo": "Busco restaurantes",
            "mensajes_explorador": [],
            "mensajes_detalle": [
                {
                    "id_mensaje": 25,
                    "client_mensaje_id": "msg-25",
                    "rol": "usuario",
                    "contenido": "¿Cuál es el horario?",
                    "creado_en": _dt(19, 6),
                    "entidad_asociada": "Catedral de Riobamba",
                },
                {
                    "id_mensaje": 26,
                    "client_mensaje_id": "msg-25",
                    "rol": "conversacion_sitio_especifico",
                    "contenido": '{"pregunta_directa":{"mensajes_app":[]}}',
                    "creado_en": _dt(19, 7),
                    "entidad_asociada": "Catedral de Riobamba",
                },
            ],
        },
        11: {
            "id_conversacion": 11,
            "id_usuario": 5,
            "sesion_id": "uuid-sesion-2",
            "titulo": "Busco museos",
            "mensajes_explorador": [
                {
                    "id_mensaje": 1,
                    "client_mensaje_id": "msg-1",
                    "rol": "usuario",
                    "contenido": "Quiero museos",
                    "creado_en": _dt(18, 1),
                    "categoria": ["Cultura"],
                    "subcategoria": ["Museo"],
                }
            ],
            "mensajes_detalle": [
                {
                    "id_mensaje": 2,
                    "client_mensaje_id": "msg-2",
                    "rol": "usuario",
                    "contenido": "¿Cuál es el horario?",
                    "creado_en": _dt(18, 10),
                    "entidad_asociada": "Mercado de la Merced",
                }
            ],
        },
        12: {
            "id_conversacion": 12,
            "id_usuario": 5,
            "sesion_id": "uuid-sesion-3",
            "titulo": "Busco rutas",
            "mensajes_explorador": [
                {
                    "id_mensaje": 3,
                    "client_mensaje_id": "msg-3",
                    "rol": "usuario",
                    "contenido": "rutas de bus",
                    "creado_en": _dt(17, 1),
                    "categoria": None,
                    "subcategoria": None,
                }
            ],
            "mensajes_detalle": [],
        },
    }
    mensajes_explorador = {
        11: conversaciones[11]["mensajes_explorador"],
        12: conversaciones[12]["mensajes_explorador"],
    }
    mensajes_detalle = {
        10: conversaciones[10]["mensajes_detalle"],
        11: conversaciones[11]["mensajes_detalle"],
    }
    sitios = {
        "catedral de riobamba": {"id_sitio": 1, "nombre": "Catedral de Riobamba"},
        "mercado de la merced": {"id_sitio": 2, "nombre": "Mercado de la Merced"},
    }
    return SesionFake(conversaciones, mensajes_explorador, mensajes_detalle, sitios)


def test_listar_conversaciones_detalle_enriquece_entidad_y_titulo():
    db = _fake_session()

    salida = listar_conversaciones(db, 5, "todos", 20, 0)

    assert salida["total"] == 3
    item = next(item for item in salida["items"] if item["id_conversacion"] == 10)
    assert item["tipo"] == "detalle"
    assert item["titulo"] == "Catedral de Riobamba"
    assert item["entidad_asociada"].model_dump() == {"tipo": "sitio", "id": 1, "nombre": "Catedral de Riobamba"}


def test_listar_conversaciones_general_mantiene_titulo_y_sin_entidad():
    db = _fake_session()

    salida = listar_conversaciones(db, 5, "general", 20, 0)

    item = next(item for item in salida["items"] if item["id_conversacion"] == 12)
    assert item["tipo"] == "general"
    assert item["titulo"] == "Busco rutas"
    assert "entidad_asociada" not in item


def test_listar_conversaciones_mixta_conserva_tipo_y_resuelve_entidad():
    db = _fake_session()

    salida = listar_conversaciones(db, 5, "todos", 20, 0)

    item = next(item for item in salida["items"] if item["id_conversacion"] == 11)
    assert item["tipo"] == "mixto"
    assert item["titulo"] == "Mercado de la Merced"
    assert item["entidad_asociada"].model_dump() == {"tipo": "sitio", "id": 2, "nombre": "Mercado de la Merced"}


def test_obtener_mensajes_detalle_incluye_entidad_por_mensaje():
    db = _fake_session()

    salida = obtener_mensajes(db, 5, 10, None, 200, 0)

    assert salida["tipo"] == "detalle"
    assert salida["titulo"] == "Catedral de Riobamba"
    assert salida["entidad_asociada"].model_dump() == {"tipo": "sitio", "id": 1, "nombre": "Catedral de Riobamba"}
    assert len(salida["mensajes"]) == 2
    for mensaje in salida["mensajes"]:
        assert mensaje["entidad_asociada"].model_dump() == {"tipo": "sitio", "id": 1, "nombre": "Catedral de Riobamba"}


def test_obtener_mensajes_general_sin_entidad():
    db = _fake_session()

    salida = obtener_mensajes(db, 5, 12, None, 200, 0)

    assert salida["tipo"] == "general"
    assert salida["titulo"] == "Busco rutas"
    assert "entidad_asociada" not in salida
    assert "entidad_asociada" not in salida["mensajes"][0]
