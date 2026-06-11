"""Modelo Tenant (E02 · T02.1.1).

En el MVP hay un solo tenant ("Aquamarine Group"), pero todo registro de negocio
lleva `tenant_id` desde el día 1 (multitenant-ready).
"""

from sqlalchemy import Column, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    # unique: evita que una carrera SELECT→INSERT cree dos tenants con el mismo nombre.
    nombre = Column(String, nullable=False, unique=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
