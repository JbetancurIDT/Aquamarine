"""Tool de búsqueda RAG para el agente Aqua (E03 · T03.2.1).

Define el schema de la tool `buscar_inmuebles` para Claude (tool use) y su handler,
que reusa `app.rag.search`. Soporta dos rutas:
- `codigo` presente → lookup exacto por id de Chroma (sin embedding).
- solo `query`      → búsqueda semántica existente.
"""

from app.rag.geo import lugares_cerca
from app.rag.geo_const import CERCANIA_KEYS, ETIQUETA_CAT
from app.rag.search import buscar_inmuebles, buscar_por_lugar, obtener_inmueble_por_codigo

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
                            "Radio máximo de cercanía en km (opcional; acompaña a `cerca_de` o "
                            "`cerca_de_lugar`). Si no lo das, se usa un radio prudente. Con `cerca_de` "
                            "solo puede AMPLIAR (piso honesto de 1.5 km, coords a nivel de barrio)."
                        ),
                    },
                    "cerca_de_lugar": {
                        "type": "string",
                        "description": (
                            "Lugar con NOMBRE PROPIO al que el cliente quiere estar cerca (un mirador, "
                            "una clínica, una universidad, una plaza, un centro comercial). Pasa el "
                            "**nombre OFICIAL de mapa, cualificado con ciudad/departamento y ya "
                            "desambiguado** — NO las palabras crudas del lead. "
                            "Ej: 'la piedra del peñol' → 'Mirador del Peñol, El Peñol, Antioquia'; "
                            "'cerca de La América' (sector Estadio) → 'Plaza de Mercado La América, "
                            "Medellín'. Se geocodifica y se rankea el inventario por distancia. "
                            "EXCLUYENTE con `cerca_de` (que es para CATEGORÍAS genéricas: un metro, un "
                            "supermercado)."
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
            "preferencias": {
                "type": "array",
                "items": {"type": "string",
                          "enum": ["parqueadero", "cerca_metro", "espacio_oficina", "conectado"]},
                "description": (
                    "Preferencia SUAVE según cómo se mueve el lead (su movilidad). **REORDENA** los "
                    "resultados (pone primero los que encajan) — NO filtra ni excluye, el conteo no baja. "
                    "Mapea: carro/moto/vehículo→parqueadero; metro/bus/transporte público→cerca_metro; "
                    "a pie/bici/patineta→conectado; desde casa/teletrabajo→espacio_oficina. Es info extra "
                    "para ofrecer algo que valore más, NO un requisito (para requisito duro de cercanía usa "
                    "`filtros.cerca_de`)."
                ),
            },
        },
        "required": ["query"],
    },
}


# Etiqueta legible de cada preferencia de movilidad, para el "(ideal para ti: …)".
_PREF_LABEL = {"parqueadero": "parqueadero", "cerca_metro": "cerca del metro",
               "espacio_oficina": "espacio para oficina/estudio", "conectado": "muy conectado"}


def _frase_pref(inm: dict) -> str:
    """"(ideal para ti: parqueadero · cerca del metro)" cuando el inmueble cumple preferencias; si no, ""."""
    ok = inm.get("preferencias_ok") or []
    if not ok:
        return ""
    return f"  (ideal para ti: {' · '.join(_PREF_LABEL.get(p, p) for p in ok)})"


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
        f"(id {inm.get('inmueble_id')}).{etiqueta}{_frase_cercania(inm, cat)}{_frase_pref(inm)}"
    )


# Tool para "¿qué hay cerca?" (E09·H8): nombres reales de POIs alrededor de un inmueble ya mostrado.
LUGARES_CERCA_TOOL = {
    "name": "lugares_cerca",
    "description": (
        "Lista los lugares REALES (con nombre y distancia aprox.) alrededor de un inmueble ya "
        "mostrado. Úsala cuando pregunten qué hay cerca/alrededor de una propiedad, o por una "
        "categoría concreta ('¿qué colegios?', '¿supermercados?'). Devuelve solo las categorías con "
        "algo en el radio; omite las vacías. NO inventes: si no está aquí, no existe."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "codigo": {"type": "string",
                       "description": "Código del inmueble ya mostrado (para tomar su ubicación)."},
            "categoria": {"type": "string", "enum": list(CERCANIA_KEYS),
                          "description": "Opcional: una sola categoría (para '¿qué colegios?')."},
        },
        "required": ["codigo"],
    },
}

