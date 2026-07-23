"""Tool de búsqueda RAG para el agente Aqua (E03 · T03.2.1).

Define el schema de la tool `buscar_inmuebles` para Claude (tool use) y su handler,
que reusa `app.rag.search`. Soporta dos rutas:
- `codigo` presente → lookup exacto por id de Chroma (sin embedding).
- solo `query`      → búsqueda semántica existente.
"""

from app.rag.geo_const import CERCANIA_KEYS, ETIQUETA_CAT
from app.rag.search import buscar_inmuebles, obtener_inmueble_por_codigo

# Schema de la tool para Claude. La descripción es PRESCRIPTIVA: dice CUÁNDO usarla.
BUSCAR_INMUEBLES_TOOL = {
    "name": "buscar_inmuebles",
    "description": (
        "Busca inmuebles reales del inventario de Aquamarine por significado + filtros. "
        "Úsala cuando el cliente quiera ver inmuebles o cuando ya entiendas su necesidad "
        "(tipo, zona, presupuesto). La búsqueda es TOLERANTE: relaja sola los criterios y "
        "devuelve alternativas cercanas si no hay match idéntico, marcando cada opción como "
        "exacta o cercana. Devuelve hasta 3 opciones para que las presentes de forma natural. "
        "No la uses para charla general ni para saludar.\n\n"
        "REGLAS para no sobre-filtrar (clave para encontrar lo que SÍ existe):\n"
        "- En `tipo` usa la categoría AMPLIA (casa, apartamento, lote, finca), NO frases "
        "específicas como 'casa campestre' o 'penthouse' (el motor ya entiende familias y el "
        "texto semántico captura el matiz). Ante la duda, omite `tipo` y deja que el `query` lo capture.\n"
        "- SIEMPRE pasa `precio_min`/`precio_max`, `habitaciones` y `banos` cuando el cliente los dé.\n"
        "- `zona`/`ciudad` se usan como pista flexible (substring tolerante), no como filtro exacto."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Qué busca el cliente, en lenguaje natural, INCLUYENDO los matices "
                    "(p.ej. 'casa campestre amplia en Las Palmas con jardín y 4 habitaciones'). "
                    "Requerido siempre; puede ser cadena vacía si solo usas `codigo`."
                ),
            },
            "filtros": {
                "type": "object",
                "description": "Filtros opcionales. Numéricos = duros; tipo/zona/ciudad = pistas tolerantes.",
                "properties": {
                    "ciudad": {"type": "string"},
                    "zona": {"type": "string"},
                    "tipo": {
                        "type": "string",
                        "description": (
                            "Categoría AMPLIA: apartamento | casa | finca | lote | local. "
                            "NO uses subtipos ('casa campestre', 'penthouse'): van en `query`."
                        ),
                    },
                    "tipo_negocio": {"type": "string", "description": "venta | arriendo"},
                    "precio_min": {"type": "integer", "description": "Precio mínimo en COP, sin puntos."},
                    "precio_max": {"type": "integer", "description": "Precio máximo en COP, sin puntos."},
                    "habitaciones": {"type": "integer", "description": "Mínimo de habitaciones."},
                    "banos": {"type": "integer", "description": "Mínimo de baños."},
                    "es_lujo": {"type": "boolean"},
                    "cerca_de": {
                        "type": "string",
                        "enum": list(CERCANIA_KEYS),
                        "description": (
                            "Categoría de lugar cercano que pide el cliente, mapeando su frase a UNA de: "
                            "metro (estación/tranvía/metrocable), supermercado (D1/Ara/Éxito/Carulla/Jumbo/"
                            "mercado/tienda), centro_comercial (mall/C.C./centro comercial), "
                            "colegio (colegio/escuela), universidad (universidad/EAFIT/UPB), "
                            "parque (parque/zona verde), clinica (clínica/hospital/EPS/centro médico). "
                            "El metro SOLO existe en el Valle de Aburrá (Medellín y su área metropolitana)."
                        ),
                    },
                    "radio_km": {
                        "type": "number",
                        "description": (
                            "Radio máximo de cercanía en km (opcional; acompaña a `cerca_de`). Si no lo "
                            "das, se usa un radio prudente por categoría. Solo puede AMPLIAR: hay un piso "
                            "honesto de 1.5 km porque las coordenadas son a nivel de barrio."
                        ),
                    },
                },
            },
            "codigo": {
                "type": "string",
                "description": (
                    "Código/ID exacto del inmueble si el cliente lo menciona "
                    "(p.ej. '9718612'). Si lo das, se hace búsqueda exacta por código, "
                    "no semántica."
                ),
            },
        },
        "required": ["query"],
    },
}


