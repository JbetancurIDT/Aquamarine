#!/usr/bin/env python
"""Seed de demo — E07: dataset realista con inmuebles reales de Chroma, asesores dinámicos
y conversaciones completas incluyendo takeover humano.

Distribución (25 leads — incluye 3 de demostración de cercanía E09):
  Estado:      5 nuevo · 6 contactado · 6 calificado · 4 negociando · 2 cerrado_ganado · 2 cerrado_perdido
  Temperatura: 7 caliente · 8 tibio · 8 frio · 2 desconocido
  Idioma:      23 español · 2 inglés (extranjeros interesados en Cartagena y Milla de Oro)

Funnel (cerrado_perdido → rank 2, igual que calificado, para no inflar el abandono):
  25 → 20 → 14 → 6 → 2
  paso previo: — / 80.0% / 70.0% / 42.9% / 33.3%
  lead → cita:        56.0%  (14/25)
  cita → negociación: 42.9%   (6/14)

Demo de cercanía (E09): 3 leads que ejercitan "cerca del metro"/D1, "cerca de EAFIT/Clínica Las
Américas", y el intercambio honesto "en Guatapé no hay metro" (ver _CERCANIA_DEMO).

Asesores: consulta dinámicamente los del tenant (Valentina Ruiz, Juana Páez, Mateo Ángel).
          Si no existen, los crea. Los pone disponible=True. Reparte asignados en round-robin.

Inmuebles: intenta `obtener_inmueble_por_codigo` desde Chroma; si falla, usa fallback curado.

Idempotente: borra y recrea leads con perfil.demo=true.

Uso (desde backend/):
    python scripts/seed_demo.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.models.asesor import Asesor
from app.models.evento import Evento
from app.models.lead import Lead
from app.models.mensaje import Mensaje
from app.services.lead_service import get_or_create_default_tenant

# ---------------------------------------------------------------------------
# Inmuebles curados (fallback cuando Chroma no está disponible)
# ---------------------------------------------------------------------------

_INM_FALLBACK = {
    "9718612":  {"titulo": "Apartamento en Poblado Campestre",       "precio": 4_500_000_000},
    "9933939":  {"titulo": "Penthouse en Milla de Oro El Poblado",   "precio": 6_400_000_000},
    "9907677":  {"titulo": "Apartamento en Patio Bonito El Poblado", "precio": 1_180_000_000},
    "9883470":  {"titulo": "Apartamento en El Poblado",              "precio": 1_280_000_000},
    "9996186":  {"titulo": "Apartamento en El Poblado",              "precio": 795_000_000},
    "9523226":  {"titulo": "Apartamento de lujo en El Esmeraldal",   "precio": 1_260_000_000},
    "10009870": {"titulo": "Apartamento en Loma de las Brujas",      "precio": 930_000_000},
    "9338102":  {"titulo": "Casa de lujo en Alto de las Palmas",     "precio": 5_600_000_000},
    "9727715":  {"titulo": "Casa campestre en Las Palmas",           "precio": 7_500_000_000},
    "9637369":  {"titulo": "Finca de lujo en Guatapé",               "precio": 2_200_000_000},
    "10009887": {"titulo": "Lote en Alto de las Palmas",             "precio": 950_000_000},
    "9439342":  {"titulo": "Casa de lujo en Cartagena",              "precio": 2_200_000_000},
}


def _get_inmueble(codigo: str) -> dict:
    """Intenta Chroma primero; usa fallback si no está disponible."""
    if not codigo:
        return {}
    try:
        from app.rag.search import obtener_inmueble_por_codigo
        data = obtener_inmueble_por_codigo(codigo)
        if data:
            return data
    except Exception:
        pass
    return _INM_FALLBACK.get(str(codigo), {})


def _precio_str(precio: int | None) -> str:
    if not precio:
        return "precio a consultar"
    return f"${precio / 1_000_000:,.0f} M COP"


def _msg_recomendacion(inm: dict, codigo: str, idioma: str = "es") -> tuple[str, list[str]]:
    """Devuelve (contenido_mensaje, [codigo]) para el mensaje de recomendación del agente."""
    titulo = inm.get("titulo") or inm.get("titulo_inmueble") or f"Inmueble #{codigo}"
    precio = inm.get("precio")
    ps = _precio_str(precio)
    if idioma == "en":
        texto = (
            f"Great news! I found a perfect match for you: **{titulo}** — {ps}. "
            "It's one of our most exclusive listings in the area. "
            "Would you like me to arrange a private showing at your convenience?"
        )
    else:
        texto = (
            f"¡Excelente! Tengo justo lo que buscas: **{titulo}** — {ps}. "
            "Es una de nuestras propiedades más exclusivas de la zona. "
            "¿Te gustaría agendar una visita privada esta semana?"
        )
    return texto, [str(codigo)]


# ---------------------------------------------------------------------------
# Especificación de los 22 leads
# (temp, estado, origen, budget, inmueble_id_o_None, idioma, nombre, zona, ciudad, tipo)
# ---------------------------------------------------------------------------

LEADS_SPEC = [
    # ── Nuevos (3) — sin asesor, IA atendiendo ──────────────────────────────
    ("caliente", "nuevo",          "meta",          795_000_000,   "9996186",  "es",
     "Alejandro Torres",  "El Poblado",          "Medellín",  "apartamento"),
    ("tibio",    "nuevo",          "meta",          930_000_000,   "10009870", "es",
     "Camila Reyes",      "Loma de las Brujas",  "Envigado",  "apartamento"),
    ("frio",     "nuevo",          "web",           500_000_000,   None,       "es",
     "Sebastián Herrera", "Robledo",             "Medellín",  "apartamento"),
    # ── Contactados (5) — sin asesor ────────────────────────────────────────
    ("caliente", "contactado",     "meta",          1_280_000_000, "9883470",  "es",
     "Valentina Ospina",  "El Poblado",          "Medellín",  "apartamento"),
    ("tibio",    "contactado",     "meta",          1_180_000_000, "9907677",  "es",
     "Daniel Ríos",       "Patio Bonito",        "Medellín",  "apartamento"),
    ("tibio",    "contactado",     "fincaraiz",     1_260_000_000, "9523226",  "es",
     "Isabella Gómez",    "El Esmeraldal",       "Envigado",  "apartamento lujo"),
    ("frio",     "contactado",     "web",           800_000_000,   None,       "es",
     "Mateo Vargas",      "Laureles",            "Medellín",  "apartamento"),
    ("desconocido", "contactado",  "metrocuadrado", 2_200_000_000, "9439342",  "en",
     "James Whitfield",   "Bocagrande",          "Cartagena", "casa lujo"),
    # ── Calificados (6) — asignados, no tomados ─────────────────────────────
    ("caliente", "calificado",     "meta",          1_280_000_000, "9883470",  "es",
     "Lucía Morales",     "El Poblado",          "Medellín",  "apartamento"),
    ("tibio",    "calificado",     "meta",          1_180_000_000, "9907677",  "es",
     "Santiago Pardo",    "Patio Bonito",        "Medellín",  "apartamento"),
    ("tibio",    "calificado",     "metrocuadrado", 950_000_000,   "10009887", "es",
     "Sofía Mejía",       "Alto de las Palmas",  "Envigado",  "lote"),
    ("frio",     "calificado",     "fincaraiz",     1_000_000_000, None,       "es",
     "Tomás Castillo",    "Sabaneta",            "Medellín",  "apartamento"),
    ("frio",     "calificado",     "web",           1_000_000_000, None,       "es",
     "María López",       "Belén",               "Medellín",  "casa"),
    ("desconocido", "calificado",  "metrocuadrado", 6_400_000_000, "9933939",  "en",
     "Amanda Chen",       "Milla de Oro",        "Medellín",  "penthouse"),
    # ── Negociando (4) — asignados, atendido_por_humano=True ────────────────
    ("caliente", "negociando",     "fincaraiz",     5_600_000_000, "9338102",  "es",
     "Andrés Pineda",     "Alto de las Palmas",  "Envigado",  "casa lujo"),
    ("caliente", "negociando",     "meta",          4_500_000_000, "9718612",  "es",
     "Ana Rueda",         "Poblado Campestre",   "Medellín",  "apartamento lujo"),
    ("tibio",    "negociando",     "metrocuadrado", 7_500_000_000, "9727715",  "es",
     "Felipe Niño",       "Las Palmas",          "Medellín",  "casa campestre"),
    ("frio",     "negociando",     "web",           2_200_000_000, "9637369",  "es",
     "Natalia Cruz",      "Guatapé",             "Antioquia", "finca lujo"),
    # ── Cerrado ganado (2) ──────────────────────────────────────────────────
    ("caliente", "cerrado_ganado", "web",           4_500_000_000, "9718612",  "es",
     "Miguel Suárez",     "Poblado Campestre",   "Medellín",  "apartamento lujo"),
    ("tibio",    "cerrado_ganado", "meta",          1_260_000_000, "9523226",  "es",
     "Juliana Leal",      "El Esmeraldal",       "Envigado",  "apartamento lujo"),
    # ── Cerrado perdido (2) — rank 2 en funnel ──────────────────────────────
    ("frio",     "cerrado_perdido","fincaraiz",     1_000_000_000, None,       "es",
     "David Soto",        "Sabaneta",            "Medellín",  "apartamento"),
    ("frio",     "cerrado_perdido","web",           1_000_000_000, None,       "es",
     "Gabriela Díaz",     "Itagüí",              "Medellín",  "casa"),
    # ── Demostración de cercanía (E09) — mensajes custom vía _CERCANIA_DEMO ──
    ("caliente", "contactado",     "web",           1_180_000_000, "9907677",  "es",
     "Cristina Vélez",    "Patio Bonito",        "Medellín",  "apartamento"),
    ("tibio",    "nuevo",          "meta",          4_500_000_000, "9718612",  "es",
     "Ricardo Salazar",   "El Poblado",          "Medellín",  "apartamento lujo"),
    ("frio",     "nuevo",          "web",           2_200_000_000, None,       "es",
     "Paola Restrepo",    "Guatapé",             "Antioquia", "finca"),
]

# Mensajes custom para los 3 leads de demostración de cercanía (E09): el lead pide proximidad en
# lenguaje natural y Aqua responde con distancia APROXIMADA y honestidad geográfica.
_CERCANIA_DEMO = {
    "Cristina Vélez": {
        "lead": ("Hola, busco apartamento en Medellín que quede **cerca de una estación del metro** "
                 "y ojalá con un **D1 cerquita**. Hasta $1.180 millones."),
        "ia": ("¡Claro que sí! Tengo justo algo así: **Apartamento en Patio Bonito, El Poblado** — a "
               "**unos ~600 m de una estación de metro** y con supermercados (incluido un D1) muy "
               "cerca. ¿Te gustaría agendar una visita? 😊"),
        "inmuebles": ["9907677"],
    },
    "Ricardo Salazar": {
        "lead": ("Buenas, me interesa algo en El Poblado pero que esté **cerca de EAFIT** o de la "
                 "**Clínica Las Américas**. El presupuesto es amplio."),
        "ia": ("¡Perfecto! Mira este **Apartamento de lujo en El Poblado** — queda a **~1.5 km de "
               "EAFIT (aprox.)** y con la zona médica bien cerca. Es de nuestras propiedades más "
               "exclusivas. ¿Te muestro más detalles?"),
        "inmuebles": ["9718612"],
    },
    "Paola Restrepo": {
        "lead": ("Quiero una finca en **Guatapé** pero que quede **cerca del metro**, ¿tienen algo así?"),
        "ia": ("¡Qué lindo Guatapé! Te soy honesta: **el metro no llega a Guatapé** — el sistema solo "
               "cubre el **Valle de Aburrá** (Medellín y su área). En Guatapé puedo ayudarte con "
               "opciones cerca del lago o el parque; y si te sirve el área metropolitana, ahí sí hay "
               "inmuebles junto al metro. ¿Qué prefieres?"),
        "inmuebles": [],
    },
}

# Mensajes iniciales por idioma
_SALUDO_LEAD = {
    "es": "Hola, buenas tardes. Estoy buscando inmueble en {ciudad}, zona {zona}. Presupuesto hasta {budget}.",
    "en": "Hello, good afternoon. I'm looking for a property in {ciudad}, {zona} area. Budget up to {budget}.",
}
_SALUDO_IA = {
    "es": ("¡Bienvenido a Aquamarine Group! Soy Aqua, tu asistente de finca raíz de lujo. "
           "Cuéntame más sobre lo que buscas: ¿tipo de inmueble, número de habitaciones y plazo?"),
    "en": ("Welcome to Aquamarine Group! I'm Aqua, your luxury real estate assistant. "
           "Tell me more about what you're looking for: property type, bedrooms, and timeline?"),
}

# Conversaciones para negociando (lead followup, asesor msgs, lead response)
_CONV_NEGOCIANDO = [
    {
        "lead_followup":   "Sí, me interesa mucho. ¿Tiene piscina y zonas sociales completas?",
        "asesor_saludo":   "¡Hola! Soy {asesor}. Sí, la propiedad cuenta con piscina, zona de BBQ y gimnasio. ¿Cuándo puedes visitarla?",
        "lead_resp":       "Perfecto. El jueves en la tarde estaría disponible.",
    },
    {
        "lead_followup":   "¿El edificio tiene parqueadero cubierto y vigilancia 24/7?",
        "asesor_saludo":   "Hola, soy {asesor}. El inmueble tiene dos parqueaderos cubiertos y seguridad las 24 horas. ¿Agendamos una visita esta semana?",
        "lead_resp":       "Excelente, me interesa el miércoles a las 3 p.m.",
    },
    {
        "lead_followup":   "¿Es posible ver la propiedad este fin de semana? Vengo de fuera.",
        "asesor_saludo":   "¡Bienvenido! Soy {asesor}. Sin problema, coordinamos el sábado a las 10 a.m. Te envío la dirección exacta.",
        "lead_resp":       "Perfecto, allí estaré. Muchas gracias.",
    },
    {
        "lead_followup":   "¿Hay posibilidad de financiación o pago en cuotas?",
        "asesor_saludo":   "Hola, soy {asesor}. Trabajamos con varias entidades financieras. Podemos estructurar un esquema de pago ajustado a tu flujo. ¿Hablamos hoy?",
        "lead_resp":       "Sí, llámame esta tarde.",
    },
]

# Conversaciones para cerrado_ganado
_CONV_GANADO = [
    {
        "lead_followup":   "Me convenció la propiedad. ¿Cómo es el proceso para hacer la oferta?",
        "asesor_cierre":   "Soy {asesor}. ¡Excelente decisión! Te envío la promesa de compraventa para revisión. La firma se hace ante notaría la próxima semana.",
        "lead_cierre":     "Revisé el documento. Todo en orden. Procedo con la firma.",
        "asesor_final":    "¡Felicitaciones! La negociación está cerrada. Bienvenido a tu nuevo hogar en Aquamarine.",
    },
    {
        "lead_followup":   "Me gustó mucho el inmueble. ¿Pueden bajar un poco el precio?",
        "asesor_cierre":   "Hola, soy {asesor}. Negociamos y el propietario acepta una rebaja del 3%. ¿Cerramos trato?",
        "lead_cierre":     "¡Trato hecho! Envíame los documentos.",
        "asesor_final":    "Perfecto. Cerramos la negociación. ¡Muchas gracias por tu confianza en Aquamarine!",
    },
]

# Conversaciones para cerrado_perdido
_CONV_PERDIDO = [
    {
        "lead_followup":   "Tengo dudas sobre la ubicación. ¿Está lejos del metro?",
        "asesor_resp":     "Hola, soy {asesor}. Está a 15 minutos en carro del metro más cercano.",
        "lead_salida":     "Entiendo. Lo pensé mejor y por ahora voy a esperar. Gracias.",
    },
    {
        "lead_followup":   "El precio está un poco por encima de mi presupuesto real. ¿Hay opciones más económicas?",
        "asesor_resp":     "Hola, soy {asesor}. Podemos mostrarle opciones en rangos más asequibles.",
        "lead_salida":     "Gracias, pero decidí posponer la compra. Cuando esté listo los contacto.",
    },
]


def _calcular_esperados() -> None:
    """Imprime los valores esperados de cada métrica para validar el dashboard.

    Nota sobre cerrado_perdido en el funnel:
      Rango efectivo de cerrado_perdido = 2 (calificado). Esto evita que leads que
      pasaron por el proceso pero no cerraron inflen el abandono hacia abajo.
      Por eso los 2 leads cerrado_perdido contribuyen al funnel hasta rank 2, no rank 3+.
    """
    n = len(LEADS_SPEC)
    n_clasif   = sum(1 for s in LEADS_SPEC if s[0] != "desconocido")
    n_caliente = sum(1 for s in LEADS_SPEC if s[0] == "caliente")

    RANK = {"nuevo": 0, "contactado": 1, "calificado": 2, "negociando": 3, "cerrado_ganado": 4}

    def rank_ef(estado: str) -> int:
        return RANK.get(estado, 2)  # cerrado_perdido/descartado → 2

    funnel = [sum(1 for s in LEADS_SPEC if rank_ef(s[1]) >= r) for r in range(5)]
    etapas = ["nuevo", "contactado", "calificado", "negociando", "cerrado_ganado"]

    PESO = {"nuevo": 0.10, "contactado": 0.25, "calificado": 0.50, "negociando": 0.75}
    pipeline = sum(s[3] * PESO[s[1]] for s in LEADS_SPEC if s[1] in PESO)
    ganados   = [s for s in LEADS_SPEC if s[1] == "cerrado_ganado"]
    v_cerrado = sum(s[3] for s in ganados)

    print("\n" + "=" * 62)
    print("  VALORES ESPERADOS DEL DASHBOARD (para validar 1:1)")
    print("=" * 62)
    print(f"  Total leads             : {n}")
    print(f"  % calificados           : {n_clasif / n * 100:.1f}%  ({n_clasif}/{n})")
    print(f"  Leads calientes         : {n_caliente / n * 100:.1f}%  ({n_caliente}/{n})")
    print()
    print("  Funnel acumulado (cerrado_perdido cuenta como rank=2):")
    for i, (et, cnt) in enumerate(zip(etapas, funnel)):
        if i == 0:
            pct = "  —"
        else:
            pct = f"{cnt / funnel[i - 1] * 100:.1f}% del paso previo"
        print(f"    {et:<20}: {cnt:>3}   {pct}")
    print()
    print(f"  Lead → cita             : {funnel[2] / n * 100:.1f}%  ({funnel[2]}/{n})")
    print(f"  Cita → negociación      : {funnel[3] / funnel[2] * 100:.1f}%  ({funnel[3]}/{funnel[2]})")
    print()
    print(f"  Pipeline ponderado      : ${pipeline / 1e6:,.1f} M COP  ({pipeline:,.0f} COP)")
    print(f"  Negocios ganados        : {len(ganados)}  · Valor cerrado ${v_cerrado / 1e6:,.0f} M COP")
    print(f"  1ª respuesta (seed)     : 30.0 s")
    print("=" * 62 + "\n")


def seed() -> None:
    db = SessionLocal()
    try:
        tenant = get_or_create_default_tenant(db)
        print(f"[tenant]  {tenant.nombre} (id={tenant.id})")

        # ── Asesores (busca los existentes; crea si no hay ninguno) ──────────
        asesores = (
            db.query(Asesor)
            .filter(Asesor.tenant_id == tenant.id)
            .order_by(Asesor.nombre)
            .all()
        )
        if not asesores:
            for nombre in ["Juana Páez", "Mateo Ángel", "Valentina Ruiz"]:
                a = Asesor(tenant_id=tenant.id, nombre=nombre, disponible=True)
                db.add(a)
            db.flush()
            asesores = (
                db.query(Asesor)
                .filter(Asesor.tenant_id == tenant.id)
                .order_by(Asesor.nombre)
                .all()
            )
            print(f"[asesores creados]  {[a.nombre for a in asesores]}")
        else:
            # Poner todos disponibles
            for a in asesores:
                a.disponible = True
            db.flush()
            print(f"[asesores existentes]  {[a.nombre for a in asesores]}")

        # ── Borrar leads de demo anteriores ───────────────────────────────────
        demos_previos = (
            db.query(Lead)
            .filter(
                Lead.tenant_id == tenant.id,
                Lead.perfil["demo"].astext == "true",
            )
            .all()
        )
        if demos_previos:
            for lead in demos_previos:
                db.delete(lead)
            db.flush()
            print(f"[limpieza]  {len(demos_previos)} leads demo anteriores eliminados")

        # ── Crear 22 leads ─────────────────────────────────────────────────────
        now = datetime.now(tz=timezone.utc)
        n_total = len(LEADS_SPEC)
        asesor_rr = 0  # round-robin index para leads asignados

        # Índice para las conversaciones variadas
        idx_negociando = 0
        idx_ganado = 0
        idx_perdido = 0

        for i, spec in enumerate(LEADS_SPEC):
            temp, estado, origen, budget, inm_id, idioma, nombre, zona, ciudad, tipo = spec
            ts = now - timedelta(hours=n_total - i)

            # Obtener datos del inmueble (puede ser None si no aplica)
            inm = _get_inmueble(inm_id) if inm_id else {}

            # Determinar si lleva asesor
            estados_asignados = {"calificado", "negociando", "cerrado_ganado", "cerrado_perdido"}
            asesor = asesores[asesor_rr % len(asesores)] if estado in estados_asignados else None
            if estado in estados_asignados:
                asesor_rr += 1

            # Crear el lead en su estado objetivo
            lead = Lead(
                tenant_id=tenant.id,
                nombre=nombre,
                origen=origen,
                idioma=idioma,
                temperatura=temp,
                estado=estado,
                score=70 + i % 30,
                perfil={
                    "presupuesto_max": budget,
                    "presupuesto_min": int(budget * 0.8),
                    "tipo": tipo,
                    "zona": zona,
                    "ciudad": ciudad,
                    "habitaciones": 2 + (i % 3),
                    "demo": True,
                },
                asesor_id=asesor.id if asesor else None,
                asignado_en=ts + timedelta(minutes=5) if asesor else None,
                creado_en=ts,
            )
            if estado in ("negociando", "cerrado_ganado", "cerrado_perdido") and asesor:
                lead.atendido_por_humano = True
            db.add(lead)
            db.flush()

            # ── Evento lead_creado ─────────────────────────────────────────
            db.add(Evento(lead_id=lead.id, tipo="lead_creado",
                          payload={"origen": origen}, creado_en=ts))

            # ── Mensaje inicial del lead + respuesta IA (30 s) ────────────
            demo_geo = _CERCANIA_DEMO.get(nombre)
            saludo_lead = demo_geo["lead"] if demo_geo else _SALUDO_LEAD[idioma].format(
                ciudad=ciudad, zona=zona, budget=_precio_str(budget)
            )
            db.add(Mensaje(lead_id=lead.id, rol="lead", contenido=saludo_lead, creado_en=ts))

            if demo_geo:
                db.add(Mensaje(lead_id=lead.id, rol="agente", contenido=demo_geo["ia"],
                               creado_en=ts + timedelta(seconds=30),
                               meta={"inmuebles": demo_geo.get("inmuebles", [])}))
            elif inm_id and inm:
                rec_texto, rec_ids = _msg_recomendacion(inm, inm_id, idioma)
                db.add(Mensaje(lead_id=lead.id, rol="agente", contenido=rec_texto,
                               creado_en=ts + timedelta(seconds=30),
                               meta={"inmuebles": rec_ids}))
            else:
                if idioma == "en":
                    ia_resp = ("Welcome to Aquamarine Group! I'm Aqua, your luxury real estate assistant. "
                               "Tell me more about your ideal property: type, bedrooms, and budget?")
                else:
                    ia_resp = ("¡Bienvenido a Aquamarine Group! Soy Aqua, tu asistente de finca raíz de lujo. "
                               "Cuéntame más: ¿tipo de inmueble, número de habitaciones y plazo?")
                db.add(Mensaje(lead_id=lead.id, rol="agente", contenido=ia_resp,
                               creado_en=ts + timedelta(seconds=30)))

            # ── Evento de asignación para leads asignados ─────────────────
            if asesor and estado != "negociando":  # negociando usa tomado_por_humano
                db.add(Evento(lead_id=lead.id, tipo="asignado",
                              payload={"asesor_id": str(asesor.id), "auto": True},
                              creado_en=ts + timedelta(minutes=5)))

            # ── Conversaciones extendidas según estado ────────────────────
            if estado in ("negociando", "cerrado_ganado", "cerrado_perdido") and asesor:
                if estado == "negociando":
                    conv = _CONV_NEGOCIANDO[idx_negociando % len(_CONV_NEGOCIANDO)]
                    idx_negociando += 1
                elif estado == "cerrado_ganado":
                    conv = _CONV_GANADO[idx_ganado % len(_CONV_GANADO)]
                    idx_ganado += 1
                else:
                    conv = _CONV_PERDIDO[idx_perdido % len(_CONV_PERDIDO)]
                    idx_perdido += 1

                # Seguimiento del lead (antes del takeover)
                db.add(Mensaje(lead_id=lead.id, rol="lead",
                               contenido=conv.get("lead_followup", "¿Cuándo puedo visitar?"),
                               creado_en=ts + timedelta(minutes=2)))

                # Despedida de la IA (handoff)
                despedida_ia = (
                    f"Con gusto te dejo con {asesor.nombre}, uno de nuestros asesores expertos, "
                    "que seguirá ayudándote personalmente. ¡Fue un placer acompañarte hasta aquí! 🙌"
                )
                db.add(Mensaje(lead_id=lead.id, rol="agente", contenido=despedida_ia,
                               creado_en=ts + timedelta(minutes=3)))

                # Evento tomado_por_humano
                db.add(Evento(lead_id=lead.id, tipo="tomado_por_humano",
                              payload={"asesor_id": str(asesor.id), "nombre_asesor": asesor.nombre},
                              creado_en=ts + timedelta(minutes=3, seconds=10)))

                # Evento asignado (handoff inicial)
                db.add(Evento(lead_id=lead.id, tipo="asignado",
                              payload={"asesor_id": str(asesor.id), "auto": True},
                              creado_en=ts + timedelta(minutes=5)))

                # Mensajes del asesor y respuestas del lead
                asesor_saludo_key = "asesor_saludo" if estado == "negociando" else "asesor_cierre" if estado == "cerrado_ganado" else "asesor_resp"
                asesor_msg = conv.get(asesor_saludo_key, "Hola, soy {asesor}. ¿En qué te puedo ayudar?")
                db.add(Mensaje(lead_id=lead.id, rol="asesor",
                               contenido=asesor_msg.format(asesor=asesor.nombre),
                               creado_en=ts + timedelta(minutes=6)))

                lead_resp_key = "lead_resp" if estado == "negociando" else "lead_cierre" if estado == "cerrado_ganado" else "lead_salida"
                db.add(Mensaje(lead_id=lead.id, rol="lead",
                               contenido=conv.get(lead_resp_key, "Gracias, lo tendré en cuenta."),
                               creado_en=ts + timedelta(minutes=7)))

                if estado == "cerrado_ganado":
                    db.add(Mensaje(lead_id=lead.id, rol="asesor",
                                   contenido=conv.get("asesor_final", "¡Cerramos trato!").format(asesor=asesor.nombre),
                                   creado_en=ts + timedelta(minutes=8)))

            elif estado in ("calificado",) and asesor:
                # Leads calificados tienen un segundo mensaje del lead (interés confirmado)
                if idioma == "en":
                    db.add(Mensaje(lead_id=lead.id, rol="lead",
                                   contenido="Sounds interesting. Could you send me more details?",
                                   creado_en=ts + timedelta(minutes=5)))
                else:
                    db.add(Mensaje(lead_id=lead.id, rol="lead",
                                   contenido="Muy interesante. ¿Puedes enviarme más información?",
                                   creado_en=ts + timedelta(minutes=5)))

        db.commit()
        print(f"[ok]  {n_total} leads de demo creados.")
        _calcular_esperados()

    finally:
        db.close()


if __name__ == "__main__":
    seed()
