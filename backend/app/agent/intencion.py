"""Derivación de intención de compra — fallback determinista (E11 · T11.2.1).

Eje NUEVO e independiente del scoring/temperatura ([[Decisiones (Decision Log)]] D26). Aqua
la INFIERE cada turno en el profiler (`perfil.intencion`); esta función es el **fallback**
para los leads que aún no la tienen (los históricos) y para la métrica al vuelo: reconstruye
la intención a partir de lo ya guardado (`perfil` + `temperatura`), sin red ni SDK.

Rúbrica (misma de D26, fuente de verdad del significado):
- `comprador` = presupuesto + plazo corto/medio; **o** pide visita/asesor; **o** inmueble concreto
  con urgencia. En señales ya guardadas: temperatura caliente, o presupuesto+plazo(corto|medio),
  o `inmueble_interes` presente.
- `curioso` ("lolo") = solo pregunta precio/info, sin presupuesto, "solo mirando" (plazo largo),
  sin contacto/visita. En señales: temperatura fría **y** sin presupuesto **y** `plazo == "largo"`.
- `explorando` = intermedio (todo lo demás).
"""

# Valores válidos del eje de intención (orden de reporte: comprador → explorando → curioso).
INTENCIONES: tuple[str, str, str] = ("comprador", "explorando", "curioso")


def _tiene_presupuesto(perfil: dict) -> bool:
    """True si el perfil registra algún presupuesto (min o max), igual criterio que el scoring."""
    return bool(perfil.get("presupuesto_min") or perfil.get("presupuesto_max"))


def derivar_intencion(perfil: dict, temperatura: str) -> str:
    """Deriva la intención (`comprador`|`explorando`|`curioso`) de forma pura y determinista.

    Es un fallback: cuando `perfil['intencion']` no existe, esta función la reconstruye desde
    las señales ya guardadas. No toca el scoring ni consulta la red.
    """
    perfil = perfil or {}
    plazo = perfil.get("plazo")
    tiene_presupuesto = _tiene_presupuesto(perfil)
    tiene_inmueble = bool(perfil.get("inmueble_interes"))

    # comprador: señal fuerte de intención real (tiene prioridad sobre curioso).
    if (
        temperatura == "caliente"
        or (tiene_presupuesto and plazo in ("corto", "medio"))
        or tiene_inmueble
    ):
        return "comprador"

    # curioso ("lolo"): frío, sin presupuesto y "solo estoy mirando".
    if temperatura == "frio" and not tiene_presupuesto and plazo == "largo":
        return "curioso"

    # intermedio: algunas señales pero sin compromiso claro.
    return "explorando"