# Etiqueta legible por categoría para el listado del handler.
_LUGARES_LABEL = {"metro": "Metro", "supermercado": "Supermercados",
                  "centro_comercial": "Centros comerciales", "colegio": "Colegios",
                  "universidad": "Universidades", "parque": "Parques", "clinica": "Clínicas"}


def _aprox_m(m: int) -> str:
    return f"~{max(100, round(m / 100) * 100)} m" if m < 1000 else f"~{m / 1000:.1f} km"


def ejecutar_lugares_cerca(args: dict) -> tuple[str, list[dict]]:
    """Lugares reales cerca de un inmueble. Devuelve (texto, []) — **sin inmuebles** (no genera tarjetas)."""
    args = args or {}
    codigo = str(args.get("codigo") or "").strip()
    categoria = args.get("categoria")
    if not codigo:
        return ("Necesito el código del inmueble para decirte qué hay cerca.", [])
    inm = obtener_inmueble_por_codigo(codigo)
    if not inm or inm.get("latitud") is None or inm.get("longitud") is None:
        return (f"No tengo la ubicación de ese inmueble ({codigo}) para decirte qué hay alrededor.", [])

    cercanos = lugares_cerca(inm["latitud"], inm["longitud"], categoria=categoria)
    if not cercanos:
        return ("No tengo lugares registrados en el radio alrededor de ese inmueble. NO afirmes que "
                "no existe nada: puede que no tengamos ese dato en la zona. Ofrece ayudar con otra cosa.", [])

    lineas = []
    for cat in CERCANIA_KEYS:  # orden congelado; omite las que no vinieron
        items = cercanos.get(cat)
        if not items:
            continue
        listado = ", ".join(f"{i['nombre']} ({_aprox_m(i['dist_m'])})" for i in items)
        lineas.append(f"- {_LUGARES_LABEL.get(cat, cat)}: {listado}")
    return ("Lugares reales cerca de ese inmueble (distancias aproximadas):\n" + "\n".join(lineas), [])


def _handler_por_lugar(lugar: str, filtros: dict) -> tuple[str, list[dict]]:
    """Fallback por nombre propio (E09·T09.8.2): geocodifica el lugar y rankea por cercanía.
    Cada `estado` produce un texto honesto (lugar no ubicado → pedir referencia, NO negar inventario).
    """
    res = buscar_por_lugar(lugar, filtros, k=3, radio_km=filtros.get("radio_km"))
    if res["estado"] == "lugar_no_encontrado":
        return (
            f"No pude ubicar “{lugar}” en el mapa. NO niegues que haya inventario: pídele al cliente "
            f"una referencia alterna (un barrio, un punto conocido o el nombre completo) y sigue "
            f"buscando por él.",
            [],
        )
    inmuebles = res["resultados"]
    if not inmuebles:  # sin_coords, o nada dentro del radio pedido
        return (
            f"Ubiqué “{lugar}”, pero no tengo inmuebles con ubicación para medir cercanía ahí. "
            f"NO afirmes que no hay nada: ofrece buscar por zona/barrio o ampliar la distancia.",
            [],
        )
    encabezado = f"Estos son los inmuebles más cercanos a “{lugar}”, con la distancia aproximada:"
    lineas = [_formatear_linea(inm, i) for i, inm in enumerate(inmuebles, 1)]
    return (encabezado + "\n" + "\n".join(lineas), inmuebles)


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

    # Routing: codigo > cerca_de_lugar > cerca_de > query/filtros.
    filtros = args.get("filtros") or None
    lugar = ((filtros or {}).get("cerca_de_lugar") or "").strip()
    if lugar:
        return _handler_por_lugar(lugar, filtros or {})

    # Camino semántico tolerante (over-fetch + relax-and-retry dentro de buscar_inmuebles).
    query = args.get("query") or ""
    cat = (filtros or {}).get("cerca_de")  # categoría de cercanía pedida (o None)
    inmuebles = buscar_inmuebles(query, filtros, k=3, preferencias=args.get("preferencias"))

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
