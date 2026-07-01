"""Schema Pydantic de Asesor (E04/E05/E07)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AsesorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    disponible: bool
    carga: int = 0  # leads activos (calificado + negociando); se computa en el endpoint


class DisponibilidadUpdate(BaseModel):
    disponible: bool
