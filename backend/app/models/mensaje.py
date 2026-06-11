"""Modelo Mensaje (E02 · T02.1.1).

Un mensaje de la conversación de un lead. El conjunto de mensajes de un lead,
ordenado por `creado_en`, ES la conversación (no hace falta tabla aparte en el MVP).
"""

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class Mensaje(Base):
    __tablename__ = "mensajes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    rol = Column(String, nullable=False)  # lead | agente | asesor
    contenido = Column(Text, nullable=False)
    # 'metadata' es un nombre reservado en SQLAlchemy declarativo → el atributo Python
    # se llama `meta`, pero la columna en la BD sí se llama "metadata".
    meta = Column("metadata", JSONB, nullable=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    lead = relationship("Lead", back_populates="mensajes")
