import React, { useCallback, useEffect, useRef, useState } from 'react'
import apiClient from '../api/client'
import type { Asesor, Lead, LeadConMensajes, Mensaje } from '../api/types'
import { TemperaturaBadge } from './TemperaturaBadge'
import { MarkdownMessage } from './MarkdownMessage'

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

const ESTADO_ESTILO: Record<string, React.CSSProperties> = {
  nuevo:           { color: 'var(--cold)',  background: 'var(--cold-bg)'  },
  contactado:      { color: 'var(--warm)',  background: 'var(--warm-bg)'  },
  calificado:      { color: '#5A6E3B',      background: '#EBF0E3'         },
  negociando:      { color: '#6B4C9E',      background: '#F0EBF8'         },
  cerrado_ganado:  { color: '#2D7A4F',      background: '#E3F0E8'         },
  cerrado_perdido: { color: '#7A3D2D',      background: '#F0E3DE'         },
  descartado:      { color: 'var(--gray)',  background: 'var(--line-soft)'},
}

type Transicion = { label: string; estado: string; primary?: boolean }

const TRANSICIONES_MAPA: Record<string, Transicion[]> = {
  nuevo:       [{ label: 'Contactar',        estado: 'contactado',      primary: true  }],
  contactado:  [{ label: 'Calificar',         estado: 'calificado',      primary: true  }],
  calificado:  [{ label: 'Tomar lead →',      estado: 'negociando',      primary: true  }],
  negociando:  [
    { label: 'Cerrar ganado',  estado: 'cerrado_ganado',  primary: true  },
    { label: 'Cerrar perdido', estado: 'cerrado_perdido'                  },
  ],
}

