"""Agente de insights de gerencia — Aqua responde preguntas de Claudia sobre métricas (E08).

`responder_gerencia(db, tenant, pregunta)` — loop manual de tool-use con Claude Haiku 4.5.
Mismo patrón que orchestrator.py: máx 3 vueltas, resiliente ante errores de API.
"""

import json
import logging

import anthropic
from sqlalchemy.orm import Session

from app.agent.insights_tools import TOOLS, ejecutar_tool
from app.agent.prompts import INSIGHTS_SYSTEM_PROMPT
from app.core.config import settings
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Haiku 4.5: veloz y barato para preguntas de métricas.
_INSIGHTS_MODEL = settings.ANTHROPIC_EXTRACTION_MODEL
_MAX_TOKENS     = 700
_MAX_VUELTAS    = 3

# `system` como bloque con cache_control: el prompt es estable → ahorra tokens.
_SYSTEM_BLOCKS = [
    {"type": "text", "text": INSIGHTS_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
]

_MENSAJE_ERROR = (
    "Disculpa, tuve un problema técnico en este momento. "
    "Por favor intenta de nuevo en un instante."
)


def _build_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _extraer_texto(respuesta) -> str:
    return "\n".join(
        bloque.text
        for bloque in respuesta.content
        if getattr(bloque, "type", None) == "text"
    ).strip()


def responder_gerencia(db: Session, tenant: Tenant, pregunta: str) -> dict:
    """Procesa la pregunta de gerencia con tool-use sobre Haiku.

    Devuelve {'respuesta': str, 'datos': dict | None}.
    'datos' = JSON crudo de la(s) tool(s) invocada(s); None si no se usó ninguna.
    """
    mensajes: list = [{"role": "user", "content": pregunta}]
    texto_final   = ""
    datos_acum:  dict = {}
    uso_tool     = False

    try:
        client = _build_client()
        for _ in range(_MAX_VUELTAS):
            respuesta = client.messages.create(
                model=_INSIGHTS_MODEL,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_BLOCKS,
                messages=mensajes,
                tools=TOOLS,
            )
            texto_final = _extraer_texto(respuesta) or texto_final

            if respuesta.stop_reason != "tool_use":
                break

            mensajes.append({"role": "assistant", "content": respuesta.content})
            tool_results = []
            for bloque in respuesta.content:
                if getattr(bloque, "type", None) != "tool_use":
                    continue
                nombre  = getattr(bloque, "name",  "")
                inputs  = getattr(bloque, "input", {}) or {}
                resultado = ejecutar_tool(nombre, inputs, db, tenant)
                datos_acum[nombre] = resultado
                uso_tool = True
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": bloque.id,
                    "content":     json.dumps(resultado, ensure_ascii=False, default=str),
                })
            mensajes.append({"role": "user", "content": tool_results})

    except Exception as exc:
        logger.exception("Insights agent error: %s", exc)
        if not texto_final:
            texto_final = _MENSAJE_ERROR

    return {
        "respuesta": texto_final or _MENSAJE_ERROR,
        "datos":     datos_acum if uso_tool else None,
    }
