"""Schemas Pydantic de Lead (E02 · T02.2.1)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import Estado, Origen
from app.schemas.mensaje import MensajeOut


class LeadCreate(BaseModel):
    origen: Origen | None = None
    nombre: str | None = None
    contacto: str | None = None
    idioma: str | None = None
    perfil: dict | None = None


class LeadUpdate(BaseModel):
    nombre: str | None = None
    contacto: str | None = None
    idioma: str | None = None
    perfil: dict | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    nombre: str | None
    contacto: str | None
    origen: str | None
    idioma: str | None
    score: int | None
    temperatura: str
    estado: str
    perfil: dict
    asesor_id: UUID | None
    creado_en: datetime
    actualizado_en: datetime
    # E07: takeover humano
    atendido_por_humano: bool = False
    asignado_en: datetime | None = None
    notificaciones_count: int = 0


class LeadConMensajes(LeadOut):
    """Detalle de un lead con su conversación (mensajes ordenados)."""

    mensajes: list[MensajeOut] = []


class EstadoUpdate(BaseModel):
    estado: Estado  # inválido → 422


class AsesorUpdate(BaseModel):
    asesor_id: UUID | None  # None = desasignar


class TomarLeadBody(BaseModel):
    asesor_id: UUID
