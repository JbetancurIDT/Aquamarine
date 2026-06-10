---
tipo: log
audiencia: ambos
estado: en-progreso
actualizado: 2026-06-10
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
- [E00] **Setup y Fundaciones completado.** Monorepo `Aquamarine Project/` (backend FastAPI + frontend React+TS con Vite + `docs/`). Backend: `GET /health` ok, SQLAlchemy 2.0 + Alembic (migraciones contra Postgres), Chroma embebido (`get_chroma_client()` + colección `inmuebles`). Frontend: rutas `/chat` y `/dashboard`; `/chat` consulta `/health` → "backend ok". Verificado en runtime (build + servidores). T00.1.1, T00.2.1, T00.2.2, T00.3.1, T00.3.2, T00.4.1, T00.5.1 ✅

## Día 2 (hackathon) — 2026-06-10
- [E00] **Ajuste de entorno.** Backend y frontend corren **nativos**; Docker **solo para las BDs**: se quitó el `Dockerfile` del backend y se agregó `docker-compose.yml` (Postgres). Chroma sigue embebido. Ver [[Decisiones (Decision Log)]] D10.
- [E00] **VS Code:** `.vscode/tasks.json` con **`Ctrl+Shift+B`** que levanta back + front en paralelo (lado a lado), sin Docker. Detalle en [[Setup del Entorno]].

---
> **Cómo usar:** al cerrar una tarea, agrega una línea aquí y marca el checkbox en su épica. Sube `actualizado` en el frontmatter.
