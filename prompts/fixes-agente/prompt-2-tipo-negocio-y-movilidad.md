# PROMPT 2 — Comportamiento del agente: fijar `tipo_negocio` + disparar movilidad

## Rol y setup
Eres **DEV** en el repo Aquamarine. Rama nueva:
```
git checkout -b feat/prompt-tipo-negocio-y-movilidad
```
Alcance: **solo prompt engineering** en `backend/app/agent/prompts.py`. Sin cambios en `tools.py`, `search.py`, `profiler.py`, ni frontend. Sin cambios de contrato en `ChatResponse` ni en la metadata de Chroma. `SYSTEM_PROMPT` es la constante de prompt caching (docstring `:1‑6`): estos cambios invalidan la caché una vez (esperado).

El motor ya soporta ambas cosas: `filtros.tipo_negocio` (`tools.py:54`) se aplica como filtro duro en `search.py` `_where_duro` en todos los niveles de relajación; `preferencias` (`tools.py:104‑116`) reordena por movilidad. Lo único que falta es que Aqua **lo dispare**. Esto es 100% prompt.

---

## Fix C — SIEMPRE fijar `tipo_negocio` (compra vs. arriendo)

### Inserción en `prompts.py`
Dentro de `## Mostrar inmuebles (uso de herramienta)`, **después de la línea 49** (tras el bullet de "Búsqueda por código") y **antes de la línea 50** ("Presenta 1–3 opciones…"), inserta esta subsección:

```
### Venta vs. arriendo — SIEMPRE fija `tipo_negocio`
Cada búsqueda es **para comprar** o **para arrendar**: son inventarios distintos y mezclarlos \
confunde (una casa en arriendo de $25M/mes "cabe" en un presupuesto de compra de $2.000M y se \
cuela sin sentido). Por eso, **SIEMPRE** que llames `buscar_inmuebles` como búsqueda general, fija \
`filtros.tipo_negocio`:
- Quiere **comprar** ("comprar", "compra", "adquirir", "que sea mío", "en venta", habla de inversión \
o de un presupuesto total en cientos/miles de millones) → `filtros.tipo_negocio = "venta"`.
- Quiere **arrendar** ("arrendar", "alquilar", "rentar", "para vivir mientras", "cuánto de canon/mensual", \
presupuesto expresado **por mes**) → `filtros.tipo_negocio = "arriendo"`.
- **Fíjalo desde el PRIMER mensaje en que quede clara la intención**, aunque aún no tengas zona ni \
número exacto de habitaciones. En finca raíz de lujo el caso por defecto es **compra**: si el cliente \
pide inmuebles y NADA sugiere arriendo, usa `"venta"`.
- Solo cuando sea **genuinamente ambiguo** (ninguna señal y el precio no aclara), haz **UNA** pregunta \
corta y natural antes de buscar: "¿lo estás buscando para comprar o para arrendar?". No la repitas ni \
la conviertas en formulario.
- **Coherencia:** una vez fijado, mantén el mismo `tipo_negocio` en las búsquedas siguientes de esa \
conversación, hasta que el cliente diga explícitamente que cambió ("mejor miremos en arriendo").
```

Por qué funciona: cubre el transcript (Andrés dijo "comprar" → `"venta"`; y aun sin decirlo, el default de compra en lujo evita el arriendo colado), dispara "desde el primer mensaje" (el fallo real fue omitir el campo), y la desambiguación es de UNA sola vez, consistente con la regla de oro "nada de formularios" (`:20`).

---

## Fix D — Disparar la pregunta de movilidad

### D.1 — Agregar movilidad al checklist de perfilamiento
Reemplaza `## Qué perfilar` (`prompts.py:25‑30`) por:
```
## Qué perfilar (de forma natural, una cosa a la vez)
A lo largo de la conversación ve entendiendo estas 4 dimensiones —sin preguntarlas de corrido ni como checklist:
1. **Tipo de inmueble** (apartamento, casa, lote, …).
2. **Zona / ciudad** de interés.
3. **Presupuesto** aproximado.
4. **Plazo** de decisión (¿para ya, o explorando?).

Y una 5.ª, **suave y opcional**, que capturas UNA vez ya que tengas las 4 anteriores:
5. **Movilidad** — cómo se mueve el lead en su día a día (carro, metro, a pie, teletrabajo…). \
No califica al lead; solo te deja ofrecer algo que le quede más cómodo. Ver "Preferencia de movilidad".
```

