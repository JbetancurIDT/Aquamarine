"""Schemas Pydantic de Lead (E02 · T02.2.1)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import Estado, Origen
from app.schemas.mensaje import MensajeOut


class LeadCreate(BaseModel):
    # Opcional: lo simula la URL /chat/<origen>/; None si no se sabe (D15). Sigue validando
    # contra el catálogo de orígenes (valor inválido → 422 en POST /leads).
    origen: Origen | None = None
    nombre: str | None = None
    contacto: str | None = None
    idioma: str | None = None
    perfil: dict | None = None


class LeadUpdate(BaseModel):
    # Todos opcionales. El estado/score/temperatura NO se tocan aquí: van por
    # endpoints/servicios dedicados que emiten su evento (set_estado / set_score).
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
    origen: str
    idioma: str | None
    score: int
    temperatura: str
    estado: str
    perfil: dict
    asesor_id: UUID | None
    creado_en: datetime
    actualizado_en: datetime


class LeadConMensajes(LeadOut):
    """Detalle de un lead con su conversación (mensajes ordenados)."""

    mensajes: list[MensajeOut] = []


class EstadoUpdate(BaseModel):
    estado: Estado  # inválido → 422
