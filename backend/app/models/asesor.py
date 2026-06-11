"""Modelo Asesor (E02 · T02.1.1).

Asesor humano al que se le hace handoff de un lead caliente (E06). Aquí solo el
modelo base; la asignación se implementa más adelante.
"""

from sqlalchemy import Boolean, Column, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base


class Asesor(Base):
    __tablename__ = "asesores"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    nombre = Column(String, nullable=False)
    disponible = Column(Boolean, nullable=False, default=True, server_default=text("true"))
