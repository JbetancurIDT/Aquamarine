---
tipo: moc
audiencia: ambos
estado: en-progreso
actualizado: 2026-07-27
tags: [moc, area/desarrollo, prompts, handoffs]
---

# 🗺️ MOC - Prompts (Handoffs Planner → Dev)

> **En términos de negocio:** aquí vive el "guion de obra" — cada tanda de instrucciones exactas que el Planner le pasa al Dev para construir una parte del producto. Guardarlo en el cerebro (y no suelto en el código) deja el *por qué* y el *cómo* de cada feature junto a su épica y su decisión, para no reconstruirlo nunca.

Este es el índice de **todos los handoffs** (prompts Planner→Dev). Antes vivían en `prompts/` en la raíz del repo; ahora son parte del cerebro (`02_DESARROLLO/Prompts/`), enlazados a su épica ([[🗺️ MOC - Desarrollo]]) y su decisión ([[Decisiones (Decision Log)]]).

## Cómo está organizado
Dos ejes, para encontrar cualquier handoff rápido:
- **`Por Épica/`** — handoffs que **entregan una épica completa** (E09, E10, E11). Cada carpeta trae su `README.md` con el itinerario y el orden.
- **`Por Módulo/`** — **tuning transversal** que no es una épica propia, agrupado por el módulo del código que afina (hoy: el **Agente**).

## Índice — Por Épica

| Épica | Carpeta | Decisión | Handoffs | Estado |
|---|---|---|---|---|
| [[E09 - Búsqueda por Proximidad Geográfica (Geo)]] | [E09 · itinerario](<Por Épica/E09 - Búsqueda por Proximidad (Geo)/README.md>) | D21 · D24 | 8 (1–6 CORE, 7–8 stretch) + README | ✅ entregada |
| [[E10 - Mapa de Inmuebles]] | [E10 · carpeta](<Por Épica/E10 - Mapa de Inmuebles/>) | D22 · D23 | mapa + rutas + pines por demanda + 3 fixes | ✅ entregada |
| [[E11 - Clasificación de Intención de Compra (Comprador vs Curioso)]] | [E11 · itinerario](<Por Épica/E11 - Intención de Compra/README.md>) | D26 | 3 (motor · métrica+surface · tests+docs) + fix estado CLAUDE.md | ✅ entregada + auditada |

## Índice — Por Módulo

| Módulo | Carpeta | Decisión | Qué afina |
|---|---|---|---|
| Agente · Movilidad | [Movilidad](<Por Módulo/Agente/Movilidad/>) | D25 | preferencia de movilidad = re-ranking **suave** (no filtra) |
| Agente · Fixes | [Fixes de Agente](<Por Módulo/Agente/Fixes de Agente/>) | — | tarjetas/mapa en el chat, `tipo_negocio`, disparo de movilidad, foco de propiedad |

## Cómo usar un handoff
Abre el archivo, **⌘A ⌘C** (todo el archivo es el prompt, sin recortar nada) y pégalo en la sesión del **Dev** (Claude Code). Cada handoff termina con **"PARA"**: el Dev se detiene, traes su resumen al Planner para una **auditoría read-only**, y recién ahí pasas al siguiente.

## Convención
- **Un archivo = un handoff = un prompt.** Sin títulos ni adornos que estorben el copiar-todo.
- El **detalle por tarea** vive en la **épica** (`../Epicas/`); los handoffs la referencian, no la duplican.
- **El loop, sin saltarlo:** pegar handoff N → el Dev construye y PARA → auditoría del Planner → handoff N+1 (o prompt de corrección). Nunca encadenar handoffs sin auditar el anterior.
- **Zona:** estas carpetas son del **cerebro** (Planner **RW**, Dev **R** — el Dev las lee/copia, no las edita). Ver [[AGENTES]].
