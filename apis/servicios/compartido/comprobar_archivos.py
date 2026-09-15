from sqlalchemy.orm import Session

from modelos.sitios_turismo import Sitio, SitioDocumento


def comprobar_archivos_sitio(db: Session, id_sitio: int) -> bool | None:
    sitio_existe = (
        db.query(Sitio.id_sitio)
        .filter(Sitio.id_sitio == id_sitio)
        .first()
    )

    if not sitio_existe:
        return None

    documento = (
        db.query(SitioDocumento.id_documento)
        .filter(
            SitioDocumento.origen == "sitio",
            SitioDocumento.id_vinculo == id_sitio,
            SitioDocumento.activo.is_(True),
            SitioDocumento.ruta_archivo.isnot(None),
        )
        .first()
    )

    return documento is not None