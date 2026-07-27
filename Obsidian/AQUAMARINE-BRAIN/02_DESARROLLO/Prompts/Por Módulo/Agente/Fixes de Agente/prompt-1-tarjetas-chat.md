# PROMPT 1 — Tarjetas del chat: mapa-como-tarjeta + fix de foco

## Rol y setup
Eres **DEV** en el repo Aquamarine (FastAPI + React/TS). Trabaja en una rama nueva:
```
git checkout -b feat/chat-cards-mapa-y-foco
```
Alcance: (A) convertir el ofrecimiento del mapa en una **tarjeta clickeable** en el chat, y (B) arreglar el **foco** para que en un turno de seguimiento de UNA propiedad solo salga la tarjeta de esa propiedad (cero tarjetas de búsqueda general). Ambos cambios comparten el mismo punto de contacto (el loop del orquestador y `response.inmuebles`/nuevo `response.mapa`), por eso van juntos.

Constraints a respetar: metadata plana de Chroma (no tocar), patrón tool-use existente, y que las tarjetas del chat salen de `response.inmuebles` (el frontend las adjunta por mensaje). Reusa `obtener_inmueble_por_codigo` (ya existe en `app/rag/search.py:394`, devuelve `titulo`, `imagen_principal`, `imagenes`, `latitud`, `longitud`, `inmueble_id` — metadata plana). NO cambies Chroma ni `search.py`.

---

## PARTE A — Mapa como tarjeta

### Diseño
Aqua emite un **marcador `[[MAPA:codigo]]`** al final de su mensaje. El orquestador lo extrae → construye un objeto `mapa` → lo mete en `ChatResponse.mapa` → el hook lo adjunta al mensaje → `ChatPage` renderiza un nuevo `<MapaCard>`. Simétrico con cómo funcionan las tarjetas de inmueble. **Respaldo determinista:** si Aqua olvidó el marcador pero en el turno corrió `lugares_cerca(codigo=X)`, el orquestador usa ese `X` como `mapa_codigo` (el mapa es el CTA natural de "¿qué hay cerca?").

### A.1 — `backend/app/agent/prompts.py` (reemplazar líneas 139‑141)

Reemplaza el bullet actual del link markdown (dentro de la sección `### "¿Qué hay cerca / alrededor?" → lugares_cerca`) por:

```
- Tras listar los lugares, OFRECE el mapa interactivo de esa propiedad. Para que el sistema lo \
muestre como una TARJETA clickeable (no como un link), termina tu mensaje con el marcador EXACTO \
[[MAPA:CODIGO]] (reemplaza CODIGO por el código REAL del inmueble, sin espacios ni puntos). \
Ej: "¿Quieres verlo en un mapa con las rutas y los servicios? 🗺️ [[MAPA:9718612]]". El cliente NO \
ve el marcador: se convierte en una tarjeta "Ver mapa interactivo". Úsalo UNA sola vez por mensaje \
y solo cuando ofrezcas el mapa de UNA propiedad concreta.
```
(Nota: este cambio invalida el prompt caching una vez — costo único esperado.)

### A.2 — `backend/app/agent/orchestrator.py`

**a) Nivel módulo** (junto a los otros helpers, e importar `re` arriba y `obtener_inmueble_por_codigo`):
```python
import re
from app.rag.search import obtener_inmueble_por_codigo

_MAPA_RE = re.compile(r"\[\[MAPA:\s*([A-Za-z0-9_-]+)\s*\]\]")

def _extraer_mapa(texto: str) -> tuple[str, str | None]:
    """Devuelve (texto_sin_marcadores, primer_codigo|None)."""
    codigos = _MAPA_RE.findall(texto or "")
    limpio = _MAPA_RE.sub("", texto or "").strip()
    limpio = re.sub(r"[ \t]{2,}", " ", limpio)
    return limpio, (codigos[0] if codigos else None)

def _construir_mapa(codigo: str | None) -> dict | None:
    if not codigo:
        return None
    inm = obtener_inmueble_por_codigo(codigo)
    if not inm or inm.get("latitud") is None or inm.get("longitud") is None:
        return None  # sin coords la página /mapa/propiedad/:codigo no puede dibujar
    imagenes = inm.get("imagenes") or []
    return {
        "codigo": codigo,
        "titulo": inm.get("titulo") or "esta propiedad",
        "imagen": inm.get("imagen_principal") or (imagenes[0] if imagenes else None),
    }
```

**b) Dentro de `responder`**, ver PARTE B (el loop se refactoriza una sola vez para A y B juntos). El respaldo determinista del mapa se captura ahí mismo (`mapa_codigo_fallback`).

**c) Return dict** (ambos returns): agregar `"mapa": mapa`. En el return de takeover (`:102‑109`), `"mapa": None`.

### A.3 — `backend/app/api/chat.py` (schema)
```python
class MapaPreview(BaseModel):
    codigo: str
    titulo: str
    imagen: str | None = None

class ChatResponse(BaseModel):
    respuesta: str
    inmuebles: list[dict]
    handoff: bool
    temperatura: str
    lead_id: UUID
    atendido_por_humano: bool = False
    mapa: MapaPreview | None = None   # ← nuevo; None cuando no se ofreció mapa
```

