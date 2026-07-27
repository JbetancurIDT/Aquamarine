# E09 — Búsqueda por Proximidad Geográfica · Prompts de handoff

- **Épica (detalle):** `Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E09 - Búsqueda por Proximidad Geográfica (Geo).md`
- **Rama:** `feat/e09-geo`
- **Decisiones:** haversine radial en km (tiempo de viaje = Fase 2) · 100% OSM/Overpass + GTFS del Metro · ambos scopes (categorías + nombre propio) · radio honesto mínimo 1.5 km · cercanía = filtro duro.

**Cómo usar:** abre el handoff, **⌘A ⌘C** (todo el archivo es el prompt), pégalo en la sesión del Dev. Cada handoff termina con **"PARA"**: el Dev se detiene, tú traes su resumen al Planner para una **auditoría read-only**, y recién ahí pasas al siguiente.

## Itinerario

| # | Archivo | Sprints | Qué construye | Checkpoint observable | Fase |
|---|---|---|---|---|---|
| 1 | `handoff-1-sprints-1-3.md` | 1-3 | contrato (`geo_const`) + datos semilla + enriquecimiento/backfill | los 50 inmuebles con `dist_*_m` en Chroma | 🟢 CORE |
| 2 | `handoff-2-sprints-4-5.md` | 4-5 | filtro de cercanía en `search.py` + tool + system prompt | chat "cerca del metro" filtra y muestra distancia | 🟢 CORE |
| 3 | `handoff-3-sprint-6.md` | 6 | tests offline + `geo.md` | `pytest` verde + doc | 🟢 CORE |
| 4 | `handoff-4-sprint-7-stretch.md` | 7 | datos en vivo (Overpass/GTFS/Nominatim) | POIs reales, `dist_*` recomputado | 🟡 STRETCH |
| 5 | `handoff-5-sprint-8-stretch.md` | 8 | fallback por nombre propio | "cerca de EAFIT" rankea por distancia | 🟡 STRETCH |
| 6 | `handoff-6-sprint-9-stretch.md` | 9 | hook de ingesta | ficha nueva nace con geo | 🟡 STRETCH |

**CORE (1-3) ≈ 0.5 día = v1 presentable.** STRETCH (4-6) = datos reales + búsqueda por nombre propio + ingesta automática.

## El loop (no te lo saltes)
1. Pega el **handoff N** en el Dev.
2. El Dev construye y **PARA** con un resumen + su verificación observable.
3. Traes ese resumen al **Planner** (la sesión de planeación) → **auditoría read-only**.
4. Si pasa → **handoff N+1**; si no → el Planner te da un prompt de corrección.
