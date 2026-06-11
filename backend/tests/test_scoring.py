"""Tests del scoring híbrido (E03 · T03.4.2). Funciones puras, sin mock ni API."""

from app.agent.scoring import calcular_score


def test_caliente_por_perfil_completo():
    perfil = {"tipo": "apartamento", "zona": "Poblado", "presupuesto_max": 5000000000, "plazo": "corto"}
    score, temp = calcular_score(perfil, "media", False)
    assert temp == "caliente"  # zona + presupuesto + plazo<3m
    assert 0 <= score <= 100


def test_un_solo_criterio_no_caliente():
    score, temp = calcular_score({"zona": "Poblado"}, "baja", False)
    assert temp != "caliente"
    assert temp in ("frio", "tibio")
    assert 0 <= score <= 100


def test_caliente_por_urgencia_e_inmueble():
    score, temp = calcular_score({}, "alta", True)
    assert temp == "caliente"  # urgencia alta + inmueble específico


def test_perfil_vacio_es_frio():
    score, temp = calcular_score({}, None, False)
    assert score == 0
    assert temp == "frio"


def test_score_acotado_a_100():
    perfil = {
        "tipo": "apartamento", "zona": "Poblado", "presupuesto_min": 1, "presupuesto_max": 2,
        "plazo": "corto", "habitaciones": 3,
    }
    score, temp = calcular_score(perfil, "alta", True)  # 90 completitud + 30 bonus = 120 → 100
    assert score == 100
    assert temp == "caliente"
