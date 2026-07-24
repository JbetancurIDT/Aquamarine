"""Orquestador del agente Aqua (E03 · T03.3.1).

`responder(db, lead, mensaje_usuario)`:
1. Persiste el mensaje del lead (vía `lead_service`).
2. Carga el historial del lead y lo convierte a formato Claude.
3. Loop **manual** de tool use con la API de Anthropic (máx 3 vueltas como guarda).
4. Persiste la respuesta del agente (con los inmuebles sugeridos en la metadata).
5. Devuelve {respuesta, inmuebles, handoff}.

No tumba el servidor ante errores de la API (auth/créditos/red): devuelve un mensaje claro.
"""

import logging
import re

import anthropic
from sqlalchemy.orm import Session

from app.agent.handoff import ejecutar_handoff_minimo
from app.agent.profiler import extraer_perfil, fusionar_perfil
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.scoring import calcular_score
from app.agent.tools import (
    BUSCAR_INMUEBLES_TOOL,
    LUGARES_CERCA_TOOL,
    ejecutar_buscar_inmuebles,
    ejecutar_lugares_cerca,
)
from app.core.config import settings
from app.models.lead import Lead
from app.rag.search import obtener_inmueble_por_codigo
from app.schemas.lead import LeadUpdate
from app.schemas.mensaje import MensajeCreate
from app.services import lead_service

logger = logging.getLogger(__name__)

_MAX_VUELTAS_TOOL = 3
_MAX_TOKENS = 1024

