"""Tests del router de métricas — E05: estructura, invariantes, valores exactos, filtros."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.asesor import Asesor
from app.models.lead import Lead
from app.models.mensaje import Mensaje
from app.services import lead_service
from app.schemas.lead import LeadCreate


# ---------------------------------------------------------------------------
# Fixture: dataset de demo (mismo que seed_demo.py) para validar valores exactos
# ---------------------------------------------------------------------------

@pytest.fixture
def leads_demo(db):
    """Crea el mismo dataset que seed_demo.py para verificar métricas exactas.

    Distribución:
      Temperatura: 4 caliente · 6 tibio · 8 frío · 2 desconocido
      Estado:      4 nuevo · 6 contactado · 6 calificado · 2 negociando · 2 cerrado_ganado
      Presupuesto: nuevo 500M · contactado 800M · calificado 1000M · negociando 1500M · ganado 1200M
    """
    tenant = lead_service.get_or_create_default_tenant(db)
    a1 = Asesor(tenant_id=tenant.id, nombre="Mateo Ángel", disponible=True)
    a2 = Asesor(tenant_id=tenant.id, nombre="Valentina Ruiz", disponible=True)
    db.add_all([a1, a2])
    db.flush()

    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)

    # (temperatura, estado, origen, presupuesto_max, asesor)
    SPEC = [
        ("caliente",    "nuevo",          "meta",          500_000_000,   None),
        ("tibio",       "nuevo",          "meta",          500_000_000,   None),
        ("frio",        "nuevo",          "web",           500_000_000,   None),
        ("desconocido", "nuevo",          "metrocuadrado", 500_000_000,   None),
        ("caliente",    "contactado",     "meta",          800_000_000,   None),
        ("tibio",       "contactado",     "meta",          800_000_000,   None),
        ("tibio",       "contactado",     "meta",          800_000_000,   None),
        ("frio",        "contactado",     "fincaraiz",     800_000_000,   None),
        ("frio",        "contactado",     "web",           800_000_000,   None),
        ("desconocido", "contactado",     "metrocuadrado", 800_000_000,   None),
        ("caliente",    "calificado",     "meta",          1_000_000_000, a1),
        ("tibio",       "calificado",     "meta",          1_000_000_000, a1),
        ("tibio",       "calificado",     "metrocuadrado", 1_000_000_000, a2),
        ("frio",        "calificado",     "web",           1_000_000_000, a2),
        ("frio",        "calificado",     "fincaraiz",     1_000_000_000, a1),
        ("frio",        "calificado",     "metrocuadrado", 1_000_000_000, a2),
        ("caliente",    "negociando",     "fincaraiz",     1_500_000_000, a1),
        ("tibio",       "negociando",     "metrocuadrado", 1_500_000_000, a2),
        ("frio",        "cerrado_ganado", "web",           1_200_000_000, a1),
        ("frio",        "cerrado_ganado", "meta",          1_200_000_000, a2),
    ]

    leads = []
    for i, (temp, estado, origen, budget, asesor) in enumerate(SPEC):
        ts = now - timedelta(hours=len(SPEC) - i)
        lead = Lead(
            tenant_id=tenant.id,
            nombre=f"Demo Lead {i + 1:02d}",
            origen=origen,
            temperatura=temp,
            estado=estado,
            perfil={"presupuesto_max": budget, "tipo": "apartamento", "zona": "norte", "demo": True},
            asesor_id=asesor.id if asesor else None,
            creado_en=ts,
        )
        db.add(lead)
        db.flush()
        db.add_all([
            Mensaje(lead_id=lead.id, rol="lead",   contenido="Hola.", creado_en=ts),
            Mensaje(lead_id=lead.id, rol="agente", contenido="Bienvenido.", creado_en=ts + timedelta(seconds=30)),
        ])
        leads.append(lead)

    db.commit()
    return leads


# ---------------------------------------------------------------------------
# Estructura vacía
# ---------------------------------------------------------------------------

def test_overview_estructura_vacia(client):
    r = client.get("/metrics/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total_leads"] == 0
    assert body["por_origen"] == {"web": 0, "meta": 0, "metrocuadrado": 0, "fincaraiz": 0, "otros": 0}
    assert body["por_temperatura"] == {"caliente": 0, "tibio": 0, "frio": 0, "desconocido": 0, "otros": 0}
    assert body["primera_respuesta_seg"] is None
    # Rate vacías
    assert body["pct_calificados"] == {"pct": 0.0, "num": 0, "den": 0}
    assert body["leads_calientes"]["count"] == 0
    assert body["leads_calientes"]["rate"] == {"pct": 0.0, "num": 0, "den": 0}
    # Conversiones vacías
    assert body["conversion"]["lead_a_cita"] == {"pct": 0.0, "num": 0, "den": 0}
    assert body["conversion"]["cita_a_negociacion"] == {"pct": 0.0, "num": 0, "den": 0}
    # Funnel: 5 etapas con count 0
    etapas = [f["etapa"] for f in body["funnel"]]
    assert etapas == ["nuevo", "contactado", "calificado", "negociando", "cerrado_ganado"]
    assert all(f["count"] == 0 for f in body["funnel"])
    assert body["funnel"][0]["pct_paso_previo"] is None
    # Pipeline y ganados en 0
    assert body["pipeline_ponderado_cop"] == 0
    assert body["negocios_ganados"] == {"count": 0, "valor_cerrado_cop": 0}


# ---------------------------------------------------------------------------
# Invariantes de buckets
# ---------------------------------------------------------------------------

def test_overview_invariante_buckets(client):
    """sum de cada bucket == total_leads siempre."""
    client.post("/leads", json={"origen": "web"})
    client.post("/leads", json={"origen": "meta"})
    body = client.get("/metrics/overview").json()
    assert sum(body["por_origen"].values()) == body["total_leads"]
    assert sum(body["por_temperatura"].values()) == body["total_leads"]


# ---------------------------------------------------------------------------
# 1ª respuesta
# ---------------------------------------------------------------------------

def test_primera_respuesta_60s(client, db):
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    client.post(f"/leads/{lid}/mensajes", json={"rol": "agente", "contenido": "resp"})
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    db.query(Lead).filter(Lead.id == lid).update({Lead.creado_en: base})
    db.query(Mensaje).filter(Mensaje.lead_id == lid).update(
        {Mensaje.creado_en: base + timedelta(seconds=60)}
    )
    db.commit()
    assert client.get("/metrics/overview").json()["primera_respuesta_seg"] == 60.0


def test_primera_respuesta_promedio(client, db):
    """Dos leads con deltas 60 y 120 → promedio 90.0."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for delta in (60, 120):
        lid = client.post("/leads", json={"origen": "web"}).json()["id"]
        client.post(f"/leads/{lid}/mensajes", json={"rol": "agente", "contenido": "resp"})
        db.query(Lead).filter(Lead.id == lid).update({Lead.creado_en: base})
        db.query(Mensaje).filter(Mensaje.lead_id == lid).update(
            {Mensaje.creado_en: base + timedelta(seconds=delta)}
        )
    db.commit()
    assert client.get("/metrics/overview").json()["primera_respuesta_seg"] == 90.0


