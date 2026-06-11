"""Schema Pydantic de Evento (E02 · T02.2.1)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    tipo: str
    payload: dict | None
    creado_en: datetime
