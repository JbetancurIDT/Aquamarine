Rol: eres el DEV de Aquamarine (lee `Obsidian/AGENTES.md`). Corrección de documentación tras la auditoría de E11 (intención de compra). Rama `feat/e11-intencion` (la misma de E11, ya con los 3 handoffs implementados en el commit ba66bb7). Editas **solo** la doc de feature en la raíz; NO toques código ni `Obsidian/**`.

CONTEXTO: la auditoría del Planner confirmó E11 **completo y verde** (261/261 tests, `npm run build` OK), pero encontró un desfase de estado: la fila de E11 en `CLAUDE.md` (tabla "Documentación por feature") quedó rotulada como **"Handoffs 1–2/3 · falta consolidar tests+docs"** — y ese mismo commit ba66bb7 **ES** el handoff de tests+docs (creó `backend/tests/test_intencion.py` e `intencion.md`). Además contradice a `intencion.md`, que se declara "Feature completo (handoffs 1–3)". El índice del repo está subestimando lo entregado.

OBJETIVO: dejar la fila de E11 en `CLAUDE.md` reflejando el estado real (feature completo, handoffs 1–3, auditado).

QUÉ HACER:
- En `CLAUDE.md`, tabla "Documentación por feature", **fila E11 → `intencion.md`**: reemplaza el texto de estado obsoleto por uno que diga que E11 está **completo (handoffs 1–3)**: eje `perfil.intencion` inferido por Aqua + `derivar_intencion` de fallback + backfill + evento `intencion_clasificada` + **`GET /metrics/intencion`** (% comprador/curioso por zona y propiedad) + tool de insights + tile en el dashboard; **261 tests verdes**. Quita el "falta consolidar tests+docs". Mantén el enlace a `intencion.md`.
- Es un cambio de **una línea/celda** (estado + enlace = zona permitida al Dev en `CLAUDE.md`). No toques ninguna otra fila ni el resto del archivo.

FUERA DE ALCANCE: nada de código; nada en `Obsidian/**` (si crees que hay que anotar algo en el cerebro, repórtalo al Planner).

VERIFICACIÓN: la fila E11 de `CLAUDE.md` ya no dice "falta consolidar tests+docs" y es consistente con `intencion.md` (feature completo). `git diff` toca solo `CLAUDE.md`.

PARA. Entrégame el antes/después de la celda. (No hay tests que correr; es doc.)
