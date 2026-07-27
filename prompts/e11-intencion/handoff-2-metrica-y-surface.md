Rol: eres el DEV de Aquamarine (lee `Obsidian/AGENTES.md`). Continúas el feature **intención de compra** (E11). Rama `feat/e11-intencion` (ya trae el handoff 1: profiler con `intencion`, `derivar_intencion`, backfill y evento `intencion_clasificada`). Editas código; **NUNCA** edites `Obsidian/**`. Épica: `Obsidian/AQUAMARINE-BRAIN/02_DESARROLLO/Epicas/E11 - Clasificación de Intención de Compra (Comprador vs Curioso).md`; decisión **D26**.

OBJETIVO DE ESTE HANDOFF (Etapas 11.4 + 11.5 = el dato a la vista): exponer el **% comprador vs curioso** segmentado por **zona** y por **propiedad**, calculado **al vuelo** (sin contadores denormalizados), y llevarlo a la gerencia por el agente de insights + un tile en el dashboard.

── A) MÉTRICA (backend/app/api/metrics.py + backend/app/schemas/metrics.py) — T11.4.1 ──
- Endpoint `GET /metrics/intencion`, **tenant-scoped**, **al vuelo** (patrón de `metrics.py`: carga `Lead` del tenant y agrega en Python con `Rate {pct, num, den}`).
- Para cada lead usa `perfil['intencion']` **o**, si falta, `derivar_intencion(perfil, temperatura)` como fallback (así el endpoint no depende de que el backfill ya corrió).
- Devuelve:
  - `por_intencion`: global, con `Rate` por comprador / explorando / curioso.
  - `por_zona`: `[{zona, comprador, explorando, curioso, pct_comprador, pct_curioso}]` usando `_cumple_ubicacion` / `leads_por_ubicacion` de `services/demanda.py` (match **tolerante**, consistente con el heatmap de E10). Un curioso "cerca del metro" **sin zona real** cuenta en el global, **no** en zona.
  - `por_propiedad`: agrupado por `perfil['inmueble_interes']`.
  - Ordena zonas y propiedades por **volumen**.
- Define el schema en `schemas/metrics.py` reutilizando `Rate`.

── B) INSIGHTS TOOL (backend/app/agent/insights_tools.py) — T11.5.1 (edit de 3 pasos) ──
- Tool `intencion_por_zona` con param **opcional** `zona`: (1) dict en `TOOLS`; (2) executor `ejecutar_intencion(db, tenant, zona=None)` que **reusa** la lógica de `GET /metrics/intencion`; (3) rama en el dispatcher `ejecutar_tool`. **No toques** `insights_agent.py` ni `api/insights.py`.
- Devuelve % comprador/curioso global o de la zona pedida, para que Claudia pregunte en lenguaje natural "¿cuántos son curiosos en El Poblado?".

── C) DASHBOARD TILE (frontend/src/pages/DashboardPage.tsx + frontend/src/api/ si aplica) — T11.5.2 ──
- Tile "Compradores vs Curiosos" que consuma `GET /metrics/intencion`: % comprador / explorando / curioso (donut o barra) + top de zonas por % de curiosos.
- Respeta la paleta de marca y el `tsc` estricto (`noUnusedLocals` / `noUnusedParameters`) → `npm run build` **verde**.

── D) TESTS (backend/tests/, sin red ni SDK) ──
- `/metrics/intencion`: el global cuenta a todos; la zona usa match tolerante; un curioso sin zona real cuenta en global pero **no** en zona; `por_propiedad` agrupa por `inmueble_interes`.
- Sin regresiones: los tests previos siguen verdes.

VERIFICACIÓN: (1) `GET /metrics/intencion` devuelve algo como `comprador 32% · explorando 28% · curioso 40%` con desglose por zona (p. ej. El Poblado 55% curiosos) y por propiedad; (2) en el dashboard la burbuja de insights responde "¿en qué zonas hay más curiosos?" con datos reales; (3) el tile pinta el % y `npm run build` pasa.

PARA aquí. Entrégame un resumen + la verificación. **No sigas al handoff 3** hasta que el Planner audite este.
