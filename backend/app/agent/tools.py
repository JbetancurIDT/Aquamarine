"""Tool de búsqueda RAG para el agente Aqua (E03 · T03.2.1).

Define el schema de la tool `buscar_inmuebles` para Claude (tool use) y su handler,
que reusa `app.rag.search`. Soporta dos rutas:
- `codigo` presente → lookup exacto por id de Chroma (sin embedding).
- solo `query`      → búsqueda semántica existente.
"""

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


def _formatear_linea(inm: dict, numero: int) -> str:
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
        f"(id {inm.get('inmueble_id')}).{etiqueta}"
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
    inmuebles = buscar_inmuebles(query, filtros, k=3)

    if not inmuebles:
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

    lineas = [_formatear_linea(inm, i) for i, inm in enumerate(inmuebles, 1)]
    return (encabezado + "\n" + "\n".join(lineas), inmuebles)
