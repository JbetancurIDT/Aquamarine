"""Schema Pydantic de las métricas — E05 (Dashboard de gerencia).

Cada porcentaje se devuelve como `Rate { pct, num, den }` para que el
dashboard pueda mostrar numerador/denominador junto al porcentaje y para
auditar los cálculos directamente en la respuesta (convención §5 del diseño).
"""

from pydantic import BaseModel


class Rate(BaseModel):
    """Tasa auditable: porcentaje (0–1) + numerador + denominador."""

    pct: float
    num: int
    den: int


class LeadsCalientes(BaseModel):
    count: int
    rate: Rate


class FunnelStep(BaseModel):
    etapa: str
    count: int
    pct_paso_previo: Rate | None  # None en la primera etapa (nuevo)


class Conversion(BaseModel):
    lead_a_cita: Rate
    cita_a_negociacion: Rate


class NegociosGanados(BaseModel):
    count: int
    valor_cerrado_cop: int


class MetricsOverview(BaseModel):
    total_leads: int
    leads_calientes: LeadsCalientes
    pct_calificados: Rate
    primera_respuesta_seg: float | None
    funnel: list[FunnelStep]
    conversion: Conversion
    pipeline_ponderado_cop: int
    negocios_ganados: NegociosGanados
    por_temperatura: dict[str, int]
    por_origen: dict[str, int]


# ── E07: métricas por asesor (reales) y propiedades (mock) ───────────────────

class AsesorMetrics(BaseModel):
    id: str
    nombre: str
    disponible: bool
    leads_asignados: int
    en_cola: int            # calificado + negociando
    tomados: int            # atendido_por_humano=True
    ganados: int
    valor_cerrado_cop: int
    primera_respuesta_seg: float | None
    tiempo_en_tomar_seg: float | None  # prom. asignado_en → evento tomado_por_humano
    ratio_conversion: Rate


class PropiedadesMetrics(BaseModel):
    """Métricas de inventario — MOCK hasta conectar la DB vectorial."""
    activas: int
    en_negociacion: int
    cerradas: int
    valor_cerrado_cop: int
