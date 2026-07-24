---
tipo: moc
audiencia: dev
estado: en-progreso
actualizado: 2026-07-24
tags: [moc, area/desarrollo]
---

# 🗺️ MOC - Desarrollo

> Índice del lado técnico. Las **épicas** están en `02_DESARROLLO/Epicas/` y cada una trae sus tareas con prompt para Claude Code.

## Documentos base (leer antes de codear)
- [[Arquitectura]] — cómo encajan las piezas
- [[Stack Tecnológico]] — qué usamos y por qué
- [[Modelo de Datos]] — tablas de Postgres + esquema de inmuebles
- [[Setup del Entorno]] — cómo arrancar el proyecto
- [[Diseño UI (referencia)]] — paleta (obligatoria) + catálogo de pantallas del frontend

## Épicas (en orden sugerido de ataque)

| # | Épica | Qué entrega | Estado |
|---|---|---|---|
| E00 | [[E00 - Setup y Fundaciones]] | Repos, esqueletos, BD, entorno | ✅ `completado` |
| E01 | [[E01 - Ingesta RAG (Firecrawl + Chroma)]] | Inventario real en base vectorial | ✅ `completado` |
| E02 | [[E02 - Backend Core (FastAPI + Postgres)]] | Modelos, CRUD, ciclo del lead | ✅ `completado` |
| E03 | [[E03 - Agente IA (Claude)]] | Conversación, perfilamiento, scoring | ✅ `completado` |
| E04 | [[E04 - Chatbot Frontend (React)]] | UI de chat para el lead | ✅ `completado` (falta solo validar paleta + tests de front) |
| E05 | [[E05 - CRM Pipeline y Dashboard]] | Panel de leads, métricas, embudo | ✅ `completado` (dashboard KPIs+funnel+donut, pipeline Kanban, /performance, modal centrado, scrollbar de marca) |
| E06 | [[E06 - Handoff Asesor]] | Notificación + cambio de estado | ✅ `completado` (auto-asignación balanceada, takeover humano, chat en vivo, notificaciones escalonadas + reasignación) |
| E07 | [[E07 - Demo, Seed y Pulido]] | Datos demo + guion técnico + fixes | ✅ `completado` (seed realista con inmuebles reales de Chroma, 3 asesores, e2e críticos, guion de demo) |
| E08 | [[E08 - Agente de Métricas (Gerencia)]] | Agente para Claudia: métricas en lenguaje natural | ✅ `completado` (/performance + burbuja "Asistente" en /dashboard con Haiku + tool-use real) |
| E09 | [[E09 - Búsqueda por Proximidad Geográfica (Geo)]] | Cercanía: "cerca del metro / de un D1 / de la Clínica X" | ✅ `completado` (post-MVP · cercanía DURA + nombre propio + lugares tolerantes + movilidad) |
| E10 | [[E10 - Mapa de Inmuebles]] | Mapa del inventario + heatmap de demanda + mapa por propiedad con rutas | ✅ `completado` (post-MVP · Leaflet/OSM, rutas ORS→OSRM→recta) |

> **E09 y E10** son las épicas **post-MVP** (no estaban en el camino crítico de los 2 días): E09 (búsqueda por proximidad, planeada 2026-07-22) y E10 (mapa de inmuebles). Ambas **entregadas y mergeadas a `master`** el 2026-07-23/24.

## Camino crítico (2 días)
```
DÍA 1:  E00 → E01 (paralelo a E02) → E02 → E03
DÍA 2:  E04 → E05 → E06 → E07
```
> E01 (ingesta RAG) puede correr en paralelo a E02 porque son independientes hasta que E03 las une.
> **E08** (agente de métricas para Claudia) es **valor agregado**: se construye cuando E02 y E05 estén listos; no bloquea la demo.

## Cómo trabajar una tarea con Claude Code
1. Abre la épica, ubica la tarea (ej. `T03.2.1`).
2. Copia el **Prompt sugerido** de esa tarea.
3. Pégalo en Claude Code; revisa el resultado contra el **Criterio de aceptación**.
4. Marca `[x]`, anota en [[Daily Log]] y actualiza [[Estado del MVP (Checklist global)]].
