---
tipo: moc
audiencia: dev
estado: en-progreso
actualizado: 2026-06-09
tags: [moc, area/desarrollo]
---

# 🗺️ MOC - Desarrollo

> Índice del lado técnico. Las **épicas** están en `02_DESARROLLO/Epicas/` y cada una trae sus tareas con prompt para Claude Code.

## Documentos base (leer antes de codear)
- [[Arquitectura]] — cómo encajan las piezas
- [[Stack Tecnológico]] — qué usamos y por qué
- [[Modelo de Datos]] — tablas de Postgres + esquema de inmuebles
- [[Setup del Entorno]] — cómo arrancar el proyecto

## Épicas (en orden sugerido de ataque)

| # | Épica | Qué entrega | Estado |
|---|---|---|---|
| E00 | [[E00 - Setup y Fundaciones]] | Repos, esqueletos, BD, entorno | `pendiente` |
| E01 | [[E01 - Ingesta RAG (Firecrawl + Chroma)]] | Inventario real en base vectorial | `pendiente` |
| E02 | [[E02 - Backend Core (FastAPI + Postgres)]] | Modelos, CRUD, ciclo del lead | `pendiente` |
| E03 | [[E03 - Agente IA (Claude)]] | Conversación, perfilamiento, scoring | `pendiente` |
| E04 | [[E04 - Chatbot Frontend (React)]] | UI de chat para el lead | `pendiente` |
| E05 | [[E05 - CRM Pipeline y Dashboard]] | Panel de leads, métricas, embudo | `pendiente` |
| E06 | [[E06 - Handoff Asesor]] | Notificación + cambio de estado | `pendiente` |
| E07 | [[E07 - Demo, Seed y Pulido]] | Datos demo + guion técnico + fixes | `pendiente` |

## Camino crítico (2 días)
```
DÍA 1:  E00 → E01 (paralelo a E02) → E02 → E03
DÍA 2:  E04 → E05 → E06 → E07
```
> E01 (ingesta RAG) puede correr en paralelo a E02 porque son independientes hasta que E03 las une.

## Cómo trabajar una tarea con Claude Code
1. Abre la épica, ubica la tarea (ej. `T03.2.1`).
2. Copia el **Prompt sugerido** de esa tarea.
3. Pégalo en Claude Code; revisa el resultado contra el **Criterio de aceptación**.
4. Marca `[x]`, anota en [[Daily Log]] y actualiza [[Estado del MVP (Checklist global)]].