# `system` como bloque con cache_control: el prompt es estable → se cachea (ahorra tokens).
_SYSTEM_BLOCKS = [
    {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
]

_MENSAJE_ERROR = (
    "Disculpa, tuve un problema técnico para responderte en este momento. "
    "¿Podrías intentarlo de nuevo en un momentico?"
)

_MENSAJE_HANDOFF = (
    "Entendido, ya te conecté con uno de nuestros asesores. "
    "Pronto se estarán comunicando contigo. ¿Hay algo más que quieras contarme mientras tanto?"
)


def _build_client() -> anthropic.Anthropic:
    """Crea el cliente de Anthropic con la key explícita de settings (no del entorno)."""
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _historial_a_mensajes(lead: Lead) -> list[dict]:
    """Convierte los mensajes del lead a formato Claude (lead→user, agente→assistant)."""
    mensajes = []
    for m in lead.mensajes:  # ya vienen ordenados por creado_en (relationship)
        if m.rol == "lead":
            mensajes.append({"role": "user", "content": m.contenido})
        elif m.rol == "agente":
            mensajes.append({"role": "assistant", "content": m.contenido})
        # El rol "asesor" (handoff humano) no se manda a Claude en este MVP.
    return mensajes


# Campos del perfil que cuentan para "calificar" un lead. Si no hay ninguno y el lead
# pide un humano, el handoff es "sin calificar" (temperatura desconocida, score null).
_CAMPOS_CALIFICAN = ("tipo", "zona", "presupuesto_min", "presupuesto_max", "plazo", "habitaciones")


def _perfil_insuficiente(perfil: dict) -> bool:
    return not any((perfil or {}).get(campo) for campo in _CAMPOS_CALIFICAN)


def _extraer_texto(respuesta) -> str:
    """Concatena los bloques de texto de una respuesta de Claude."""
    partes = [
        bloque.text
        for bloque in respuesta.content
        if getattr(bloque, "type", None) == "text"
    ]
    return "\n".join(partes).strip()


# Marcador que Aqua emite para ofrecer el mapa como TARJETA clickeable: [[MAPA:codigo]].
_MAPA_RE = re.compile(r"\[\[MAPA:\s*([A-Za-z0-9_-]+)\s*\]\]")


def _extraer_mapa(texto: str) -> tuple[str, str | None]:
    """Devuelve (texto_sin_marcadores, primer_codigo|None). El cliente NUNCA ve el marcador."""
    codigos = _MAPA_RE.findall(texto or "")
    limpio = _MAPA_RE.sub("", texto or "").strip()
    limpio = re.sub(r"[ \t]{2,}", " ", limpio)
    return limpio, (codigos[0] if codigos else None)


def _construir_mapa(codigo: str | None) -> dict | None:
    """Construye el preview del mapa (código + título + imagen) o None si no hay ficha/coords."""
    if not codigo:
        return None
    inm = obtener_inmueble_por_codigo(codigo)
    if not inm or inm.get("latitud") is None or inm.get("longitud") is None:
        return None  # sin coords la página /mapa/propiedad/:codigo no puede dibujar
    imagenes = inm.get("imagenes") or []
    return {
        "codigo": codigo,
        "titulo": inm.get("titulo") or "esta propiedad",
        "imagen": inm.get("imagen_principal") or (imagenes[0] if imagenes else None),
    }


def _resolver_foco(inmuebles_foco: list[dict], inmuebles_general: list[dict],
                   foco_codigo: str | None) -> dict | None:
    """La única tarjeta a mostrar en un turno de SEGUIMIENTO de una propiedad."""
    if inmuebles_foco:
        return inmuebles_foco[0]
    if foco_codigo:
        for inm in inmuebles_general:
            if str(inm.get("inmueble_id")) == str(foco_codigo):
                return inm
        return obtener_inmueble_por_codigo(foco_codigo)  # aunque solo se corrió lugares_cerca
    return None


def responder(db: Session, lead: Lead, mensaje_usuario: str) -> dict:
    """Procesa un turno: persiste, llama a Claude (con tool use) y devuelve la respuesta.

    Si el lead ya fue tomado por un asesor humano (`atendido_por_humano=True`), persiste
    el mensaje del lead pero NO llama a la IA. El asesor responde por su cuenta.
    """
    # Takeover: IA silenciada — solo persiste el mensaje del lead.
    if lead.atendido_por_humano:
        lead_service.agregar_mensaje(
            db, lead, MensajeCreate(rol="lead", contenido=mensaje_usuario)
        )
        return {
            "respuesta": "",
            "inmuebles": [],
            "handoff": False,
            "temperatura": lead.temperatura,
            "lead_id": lead.id,
            "atendido_por_humano": True,
            "mapa": None,
        }

    # 1) Persistir el mensaje del lead.
    lead_service.agregar_mensaje(
        db, lead, MensajeCreate(rol="lead", contenido=mensaje_usuario)
    )

    # 2) Historial → formato Claude (incluye el mensaje recién persistido).
    db.refresh(lead)
    mensajes = _historial_a_mensajes(lead)

    # 3) Loop manual de tool use. Rastrea el ORIGEN de las tarjetas para el fix de FOCO:
    #    lugares_cerca / code-lookup ⇒ turno de seguimiento de UNA propiedad (solo esa tarjeta).
    inmuebles_general: list[dict] = []
    inmuebles_foco: list[dict] = []
    uso_lugares_cerca = False
    foco_codigo: str | None = None
    mapa_codigo_fallback: str | None = None  # respaldo del mapa: el codigo de lugares_cerca del turno
    texto_final = ""
    try:
        client = _build_client()
        for _ in range(_MAX_VUELTAS_TOOL):
            respuesta = client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_BLOCKS,
                messages=mensajes,
                tools=[BUSCAR_INMUEBLES_TOOL, LUGARES_CERCA_TOOL],
            )
            texto_final = _extraer_texto(respuesta) or texto_final

            if respuesta.stop_reason != "tool_use":
                break

            # Registro de handlers por nombre. `buscar_inmuebles` aporta inmuebles (→ tarjetas en el
            # chat); `lugares_cerca` devuelve solo texto (no genera tarjetas). Se arma aquí para que
            # respete el monkeypatch de los handlers en los tests.
            handlers = {
                "buscar_inmuebles": ejecutar_buscar_inmuebles,
                "lugares_cerca": ejecutar_lugares_cerca,
            }
            # Agrega el turno del assistant (con sus bloques tool_use) al historial...
            mensajes.append({"role": "assistant", "content": respuesta.content})
            # ...ejecuta cada tool_use y devuelve los tool_result como un turno de usuario.
            resultados = []
            for bloque in respuesta.content:
                if getattr(bloque, "type", None) != "tool_use":
                    continue
                nombre = getattr(bloque, "name", None)
                handler = handlers.get(nombre)
                if handler is None:
                    continue
                entrada = bloque.input or {}
                texto_tool, inmuebles = handler(entrada)
                if nombre == "lugares_cerca":
                    uso_lugares_cerca = True
                    cod = str(entrada.get("codigo") or "")
                    if cod:
                        foco_codigo = cod
                        mapa_codigo_fallback = cod
                elif nombre == "buscar_inmuebles":
                    if entrada.get("codigo"):          # code-lookup → foco en esa propiedad
                        foco_codigo = str(entrada.get("codigo"))
                        inmuebles_foco.extend(inmuebles)
                    else:                              # búsqueda general
                        inmuebles_general.extend(inmuebles)
                resultados.append({
                    "type": "tool_result",
                    "tool_use_id": bloque.id,
                    "content": texto_tool,
                })
            mensajes.append({"role": "user", "content": resultados})
    except Exception as exc:  # no tumbar el servidor ante errores de la API/red
        logger.exception("Fallo del agente Aqua: %s", exc)
        if not texto_final:
            texto_final = _MENSAJE_ERROR

    # Foco: si el turno fue seguimiento de UNA propiedad, solo su tarjeta (descarta la búsqueda general).
    if uso_lugares_cerca or inmuebles_foco:
        foco = _resolver_foco(inmuebles_foco, inmuebles_general, foco_codigo)
        inmuebles_sugeridos = [foco] if foco else []
    else:
        inmuebles_sugeridos = inmuebles_general

    # Parte A: extrae el marcador [[MAPA:x]] del texto (el cliente no lo ve) + respaldo determinista.
    texto_final, mapa_codigo = _extraer_mapa(texto_final)
    mapa = _construir_mapa(mapa_codigo or mapa_codigo_fallback)

    # 4) Persistir la respuesta del agente con los inmuebles sugeridos.
    ids = [inm.get("inmueble_id") for inm in inmuebles_sugeridos if inm.get("inmueble_id")]
    lead_service.agregar_mensaje(
        db,
        lead,
        MensajeCreate(rol="agente", contenido=texto_final or "…", metadata={"inmuebles": ids}),
    )

    # 5) Post-turno: perfilamiento + scoring + estado + nurturing. Envuelto en try/except:
    # si falla la extracción, NO se rompe la respuesta ya generada para el cliente.
    temperatura = lead.temperatura
    handoff = False
    try:
        db.refresh(lead)
        historial = _historial_a_mensajes(lead)
        extraido = extraer_perfil(historial)
        fusionar_perfil(db, lead, extraido)

        if extraido.pide_humano:
            # Handoff POR SOLICITUD: no se bloquea por datos faltantes (Aqua ya pidió
            # nombre/contacto por el system prompt; procede con lo que haya).
            if _perfil_insuficiente(lead.perfil or {}):
                # No alcanzó a calificar → temperatura desconocida, score null (D15).
                lead_service.set_score(db, lead, None, "desconocido")
                temperatura = "desconocido"
                hecho = ejecutar_handoff_minimo(db, lead, sin_calificar=True)
            else:
                score, temperatura = calcular_score(
                    lead.perfil or {}, extraido.interes_urgencia, bool(extraido.inmueble_interes)
                )
                lead_service.set_score(db, lead, score, temperatura)
                hecho = ejecutar_handoff_minimo(db, lead)
            handoff = True
            if hecho:
                # El mensaje de handoff reemplaza el texto de la propiedad → descarta su mapa/tarjetas
                # (si no, quedaría un CTA "Ver mapa" y fichas huérfanas junto a "ya te conecté…").
                texto_final = _MENSAJE_HANDOFF
                mapa = None
                inmuebles_sugeridos = []
        else:
            # Flujo normal: scoring + estado + (handoff si caliente | nurturing si tibio/frío).
            score, temperatura = calcular_score(
                lead.perfil or {}, extraido.interes_urgencia, bool(extraido.inmueble_interes)
            )
            lead_service.set_score(db, lead, score, temperatura)

            if lead.estado == "nuevo":
                lead_service.set_estado(db, lead, "contactado")

            if temperatura == "caliente":
                ejecutar_handoff_minimo(db, lead)
                handoff = True
            elif temperatura in ("tibio", "frio"):
                # Nurturing (esqueleto): marca de seguimiento. La reactivación programada queda como roadmap.
                perfil = dict(lead.perfil or {})
                perfil["nurturing"] = "seguimiento pendiente"
                lead_service.update_lead(db, lead, LeadUpdate(perfil=perfil))
    except Exception as exc:
        logger.exception("Post-turno (perfil/scoring/handoff) falló: %s", exc)
        temperatura = lead.temperatura  # conserva lo que haya

    return {
        "respuesta": texto_final,
        "inmuebles": inmuebles_sugeridos,
        "handoff": handoff,
        "temperatura": temperatura,
        "lead_id": lead.id,
        "atendido_por_humano": False,
        "mapa": mapa,
    }
