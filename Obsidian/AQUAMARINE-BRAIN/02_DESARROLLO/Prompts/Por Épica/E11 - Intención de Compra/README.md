# E11 — Clasificación de Intención de Compra (Comprador vs Curioso) · Prompts de handoff

- **Épica (detalle):** `Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E11 - Clasificación de Intención de Compra (Comprador vs Curioso).md`
- **Rama:** `feat/e11-intencion` (desde `master`, que ya trae E09/E10)
- **Decisión de origen:** [[Decisiones (Decision Log)]] **D26** (2026-07-24).
- **Estado:** ✅ **entregada y auditada** (2026-07-27, commit `ba66bb7`) — **261/261 tests verdes**, `npm run build` OK. Pendiente: merge a `master` + `handoff-4` (fix de estado en `CLAUDE.md`).
- **Idea:** distinguir **compradores** reales de **curiosos** ("lolos") que solo preguntan precio, y medir el **% por zona/propiedad**. Eje **nuevo e independiente**: en v1 **no** toca el scoring; Aqua **infiere**, no interroga; todo se calcula **al vuelo**, sin contadores denormalizados.

**Cómo usar:** abre el handoff, **⌘A ⌘C** (todo el archivo es el prompt), pégalo en la sesión del Dev. Cada handoff termina con **"PARA"**: el Dev se detiene, tú traes su resumen al Planner para una **auditoría read-only**, y recién ahí pasas al siguiente.

## Itinerario

| # | Archivo | Etapas | Qué construye | Checkpoint observable |
|---|---|---|---|---|
| 1 | `handoff-1-senal-y-derivacion.md` | 11.1–11.3 | señal `perfil.intencion` en el profiler + `derivar_intencion` (fallback) + backfill + evento `intencion_clasificada` | "¿cuánto vale?" pelado → `curioso`; presupuesto+plazo → `comprador`; evento al cambiar |
| 2 | `handoff-2-metrica-y-surface.md` | 11.4–11.5 | `GET /metrics/intencion` (% por zona/propiedad, al vuelo) + tool de insights + tile en el dashboard | endpoint devuelve % comprador/curioso por zona; insights responde; tile pinta |
| 3 | `handoff-3-tests-y-docs.md` | 11.6 | `test_intencion.py` + `intencion.md` + fila en `CLAUDE.md` | `pytest` + `npm run build` verdes; doc creada |
| 4 | `handoff-4-fix-estado-claude-md.md` | post-auditoría | corrige el estado obsoleto de la fila E11 en `CLAUDE.md` | la fila ya no dice "falta consolidar tests+docs" |

**Backend puro (handoff 1) → dato + surface (handoff 2) → blindaje/doc (handoff 3).** Es un feature medio; cada handoff es un chunk coherente y auditable.

## El loop (no te lo saltes)
1. Pega el **handoff N** en el Dev.
2. El Dev construye y **PARA** con un resumen + su verificación observable.
3. Traes ese resumen al **Planner** (la sesión de planeación) → **auditoría read-only**.
4. Si pasa → **handoff N+1**; si no → el Planner te da un prompt de corrección.

## Al cerrar E11 (lo hace el Planner, no el Dev)
Tras el handoff 3, el Planner registra en el cerebro: `Modelo de Datos.md` (`perfil.intencion`/`perfil.interes_urgencia`, evento `intencion_clasificada`, métrica derivada), `Daily Log.md`, checklist E11 → hecho, frontmatter de la épica `estado: completado`, y (si aplica) una fila de resultado en el Decision Log. El Dev **reporta**, no toca `Obsidian/**`.
