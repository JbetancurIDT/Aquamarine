# Prompts

Prompts de handoff **Planner → Dev**, organizados **por feature**. Cada feature tiene su carpeta
con los prompts en orden de ejecución.

**Cómo usar:** abre el archivo del handoff, **selecciona todo (⌘A) y copia (⌘C)** — el archivo
entero es el prompt — y pégalo en la sesión del Dev (Claude Code, Opus 4.8 + ultracode).

## Features
- [`e09-geo/`](e09-geo/) — Búsqueda por proximidad geográfica (E09). Ver su `README.md` para el itinerario y el orden.
- [`mapa-inmuebles/`](mapa-inmuebles/) — Pantalla de mapa (OpenStreetMap) con pines de todos los inmuebles + popup con imagen (E10). Feature; sirve además para calibrar la búsqueda por cercanía. Handoffs del mapa + rutas + fixes.
- [`movilidad/`](movilidad/) — Preferencia de movilidad de Aqua: re-ranking suave (D25). Un solo handoff.
- [`fixes-agente/`](fixes-agente/) — Tuning del agente: tarjetas/mapa en el chat, `tipo_negocio`, disparo de movilidad.
- [`e11-intencion/`](e11-intencion/) — Clasificación de intención de compra: comprador vs curioso/"lolo" por zona/propiedad (E11, D26). Ver su `README.md` para el itinerario (3 handoffs).

## Convención
- Un archivo por handoff: `handoff-N-....md`. **Todo el archivo es el prompt** (sin títulos ni adornos) → seleccionar-todo y copiar sin recortar nada.
- El detalle de cada tarea vive en la **épica del cerebro** (`Obsidian/.../Epicas/`); los handoffs la referencian, no la duplican.
- **Flujo:** el Dev ejecuta un handoff y PARA → traes el resultado al Planner → auditoría read-only → el siguiente handoff. Nunca encadenes handoffs sin auditar el anterior.
