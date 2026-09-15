from esquemas.historial_exploracion import HistorialExploracionEntrada
from servicios import historial_exploracion
from servicios.historial_exploracion import guardar_historial_exploracion


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
        self.queries_mensajes = []
        self.commit_llamado = False
        self.rollback_llamado = False

    def execute(self, query, params):
        query_text = str(query)
        if "SELECT id_conversacion" in query_text:
            return ResultadoFake(self.conversacion_existente)
        if "INSERT INTO conversacion.conversacion" in query_text:
            return ResultadoFake({"id_conversacion": 77})
        if "SELECT id_mensaje_ex" in query_text:
            row = {"id_mensaje_ex": 1} if params["rol"] in self.mensajes_existentes else None
            return ResultadoFake(row)
        if "INSERT INTO conversacion.mensaje_explorador" in query_text:
            self.queries_mensajes.append(query_text)
            self.inserts_mensajes.append(dict(params))
            return ResultadoFake()
        return ResultadoFake()

    def commit(self):
        self.commit_llamado = True

    def rollback(self):
        self.rollback_llamado = True


def test_historial_inserta_dos_mensajes_con_mismo_client_id(monkeypatch):
    monkeypatch.setattr(
        historial_exploracion,
        "generar_embedding",
        lambda texto: "[" + ",".join(["0.1"] * 1024) + "]",
    )
    db = SesionFake()

    salida = guardar_historial_exploracion(
        db,
        HistorialExploracionEntrada(
            id_usuario=5,
            sesion_id="sesion-1",
            client_message_id="msg-1",
            texto_usuario="Quiero museos",
            respuesta_json={"exploracion": {"mensajes_app": []}},
            categorias=[" Manifestaciones Culturales ", "manifestaciones culturales"],
            subcategorias=["Museo"],
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
    assert respuesta["rol"] == "conversacion_general"
    assert usuario["contenido"] == "Quiero museos"
    assert respuesta["contenido"] == '{"exploracion":{"mensajes_app":[]}}'
    assert usuario["embedding"] is not None
    assert respuesta["embedding"] is None
    assert usuario["categorias"] == ["Manifestaciones Culturales"]
    assert usuario["subcategorias"] == ["Museo"]
    assert "CAST(:categorias AS VARCHAR(100)[])" in db.queries_mensajes[0]
    assert "CAST(:subcategorias AS VARCHAR(100)[])" in db.queries_mensajes[0]


def test_historial_reintento_no_duplica_mensajes(monkeypatch):
    monkeypatch.setattr(historial_exploracion, "generar_embedding", lambda texto: "[0.1]")
    db = SesionFake(
        conversacion_existente={"id_conversacion": 9},
        mensajes_existentes={"usuario", "conversacion_general"},
    )

    salida = guardar_historial_exploracion(
        db,
        HistorialExploracionEntrada(
            id_usuario=5,
            sesion_id="sesion-1",
            client_message_id="msg-1",
            texto_usuario="Quiero museos",
            respuesta_json={"ok": True},
        ),
    )

    assert salida.id_conversacion == 9
    assert salida.usuario_guardado is False
    assert salida.respuesta_guardada is False
    assert db.inserts_mensajes == []
    assert db.commit_llamado is True


def test_historial_sin_id_usuario_no_guarda():
    db = SesionFake()

    salida = guardar_historial_exploracion(
        db,
        HistorialExploracionEntrada(
            sesion_id="sesion-1",
            client_message_id="msg-1",
            texto_usuario="Quiero museos",
            respuesta_json={"ok": True},
        ),
    )

    assert salida.usuario_guardado is False
    assert salida.respuesta_guardada is False
    assert db.inserts_mensajes == []
    assert db.commit_llamado is False
