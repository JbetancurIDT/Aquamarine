Rol: eres el DEV de Aquamarine (lee `Obsidian/AGENTES.md`). Cierre del feature **intención de compra** (E11). Rama `feat/e11-intencion` (ya trae los handoffs 1 y 2: señal+derivación+evento, y métrica+surface). Editas código y **docs de feature en la raíz**; **NUNCA** edites `Obsidian/**`. Épica: `Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E11 - Clasificación de Intención de Compra (Comprador vs Curioso).md`; decisión **D26**.

OBJETIVO DE ESTE HANDOFF (Etapa 11.6 = blindaje + documentación):

── A) SUITE DE TESTS (backend/tests/test_intencion.py — NUEVO) — T11.6.1 ──
- Consolida y cubre, **offline** (sin red ni SDK): extracción de `intencion` por el profiler; `derivar_intencion` (tabla de casos); emisión de `intencion_clasificada` (emite al cambiar, no si es igual); `GET /metrics/intencion` (global + por zona tolerante + por propiedad). Los ~228 tests previos siguen verdes.

── B) DOC DE FEATURE (intencion.md — NUEVO en la raíz + CLAUDE.md) — T11.6.2 ──
- Crea `intencion.md` en la raíz: qué resuelve (bloque "En términos de negocio"), la rúbrica, cómo se **infiere** (profiler) y se **deriva** (`derivar_intencion`), el evento `intencion_clasificada`, la métrica segmentada por zona/propiedad, y cómo correr el backfill y los tests.
- Añade la fila a la tabla "Documentación por feature" de `CLAUDE.md` (solo estado/enlaces, según la convención del proyecto).

── C) REPORTE AL PLANNER (esto NO lo tocas tú) ──
- En tu resumen final, **repórtame** para que yo actualice `Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Modelo de Datos.md`: los campos `perfil.intencion` + `perfil.interes_urgencia`, el `eventos.tipo = intencion_clasificada` (+ su payload) y la métrica derivada; citando **D26**. Recuerda que `Modelo de Datos.md` está desactualizado (le faltan también `atendido_por_humano`/D17 y `perfil.movilidad`/D25) — no lo arregles tú, solo repórtalo.

VERIFICACIÓN: `pytest` verde (previos + intención), `npm run build` verde, `intencion.md` creado y enlazado en la tabla de `CLAUDE.md`.

PARA. Entrégame el resumen final + exactamente lo que debo registrar en el cerebro (Modelo de Datos, Daily Log, checklist E11 → hecho, frontmatter de la épica → `estado: completado`). Con ese reporte el Planner cierra E11 en el cerebro.