### A.4 — `frontend/src/hooks/useChatSession.ts`
- Añadir tipo y propagarlo:
```ts
export type MapaPreview = { codigo: string; titulo: string; imagen?: string | null }
```
- En `Mensaje` (`:5‑12`) añadir `mapa?: MapaPreview | null`.
- En el tipo local `ChatResponse` (`:23‑30`) añadir `mapa?: MapaPreview | null`.
- En `mensajeAgente` (`:99‑106`) añadir `mapa: response.mapa`.

### A.5 — `frontend/src/components/MapaCard.tsx` (nuevo)
Tarjeta consistente con `PropertyCard` (tokens `--card/--line/--ink/--champ/--gray-soft`, `w-52`, Newsreader en el título). Abre `/mapa/propiedad/:codigo` en **nueva pestaña** (`target="_blank"`, ruta ya existe en `App.tsx:24`). Velo + emoji 🗺️ para distinguirla de un inmueble:
```tsx
import type { MapaPreview } from '../hooks/useChatSession'

export function MapaCard({ mapa }: { mapa: MapaPreview }) {
  return (
    <a href={`/mapa/propiedad/${mapa.codigo}`} target="_blank" rel="noopener noreferrer"
       className="group flex flex-col flex-shrink-0 w-52 rounded-xl overflow-hidden mt-1"
       style={{ background: 'var(--card)', border: '1px solid var(--line)',
                boxShadow: '0 1px 4px rgba(26,26,26,.07)' }}>
      <div className="relative h-24 w-full">
        {mapa.imagen ? (
          <img src={mapa.imagen} alt={mapa.titulo} loading="lazy" className="w-full h-24 object-cover" />
        ) : (
          <div className="w-full h-24"
               style={{ background: 'linear-gradient(135deg, var(--charcoal), var(--champ))' }} />
        )}
        <div className="absolute inset-0 flex items-center justify-center"
             style={{ background: 'rgba(26,26,26,.35)' }}>
          <span className="text-2xl">🗺️</span>
        </div>
      </div>
      <div className="p-3 flex flex-col gap-1">
        <p className="text-sm font-semibold leading-snug"
           style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}>
          Ver mapa interactivo
        </p>
        <p className="text-xs line-clamp-1" style={{ color: 'var(--gray-soft)' }}>{mapa.titulo}</p>
        <span className="text-xs mt-1 font-medium" style={{ color: 'var(--champ)' }}>
          Rutas y servicios cercanos →
        </span>
      </div>
    </a>
  )
}
```

### A.6 — `frontend/src/pages/ChatPage.tsx`
En `BurbujaMensaje`, tras el `PropertyCardList` (después de `:33‑35`), añadir:
```tsx
{!esLead && mensaje.mapa && <MapaCard mapa={mensaje.mapa} />}
```
E importar `MapaCard` arriba (`import { MapaCard } from '../components/MapaCard'`).

---

## PARTE B — Fix de foco (mecanismo determinista)

### Regla dura
*Si en el turno se usó `lugares_cerca`, o hubo un code-lookup (`buscar_inmuebles` con `codigo`), el turno es SEGUIMIENTO de una propiedad → `response.inmuebles` contiene SOLO la tarjeta del inmueble en foco; se descarta cualquier resultado de búsqueda general recolectado en el mismo turno.*

### B.1 — `backend/app/agent/orchestrator.py` (refactor del loop `:120‑174`)

Reemplaza la recolección ciega (`inmuebles_sugeridos.extend` en `:156` y el uso en `:169`/`:227`) por seguimiento por origen. Antes del loop:
```python
inmuebles_general: list[dict] = []
inmuebles_foco: list[dict] = []
uso_lugares_cerca = False
foco_codigo: str | None = None
mapa_codigo_fallback: str | None = None
texto_final = ""
```
Dentro del bucle sobre `respuesta.content`, al despachar cada `tool_use` (reemplazando el bloque `:149‑161`):
```python
for bloque in respuesta.content:
    if getattr(bloque, "type", None) != "tool_use":
        continue
    nombre = getattr(bloque, "name", None)
    handler = handlers.get(nombre)
    if handler is None:
        continue
    entrada = bloque.input or {}
    texto_tool, inmuebles = handler(entrada)
    if nombre == "lugares_cerca":
        uso_lugares_cerca = True
        cod = str(entrada.get("codigo") or "")
        if cod:
            foco_codigo = cod
            mapa_codigo_fallback = cod          # respaldo del mapa (Parte A)
    elif nombre == "buscar_inmuebles":
        if entrada.get("codigo"):               # code-lookup → foco
            foco_codigo = str(entrada.get("codigo"))
            inmuebles_foco.extend(inmuebles)
        else:                                   # búsqueda general
            inmuebles_general.extend(inmuebles)
    resultados.append({
        "type": "tool_result",
        "tool_use_id": bloque.id,
        "content": texto_tool,
    })
```
Tras el loop (reemplaza el uso directo de `inmuebles_sugeridos`):
```python
if uso_lugares_cerca or inmuebles_foco:
    foco = _resolver_foco(inmuebles_foco, inmuebles_general, foco_codigo)
    inmuebles_sugeridos = [foco] if foco else []
else:
    inmuebles_sugeridos = inmuebles_general

# Parte A: extraer marcador de mapa del texto final + respaldo determinista
texto_final, mapa_codigo = _extraer_mapa(texto_final)
mapa = _construir_mapa(mapa_codigo or mapa_codigo_fallback)
```
Nuevo helper (nivel módulo):
```python
def _resolver_foco(inmuebles_foco, inmuebles_general, foco_codigo):
    if inmuebles_foco:
        return inmuebles_foco[0]
    if foco_codigo:
        for inm in inmuebles_general:
            if str(inm.get("inmueble_id")) == str(foco_codigo):
                return inm
        return obtener_inmueble_por_codigo(foco_codigo)  # aunque solo se llamó lugares_cerca
    return None
```
Robusto: aunque Aqua vuelva a correr `buscar_inmuebles` general en un turno de "¿qué hay cerca?", los arriendos se descartan y solo queda la casa en foco.

