# Handoff completo: takeover humano + barrido + performance — feature doc (E07)

## Qué hace
Cierra el ciclo del handoff: el lead calificado se **auto-asigna** al asesor con menor carga, un
**barrido periódico** escala notificaciones y reasigna si nadie responde, el asesor puede **tomar el
chat en vivo** (la IA se silencia y responde un humano), y la gerencia ve **performance por asesor**
con semáforos de SLA. Todo por **polling** (sin WebSockets).

---

## 1. Modelo — nuevos campos del Lead

| Campo | Tipo | Significado |
|---|---|---|
| `atendido_por_humano` | bool | `True` = IA silenciada, un asesor responde manualmente |
| `asignado_en` | timestamptz | momento de la (re)asignación a un asesor |
| `ultima_notificacion_en` | timestamptz | última notificación escalada emitida por el barrido |
| `notificaciones_count` | int | nº de notificaciones desde la asignación (gatilla la reasignación) |

Migración: `alembic/versions/…_e07_handoff_fields.py` (server_default para backfill de los existentes).

---

## 2. Auto-asignación con balanceo (`asesor_con_menor_cola`)

`lead_service.asesor_con_menor_cola(db, tenant_id, excluir=None)`:
- Elige el asesor **disponible** del tenant con **menos leads activos** (`calificado` + `negociando`).
- **Cap blando** (`MAX_LEADS_ACTIVOS_POR_ASESOR`, default 5): prefiere asesores bajo el cap; si todos lo
  superan, igual devuelve el de menor cola (nunca deja el lead sin asesor por eso).
- `excluir`: descarta un asesor **si hay otra opción** (lo usa la reasignación para no caer en el mismo).
  Si el único disponible es el excluido → devuelve `None` (no hay alternativa).

El handoff (`agent/handoff.py`) la usa al calificar: asigna, setea `asignado_en`, resetea contadores y
emite el evento `asignado` (además del `handoff`).

---

## 3. Barrido periódico (`services/sweep.py`)

Arranca en el **lifespan** de FastAPI (`asyncio.create_task(sweep_loop)`); cada `SWEEP_INTERVALO_SEG`
corre `_sweep_once` vía `asyncio.to_thread` (sesión propia, no bloquea el event loop).

Por pasada (**commit por lead** → robusto y hace visibles las asignaciones dentro de la misma pasada,
para que el balanceo no apile todos los leads sobre el mismo asesor con `autoflush=False`):

1. **Asignar** leads `calificado` sin asesor al de menor cola → evento `asignado`.
2. Para cada lead `calificado` asignado y **no tomado**, si pasó el intervalo de su temperatura desde la
   última notificación/asignación:
   - `notificaciones_count < NOTIF_MAX` → emite `notificacion` (escalada) y sube el contador.
   - `>= NOTIF_MAX` → **reasigna** al asesor de menor cola **distinto** (`excluir=actual`), con un mensaje
     de disculpa de la IA y evento `reasignado`. Si **no hay otro** asesor, solo refresca el reloj
     (ni reasigna al mismo, ni emite evento/disculpa → sin churn infinito).

Intervalos por temperatura (config, segundos; `NOTIF_SCALE` los divide para demo):
`caliente 300 · tibio 1200 · frío 3600 · desconocido 1200`. Ej. `NOTIF_SCALE=60` → caliente cada 5 s.

---

## 4. Takeover: el asesor toma el chat

`POST /leads/{id}/tomar` `{asesor_id}` → `lead_service.tomar_lead` (**idempotente**):
- `atendido_por_humano=True`, asigna el asesor, mueve a `negociando`, resetea contadores.
- Persiste una **despedida de la IA** y emite `tomado_por_humano`.

`orchestrator.responder()` **silencia la IA** cuando `atendido_por_humano=True`: persiste el mensaje del
lead y devuelve `{respuesta:"", atendido_por_humano:True}` sin llamar a Claude. El asesor responde por el
compositor del modal (`POST /leads/{id}/mensajes` rol=`asesor`).

> El compositor del asesor **solo** aparece cuando el chat ya fue tomado; si no, el modal muestra el botón
> «Tomar este chat para responder» (no se puede escribir con la IA activa → evita respuestas duplicadas).

---

## 5. Endpoints E07