### D.2 — Anclar el gatillo a un momento observable
Reemplaza el arranque de "### Preferencia de movilidad" (`prompts.py:52‑58`, hasta antes del "Mapea la respuesta…" de la línea 59, que se conserva) por:
```
### Preferencia de movilidad (pregunta proactiva y suave)
**Gatillo (hazlo una vez):** ANTES de tu PRIMERA `buscar_inmuebles` general, revisa si ya tienes \
tipo + zona + presupuesto pero AÚN no sabes cómo se mueve el lead. Si es así, en ESE turno pregúntalo \
UNA sola vez —natural, en una frase, sin interrogatorio— antes o junto con las primeras opciones: \
"¿Y cómo te mueves normalmente — en carro, en metro, de otra forma? Así te muestro algo que te quede cómodo 🙂".
- Prefiere preguntar **antes** de la primera tanda de tarjetas; si el lead ya pidió ver opciones con afán, \
muéstralas y engancha la pregunta al final de ese mismo mensaje.
- **Una sola vez, no bloqueante:** si ya lo sabes, no lo tienes, o el lead lo ignora/cambia de tema, \
sigue normal y **NO lo vuelvas a preguntar**.
- Si responde, **NO es requisito**: es info EXTRA para reordenar y resaltar lo que más valore.
```
Conserva intacto el resto de la sección (el mapeo a `preferencias` y la nota "suave ≠ filtro duro", `:59‑72`).

Por qué funciona: el gatillo pasa de un difuso "durante el perfilamiento" a una condición binaria evaluable en un momento único e ineludible ("antes de la primera `buscar_inmuebles` general"), y se coloca como **precondición de la acción que el modelo más quiere hacer** (buscar), en vez de competir con ella. Se coordina limpio con Fix C (dimensiones ortogonales) y con el foco del Prompt 1 (en modo seguimiento no hay "primera búsqueda general", así que no se re-dispara).

---

## Tests (sin red ni SDK)
Los prompts no son verificables por unit test de contenido conversacional, pero sí hay que blindar que **el motor honra `tipo_negocio`** y que **la caché no se rompió**:
1. **`tipo_negocio` filtra duro** (test de motor, en `backend/tests/test_rag_search.py` o similar, sin red — usa el patrón de mock de Chroma ya presente en `test_rag_search.py`): dado un inventario con un inmueble `"venta"` y uno `"arriendo"`, `buscar_inmuebles(query, {"tipo_negocio":"venta"})` **no** devuelve el de arriendo en ningún nivel de relajación. Si no existe cobertura de `_where_duro` para `tipo_negocio`, agrégala.
2. **Smoke del prompt**: `from app.agent.prompts import SYSTEM_PROMPT; assert "tipo_negocio" in SYSTEM_PROMPT and "Movilidad" in SYSTEM_PROMPT` — garantiza que las reglas quedaron insertadas.
3. No-regresión: `cd backend && pytest -q` (los 145 en verde).

Verificación manual recomendada (con API real, opcional): reproducir el turno inicial de Andrés y confirmar en logs/among tool inputs que `buscar_inmuebles` se llamó con `filtros.tipo_negocio="venta"` y que aparece una pregunta de movilidad una sola vez.

## Verificación contra el transcript
- **Turno inicial de Andrés** ("busco una casa o apto por menos de 2000 millones", quiere comprar): Aqua fija `filtros.tipo_negocio="venta"` → **cero arriendos** en los resultados (los $48M/$25M mensuales ya no se cuelan). Y como es su primera búsqueda general con tipo+zona+presupuesto ya conocidos y movilidad desconocida, **pregunta una vez** cómo se mueve (antes o enganchada a las primeras 3 opciones).
- **Turnos siguientes**: no vuelve a preguntar movilidad, y mantiene `tipo_negocio="venta"` salvo que Andrés pida explícitamente arriendo.

---

### Nota de robustez (fuera de alcance, plan B anotado)
Si tras estos prompts Aqua **siguiera** omitiendo el filtro (como pasó con la regla de foco: prompt-only no bastó), el refuerzo determinista natural —sin tocar Chroma— es en `ejecutar_buscar_inmuebles` (`tools.py:253`): si una búsqueda general no trae `filtros.tipo_negocio`, inyectar default `"venta"` salvo señales de arriendo en `query`/filtros. Y para la movilidad, inyectar un bloque de "estado del lead" (`lead.perfil`) al inicio de `messages` por turno. Ambos comparten causa raíz con el foco. Quedan como plan B, no en el alcance de este prompt.