Rol: eres el DEV de Aquamarine (lee AGENTES.md). Correcciones del Prompt 1 (foco + mapa-tarjeta) tras
revisión adversarial. Misma rama del Prompt 1. Editas código; NO edites Obsidian/.

Contexto: la revisión confirmó **2 bugs de comportamiento MEDIA disparables por un lead hoy** + robustez
barata. El camino feliz está bien (226 tests en verde y el test que reproduce el transcript pasa).
Arregla FIX 1 y FIX 2 **antes del merge**; los demás son baratos y conviene incluirlos.

── FIX 1 [MEDIA · bloqueante] — el gate de foco puede dejar 0 tarjetas (peor que el bug original) ──
En `backend/app/agent/orchestrator.py`, `uso_lugares_cerca = True` se fija con solo ver el nombre de la
tool (~línea 207), aunque el `codigo` venga vacío / alucinado / whitespace. Si además hubo una búsqueda
general EXITOSA en el mismo turno, el gate entra por foco, `_resolver_foco` devuelve None y
`inmuebles_sugeridos = []` → **el lead ve 0 tarjetas pese a una búsqueda general exitosa**.
- Cambia el gate (líneas 230-234) para que **caiga a la búsqueda general cuando no resuelve un foco**:
  `inmuebles_sugeridos = [foco] if foco else inmuebles_general`  (en vez de `... else []`).
  Esto MANTIENE el fix del transcript: cuando el foco SÍ resuelve (lugares_cerca(9718612) → obtiene la
  ficha real) sigue mostrando solo esa y descartando los arriendos; y evita el 0-tarjetas cuando NO resuelve.
- Añade `.strip()` al leer el código en ~:208: `cod = str(entrada.get("codigo") or "").strip()`.
- Tests nuevos (backend/tests/test_foco_mapa.py): (a) `lugares_cerca({})` sin código + `buscar_inmuebles(general)`
  con 2 fichas → `out["inmuebles"]` son las 2 generales (NO []); (b) `lugares_cerca(codigo="XXXX")` inexistente
  (mock `obtener_inmueble_por_codigo`→None) + general → cae a las generales.

── FIX 2 [MEDIA · bloqueante] — handoff: la BD guarda lo que el lead NO vio ──
La persistencia del mensaje del agente (`:242-246`) ocurre ANTES del override de handoff (`:273-278`), y los
`ids` (`:241`) se calculan del `inmuebles_sugeridos` aún poblado. Resultado: en un turno con handoff, la BD
guarda el TEXTO de la propiedad + `metadata.inmuebles=[cod]`, aunque al lead se le devolvió el mensaje de
handoff sin fichas. Al **recargar el historial** reaparecen la ficha y el texto, contradiciendo "ya te
conecté con un asesor". (La divergencia de texto era pre-existente; el Prompt 1 amplió la de fichas.)
- Fix recomendado (menos riesgoso): guarda la referencia del mensaje que devuelve `agregar_mensaje(...)`; tras
  el override de handoff (`texto_final=_MENSAJE_HANDOFF; mapa=None; inmuebles_sugeridos=[]`), **actualiza ese
  mensaje** en BD: `contenido=texto_final` y `metadata={"inmuebles": []}` (+ `db.commit()`), o vía lead_service.
- Alternativa: reestructurar para persistir UNA sola vez tras el post-turno (ojo: `extraer_perfil` usa el
  historial — verifica que no dependa del mensaje del agente recién persistido antes de mover la persistencia).
- Test: turno con `buscar_inmuebles(codigo=X)` + `pide_humano=True` → consulta el mensaje del agente en BD:
  `contenido` = mensaje de handoff y `metadata["inmuebles"] == []`. (Hoy el test solo valida el retorno.)

── FIX 3 [BAJA] — cubrir la rama code-lookup del gate ──
Ningún test ejercita `buscar_inmuebles(codigo)` → `inmuebles_foco` (solo la rama `lugares_cerca`). Añade:
`buscar_inmuebles(codigo=X)` (llena foco) + `buscar_inmuebles(general)` en el mismo turno → sobrevive solo X.

── FIX 4 [BAJA] — marcador `[[MAPA:…]]` malformado se filtra crudo al cliente ──
`_MAPA_RE` (`:94`) es case-sensitive y estricto: `[[mapa:x]]`, `[[MAPA:9718612.]]` (punto pegado) o cierre con
un solo `]` no matchean → el marcador NO se limpia y el cliente lo VE, y no se dibuja mapa. Hazlo tolerante:
`re.IGNORECASE`, tolerar espacios/puntuación pegada al código. Test con marcador malformado (no debe filtrarse crudo).

── FIX 5 [BAJA] — turno degradado por error de API muestra ficha + "Ver mapa" ──
Si la 2ª `messages.create` lanza tras un `lugares_cerca` OK, el `except` fija `_MENSAJE_ERROR` pero el gate y
`_construir_mapa` corren igual → "tuve un problema técnico…" acompañado de una tarjeta y un botón "Ver mapa".
Fix: si `texto_final == _MENSAJE_ERROR`, fuerza `mapa=None` e `inmuebles_sugeridos=[]`.

── FIX 6 [BAJA · cosmético] — MapaCard sin onError ──
`frontend/src/components/MapaCard.tsx` (~:15-16): la `<img>` no tiene `onError` (PropertyCard sí, :52). URL
rota/hotlink → glifo de imagen rota bajo el velo. Replica el patrón `fotoError` de PropertyCard → cae al gradiente.

── FIX 7 [MUY BAJA] — encodeURIComponent en el href ──
`MapaCard.tsx:10`: `href={`/mapa/propiedad/${encodeURIComponent(mapa.codigo)}`}`.

VERIFICACIÓN: `cd backend && pytest -q` (226 + los nuevos, en verde) y `cd frontend && npm run build`. Reproduce
mentalmente el transcript: lugares_cerca(loma)+general → **solo loma** (sin regresión); lugares_cerca sin código
+ general → **las generales** (no 0); handoff → BD y retorno **coinciden** (sin ficha). Entrégame un resumen.
