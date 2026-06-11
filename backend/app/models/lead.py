"""Modelo Lead (E02 · T02.1.1).

Entidad central del CRM: el cliente potencial. Su "conversación" son sus `mensajes`
ordenados por fecha; cada cambio relevante emite un `evento` (base de las métricas).
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    nombre = Column(String, nullable=True)
    contacto = Column(String, nullable=True)  # email/teléfono si lo da
    # origen nullable: lo simula la URL /chat/<origen>/; null si no se sabe (D15).
    origen = Column(String, nullable=True)  # web | meta | metrocuadrado | fincaraiz | null
    idioma = Column(String, nullable=True)

    # score nullable: null = aún sin calificar (handoff por solicitud antes de perfilar, D15).
    score = Column(Integer, nullable=True, default=0, server_default=text("0"))
    temperatura = Column(String, nullable=False, default="frio", server_default=text("'frio'"))
    estado = Column(String, nullable=False, default="nuevo", server_default=text("'nuevo'"))
    perfil = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    asesor_id = Column(UUID(as_uuid=True), ForeignKey("asesores.id"), nullable=True, index=True)

    creado_en = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relaciones útiles (la conversación = mensajes ordenados por fecha).
    mensajes = relationship(
        "Mensaje", back_populates="lead", order_by="Mensaje.creado_en",
        cascade="all, delete-orphan",
    )
    eventos = relationship(
        "Evento", back_populates="lead", order_by="Evento.creado_en",
        cascade="all, delete-orphan",
    )
    asesor = relationship("Asesor")