const CAMPOS_PERFIL = [
  { key: 'tipo',            etiqueta: 'Tipo'             },
  { key: 'zona',            etiqueta: 'Zona'             },
  { key: 'ciudad',          etiqueta: 'Ciudad'           },
  { key: 'presupuesto_min', etiqueta: 'Presupuesto mín.' },
  { key: 'presupuesto_max', etiqueta: 'Presupuesto máx.' },
  { key: 'habitaciones',    etiqueta: 'Habitaciones'     },
  { key: 'plazo',           etiqueta: 'Plazo'            },
  { key: 'notas',           etiqueta: 'Notas'            },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function copM(cop: number): string {
  return `$${(cop / 1_000_000).toLocaleString('es-CO', { maximumFractionDigits: 0 })} M`
}

function formatFecha(iso: string): string {
  return new Date(iso).toLocaleDateString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

function formatHHMM(iso: string): string {
  return new Date(iso).toLocaleTimeString('es-CO', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

function diasSinGestion(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
}

// ---------------------------------------------------------------------------
// Sub-componentes internos
// ---------------------------------------------------------------------------

function EstadoBadge({ estado }: { estado: string }) {
  const s = ESTADO_ESTILO[estado] ?? { color: 'var(--gray)', background: 'var(--line-soft)' }
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={s}>
      {estado.replace('_', ' ')}
    </span>
  )
}

function BurbujaTimeline({ m }: { m: Mensaje }) {
  const esLead   = m.rol === 'lead'
  const esAsesor = m.rol === 'asesor'
  // Markdown solo para la IA ('agente'): el texto tecleado por lead/asesor humano va plano.
  const esTextoPlano = esLead || esAsesor
  return (
    <div className={`flex ${esLead ? 'justify-end' : 'justify-start'} mb-2`}>
      <div className={`max-w-[80%] min-w-0 flex flex-col gap-0.5 ${esLead ? 'items-end' : 'items-start'}`}>
        {esAsesor && (
          <span className="text-xs px-1" style={{ color: 'var(--champ)' }}>Asesor</span>
        )}
        <div
          className={`px-3 py-2 rounded-2xl text-sm break-words min-w-0 max-w-full${esTextoPlano ? ' whitespace-pre-wrap' : ''}`}
          style={
            esLead
              ? { background: 'var(--charcoal)', color: 'var(--card)', borderBottomRightRadius: '5px' }
              : { background: 'var(--line-soft)', color: 'var(--ink)',  borderBottomLeftRadius:  '5px' }
          }
        >
          {esTextoPlano ? m.contenido : <MarkdownMessage text={m.contenido} />}
        </div>
        <span className="text-xs px-1" style={{ color: 'var(--gray-soft)' }}>
          {formatHHMM(m.creado_en)}
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// LeadDetailModal
// ---------------------------------------------------------------------------

export interface LeadDetailModalProps {
  leadId: string
  asesores: Asesor[]
  onClose: () => void
  onMoverEstado: (leadId: string, estado: string) => void
  onAsignarAsesor: (leadId: string, asesorId: string | null) => void
  /** Si se proporciona, solo se muestran botones para estas transiciones destino. */
  transicionesPermitidas?: string[]
  /** Modo asesor: oculta el select de asesor y muestra compositor de mensajes. */
  modoAsesor?: boolean
  /** Callback para tomar el chat (POST /leads/{id}/tomar). Requerido para componer en modoAsesor. */
  onTomar?: (leadId: string) => Promise<void> | void
}

export function LeadDetailModal({
  leadId, asesores, onClose, onMoverEstado, onAsignarAsesor, transicionesPermitidas, modoAsesor, onTomar,
}: LeadDetailModalProps) {
  const [lead, setLead]               = useState<LeadConMensajes | null>(null)
  const [actualizando, setActualizando] = useState(false)
  const [asignando, setAsignando]     = useState(false)
  const [moviendo, setMoviendo]       = useState<string | null>(null)
  const [msgTexto, setMsgTexto]       = useState('')
  const [enviando, setEnviando]       = useState(false)
  const [tomando, setTomando]         = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const cargar = useCallback(async () => {
    setActualizando(true)
    try {
      const { data } = await apiClient.get<LeadConMensajes>(`/leads/${leadId}`)
      setLead(data)
    } finally {
      setActualizando(false)
    }
  }, [leadId])

  useEffect(() => { void cargar() }, [cargar])

  // Polling 4.5 s
  useEffect(() => {
    const id = setInterval(() => void cargar(), 4500)
    return () => clearInterval(id)
  }, [cargar])

  // Auto-scroll al último mensaje
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lead?.mensajes?.length])

  // Cerrar con Esc
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleAsignar = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value || null
    setAsignando(true)
    try {
      const { data } = await apiClient.patch<Lead>(`/leads/${leadId}/asesor`, { asesor_id: val })
      setLead(prev => prev ? { ...prev, asesor_id: data.asesor_id } : prev)
      onAsignarAsesor(leadId, val)
    } finally {
      setAsignando(false)
    }
  }

  const handleMover = async (estado: string) => {
    setMoviendo(estado)
    try {
      await apiClient.patch(`/leads/${leadId}/estado`, { estado })
      setLead(prev => prev ? { ...prev, estado } : prev)
      onMoverEstado(leadId, estado)
    } finally {
      setMoviendo(null)
    }
  }

  const handleEnviarMensaje = async () => {
    const contenido = msgTexto.trim()
    if (!contenido || enviando) return
    setEnviando(true)
    try {
      await apiClient.post(`/leads/${leadId}/mensajes`, { rol: 'asesor', contenido })
      setMsgTexto('')
      await cargar()
    } finally {
      setEnviando(false)
    }
  }

  const handleTomarClick = async () => {
    if (!onTomar) return
    setTomando(true)
    try {
      await onTomar(leadId)
      await cargar()  // refresca: atendido_por_humano=true → aparece el compositor
    } finally {
      setTomando(false)
    }
  }

  // Loading inicial
  if (!lead) {
    return (
      <div
        className="fixed inset-0 flex items-center justify-center z-50"
        style={{ background: 'rgba(26,26,26,.45)' }}
        onClick={onClose}
      >
        <div className="rounded-2xl p-8" style={{ background: 'var(--card)' }}
             onClick={e => e.stopPropagation()}>
          <p className="text-sm" style={{ color: 'var(--gray-soft)' }}>Cargando…</p>
        </div>
      </div>
    )
  }

  // Datos derivados
  const perfil           = lead.perfil ?? {}
  const camposConValor   = CAMPOS_PERFIL.filter(c => perfil[c.key] != null)
  const scoreW           = lead.score != null ? Math.max(0, Math.min(100, lead.score)) : 0
  const dias             = diasSinGestion(lead.actualizado_en)
  const valor            = typeof perfil.presupuesto_max === 'number' ? perfil.presupuesto_max : null

  const transiciones = (TRANSICIONES_MAPA[lead.estado] ?? []).filter(t =>
    !transicionesPermitidas || transicionesPermitidas.includes(t.estado),
  )

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50 p-4"
      style={{ background: 'rgba(26,26,26,.45)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="flex flex-col rounded-2xl shadow-2xl overflow-hidden"
        style={{ width: 'min(900px, 94vw)', maxHeight: '88vh', background: 'var(--card)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header fijo ── */}
        <div
          className="flex-shrink-0 px-6 py-4 border-b flex items-start justify-between gap-4"
          style={{ borderColor: 'var(--line)' }}
        >
          <div className="flex flex-col gap-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2
                className="text-lg font-semibold"
                style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}
              >
                {lead.nombre ?? 'Lead sin nombre'}
              </h2>
              <TemperaturaBadge temperatura={lead.temperatura} />
              <EstadoBadge estado={lead.estado} />
            </div>
            <p className="text-xs" style={{ color: 'var(--gray-soft)' }}>
              {[lead.origen, lead.contacto].filter(Boolean).join(' · ')}
            </p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {actualizando && (
              <span className="text-xs" style={{ color: 'var(--gray-soft)' }}>actualizando…</span>
            )}
            <button
              onClick={onClose}
              className="text-sm px-3 py-1.5 rounded-lg"
              style={{ color: 'var(--gray)', background: 'var(--line-soft)' }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* ── Body: 2 columnas con scroll independiente ── */}
        <div className="flex-1 overflow-hidden flex min-h-0">

          {/* Columna izquierda — datos del lead */}
          <div
            className="overflow-y-auto scrollbar-brand flex-shrink-0 border-r"
            style={{ width: '300px', borderColor: 'var(--line)' }}
          >
            {/* Score IA */}
            {lead.score != null && (
              <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--line)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold" style={{ color: 'var(--gray-soft)' }}>
                    Score IA
                  </span>
                  <span className="text-sm font-mono font-semibold" style={{ color: 'var(--ink)' }}>
                    {lead.score}/100
                  </span>
                </div>
                <div className="rounded-full overflow-hidden" style={{ height: '6px', background: 'var(--line-soft)' }}>
                  <div
                    style={{
                      width: `${scoreW}%`, height: '100%', borderRadius: 'inherit',
                      background: scoreW >= 70 ? 'var(--hot)' : scoreW >= 40 ? 'var(--warm)' : 'var(--cold)',
                      transition: 'width 0.4s',
                    }}
                  />
                </div>
              </div>
            )}

            {/* Asesor asignado — oculto en modoAsesor */}
            {!modoAsesor && (
              <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--line)' }}>
                <p className="text-xs font-semibold mb-2" style={{ color: 'var(--gray-soft)' }}>
                  Asesor asignado
                </p>
                <select
                  className="w-full text-sm px-3 py-1.5 rounded-lg border"
                  style={{
                    background: 'var(--bg)', borderColor: 'var(--line)', color: 'var(--ink)',
                    opacity: asignando ? 0.5 : 1,
                  }}
                  value={lead.asesor_id ?? ''}
                  onChange={handleAsignar}
                  disabled={asignando}
                >
                  <option value="">Sin asesor</option>
                  {asesores.map(a => <option key={a.id} value={a.id}>{a.nombre}</option>)}
                </select>
              </div>
            )}

            {/* Acciones rápidas */}
            {transiciones.length > 0 && (
              <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--line)' }}>
                <p className="text-xs font-semibold mb-2" style={{ color: 'var(--gray-soft)' }}>
                  Acciones rápidas
                </p>
                <div className="flex flex-col gap-2">
                  {transiciones.map(t => (
                    <button
                      key={t.estado}
                      onClick={() => handleMover(t.estado)}
                      disabled={!!moviendo}
                      className="w-full py-2.5 rounded-xl text-sm font-semibold transition-opacity disabled:opacity-50"
                      style={
                        t.primary
                          ? { background: 'var(--charcoal)', color: 'var(--card)' }
                          : { background: 'var(--line-soft)', color: 'var(--ink)'  }
                      }
                    >
                      {moviendo === t.estado ? '…' : t.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Perfil de búsqueda */}
            {camposConValor.length > 0 && (
              <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--line)', background: 'var(--champ-bg)' }}>
                <p className="text-xs font-semibold mb-3" style={{ color: 'var(--champ)' }}>
                  Perfil de búsqueda
                </p>
                <div className="flex flex-col gap-1.5">
                  {camposConValor.map(({ key, etiqueta }) => (
                    <div key={key} className="flex items-baseline gap-1 flex-wrap">
                      <span className="text-xs" style={{ color: 'var(--gray-soft)' }}>{etiqueta}:</span>
                      <span className="text-xs font-medium" style={{ color: 'var(--ink)' }}>
                        {key.startsWith('presupuesto') && typeof perfil[key] === 'number'
                          ? copM(perfil[key] as number)
                          : String(perfil[key])}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Metadata: valor, días sin gestión, idioma, fechas */}
            <div className="px-5 py-4">
              <div className="flex flex-col gap-2">
                {valor !== null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs" style={{ color: 'var(--gray-soft)' }}>Valor estimado</span>
                    <span className="text-sm font-semibold" style={{ color: 'var(--champ)' }}>
                      {copM(valor)}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-xs" style={{ color: 'var(--gray-soft)' }}>Sin gestión</span>
                  <span
                    className="text-xs font-medium"
                    style={{ color: dias >= 4 ? 'var(--hot)' : 'var(--ink)' }}
                  >
                    {dias === 0 ? 'Hoy' : `${dias} d`}
                  </span>
                </div>
                {lead.idioma && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs" style={{ color: 'var(--gray-soft)' }}>Idioma</span>
                    <span className="text-xs font-medium" style={{ color: 'var(--ink)' }}>
                      {lead.idioma}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-between gap-4">
                  <span className="text-xs flex-shrink-0" style={{ color: 'var(--gray-soft)' }}>Creado</span>
                  <span className="text-xs text-right" style={{ color: 'var(--gray)' }}>
                    {formatFecha(lead.creado_en)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-xs flex-shrink-0" style={{ color: 'var(--gray-soft)' }}>Actualizado</span>
                  <span className="text-xs text-right" style={{ color: 'var(--gray)' }}>
                    {formatFecha(lead.actualizado_en)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Columna derecha — conversación + (opcional) compositor */}
          <div className="flex-1 flex flex-col min-w-0 min-h-0">
            <div className="flex-1 overflow-y-auto scrollbar-brand-thin px-5 py-4 min-h-0">
              {lead.mensajes.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <p className="text-sm text-center" style={{ color: 'var(--gray-soft)' }}>
                    Sin mensajes todavía.
                  </p>
                </div>
              ) : (
                lead.mensajes.map(m => <BurbujaTimeline key={m.id} m={m} />)
              )}
              <div ref={bottomRef} />
            </div>

            {/* Sin tomar todavía: botón para tomar el chat (no se puede componer con la IA activa) */}
            {modoAsesor && !lead.atendido_por_humano && onTomar && (
              <div
                className="flex-shrink-0 border-t px-4 py-3"
                style={{ borderColor: 'var(--line)', background: 'var(--card)' }}
              >
                <button
                  onClick={() => void handleTomarClick()}
                  disabled={tomando}
                  className="w-full py-2.5 rounded-xl text-sm font-semibold transition-opacity disabled:opacity-50"
                  style={{ background: 'var(--charcoal)', color: 'var(--card)' }}
                >
                  {tomando ? 'Tomando…' : 'Tomar este chat para responder'}
                </button>
                <p className="text-xs text-center mt-1.5" style={{ color: 'var(--gray-soft)' }}>
                  La IA sigue activa hasta que tomes el chat.
                </p>
              </div>
            )}

            {/* Compositor del asesor (solo cuando el chat ya fue tomado) */}
            {modoAsesor && lead.atendido_por_humano && (
              <div
                className="flex-shrink-0 border-t px-4 py-3 flex items-end gap-2"
                style={{ borderColor: 'var(--line)', background: 'var(--card)' }}
              >
                <textarea
                  rows={1}
                  value={msgTexto}
                  onChange={e => setMsgTexto(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      void handleEnviarMensaje()
                    }
                  }}
                  disabled={enviando}
                  placeholder="Escribe tu respuesta al lead…"
                  className="flex-1 resize-none text-sm focus:outline-none disabled:opacity-50 max-h-20 leading-snug bg-transparent"
                  style={{
                    minHeight: '2.25rem',
                    border: '1px solid var(--line)',
                    borderRadius: '999px',
                    padding: '0.4rem 0.9rem',
                    color: 'var(--ink)',
                  }}
                />
                <button
                  onClick={() => void handleEnviarMensaje()}
                  disabled={enviando || !msgTexto.trim()}
                  className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center transition-opacity disabled:opacity-40"
                  style={{ background: 'var(--champ)', color: '#fff' }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                    <path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" />
                  </svg>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
