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
        "(tipo, zona, presupuesto). Devuelve hasta 3 opciones para que las presentes de "
        "forma natural. No la uses para charla general ni para saludar."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Qué busca el cliente, en lenguaje natural "
                    "(p.ej. 'apartamento de lujo en El Poblado con 3 habitaciones'). "
                    "Requerido siempre; puede ser cadena vacía si solo usas `codigo`."
                ),
            },
            "filtros": {
                "type": "object",
                "description": "Filtros opcionales para acotar la búsqueda semántica.",
                "properties": {
                    "ciudad": {"type": "string"},
                    "zona": {"type": "string"},
                    "tipo": {"type": "string", "description": "apartamento | casa | lote | ..."},
                    "precio_max": {"type": "integer", "description": "Precio máximo en COP, sin puntos."},
                    "habitaciones": {"type": "integer"},
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
    return (
        f"{numero}. {inm.get('titulo', 'Inmueble')} — {inm.get('tipo', '?')} en "
        f"{inm.get('zona', '?')}, {inm.get('ciudad', '?')}. {precio_txt}. "
        f"{inm.get('habitaciones', '?')} hab, {inm.get('banos', '?')} baños "
        f"(id {inm.get('inmueble_id')})."
    )


def ejecutar_buscar_inmuebles(args: dict) -> tuple[str, list[dict]]:
    """Ejecuta la búsqueda RAG. Devuelve (texto_para_claude, inmuebles_crudos).

    Si `args["codigo"]` tiene valor, hace lookup exacto; si no, búsqueda semántica.
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

    # Camino semántico existente.
    query = args.get("query") or ""
    filtros = args.get("filtros") or None
    inmuebles = buscar_inmuebles(query, filtros, k=3)

    if not inmuebles:
        return ("Sin resultados: no hay inmuebles que coincidan con esos criterios.", [])

    lineas = [_formatear_linea(inm, i) for i, inm in enumerate(inmuebles, 1)]
    return ("\n".join(lineas), inmuebles)