# ---------------------------------------------------------------------------
# Valores EXACTOS del dataset demo (red de seguridad de cálculos)
# ---------------------------------------------------------------------------

def test_demo_total(client, leads_demo):
    assert client.get("/metrics/overview").json()["total_leads"] == 20


def test_demo_pct_calificados(client, leads_demo):
    """18/20 tienen temperatura != desconocido → 90%."""
    r = client.get("/metrics/overview").json()["pct_calificados"]
    assert r == {"pct": 0.9, "num": 18, "den": 20}


def test_demo_leads_calientes(client, leads_demo):
    """4/20 son calientes → 20%."""
    lc = client.get("/metrics/overview").json()["leads_calientes"]
    assert lc["count"] == 4
    assert lc["rate"] == {"pct": 0.2, "num": 4, "den": 20}


def test_demo_funnel(client, leads_demo):
    """Funnel acumulado: 20→16→10→4→2 con % 80%/62.5%/40%/50%."""
    funnel = {f["etapa"]: f for f in client.get("/metrics/overview").json()["funnel"]}

    assert funnel["nuevo"]["count"] == 20
    assert funnel["nuevo"]["pct_paso_previo"] is None

    assert funnel["contactado"]["count"] == 16
    assert funnel["contactado"]["pct_paso_previo"] == {"pct": 0.8, "num": 16, "den": 20}

    assert funnel["calificado"]["count"] == 10
    assert funnel["calificado"]["pct_paso_previo"] == {"pct": 0.625, "num": 10, "den": 16}

    assert funnel["negociando"]["count"] == 4
    assert funnel["negociando"]["pct_paso_previo"] == {"pct": 0.4, "num": 4, "den": 10}

    assert funnel["cerrado_ganado"]["count"] == 2
    assert funnel["cerrado_ganado"]["pct_paso_previo"] == {"pct": 0.5, "num": 2, "den": 4}


