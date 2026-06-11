"""Scoring híbrido del lead (E03 · T03.4.2).

Combina **completitud del perfil** + **tono/urgencia** + **foco en un inmueble específico**
para producir (score 0–100, temperatura). Lo consume el orquestador, que persiste con
`lead_service.set_score` (emite `score_actualizado`).
"""


def calcular_score(perfil: dict, interes_urgencia, tiene_inmueble_interes: bool) -> tuple[int, str]:
    """Devuelve (score 0–100, temperatura: 'caliente' | 'tibio' | 'frio')."""
    perfil = perfil or {}

    tiene_zona = bool(perfil.get("zona"))
    tiene_presupuesto = bool(perfil.get("presupuesto_min") or perfil.get("presupuesto_max"))
    plazo_corto = perfil.get("plazo") == "corto"  # corto = decide en <3 meses

    # Completitud del perfil.
    score = 0
    if perfil.get("tipo"):
        score += 15
    if tiene_zona:
        score += 20
    if tiene_presupuesto:
        score += 25
    if plazo_corto:
        score += 25
    if perfil.get("habitaciones"):
        score += 5

    # Bonus por tono/urgencia y foco en un inmueble específico.
    if interes_urgencia == "alta":
        score += 20
    elif interes_urgencia == "media":
        score += 10
    if tiene_inmueble_interes:
        score += 10

    score = min(100, score)

    # Temperatura: la regla núcleo del epic (zona + presupuesto + plazo<3m) más los
    # extras de tono/urgencia que pidió el negocio.
    caliente = (
        (tiene_zona and tiene_presupuesto and plazo_corto)
        or (interes_urgencia == "alta" and tiene_inmueble_interes)
        or score >= 70
    )
    if caliente:
        temperatura = "caliente"
    elif score >= 35:
        temperatura = "tibio"
    else:
        temperatura = "frio"

    return score, temperatura