### B.2 — `backend/app/agent/prompts.py` (refuerzo, en "Seguimiento de UNA propiedad" `:120‑128`)
Añade al final de esa lista:
```
- En el MISMO turno en que uses `lugares_cerca` (o consultes una propiedad por su `codigo`), \
NO llames `buscar_inmuebles` como búsqueda general: el sistema solo mostrará la tarjeta de ESA \
propiedad y descartará cualquier búsqueda general. Si el lead quiere ver otras opciones, hazlo en \
un turno aparte y solo cuando lo pida explícitamente.
```

### B.3 (opcional, defensa en profundidad) — `frontend/src/hooks/useChatSession.ts`
Al construir `mensajeAgente`, si `response.inmuebles` es idéntico (por `inmueble_id`, mismo set y orden) al del último mensaje de agente, adjuntar `inmuebles: []` para no re-renderizar el mismo bloque (arregla el re-listado en "¿quedan cerca del metro?"). No sustituye el fix backend.

---

## Tests (sin red ni SDK)
Usa la infraestructura ya existente en `backend/tests/test_lugares.py` (`_FakeClient`, `_Respuesta`, `_BloqueTexto`, `_BloqueTool`, y `monkeypatch` de `orchestrator._build_client`, `orchestrator.extraer_perfil`, y los handlers). Agrega a `test_lugares.py` (o un `test_foco_mapa.py` nuevo):

1. **Foco descarta arriendos** (reproduce el transcript). Respuesta fake: un `_Respuesta` con `stop_reason="tool_use"` que contenga DOS `_BloqueTool`: `lugares_cerca(codigo="9718612")` y `buscar_inmuebles({"query": "..."})` (general), seguido de un `_Respuesta` `end_turn` con texto. Monkeypatch de handlers: `ejecutar_lugares_cerca` → `("Cerca: Éxito", [])`; `ejecutar_buscar_inmuebles` → `("...", [{"inmueble_id":"48M",...},{"inmueble_id":"25M",...}])`. Monkeypatch `orchestrator.obtener_inmueble_por_codigo` → `{"inmueble_id":"9718612","titulo":"La Loma","latitud":6.2,"longitud":-75.5}`. Aserción: `len(out["inmuebles"]) == 1` y `out["inmuebles"][0]["inmueble_id"] == "9718612"`; ningún arriendo presente.
2. **Marcador de mapa → objeto `mapa`**. Respuesta fake `end_turn` con texto `"Cerca tienes... 🗺️ [[MAPA:9718612]]"`, monkeypatch `obtener_inmueble_por_codigo` como arriba. Aserción: `out["mapa"]["codigo"] == "9718612"`, `"[[MAPA" not in out["respuesta"]` (texto limpio), `out["mapa"]["titulo"] == "La Loma"`.
3. **Respaldo determinista del mapa** (sin marcador, con `lugares_cerca`): Aserción `out["mapa"]["codigo"] == <codigo de lugares_cerca>`.
4. **Mapa None sin coords**: `obtener_inmueble_por_codigo` devuelve dict sin `latitud` → `out["mapa"] is None`.
5. **No-regresión**: verifica que `test_orchestrator_despacha_lugares_cerca` (ya existe) sigue verde con `out["mapa"]` posiblemente None y `out["inmuebles"] == []`.

Corre: `cd backend && pytest -q` (los 145 deben seguir en verde). Frontend: `cd frontend && npm run build` (typecheck del nuevo campo y componente).

## Verificación contra el transcript
- Turno "me gusta la de la loma del esmeraldal, ¿qué tiene cerca?": el texto lista los POIs reales (sin cambio) y `response.inmuebles` trae **una sola** tarjeta (La Loma), **cero** arriendos en Las Palmas. Además aparece una **`MapaCard` clickeable** al final del turno → nueva pestaña a `/mapa/propiedad/9718612`.
- Turno "¿quedan cerca del metro?": con B.3, ya no se re-listan las 3 mismas tarjetas.

---