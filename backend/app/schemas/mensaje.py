"""Schemas Pydantic de Mensaje (E02 · T02.2.1)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Rol


class MensajeCreate(BaseModel):
    rol: Rol  # lead | agente | asesor (inválido → 422)
    contenido: str = Field(min_length=1)  # no se aceptan mensajes vacíos (→ 422)
    metadata: dict | None = None  # tokens, inmuebles sugeridos, etc.


class MensajeOut(BaseModel):
    # El atributo ORM se llama `meta` (la columna es "metadata"); lo leemos por
    # `validation_alias` y lo exponemos como `metadata` en la respuesta.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    lead_id: UUID
    rol: str
    contenido: str
    metadata: dict | None = Field(default=None, validation_alias="meta")
    creado_en: datetime
