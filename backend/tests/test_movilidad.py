"""Tests de la preferencia de movilidad (re-ranking suave). Sin red ni SDK."""

import app.rag.search as search_mod
from app.agent import orchestrator
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.profiler import PerfilExtraido, fusionar_perfil
from app.rag.search import _cumple_pref, buscar_inmuebles
from app.schemas.lead import LeadCreate
from app.services import lead_service


def _m(id_, **extra):
    return {"inmueble_id": id_, "relevancia": extra.pop("rel", 0.5), **extra}


# --- _cumple_pref (umbrales) ---

def test_cumple_pref_parqueadero():
    assert _cumple_pref({"parqueaderos": 2}, "parqueadero") is True
    assert _cumple_pref({"parqueaderos": 0}, "parqueadero") is False
    assert _cumple_pref({}, "parqueadero") is False


def test_cumple_pref_cerca_metro():
    assert _cumple_pref({"dist_metro_m": 600}, "cerca_metro") is True
    assert _cumple_pref({"dist_metro_m": 2000}, "cerca_metro") is False
    assert _cumple_pref({}, "cerca_metro") is False  # sin dist_metro_m → no cumple (honesto)


def test_cumple_pref_espacio_oficina():
    assert _cumple_pref({"area_m2": 90}, "espacio_oficina") is True
    assert _cumple_pref({"habitaciones": 3}, "espacio_oficina") is True
    assert _cumple_pref({"area_m2": 60, "habitaciones": 2}, "espacio_oficina") is False


def test_cumple_pref_conectado():
    assert _cumple_pref({"dist_metro_m": 800}, "conectado") is True  # metro cercano basta
    assert _cumple_pref({"dist_super_m": 300, "dist_colegio_m": 400, "dist_parque_m": 500},
                        "conectado") is True                          # ≥3 categorías ≤800
    assert _cumple_pref({"dist_super_m": 300, "dist_colegio_m": 400}, "conectado") is False  # solo 2


# --- buscar_inmuebles: reordena, NUNCA excluye, conteo igual ---

def test_buscar_reordena_no_excluye(monkeypatch):
    base = [_m("A"), _m("B", parqueaderos=2), _m("C")]
    monkeypatch.setattr(search_mod, "_buscar_base", lambda q, f, k: [dict(x) for x in base])

    r0 = buscar_inmuebles("x", {}, k=3)  # sin preferencias → orden intacto
    assert [i["inmueble_id"] for i in r0] == ["A", "B", "C"]
    assert all(i["preferencias_ok"] == [] for i in r0)

    r1 = buscar_inmuebles("x", {}, k=3, preferencias=["parqueadero"])  # B (parqueadero) primero
    assert [i["inmueble_id"] for i in r1] == ["B", "A", "C"]
    assert r1[0]["preferencias_ok"] == ["parqueadero"]
    assert len(r1) == 3  # A y C siguen apareciendo (no excluye)


def test_buscar_reordena_estable(monkeypatch):
    base = [_m("A", parqueaderos=1), _m("B"), _m("C", parqueaderos=1)]
    monkeypatch.setattr(search_mod, "_buscar_base", lambda q, f, k: [dict(x) for x in base])
    r = buscar_inmuebles("x", {}, k=3, preferencias=["parqueadero"])
    assert [i["inmueble_id"] for i in r] == ["A", "C", "B"]  # A,C (cumplen) en su orden; B al final


def test_buscar_multiples_preferencias_ordena_por_cantidad(monkeypatch):
    base = [
        _m("A", parqueaderos=1),                       # 1 pref (parqueadero)
        _m("B", parqueaderos=2, dist_metro_m=500),     # 2 prefs (parqueadero + cerca_metro)
        _m("C"),                                        # 0
    ]
    monkeypatch.setattr(search_mod, "_buscar_base", lambda q, f, k: [dict(x) for x in base])
    r = buscar_inmuebles("x", {}, k=3, preferencias=["parqueadero", "cerca_metro"])
    assert [i["inmueble_id"] for i in r] == ["B", "A", "C"]  # más preferencias → primero
    assert set(r[0]["preferencias_ok"]) == {"parqueadero", "cerca_metro"}


# --- profiler: captura movilidad, no la usa para calificar ---

def test_profiler_persiste_movilidad(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    fusionar_perfil(db, lead, PerfilExtraido(movilidad="carro", tipo="apartamento"))
    db.refresh(lead)
    assert lead.perfil.get("movilidad") == "carro"


def test_profiler_sin_movilidad_no_agrega_clave(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    fusionar_perfil(db, lead, PerfilExtraido(tipo="casa"))  # sin movilidad
    db.refresh(lead)
    assert "movilidad" not in (lead.perfil or {})


def test_movilidad_no_califica_al_lead():
    # movilidad es preferencia, NO calificador → un lead solo con movilidad sigue "insuficiente".
    assert orchestrator._perfil_insuficiente({"movilidad": "carro"}) is True
    assert orchestrator._perfil_insuficiente({"tipo": "casa"}) is False


def test_prompt_incluye_reglas_tipo_negocio_y_movilidad():
    # Las reglas quedaron insertadas en el SYSTEM_PROMPT (y la caché se invalidó una vez, esperado).
    assert "tipo_negocio" in SYSTEM_PROMPT and "Movilidad" in SYSTEM_PROMPT
