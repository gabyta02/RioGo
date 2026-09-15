from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    Time,
    Numeric,
    SmallInteger,
    DateTime, 
    Identity,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.conexion import Base
from sqlalchemy.dialects.postgresql import ENUM


class Parroquia(Base):
    __tablename__ = "parroquia"
    __table_args__ = {"schema": "turismo"}

    id_parroquia = Column(BigInteger, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)


class Plataforma(Base):
    __tablename__ = "plataforma"
    __table_args__ = {"schema": "turismo"}

    id_plataforma = Column(BigInteger, primary_key=True, index=True)
    id_parroquia = Column(
        BigInteger,
        ForeignKey("turismo.parroquia.id_parroquia"),
        nullable=False,
    )
    nombre = Column(String(100), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = {"schema": "turismo"}

    id_categoria = Column(BigInteger, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    activo = Column(Boolean, nullable=False, default=True)

    sitios = relationship("Sitio", back_populates="categoria")


class Subcategoria(Base):
    __tablename__ = "subcategoria"
    __table_args__ = {"schema": "turismo"}

    id_subcategoria = Column(BigInteger, primary_key=True, index=True)
    id_categoria = Column(
        BigInteger,
        ForeignKey("turismo.categoria.id_categoria"),
        nullable=False,
    )
    nombre = Column(String(100), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)

    categoria = relationship("Categoria")
    sitios = relationship("Sitio", back_populates="subcategoria")


class Sitio(Base):
    __tablename__ = "sitio"
    __table_args__ = {"schema": "turismo"}

    id_sitio = Column(BigInteger, primary_key=True, index=True)

    id_parroquia = Column(
        BigInteger,
        ForeignKey("turismo.parroquia.id_parroquia"),
        nullable=True,
    )
    id_plataforma = Column(
        BigInteger,
        ForeignKey("turismo.plataforma.id_plataforma"),
        nullable=True,
    )
    id_categoria = Column(
        BigInteger,
        ForeignKey("turismo.categoria.id_categoria"),
        nullable=False,
    )
    id_subcategoria = Column(
        BigInteger,
        ForeignKey("turismo.subcategoria.id_subcategoria"),
        nullable=True,
    )

    tipo = Column(String(40), nullable=False)
    nombre = Column(String(180), nullable=False)
    descripcion_corta = Column(String(350), nullable=True)

    from geoalchemy2 import Geography
    ubicacion = Column(Geography(geometry_type="POINT", srid=4326), nullable=True)

    es_gratuito = Column(Boolean, nullable=True)
    permite_mascotas = Column(Boolean, nullable=True)
    parqueadero = Column(Boolean, nullable=True)
    tiene_wifi = Column(Boolean, nullable=True)
    accesibilidad = Column(Boolean, nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    categoria = relationship("Categoria", back_populates="sitios")
    subcategoria = relationship("Subcategoria", back_populates="sitios")
    parroquia = relationship("Parroquia")
    plataforma = relationship("Plataforma")

    direccion = relationship(
        "Direccion",
        back_populates="sitio",
        uselist=False,
        cascade="all, delete-orphan",
    )
    media = relationship(
        "Multimedia",
        back_populates="sitio",
        cascade="all, delete-orphan",
    )
    contactos = relationship(
        "Contacto",
        back_populates="sitio",
        cascade="all, delete-orphan",
    )
    horario = relationship(
        "Horario",
        back_populates="sitio",
        uselist=False,
        cascade="all, delete-orphan",
    )
    precio = relationship(
        "RangoPrecio",
        back_populates="sitio",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tarifas = relationship(
        "TarifaAcceso",
        back_populates="sitio",
        cascade="all, delete-orphan",
    )


class Direccion(Base):
    __tablename__ = "direccion"
    __table_args__ = {"schema": "turismo"}

    id_direccion = Column(BigInteger, primary_key=True, index=True)
    id_sitio = Column(
        BigInteger,
        ForeignKey("turismo.sitio.id_sitio", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    direccion_texto = Column(String(200), nullable=False)
    referencia_adicional = Column(String(200), nullable=True)

    sitio = relationship("Sitio", back_populates="direccion")


class Multimedia(Base):
    __tablename__ = "multimedia"
    __table_args__ = {"schema": "turismo"}

    id_multimedia = Column(Integer, primary_key=True, index=True)
    id_sitio = Column(
        BigInteger,
        ForeignKey("turismo.sitio.id_sitio", ondelete="CASCADE"),
        nullable=False,
    )
    url = Column(Text, nullable=False)
    es_principal = Column(Boolean, nullable=False, default=False)
    activo = Column(Boolean, nullable=False, default=True)

    sitio = relationship("Sitio", back_populates="media")


class Contacto(Base):
    __tablename__ = "contacto"
    __table_args__ = {"schema": "turismo"}

    id_contacto = Column(Integer, primary_key=True, index=True)
    id_sitio = Column(
        BigInteger,
        ForeignKey("turismo.sitio.id_sitio", ondelete="CASCADE"),
        nullable=False,
    )
    nombre = Column(String(40), nullable=False)
    contenido = Column(String(200), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)

    sitio = relationship("Sitio", back_populates="contactos")


class Horario(Base):
    __tablename__ = "horario"
    __table_args__ = {"schema": "turismo"}

    id_horario = Column(Integer, primary_key=True, index=True)
    id_sitio = Column(
        BigInteger,
        ForeignKey("turismo.sitio.id_sitio", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    abierto_24h = Column(Boolean, nullable=False, default=False)
    comentario = Column(String(200), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    sitio = relationship("Sitio", back_populates="horario")
    detalles = relationship(
        "HorarioDetalle",
        back_populates="horario",
        cascade="all, delete-orphan",
    )


class HorarioDetalle(Base):
    __tablename__ = "horario_detalle"
    __table_args__ = {"schema": "turismo"}

    id_horario_detalle = Column(Integer, primary_key=True, index=True)
    id_horario = Column(
        Integer,
        ForeignKey("turismo.horario.id_horario", ondelete="CASCADE"),
        nullable=False,
    )
    dia_semana = Column(SmallInteger, nullable=False)
    hora_inicio = Column(Time, nullable=True)
    hora_fin = Column(Time, nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    horario = relationship("Horario", back_populates="detalles")


class RangoPrecio(Base):
    __tablename__ = "rango_precio"
    __table_args__ = {"schema": "turismo"}

    id_rango_precio = Column(Integer, primary_key=True, index=True)
    id_sitio = Column(
        BigInteger,
        ForeignKey("turismo.sitio.id_sitio", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    precio_min = Column(Numeric(8, 2), nullable=True)
    precio_max = Column(Numeric(8, 2), nullable=True)
    etiqueta_precio = Column(String(30), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    sitio = relationship("Sitio", back_populates="precio")


class TarifaAcceso(Base):
    __tablename__ = "tarifa_acceso"
    __table_args__ = {"schema": "turismo"}

    id_tarifa_acceso = Column(Integer, primary_key=True, index=True)
    id_sitio = Column(
        BigInteger,
        ForeignKey("turismo.sitio.id_sitio", ondelete="CASCADE"),
        nullable=False,
    )
    precio = Column(Numeric(8, 2), nullable=False)
    condicion = Column(String(150), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    sitio = relationship("Sitio", back_populates="tarifas")


class SitioDocumento(Base):
    __tablename__ = "sitio_documento"
    __table_args__ = {"schema": "turismo"}

    id_documento = Column(BigInteger, Identity(always=False), primary_key=True, index=True)
    origen = Column(ENUM(name="tipo_documento_t",schema="turismo",create_type=False), nullable=False)
    titulo = Column(String(200), nullable=False)
    id_vinculo = Column(BigInteger, nullable=False)
    repositorio_nombre = Column(String(180), nullable=True)
    descripcion = Column(String(800), nullable=False)
    ruta_archivo = Column(Text, nullable=True)
    activo = Column(Boolean, nullable=False, default=False)
    creado_en = Column(DateTime(timezone=True), nullable=False, server_default="NOW()")