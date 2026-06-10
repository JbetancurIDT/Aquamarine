---
tipo: log
audiencia: ambos
estado: en-progreso
actualizado: 2026-06-09
tags: [area/proyecto, log, progreso]
---

# Daily Log

> Bitácora del proyecto. Cada avance, una línea. Sirve para que la comercial sepa en qué va el dev y viceversa. Formato: fecha + qué se hizo + referencia a tarea (ej. T03.2.1).

## 2026-06-09 — Planeación
- Cerrado el alcance del MVP y el stack (ver [[Decisiones (Decision Log)]] D01–D09).
- Creado este vault como cerebro del proyecto.
- Definidas las épicas E00–E07 con tareas granulares.
- **Pendiente de definir:** URLs fuente concretas para el scraping (ver [[Riesgos y Bloqueos]]).

## Día 1 (hackathon) — 2026-06-09
- [E00] **Setup y Fundaciones completado.** Monorepo en `Aquamarine Project/` (backend FastAPI + frontend React+TS con Vite + `docs/`). Backend: `GET /health` → `{"status":"ok"}`, SQLAlchemy + Alembic (`alembic upgrade head` y `--autogenerate` corren contra Postgres), Chroma (`get_chroma_client()` + colección `inmuebles`). Frontend: rutas `/chat` y `/dashboard`; `/chat` consulta `/health` y muestra "backend ok". Verificado en runtime (`npm run build` y servidores levantan). T00.1.1, T00.2.1, T00.2.2, T00.3.1, T00.3.2, T00.4.1, T00.5.1 ✅

<!-- Ejemplo:
- [E00] Monorepo y backend base listos. T00.1.1, T00.2.1 ✅
- [E01] Cliente Firecrawl funcionando. T01.1.1 ✅
-->

## Día 2 (hackathon) — _por registrar_

---
> **Cómo usar:** al cerrar una tarea, agrega una línea aquí y marca el checkbox en su épica. Sube `actualizado` en el frontmatter.
