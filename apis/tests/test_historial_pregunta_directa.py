from esquemas.historial_pregunta_directa import HistorialPreguntaDirectaEntrada
from servicios import historial_pregunta_directa
from servicios.historial_pregunta_directa import guardar_historial_pregunta_directa


class ResultadoFake:
    def __init__(self, row=None):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row

    def one(self):
        return self.row


class SesionFake:
    def __init__(self, *, conversacion_existente=None, mensajes_existentes=None):
        self.conversacion_existente = conversacion_existente
        self.mensajes_existentes = set(mensajes_existentes or [])
        self.inserts_mensajes = []
        self.commit_llamado = False
        self.rollback_llamado = False

    def execute(self, query, params):
        query_text = str(query)
        if "SELECT id_conversacion" in query_text:
            return ResultadoFake(self.conversacion_existente)
        if "INSERT INTO conversacion.conversacion" in query_text:
            return ResultadoFake({"id_conversacion": 77})
        if "SELECT id_mensaje_pd" in query_text:
            row = {"id_mensaje_pd": 1} if params["rol"] in self.mensajes_existentes else None
            return ResultadoFake(row)
        if "INSERT INTO conversacion.mensaje_detalle" in query_text:
            self.inserts_mensajes.append(dict(params))
            return ResultadoFake()
        return ResultadoFake()

    def commit(self):
        self.commit_llamado = True

    def rollback(self):
        self.rollback_llamado = True


def test_historial_pregunta_directa_inserta_detalle(monkeypatch):
    monkeypatch.setattr(
        historial_pregunta_directa,
        "generar_embedding",
        lambda texto: "[" + ",".join(["0.1"] * 1024) + "]",
    )
    db = SesionFake()

    salida = guardar_historial_pregunta_directa(
        db,
        HistorialPreguntaDirectaEntrada(
            id_usuario=5,
            sesion_id="sesion-1",
            client_message_id="msg-1",
            texto_usuario="¿Cuál es el horario?",
            entidad_asociada="Mercado de la Merced",
            respuesta_json={"pregunta_directa": {"mensajes_app": []}},
        ),
    )

    assert salida.id_conversacion == 77
    assert salida.usuario_guardado is True
    assert salida.respuesta_guardada is True
    assert db.commit_llamado is True
    assert len(db.inserts_mensajes) == 2
    usuario, respuesta = db.inserts_mensajes
    assert usuario["client_message_id"] == "msg-1"
    assert respuesta["client_message_id"] == "msg-1"
    assert usuario["rol"] == "usuario"
    assert respuesta["rol"] == "conversacion_sitio_especifico"
    assert usuario["entidad_asociada"] == "Mercado de la Merced"
    assert respuesta["embedding"] is None


def test_historial_pregunta_directa_reintento_no_duplica(monkeypatch):
    monkeypatch.setattr(historial_pregunta_directa, "generar_embedding", lambda texto: "[0.1]")
    db = SesionFake(
        conversacion_existente={"id_conversacion": 9},
        mensajes_existentes={"usuario", "conversacion_sitio_especifico"},
    )

    salida = guardar_historial_pregunta_directa(
        db,
        HistorialPreguntaDirectaEntrada(
            id_usuario=5,
            sesion_id="sesion-1",
            client_message_id="msg-1",
            texto_usuario="Hola",
            entidad_asociada="Mercado",
            respuesta_json={"ok": True},
        ),
    )

    assert salida.id_conversacion == 9
    assert salida.usuario_guardado is False
    assert salida.respuesta_guardada is False
    assert db.inserts_mensajes == []
    assert db.commit_llamado is True
