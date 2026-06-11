"""Modelo Evento (E02 · T02.1.1).

Cada cambio relevante en un lead emite un evento. Son la base de las métricas del
dashboard (tiempos, conversión, volúmenes). Los emite `lead_service`, no los routers.
"""

from sqlalchemy import Column, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class Evento(Base):
    __tablename__ = "eventos"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    tipo = Column(String, nullable=False)  # lead_creado | estado_cambiado | score_actualizado | ...
    payload = Column(JSONB, nullable=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    lead = relationship("Lead", back_populates="eventos")
