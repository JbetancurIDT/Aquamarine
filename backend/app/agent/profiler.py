"""Perfilamiento del lead + idioma (E03 · T03.4.1 / T03.1.2).

Una llamada de **extracción estructurada** (modelo barato) que saca de la conversación
solo los datos CONFIRMADOS del cliente; lo que no aparece queda en `None` (no se inventa).
`fusionar_perfil` los persiste sin pisar datos previos con `None`.
"""

import logging
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lead import Lead
from app.schemas.lead import LeadUpdate
from app.services import lead_service

logger = logging.getLogger(__name__)


class PerfilExtraido(BaseModel):
    """Datos del lead extraídos de la conversación (solo lo confirmado; el resto None)."""

    nombre: Optional[str] = None
    contacto: Optional[str] = None  # correo o WhatsApp
    idioma: Optional[Literal["es", "en"]] = None
    tipo: Optional[str] = None  # apartamento | casa | lote | ...
    zona: Optional[str] = None
    ciudad: Optional[str] = None
    presupuesto_min: Optional[int] = None
    presupuesto_max: Optional[int] = None
    habitaciones: Optional[int] = None
    plazo: Optional[Literal["corto", "medio", "largo"]] = None  # corto = decide en <3 meses
    notas: Optional[str] = None
    interes_urgencia: Optional[Literal["alta", "media", "baja"]] = None
    inmueble_interes: Optional[str] = None  # inmueble_id si se enfocó en uno específico
    origen: Optional[str] = None  # canal si el cliente dijo cómo nos conoció
    pide_humano: bool = False  # True si pidió hablar con una persona / asesor real


_EXTRACTION_SYSTEM = """\
Eres un extractor de datos. A partir de la conversación entre un cliente y el asistente \
inmobiliario, llama a la herramienta `extraer_perfil_cliente` con SOLO los datos que el \
cliente haya confirmado o dicho explícitamente. Lo que no aparezca, omítelo (null).

Normalización:
- `idioma`: "es" si el cliente escribe en español, "en" si en inglés.
- `plazo`: "corto" si decide en menos de 3 meses; "medio" si 3–12 meses; "largo" si solo explora.
- `presupuesto_min`/`presupuesto_max`: pesos colombianos, enteros sin puntos \
(p.ej. "5 mil millones" → 5000000000).
- `interes_urgencia`: "alta" si suena decidido/urgente o pide visitar ya; "media" si \
interesado sin afán; "baja" si solo explora.
- `pide_humano`: true si el cliente pide hablar con una persona o asesor real.
"""

# Tool schema para extracción estructurada — evita grammar compilation de messages.parse().
_EXTRACTION_TOOL: dict = {
    "name": "extraer_perfil_cliente",
    "description": "Registra los datos del cliente extraídos de la conversación.",
    "input_schema": {
        "type": "object",
        "properties": {
            "nombre": {"type": "string"},
            "contacto": {"type": "string"},
            "idioma": {"type": "string", "enum": ["es", "en"]},
            "tipo": {"type": "string"},
            "zona": {"type": "string"},
            "ciudad": {"type": "string"},
            "presupuesto_min": {"type": "integer"},
            "presupuesto_max": {"type": "integer"},
            "habitaciones": {"type": "integer"},
            "plazo": {"type": "string", "enum": ["corto", "medio", "largo"]},
            "notas": {"type": "string"},
            "interes_urgencia": {"type": "string", "enum": ["alta", "media", "baja"]},
            "inmueble_interes": {"type": "string"},
            "origen": {"type": "string"},
            "pide_humano": {"type": "boolean"},
        },
        "required": ["pide_humano"],
    },
}


def _build_client() -> anthropic.Anthropic:
    """Cliente de Anthropic con la key explícita de settings."""
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def extraer_perfil(historial: list[dict]) -> PerfilExtraido:
    """Extrae el perfil del cliente usando tool_use (sin grammar compilation)."""
    if not historial:
        return PerfilExtraido()

    transcripto = "\n".join(
        f"{'Cliente' if m.get('role') == 'user' else 'Asistente'}: {m.get('content', '')}"
        for m in historial
        if isinstance(m.get("content"), str)
    )

    client = _build_client()
    resp = client.messages.create(
        model=settings.ANTHROPIC_EXTRACTION_MODEL,
        max_tokens=512,
        system=_EXTRACTION_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Conversación:\n{transcripto}\n\nExtrae el perfil del cliente.",
        }],
        tools=[_EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extraer_perfil_cliente"},
    )
    for bloque in resp.content:
        if getattr(bloque, "type", None) == "tool_use" and bloque.name == "extraer_perfil_cliente":
            return PerfilExtraido(**bloque.input)
    return PerfilExtraido()


# Campos del PerfilExtraido que viven en el jsonb `lead.perfil` (no en columnas del lead).
_CAMPOS_PERFIL = (
    "tipo", "zona", "ciudad", "presupuesto_min", "presupuesto_max",
    "habitaciones", "plazo", "notas", "inmueble_interes",
)


def fusionar_perfil(db: Session, lead: Lead, extraido: PerfilExtraido) -> Lead:
    """Persiste el perfil extraído SIN pisar datos previos con `None`."""
    # Origen deducido: solo si el lead aún no tiene origen (de la URL). Nunca sobrescribe
    # un origen ya seteado por el canal de entrada.
    if lead.origen is None and extraido.origen:
        lead.origen = extraido.origen

    datos = {}
    if extraido.nombre:
        datos["nombre"] = extraido.nombre
    if extraido.contacto:
        datos["contacto"] = extraido.contacto
    if extraido.idioma:
        datos["idioma"] = extraido.idioma

    # jsonb perfil: parte del previo y agrega solo los campos no-None.
    perfil = dict(lead.perfil or {})
    for campo in _CAMPOS_PERFIL:
        valor = getattr(extraido, campo)
        if valor is not None:
            perfil[campo] = valor
    datos["perfil"] = perfil

    return lead_service.update_lead(db, lead, LeadUpdate(**datos))
