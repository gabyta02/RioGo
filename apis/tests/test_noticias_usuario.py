from datetime import date, timedelta

from servicios.panel_administrativo.noticias import obtener_estado_noticias_usuario


class ResultadoFake:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def one(self):
        return self.row


class DbNoticiasFake:
    def __init__(self, noticias):
        self.noticias = noticias
        self.sql = None

    def execute(self, query):
        self.sql = str(query)
        hoy = date.today()
        visibles = [
            noticia
            for noticia in self.noticias
            if noticia["activa"]
            and noticia["fecha_inicio"] <= hoy
            and (noticia.get("fecha_fin") is None or noticia["fecha_fin"] >= hoy)
        ]
        return ResultadoFake(
            {
                "ultimo_id": max((noticia["id_noticia"] for noticia in visibles), default=0),
                "total": len(visibles),
            }
        )


def _noticia(id_noticia, *, activa=True, inicio=None, fin=None):
    hoy = date.today()
    return {
        "id_noticia": id_noticia,
        "activa": activa,
        "fecha_inicio": inicio or hoy,
        "fecha_fin": fin,
    }


def test_estado_noticias_usuario_sin_noticias_vigentes():
    respuesta = obtener_estado_noticias_usuario(DbNoticiasFake([]))

    assert respuesta.ultimo_id == 0
    assert respuesta.total == 0


def test_estado_noticias_usuario_con_una_noticia_activa_y_vigente():
    respuesta = obtener_estado_noticias_usuario(DbNoticiasFake([_noticia(7)]))

    assert respuesta.ultimo_id == 7
    assert respuesta.total == 1


def test_estado_noticias_usuario_con_varias_noticias_activas_y_vigentes():
    db = DbNoticiasFake([_noticia(3), _noticia(9), _noticia(5)])

    respuesta = obtener_estado_noticias_usuario(db)

    assert respuesta.ultimo_id == 9
    assert respuesta.total == 3


def test_estado_noticias_usuario_excluye_inactivas_futuras_y_vencidas():
    hoy = date.today()
    db = DbNoticiasFake(
        [
            _noticia(2),
            _noticia(8, activa=False),
            _noticia(9, inicio=hoy + timedelta(days=1)),
            _noticia(10, inicio=hoy - timedelta(days=5), fin=hoy - timedelta(days=1)),
        ]
    )

    respuesta = obtener_estado_noticias_usuario(db)

    assert respuesta.ultimo_id == 2
    assert respuesta.total == 1


def test_estado_noticias_usuario_es_consulta_de_solo_lectura():
    db = DbNoticiasFake([_noticia(1)])

    obtener_estado_noticias_usuario(db)

    sql = db.sql.lower()
    assert "select" in sql
    assert "from turismo.noticia" in sql
    assert "n.activa = true" in sql
    assert "n.fecha_inicio <= current_date" in sql
    assert "n.fecha_fin is null or n.fecha_fin >= current_date" in sql
    assert "insert" not in sql
    assert "update" not in sql
    assert "delete" not in sql