| Endpoint | Descripción |
|---|---|
| `GET /leads/en-vivo` | leads `calificado`/`negociando` **sin asesor** (declarado ANTES de `/{lead_id}`) |
| `POST /leads/{id}/tomar` | takeover humano (silencia IA, → negociando, evento `tomado_por_humano`) |
| `PATCH /asesores/{id}/disponibilidad` | `{disponible}` — entra/sale del balanceo |
| `GET /asesores` | ahora incluye `carga` (leads activos del asesor) |
| `GET /asesores/{id}/notificaciones` | eventos dirigidos al asesor: `handoff/asignado/notificacion/reasignado/tomado_por_humano`. Atribuye por `payload.asesor_id` (o `asesor_nuevo` en `reasignado`), **no** por el asesor actual del lead → tras reasignar, cada quien ve solo lo suyo |
| `GET /metrics/asesores` | métricas **reales** por asesor (ver §6) |
| `GET /metrics/propiedades` | inventario — **MOCK** (Chroma no expone conteos por tenant aún) |

---

## 6. Métricas por asesor (`GET /metrics/asesores`)

Por asesor: `leads_asignados`, `en_cola` (calificado+negociando), `tomados` (atendido_por_humano),
`ganados`, `valor_cerrado_cop`, `primera_respuesta_seg`, `tiempo_en_tomar_seg`, `ratio_conversion`.

- **`tiempo_en_tomar_seg`** = `asignado_en` → tiempo del evento `tomado_por_humano` (el más temprano por
  lead). Se usa el **evento** (siempre existe al tomar) y no el primer mensaje del asesor (que puede no
  haber llegado), tz-safe.
- **`primera_respuesta_seg`** = promedio de `creado_en` → primer mensaje rol=`agente`.

---

## 7. Frontend

| Vista | Novedad E07 |
|---|---|
| `/chat` | Banner «te atiende un asesor humano» + **poll base** de `GET /leads/{id}` (detecta el takeover aunque el lead esté inactivo) + render de mensajes `asesor` |
| `/asesor/:id` | Toggle de **disponibilidad**; sección **«En vivo · sin asignar»** (`GET /leads/en-vivo` + «Tomar este chat»); **campana** con badge + **toasts** de notificaciones (dedupe por `evento_id`, reset al cambiar de asesor); modal en `modoAsesor` |
| `LeadDetailModal` | `modoAsesor`: oculta el select de asesor; compositor de chat solo si el chat fue tomado; si no, botón «Tomar este chat» (`onTomar`) |
| `/dashboard` | Bloque **inventario** (mock) + tabla resumen **equipo de asesores** con link a `/performance` |
| `/performance` | Tabla **ordenable** de métricas por asesor + **semáforos de SLA** (ok `#4F6F52` · riesgo `#B08428` · fuera `#B4543A`). 1ª resp: ok<60s, riesgo<300s · tiempo en tomar: ok<300s, riesgo<1800s |

### Polling

| Vista | Intervalo | Qué refresca |
|---|---|---|
| `/chat` (poll base) | 3 s | `GET /leads/{id}` → detecta takeover + transcripción del asesor |
| `/asesor/:id` | 5 s | leads + en-vivo + notificaciones (combinado) |
| `/asesor/:id` (modal) | 4.5 s | lead abierto |
| `/performance` | 6 s | `GET /metrics/asesores` |
| `/dashboard` (extras) | 6 s | propiedades (mock) + métricas por asesor |

---

## 8. Configuración (`core/config.py`)

```
MAX_LEADS_ACTIVOS_POR_ASESOR=5      # cap blando del balanceo
NOTIF_MAX_ANTES_REASIGNAR=5         # notificaciones antes de reasignar
SWEEP_INTERVALO_SEG=60              # cada cuánto corre el barrido
NOTIF_SCALE=1.0                     # divide los intervalos (demo: 60 → caliente cada 5 s)
NOTIF_SEG_CALIENTE=300 · TIBIO=1200 · FRIO=3600 · DESCONOCIDO=1200
```

---

## 9. Eventos nuevos
`asignado` · `notificacion` · `reasignado` · `tomado_por_humano` (además de los de E02). Base de las
notificaciones del asesor y de las métricas de performance.

## 10. Tests
`tests/test_sweep.py` (asignación, distribución de carga, notificación escalada, reasignación a otro /
no-reasignar con un solo asesor, exclusión del tomado), `tests/test_leads.py` (en-vivo, tomar happy/
idempotente/404), `tests/test_asesores.py` (disponibilidad, carga, atribución de notificaciones por
payload). **117 tests en verde** (`pytest -q`).

## Archivos
`app/models/lead.py`, `app/services/{sweep,lead_service}.py`, `app/agent/{handoff,orchestrator}.py`,
`app/api/{leads,asesores,metrics,chat}.py`, `app/main.py` (lifespan), `app/core/config.py`,
`alembic/versions/…_e07_handoff_fields.py`. Front: `pages/{ChatPage,AsesorPage,PerformancePage,
DashboardPage}.tsx`, `components/LeadDetailModal.tsx`, `hooks/useChatSession.ts`, `api/types.ts`,
`App.tsx`.
