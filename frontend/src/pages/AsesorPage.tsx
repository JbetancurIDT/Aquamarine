import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import apiClient from '../api/client'
import type { Asesor, Lead, NotificacionOut } from '../api/types'
import { KanbanBoard, type ColDef } from '../components/KanbanBoard'
import { LeadDetailModal } from '../components/LeadDetailModal'
import { TemperaturaBadge } from '../components/TemperaturaBadge'

const ASESOR_COLS: ColDef[] = [
  { estado: 'calificado',      label: 'Nuevo handoff',     color: '#5A6E3B' },
  { estado: 'negociando',      label: 'En gestión',        color: '#6B4C9E' },
  { estado: 'cerrado_ganado',  label: 'Cerrado · ganado',  color: '#2D7A4F' },
  { estado: 'cerrado_perdido', label: 'Cerrado · perdido', color: '#7A3D2D' },
]

// El asesor puede arrastrar hacia estas columnas (no puede regresar a calificado)
const ESTADOS_PERMITIDOS = ['negociando', 'cerrado_ganado', 'cerrado_perdido']

// Presentación de cada tipo de notificación (toast + campana)
const NOTIF_PRESENT: Record<string, { label: string; color: string; bg: string }> = {
  asignado:          { label: 'Nuevo lead asignado',          color: 'var(--champ)', bg: 'var(--champ-bg)' },
  notificacion:      { label: 'Recordatorio: lead sin atender', color: 'var(--warm)',  bg: 'var(--warm-bg)'  },
  reasignado:        { label: 'Lead reasignado a ti',          color: 'var(--cold)',  bg: 'var(--cold-bg)'  },
  tomado_por_humano: { label: 'Chat tomado',                   color: 'var(--champ)', bg: 'var(--champ-bg)' },
  handoff:           { label: 'Handoff recibido',              color: 'var(--champ)', bg: 'var(--champ-bg)' },
}

function presentar(tipo: string) {
  return NOTIF_PRESENT[tipo] ?? { label: tipo, color: 'var(--gray)', bg: 'var(--line-soft)' }
}

function hace(iso: string): string {
  const seg = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (seg < 60) return 'hace un momento'
  const min = Math.floor(seg / 60)
  if (min < 60) return `hace ${min} min`
  const h = Math.floor(min / 60)
  if (h < 24) return `hace ${h} h`
  return `hace ${Math.floor(h / 24)} d`
}

