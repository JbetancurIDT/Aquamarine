"""Router de métricas — E05 (Dashboard de gerencia).

GET /metrics/overview  Resumen completo del embudo + 8 KPIs con filtros opcionales.

Filtros (query params opcionales): asesor_id · origen · temperatura · zona
Todas las tasas se devuelven como { pct, num, den } para auditoría (convención §5).

Definiciones exactas (documentadas también en dashboard.md):
  valor_lead:       perfil.presupuesto_max ?? null
  % calificados:    #{temperatura != 'desconocido'} / N
  funnel acumulado: funnel[i] = #{rank_efectivo(estado) >= i}
    cerrado_perdido / descartado → rank 2 (calificado) en el funnel
  pesos pipeline:   nuevo 0.10 · contactado 0.25 · calificado 0.50 · negociando 0.75
  lead→cita:        funnel[calificado] / N
  cita→negociación: funnel[negociando] / funnel[calificado]
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.agent.intencion import INTENCIONES, derivar_intencion
from app.api.deps import tenant_actual
from app.core.config import settings
from app.core.db import get_db
from app.core.enums import Origen, Temperatura
from app.models.asesor import Asesor
from app.models.evento import Evento
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.rag.chroma_client import COLLECTION_NAME, get_chroma_client
from app.rag.search import _cumple_ubicacion, _norm
from app.schemas.metrics import (
    AsesorMetrics,
    Conversion,
    FunnelStep,
    IntencionMetrics,
    LeadsCalientes,
    MetricsOverview,
    NegociosGanados,
    PropiedadesMetrics,
    Rate,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Embudo: 5 etapas activas en orden de avance
FUNNEL_ORDEN = ["nuevo", "contactado", "calificado", "negociando", "cerrado_ganado"]
FUNNEL_RANK = {e: i for i, e in enumerate(FUNNEL_ORDEN)}

# Pesos pipeline ponderado (cerrado_* / descartado = 0, no se listan aquí)
PESO_PIPELINE = {
    "nuevo": 0.10,
    "contactado": 0.25,
    "calificado": 0.50,
    "negociando": 0.75,
}


def _bump(bucket: dict[str, int], valor: str | None) -> None:
    """Suma 1 al bucket del valor; None / valor fuera de catálogo → 'otros'.

    Invariante: sum(bucket.values()) == total_leads siempre.
    """
    key = valor if (valor and valor in bucket) else "otros"
    bucket[key] += 1


def _rate(num: int, den: int) -> Rate:
    return Rate(pct=round(num / den, 4) if den > 0 else 0.0, num=num, den=den)


def _rank_efectivo(estado: str) -> int:
    """
    cerrado_perdido / descartado se contabilizan como `calificado` (rank 2) en el funnel.
    Esto evita que leads que pasaron por el proceso pero no cerraron inflen artificialmente
    la conversión hacia abajo. El seed sólo usa las 5 etapas principales.
    """
    return FUNNEL_RANK.get(estado, 2)


def _valor_lead_cop(perfil: dict) -> int | None:
    """
    valor_lead: perfil.presupuesto_max si disponible; None si no hay información.
    """
    max_ = perfil.get("presupuesto_max")
    if max_ is not None:
        return int(max_)
    min_ = perfil.get("presupuesto_min")
    if min_ is not None:
        return int(min_)
    return None


def _aware(dt):
    """Normaliza un datetime a UTC-aware para poder restarlo sin error de tz."""
    from datetime import timezone
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _primera_respuesta_seg(leads: list[Lead]) -> float | None:
    """Promedio (seg) entre `lead.creado_en` y el primer mensaje rol `agente`."""
    tiempos = []
    for lead in leads:
        respuestas = [m.creado_en for m in lead.mensajes if m.rol == "agente"]
        if respuestas:
            delta = (min(respuestas) - lead.creado_en).total_seconds()
            if delta >= 0:
                tiempos.append(delta)
    return round(sum(tiempos) / len(tiempos), 2) if tiempos else None


@router.get("/overview", response_model=MetricsOverview)
def overview(
    asesor_id: UUID | None = None,
    origen: str | None = None,
    temperatura: str | None = None,
    zona: str | None = None,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> MetricsOverview:
    """Resumen de métricas del embudo con filtros opcionales para el dashboard de gerencia."""
    q = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant.id)
        .options(selectinload(Lead.mensajes))
    )
    if asesor_id is not None:
        q = q.filter(Lead.asesor_id == asesor_id)
    if origen is not None:
        q = q.filter(Lead.origen == origen)
    if temperatura is not None:
        q = q.filter(Lead.temperatura == temperatura)
    if zona is not None:
        q = q.filter(Lead.perfil["zona"].astext == zona)

    leads = q.all()
    n = len(leads)

    # ── Buckets de distribución (invariante: sum == n) ───────────────────────
    por_origen = {o.value: 0 for o in Origen} | {"otros": 0}
    por_temperatura = {t.value: 0 for t in Temperatura} | {"otros": 0}
    for lead in leads:
        _bump(por_origen, lead.origen)
        _bump(por_temperatura, lead.temperatura)

    # ── KPIs escalares ───────────────────────────────────────────────────────
    n_calientes = sum(1 for l in leads if l.temperatura == "caliente")
    # % calificados: IA logró clasificar el lead (temperatura != desconocido)
    n_clasif = sum(1 for l in leads if l.temperatura != "desconocido")

    # ── Funnel acumulado ─────────────────────────────────────────────────────
    # funnel[i] = #{rank_efectivo(lead.estado) >= i} para las 5 etapas en orden
    funnel_counts = [
        sum(1 for l in leads if _rank_efectivo(l.estado) >= rank)
        for rank in range(len(FUNNEL_ORDEN))
    ]
    funnel: list[FunnelStep] = []
    for i, (etapa, count) in enumerate(zip(FUNNEL_ORDEN, funnel_counts)):
        pct_paso_previo = None if i == 0 else _rate(count, funnel_counts[i - 1])
        funnel.append(FunnelStep(etapa=etapa, count=count, pct_paso_previo=pct_paso_previo))

    # ── Conversiones ─────────────────────────────────────────────────────────
    # cita = leads que alcanzaron al menos `calificado`
    n_cita = funnel_counts[FUNNEL_RANK["calificado"]]
    n_negoc = funnel_counts[FUNNEL_RANK["negociando"]]

    # ── Pipeline ponderado (sólo leads abiertos) ─────────────────────────────
    pipeline_ponderado = 0
    for lead in leads:
        peso = PESO_PIPELINE.get(lead.estado)
        if peso is not None:
            valor = _valor_lead_cop(lead.perfil or {})
            if valor is not None:
                pipeline_ponderado += int(round(valor * peso))

    # ── Negocios ganados ─────────────────────────────────────────────────────
    ganados = [l for l in leads if l.estado == "cerrado_ganado"]
    valor_cerrado = sum(_valor_lead_cop(l.perfil or {}) or 0 for l in ganados)

    return MetricsOverview(
        total_leads=n,
        leads_calientes=LeadsCalientes(count=n_calientes, rate=_rate(n_calientes, n)),
        pct_calificados=_rate(n_clasif, n),
        primera_respuesta_seg=_primera_respuesta_seg(leads),
        funnel=funnel,
        conversion=Conversion(
            lead_a_cita=_rate(n_cita, n),
            cita_a_negociacion=_rate(n_negoc, n_cita),
        ),
        pipeline_ponderado_cop=pipeline_ponderado,
        negocios_ganados=NegociosGanados(count=len(ganados), valor_cerrado_cop=valor_cerrado),
        por_temperatura=por_temperatura,
        por_origen=por_origen,
    )


@router.get("/asesores", response_model=list[AsesorMetrics])
def metrics_asesores(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> list[AsesorMetrics]:
    """Métricas reales por asesor: leads asignados, en cola, tomados, ganados, conversión."""
    asesores = db.query(Asesor).filter(Asesor.tenant_id == tenant.id).all()
    leads_all = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant.id, Lead.asesor_id.isnot(None))
        .options(selectinload(Lead.mensajes))
        .all()
    )

    # Agrupa leads por asesor
    leads_por_asesor: dict = {}
    for lead in leads_all:
        leads_por_asesor.setdefault(lead.asesor_id, []).append(lead)

    # Momento real del takeover por lead: el evento `tomado_por_humano` (siempre existe
    # cuando atendido_por_humano=True, a diferencia del primer mensaje del asesor, que
    # puede no haber llegado todavía). Tomamos el más temprano por lead.
    lead_ids = [l.id for l in leads_all]
    tomado_en: dict = {}
    if lead_ids:
        eventos_tomado = (
            db.query(Evento.lead_id, Evento.creado_en)
            .filter(Evento.lead_id.in_(lead_ids), Evento.tipo == "tomado_por_humano")
            .all()
        )
        for lid, creado in eventos_tomado:
            if lid not in tomado_en or creado < tomado_en[lid]:
                tomado_en[lid] = creado

    result = []
    for asesor in asesores:
        leads_a = leads_por_asesor.get(asesor.id, [])
        en_cola = sum(1 for l in leads_a if l.estado in ("calificado", "negociando"))
        tomados = sum(1 for l in leads_a if l.atendido_por_humano)
        ganados = [l for l in leads_a if l.estado == "cerrado_ganado"]
        valor_cerrado = sum(_valor_lead_cop(l.perfil or {}) or 0 for l in ganados)

        # Tiempo promedio en tomar: asignación (asignado_en) → takeover (evento tomado_por_humano).
        # `asignado_en` viene del reloj de Python y el evento de `func.now()` (reloj de la BD):
        # en un takeover instantáneo el delta puede salir levemente negativo por skew de relojes.
        # El tiempo en tomar no puede ser negativo → se acota a 0 (no se descarta la medición).
        tiempos_tomar = []
        for lead in leads_a:
            t_tomado = tomado_en.get(lead.id)
            if t_tomado is not None and lead.asignado_en is not None:
                delta = (_aware(t_tomado) - _aware(lead.asignado_en)).total_seconds()
                tiempos_tomar.append(max(0.0, delta))

        result.append(AsesorMetrics(
            id=str(asesor.id),
            nombre=asesor.nombre,
            disponible=asesor.disponible,
            leads_asignados=len(leads_a),
            en_cola=en_cola,
            tomados=tomados,
            ganados=len(ganados),
            valor_cerrado_cop=valor_cerrado,
            primera_respuesta_seg=_primera_respuesta_seg(leads_a),
            tiempo_en_tomar_seg=round(sum(tiempos_tomar) / len(tiempos_tomar), 2) if tiempos_tomar else None,
            ratio_conversion=_rate(len(ganados), len(leads_a)),
        ))

    return result


@router.get("/propiedades", response_model=PropiedadesMetrics)
def metrics_propiedades(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> PropiedadesMetrics:
    """Métricas de inventario de inmuebles — MOCK (Chroma no expone conteos por tenant aún)."""
    return PropiedadesMetrics(
        activas=47,
        en_negociacion=8,
        cerradas=12,
        valor_cerrado_cop=28_500_000_000,
    )


# ── E11: intención de compra (comprador vs curioso), segmentada ──────────────

def _clasificar_intencion(perfil: dict, temperatura: str) -> str:
    """Intención del lead: la que Aqua ya infirió (`perfil.intencion`) o el fallback determinista."""
    perfil = perfil or {}
    return perfil.get("intencion") or derivar_intencion(perfil, temperatura)


def _pct(num: int, den: int) -> float:
    return round(num / den, 4) if den > 0 else 0.0


def _intencion_metrics(leads: list, propiedades: list[dict]) -> dict:
    """Agrega la intención al vuelo: global + por zona (match tolerante) + por propiedad. PURA.

    - `leads`: objetos con `.perfil` (dict) y `.temperatura` (str).
    - `propiedades`: metadatas del inventario (Chroma) — definen las zonas "reales" y los títulos.
    Un lead con zona que no matchea el inventario (p. ej. "cerca del metro") cuenta en el global
    pero **no** en ninguna zona (mismo criterio tolerante del heatmap de E10).
    """
    propiedades = propiedades or []

    # Clasifica cada lead una sola vez.
    clasificados: list[tuple[dict, str]] = []
    conteo_global = {k: 0 for k in INTENCIONES}
    for lead in leads:
        perfil = lead.perfil or {}
        intn = _clasificar_intencion(perfil, lead.temperatura)
        clasificados.append((perfil, intn))
        conteo_global[intn] += 1

    n = len(leads)
    por_intencion = {k: _rate(conteo_global[k], n).model_dump() for k in INTENCIONES}

    # ── por_zona: zonas canónicas del inventario; leads asignados por match tolerante ──
    zonas: dict[str, dict] = {}
    for meta in propiedades:
        clave = _norm(meta.get("zona"))
        if not clave:
            continue
        zonas.setdefault(clave, {"zona": meta.get("zona"), "conteo": {k: 0 for k in INTENCIONES}})

    for perfil, intn in clasificados:
        lead_zona = perfil.get("zona")
        if not lead_zona:
            continue
        # Match tolerante SOLO contra la ZONA del inventario (no contra título/ciudad/dirección):
        # un lead de "El Poblado" no debe caer en "El Tesoro"/"Castropol" solo porque el título de esas
        # propiedades mencione "El Poblado". Así tampoco cuenta un lead de ciudad ("Medellín") en cada
        # barrio. `{"zona": label}` reusa `_cumple_ubicacion` (misma tolerancia acentos/tokens ≥4).
        for bucket in zonas.values():
            if _cumple_ubicacion({"zona": bucket["zona"]}, lead_zona):
                bucket["conteo"][intn] += 1

    por_zona = []
    for bucket in zonas.values():
        c = bucket["conteo"]
        total = c["comprador"] + c["explorando"] + c["curioso"]
        if total == 0:
            continue  # zona del inventario sin leads interesados → no se lista
        por_zona.append({
            "zona": bucket["zona"], "comprador": c["comprador"], "explorando": c["explorando"],
            "curioso": c["curioso"], "total": total,
            "pct_comprador": _pct(c["comprador"], total), "pct_curioso": _pct(c["curioso"], total),
        })
    por_zona.sort(key=lambda z: -z["total"])

    # ── por_propiedad: agrupa por inmueble_interes (título del inventario si existe) ──
    titulo_por_codigo = {
        str(m["inmueble_id"]): m.get("titulo") for m in propiedades if m.get("inmueble_id")
    }
    props: dict[str, dict] = {}
    for perfil, intn in clasificados:
        cod = perfil.get("inmueble_interes")
        if not cod:
            continue
        props.setdefault(str(cod), {k: 0 for k in INTENCIONES})[intn] += 1

    por_propiedad = []
    for cod, c in props.items():
        total = c["comprador"] + c["explorando"] + c["curioso"]
        por_propiedad.append({
            "inmueble_interes": cod, "titulo": titulo_por_codigo.get(cod),
            "comprador": c["comprador"], "explorando": c["explorando"], "curioso": c["curioso"],
            "total": total,
            "pct_comprador": _pct(c["comprador"], total), "pct_curioso": _pct(c["curioso"], total),
        })
    por_propiedad.sort(key=lambda p: -p["total"])

    return {"total_leads": n, "por_intencion": por_intencion,
            "por_zona": por_zona, "por_propiedad": por_propiedad}


def _cargar_inventario() -> list[dict]:
    """Metadatas del inventario del tenant desde Chroma (para las zonas/títulos). `[]` si falla."""
    try:
        col = get_chroma_client().get_or_create_collection(COLLECTION_NAME)
        res = col.get(where={"tenant_id": {"$eq": settings.DEFAULT_TENANT_ID}}, include=["metadatas"])
        return res.get("metadatas") or []
    except Exception:  # noqa: BLE001 — sin inventario el global/propiedad siguen sirviendo
        return []


def calcular_intencion(db: Session, tenant: Tenant) -> dict:
    """Carga los leads del tenant + el inventario y agrega la intención. Reusable (endpoint + insights)."""
    leads = db.query(Lead).filter(Lead.tenant_id == tenant.id).all()
    return _intencion_metrics(leads, _cargar_inventario())


@router.get("/intencion", response_model=IntencionMetrics)
def metrics_intencion(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> IntencionMetrics:
    """% comprador vs curioso (E11), global + por zona + por propiedad, calculado al vuelo."""
    return calcular_intencion(db, tenant)
