"""Schema Pydantic de las métricas (E02 · contrato estable para el dashboard)."""

from pydantic import BaseModel


class Conversion(BaseModel):
    lead_a_cita: float
    cita_a_negociacion: float


class MetricsOverview(BaseModel):
    total_leads: int
    por_origen: dict[str, int]
    por_temperatura: dict[str, int]
    por_estado: dict[str, int]
    tiempo_primera_respuesta_seg: float | None
    conversion: Conversion