function resumenPerfil(perfil: Record<string, unknown>): string {
  return [perfil?.['tipo'], perfil?.['zona']].filter(Boolean).join(' · ')
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

type Toast = { id: string; tipo: string; detalle: string }

function ToastStack({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  return (
    <div className="fixed top-4 right-4 z-[60] flex flex-col gap-2 w-72">
      {toasts.map(t => {
        const p = presentar(t.tipo)
        return (
          <div
            key={t.id}
            className="rounded-xl px-4 py-3 shadow-lg border flex items-start gap-2 cursor-pointer"
            style={{ background: 'var(--card)', borderColor: p.color }}
            onClick={() => onDismiss(t.id)}
          >
            <span className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: p.color }} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold" style={{ color: p.color }}>{p.label}</p>
              {t.detalle && (
                <p className="text-xs truncate" style={{ color: 'var(--gray)' }}>{t.detalle}</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tarjeta "En vivo · sin asignar"
// ---------------------------------------------------------------------------

function EnVivoCard({
  lead, tomando, onTomar, onPreview,
}: {
  lead: Lead
  tomando: boolean
  onTomar: () => void
  onPreview: () => void
}) {
  const resumen = resumenPerfil(lead.perfil ?? {})
  return (
    <div
      className="flex-shrink-0 w-64 p-3 rounded-xl border flex flex-col gap-2"
      style={{ background: 'var(--card)', borderColor: 'var(--hot)' }}
    >
      <div className="flex items-start gap-2 cursor-pointer" onClick={onPreview}>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate" style={{ color: 'var(--ink)' }}>
            {lead.nombre ?? 'Lead sin nombre'}
          </p>
          {resumen && (
            <p className="text-xs truncate" style={{ color: 'var(--gray-soft)' }}>{resumen}</p>
          )}
        </div>
        <TemperaturaBadge temperatura={lead.temperatura} />
      </div>
      <div className="flex items-center gap-2">
        {lead.origen && (
          <span className="text-xs px-1.5 py-0.5 rounded-full"
            style={{ background: 'var(--line-soft)', color: 'var(--gray)' }}>
            {lead.origen}
          </span>
        )}
        <span className="text-xs ml-auto" style={{ color: 'var(--gray-soft)' }}>
          {hace(lead.actualizado_en)}
        </span>
      </div>
      <button
        onClick={onTomar}
        disabled={tomando}
        className="w-full py-2 rounded-lg text-sm font-semibold transition-opacity disabled:opacity-50"
        style={{ background: 'var(--charcoal)', color: 'var(--card)' }}
      >
        {tomando ? 'Tomando…' : 'Tomar este chat'}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AsesorPage
// ---------------------------------------------------------------------------

export default function AsesorPage() {
  const { asesorId } = useParams<{ asesorId: string }>()
  const [asesor, setAsesor]         = useState<Asesor | null>(null)
  const [asesores, setAsesores]     = useState<Asesor[]>([])
  const [leads, setLeads]           = useState<Lead[]>([])
  const [enVivo, setEnVivo]         = useState<Lead[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [cargando, setCargando]     = useState(true)
  const [error, setError]           = useState<string | null>(null)

  const [disponiendo, setDisponiendo] = useState(false)
  const [tomandoId, setTomandoId]     = useState<string | null>(null)

  const [toasts, setToasts]         = useState<Toast[]>([])
  const [notifs, setNotifs]         = useState<NotificacionOut[]>([])
  const [nuevas, setNuevas]         = useState(0)
  const [panelAbierto, setPanelAbierto] = useState(false)

  // Dedup de notificaciones ya vistas (no re-toastear en cada poll)
  const seenRef = useRef<Set<string>>(new Set())
  const primeraVezRef = useRef(true)

  // ── Fetchers ──────────────────────────────────────────────────────────────

  const cargarLeads = useCallback(async () => {
    if (!asesorId) return
    const { data } = await apiClient.get<Lead[]>(`/asesores/${asesorId}/leads`)
    setLeads(data)
  }, [asesorId])

  const cargarEnVivo = useCallback(async () => {
    const { data } = await apiClient.get<Lead[]>('/leads/en-vivo')
    setEnVivo(data)
  }, [])

  const pushToast = useCallback((tipo: string, detalle: string) => {
    const id = crypto.randomUUID()
    setToasts(prev => [...prev, { id, tipo, detalle }])
    window.setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 5000)
  }, [])

  const cargarNotifs = useCallback(async () => {
    if (!asesorId) return
    const { data } = await apiClient.get<NotificacionOut[]>(`/asesores/${asesorId}/notificaciones`)
    setNotifs(data)

    if (primeraVezRef.current) {
      // Primera carga: marca todo como visto, sin toasts
      data.forEach(n => seenRef.current.add(n.evento_id))
      primeraVezRef.current = false
      return
    }

    // Nuevas (vienen desc → recorre en orden cronológico para apilar bien)
    const nuevasNotifs = data.filter(n => !seenRef.current.has(n.evento_id)).reverse()
    if (nuevasNotifs.length > 0) {
      nuevasNotifs.forEach(n => {
        seenRef.current.add(n.evento_id)
        pushToast(n.tipo, resumenPerfil(n.perfil_resumen ?? {}))
      })
      setNuevas(prev => prev + nuevasNotifs.length)
    }
  }, [asesorId, pushToast])

  // ── Reset de dedup al cambiar de asesor (evita tormenta de toasts) ────────
  useEffect(() => {
    seenRef.current = new Set()
    primeraVezRef.current = true
    setNuevas(0)
  }, [asesorId])

  // ── Carga inicial ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!asesorId) return
    const init = async () => {
      try {
        const [asesoresRes] = await Promise.all([
          apiClient.get<Asesor[]>('/asesores'),
          cargarLeads(),
          cargarEnVivo(),
          cargarNotifs(),
        ])
        setAsesores(asesoresRes.data)
        setAsesor(asesoresRes.data.find(a => a.id === asesorId) ?? null)
      } catch {
        setError('No se pudo cargar la información del asesor.')
      } finally {
        setCargando(false)
      }
    }
    void init()
  }, [asesorId, cargarLeads, cargarEnVivo, cargarNotifs])

  // ── Polling combinado ~5 s ────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      void cargarLeads()
      void cargarEnVivo()
      void cargarNotifs()
    }, 5000)
    return () => clearInterval(id)
  }, [cargarLeads, cargarEnVivo, cargarNotifs])

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleMoverEstado = async (leadId: string, estado: string) => {
    setLeads(prev => prev.map(l => l.id === leadId ? { ...l, estado } : l))
    try {
      await apiClient.patch(`/leads/${leadId}/estado`, { estado })
    } catch {
      pushToast('notificacion', 'No se pudo mover el lead')
    } finally {
      await cargarLeads()  // re-sincroniza con el servidor (revierte si falló)
    }
  }

  const handleAsignarAsesor = (leadId: string, nuevoAsesorId: string | null) => {
    setLeads(prev => prev.map(l => l.id === leadId ? { ...l, asesor_id: nuevoAsesorId } : l))
  }

  const handleTomar = async (leadId: string) => {
    if (!asesorId) return
    setTomandoId(leadId)
    try {
      await apiClient.post(`/leads/${leadId}/tomar`, { asesor_id: asesorId })
      // cargarNotifs emite el toast `tomado_por_humano` UNA sola vez (evita el doble toast).
      await Promise.all([cargarLeads(), cargarEnVivo(), cargarNotifs()])
      setSelectedId(leadId)
    } catch {
      pushToast('notificacion', 'No se pudo tomar el chat')
    } finally {
      setTomandoId(null)
    }
  }

  const handleToggleDisponible = async () => {
    if (!asesor || disponiendo) return
    setDisponiendo(true)
    const nuevo = !asesor.disponible
    try {
      const { data } = await apiClient.patch<Asesor>(
        `/asesores/${asesor.id}/disponibilidad`, { disponible: nuevo },
      )
      setAsesor(data)
      setAsesores(prev => prev.map(a => a.id === data.id ? data : a))
    } finally {
      setDisponiendo(false)
    }
  }

  const abrirPanel = () => {
    setPanelAbierto(o => !o)
    setNuevas(0)
  }

  const handoffCount = leads.filter(l => l.estado === 'calificado').length

  // ── Render ────────────────────────────────────────────────────────────────

  if (cargando) {
    return (
      <div className="flex items-center justify-center h-screen" style={{ background: 'var(--bg)' }}>
        <p className="text-sm" style={{ color: 'var(--gray-soft)' }}>Cargando…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen" style={{ background: 'var(--bg)' }}>
        <p className="text-sm" style={{ color: '#B4543A' }}>{error}</p>
      </div>
    )
  }

  const disponible = asesor?.disponible ?? false

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>
      <ToastStack toasts={toasts} onDismiss={id => setToasts(prev => prev.filter(t => t.id !== id))} />

      {/* Header */}
      <header
        className="flex-shrink-0 border-b px-5 py-3 flex items-center justify-between gap-3"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        <div className="min-w-0">
          <h1 className="text-sm font-semibold truncate" style={{ color: 'var(--ink)' }}>
            Aqua<span className="italic" style={{ color: 'var(--champ)' }}>marine</span>
            <span className="font-normal" style={{ color: 'var(--gray-soft)' }}>
              {' '}· Asesor: {asesor?.nombre ?? asesorId}
            </span>
          </h1>
          {handoffCount > 0 && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--hot)' }}>
              {handoffCount} lead{handoffCount > 1 ? 's' : ''} pendiente{handoffCount > 1 ? 's' : ''} de tomar
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Disponibilidad */}
          <button
            onClick={handleToggleDisponible}
            disabled={disponiendo}
            className="text-xs px-3 py-1.5 rounded-full font-medium flex items-center gap-1.5 transition-opacity disabled:opacity-50 border"
            style={
              disponible
                ? { color: '#2D7A4F', background: '#E3F0E8', borderColor: '#BfDcc9' }
                : { color: 'var(--gray)', background: 'var(--line-soft)', borderColor: 'var(--line)' }
            }
            title="Cambiar disponibilidad"
          >
            <span className="w-2 h-2 rounded-full"
              style={{ background: disponible ? '#2D7A4F' : 'var(--gray-soft)' }} />
            {disponible ? 'Disponible' : 'No disponible'}
          </button>

          {/* Campana */}
          <div className="relative">
            <button
              onClick={abrirPanel}
              className="relative w-9 h-9 rounded-full flex items-center justify-center"
              style={{ background: 'var(--line-soft)', color: 'var(--gray)' }}
              title="Notificaciones"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                <path fillRule="evenodd" d="M10 2a6 6 0 00-6 6c0 1.887-.454 3.665-1.257 5.234a.75.75 0 00.515 1.076 32.91 32.91 0 003.256.508 3.5 3.5 0 006.972 0 32.903 32.903 0 003.256-.508.75.75 0 00.515-1.076A11.448 11.448 0 0116 8a6 6 0 00-6-6zm0 14.5a2 2 0 01-1.95-1.557 33.54 33.54 0 003.9 0A2 2 0 0110 16.5z" clipRule="evenodd" />
              </svg>
              {nuevas > 0 && (
                <span
                  className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full text-[10px] font-bold flex items-center justify-center"
                  style={{ background: 'var(--hot)', color: '#fff' }}
                >
                  {nuevas > 9 ? '9+' : nuevas}
                </span>
              )}
            </button>

            {/* Panel de notificaciones */}
            {panelAbierto && (
              <div
                className="absolute right-0 mt-2 w-80 rounded-xl border shadow-xl z-50 overflow-hidden"
                style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
              >
                <div className="px-4 py-2.5 border-b flex items-center justify-between"
                  style={{ borderColor: 'var(--line)' }}>
                  <span className="text-xs font-semibold" style={{ color: 'var(--ink)' }}>Notificaciones</span>
                  <button className="text-xs" style={{ color: 'var(--gray-soft)' }}
                    onClick={() => setPanelAbierto(false)}>✕</button>
                </div>
                <div className="max-h-80 overflow-y-auto scrollbar-brand">
                  {notifs.length === 0 ? (
                    <p className="text-xs text-center py-6" style={{ color: 'var(--gray-soft)' }}>
                      Sin notificaciones todavía.
                    </p>
                  ) : (
                    notifs.map(n => {
                      const p = presentar(n.tipo)
                      const res = resumenPerfil(n.perfil_resumen ?? {})
                      return (
                        <button
                          key={n.evento_id}
                          onClick={() => { setSelectedId(n.lead_id); setPanelAbierto(false) }}
                          className="w-full text-left px-4 py-2.5 border-b flex items-start gap-2 hover:bg-[var(--line-soft)] transition-colors"
                          style={{ borderColor: 'var(--line-soft)' }}
                        >
                          <span className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: p.color }} />
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium" style={{ color: p.color }}>{p.label}</p>
                            {res && <p className="text-xs truncate" style={{ color: 'var(--gray)' }}>{res}</p>}
                            <p className="text-[11px]" style={{ color: 'var(--gray-soft)' }}>{hace(n.creado_en)}</p>
                          </div>
                        </button>
                      )
                    })
                  )}
                </div>
              </div>
            )}
          </div>

          <Link to="/asesores" className="text-xs px-3 py-1.5 rounded-lg"
            style={{ color: 'var(--gray)', background: 'var(--line-soft)' }}>
            ← Asesores
          </Link>
          <Link to="/performance" className="text-xs px-3 py-1.5 rounded-lg"
            style={{ color: 'var(--gray)', background: 'var(--line-soft)' }}>
            Performance
          </Link>
          <Link to="/dashboard" className="text-xs px-3 py-1.5 rounded-lg"
            style={{ color: 'var(--gray)', background: 'var(--line-soft)' }}>
            Dashboard
          </Link>
        </div>
      </header>

      {/* En vivo · sin asignar */}
      {enVivo.length > 0 && (
        <div
          className="flex-shrink-0 border-b px-4 py-3"
          style={{ background: 'var(--hot-bg)', borderColor: 'var(--line)' }}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--hot)' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--hot)' }}>
              En vivo · sin asignar ({enVivo.length})
            </span>
          </div>
          <div className="flex gap-3 overflow-x-auto scrollbar-brand pb-1">
            {enVivo.map(lead => (
              <EnVivoCard
                key={lead.id}
                lead={lead}
                tomando={tomandoId === lead.id}
                onTomar={() => void handleTomar(lead.id)}
                onPreview={() => setSelectedId(lead.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Kanban — 4 columnas del asesor */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden p-4 scrollbar-brand">
        <KanbanBoard
          columnas={ASESOR_COLS}
          leads={leads}
          asesores={asesores}
          selectedId={selectedId}
          onCardClick={setSelectedId}
          onMoverEstado={handleMoverEstado}
          estadosPermitidos={ESTADOS_PERMITIDOS}
        />
      </div>

      {/* Modal de detalle (modo asesor: chat + sin select de asesor) */}
      {selectedId && (
        <LeadDetailModal
          leadId={selectedId}
          asesores={asesores}
          onClose={() => setSelectedId(null)}
          onMoverEstado={handleMoverEstado}
          onAsignarAsesor={handleAsignarAsesor}
          transicionesPermitidas={ESTADOS_PERMITIDOS}
          modoAsesor
          onTomar={handleTomar}
        />
      )}
    </div>
  )
}