def _frase_cercania(inm: dict, cat: str | None) -> str:
    """Frase de distancia APROXIMADA para la línea, o "" si no aplica (E09·T09.5.1).

    Lee `dist_<cat>_m` (vía `CERCANIA_KEYS`) y lo comunica **redondeado**: "a ~700 m" (<1 km) o
    "a ~1.3 km" (≥1 km) de `ETIQUETA_CAT[cat]`. Nunca cifras exactas — el prompt refuerza la regla
    (prohibido "a 668 m", "caminando" o "a X cuadras").
    """
    if not cat or cat not in CERCANIA_KEYS:
        return ""
    d = inm.get(CERCANIA_KEYS[cat])
    if not isinstance(d, int):
        return ""
    aprox = f"~{max(100, round(d / 100) * 100)} m" if d < 1000 else f"~{d / 1000:.1f} km"
    return f"  [A {aprox} de {ETIQUETA_CAT.get(cat, 'el lugar')} — aprox.]"


def _formatear_linea(inm: dict, numero: int, cat: str | None = None) -> str:
    precio = inm.get("precio")
    precio_txt = f"${precio:,} COP" if isinstance(precio, int) else "precio a consultar"
    # Etiqueta de honestidad: distingue match exacto de alternativa cercana (para que Aqua
    # lo comunique sin inventar un "no hay").
    coincidencia = inm.get("coincidencia")
    if coincidencia == "cercana":
        etiqueta = f"  [ALTERNATIVA CERCANA — {inm.get('motivo', 'opción parecida')}]"
    elif coincidencia == "exacta":
        etiqueta = "  [COINCIDENCIA EXACTA]"
    else:
        etiqueta = ""
    return (
        f"{numero}. {inm.get('titulo', 'Inmueble')} — {inm.get('tipo', '?')} en "
        f"{inm.get('zona', '?')}, {inm.get('ciudad', '?')}. {precio_txt}. "
        f"{inm.get('habitaciones', '?')} hab, {inm.get('banos', '?')} baños "
        f"(id {inm.get('inmueble_id')}).{etiqueta}{_frase_cercania(inm, cat)}"
    )


def ejecutar_buscar_inmuebles(args: dict) -> tuple[str, list[dict]]:
    """Ejecuta la búsqueda RAG. Devuelve (texto_para_claude, inmuebles_crudos).

    Si `args["codigo"]` tiene valor, hace lookup exacto; si no, búsqueda semántica tolerante
    (con relajación). El texto distingue claramente "coincidencia exacta" de "alternativa
    cercana" para que el agente sea honesto y NUNCA afirme un "no hay" infundado.
    Contrato de retorno: (str, list[dict]) — sin romper aunque Chroma no devuelva nada.
    """
    args = args or {}
    codigo = str(args.get("codigo") or "").strip()

    if codigo:
        inm = obtener_inmueble_por_codigo(codigo)
        if inm is None:
            return (
                f"No encontré ningún inmueble con el código {codigo} en el inventario.",
                [],
            )
        return (_formatear_linea(inm, 1), [inm])

    # Camino semántico tolerante (over-fetch + relax-and-retry dentro de buscar_inmuebles).
    query = args.get("query") or ""
    filtros = args.get("filtros") or None
    cat = (filtros or {}).get("cerca_de")  # categoría de cercanía pedida (o None)
    inmuebles = buscar_inmuebles(query, filtros, k=3)

    if not inmuebles:
        if cat:
            # Cercanía es filtro DURO y no se ensancha en silencio: vacío = honestidad, no "no existe".
            etiqueta_cat = ETIQUETA_CAT.get(cat, "ese lugar")
            return (
                f"No hay inmuebles del inventario dentro de la distancia buscada a {etiqueta_cat}. "
                "NO afirmes que 'no existe nada'. Si pidieron cerca del metro, recuerda con calidez "
                "que el metro solo cubre el Valle de Aburrá (Medellín y su área). Ofrece ampliar un "
                "poco la distancia, cambiar de zona, o quitar ese requisito de cercanía y seguir buscando.",
                [],
            )
        # Vacío real solo si NO hay nada dentro de precio/habitaciones ni ampliando ±15%.
        return (
            "Sin resultados dentro de esos parámetros, ni siquiera ampliando el rango. "
            "NO afirmes tajante que 'no existe nada': ofrece seguir buscando y pregunta si "
            "puede flexibilizar zona, tipo o presupuesto.",
            [],
        )

    hay_exacta  = any(i.get("coincidencia") == "exacta" for i in inmuebles)
    hay_cercana = any(i.get("coincidencia") == "cercana" for i in inmuebles)
    if hay_exacta and hay_cercana:
        encabezado = ("Encontré opciones: algunas calzan exacto con lo pedido y otras son "
                      "alternativas cercanas. Preséntalas con honestidad (di cuáles son alternativas):")
    elif hay_exacta:
        encabezado = "Encontré opciones que CALZAN con lo que pidió el cliente:"
    else:
        encabezado = ("No hay un match idéntico, pero estas ALTERNATIVAS CERCANAS encajan bien. "
                      "Ofrécelas proactivamente como alternativas (sin decir que 'no hay nada'):")

    lineas = [_formatear_linea(inm, i, cat) for i, inm in enumerate(inmuebles, 1)]
    return (encabezado + "\n" + "\n".join(lineas), inmuebles)
