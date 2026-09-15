from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Identity, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from core.conexion import Base


class ChunkFuente(Base):
    __tablename__ = "chunk_fuente"
    __table_args__ = {"schema": "turismo"}

    id_fuente = Column(BigInteger, Identity(always=False), primary_key=True, index=True)
    tipo_chunk = Column(ENUM(name="tipo_chunk_t", schema="turismo", create_type=False), nullable=False)
    origen = Column(ENUM(name="origen_chunk_t", schema="turismo", create_type=False), nullable=False)
    id_vinculo = Column(BigInteger, nullable=False)
    id_documento = Column(BigInteger, ForeignKey("turismo.sitio_documento.id_documento", ondelete="CASCADE"), nullable=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    chunks = relationship("Chunk", back_populates="fuente", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunk"
    __table_args__ = {"schema": "turismo"}

    id_chunk = Column(UUID(as_uuid=True), primary_key=True)
    id_fuente = Column(BigInteger, ForeignKey("turismo.chunk_fuente.id_fuente", ondelete="CASCADE"), nullable=False, index=True)
    contenido = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=False)
    creado_en = Column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    fuente = relationship("ChunkFuente", back_populates="chunks")