def test_demo_conversion(client, leads_demo):
    """lead→cita 50% (10/20), cita→negociación 40% (4/10)."""
    conv = client.get("/metrics/overview").json()["conversion"]
    assert conv["lead_a_cita"] == {"pct": 0.5, "num": 10, "den": 20}
    assert conv["cita_a_negociacion"] == {"pct": 0.4, "num": 4, "den": 10}


def test_demo_pipeline_ponderado(client, leads_demo):
    """
    4*500M*0.10 + 6*800M*0.25 + 6*1000M*0.50 + 2*1500M*0.75
    = 200M + 1200M + 3000M + 2250M = 6650M COP
    """
    assert client.get("/metrics/overview").json()["pipeline_ponderado_cop"] == 6_650_000_000


def test_demo_negocios_ganados(client, leads_demo):
    """2 cerrados ganados × 1200M = 2400M COP."""
    ng = client.get("/metrics/overview").json()["negocios_ganados"]
    assert ng["count"] == 2
    assert ng["valor_cerrado_cop"] == 2_400_000_000


def test_demo_primera_respuesta(client, leads_demo):
    """Todos los leads tienen respuesta del agente 30s después."""
    assert client.get("/metrics/overview").json()["primera_respuesta_seg"] == 30.0


# ---------------------------------------------------------------------------
# Filtros de /metrics/overview
# ---------------------------------------------------------------------------

def test_filtro_origen(client, leads_demo):
    """Filtrar por origen='web' → sólo los leads de ese origen."""
    body = client.get("/metrics/overview", params={"origen": "web"}).json()
    # En el seed: 1 nuevo-web + 1 contactado-web + 1 calificado-web + 1 ganado-web = 4
    assert body["total_leads"] == 4
    assert body["por_origen"]["web"] == 4
    assert all(v == 0 for k, v in body["por_origen"].items() if k != "web" and k != "otros")


def test_filtro_temperatura(client, leads_demo):
    """Filtrar por temperatura='caliente' → 4 leads."""
    body = client.get("/metrics/overview", params={"temperatura": "caliente"}).json()
    assert body["total_leads"] == 4


def test_filtro_asesor(client, leads_demo):
    """Filtrar por asesor_id → sólo sus leads."""
    asesores = client.get("/asesores").json()
    mateo = next(a for a in asesores if a["nombre"] == "Mateo Ángel")
    body = client.get("/metrics/overview", params={"asesor_id": mateo["id"]}).json()
    # Mateo tiene: 3 calificados + 1 negociando + 1 cerrado_ganado = 5
    assert body["total_leads"] == 5


def test_filtro_zona(client, leads_demo):
    """Filtrar por zona='norte' → todos los 20 leads del demo."""
    body = client.get("/metrics/overview", params={"zona": "norte"}).json()
    assert body["total_leads"] == 20


def test_filtro_zona_inexistente(client, leads_demo):
    """Zona que no existe → 0 leads."""
    body = client.get("/metrics/overview", params={"zona": "sur_ficticio"}).json()
    assert body["total_leads"] == 0
