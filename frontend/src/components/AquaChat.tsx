import { useEffect, useRef, useState } from 'react'
import apiClient from '../api/client'
import type { InsightsResponse } from '../api/types'
import { MarkdownMessage } from './MarkdownMessage'

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------

const PRESETS = [
  '¿Cuál es el % de conversión del embudo?',
  '¿Cuántos leads calientes hay ahora?',
  '¿Cómo van los asesores?',
  '¿Quién es el mejor asesor?',
  '¿Cuánto hemos cerrado por mes?',
  '¿Cuántos leads nuevos entraron por mes?',
  '¿De qué canal llegan más leads?',
  'Dame un resumen de cómo vamos.',
]

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Msg = {
  role: 'user' | 'aqua'
  text: string
  datos?: Record<string, unknown> | null
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-3 py-2.5 rounded-2xl rounded-bl-sm"
      style={{ background: 'var(--bg)', border: '1px solid var(--line)', width: 'fit-content' }}>
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="block w-1.5 h-1.5 rounded-full"
          style={{
            background: 'var(--champ)',
            animation: 'aqua-bounce 1.2s ease-in-out infinite',
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
    </div>
  )
}

function AquaBubble({ msg }: { msg: Msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div
          className="px-3 py-2 rounded-2xl rounded-br-sm text-sm max-w-[78%]"
          style={{ background: 'var(--champ-bg)', color: 'var(--ink)', border: '1px solid var(--champ-soft)' }}
        >
          {msg.text}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="flex flex-col gap-1.5 max-w-[86%] min-w-0">
        <div
          className="px-3 py-2 rounded-2xl rounded-bl-sm text-sm min-w-0 max-w-full"
          style={{ background: 'var(--bg)', color: 'var(--ink)', border: '1px solid var(--line)' }}
        >
          <MarkdownMessage text={msg.text} />
        </div>
      </div>
    </div>
  )
}

function PresetMenu({
  presets,
  onSelect,
}: {
  presets: string[]
  onSelect: (p: string) => void
}) {
  return (
    <div
      className="absolute bottom-full left-0 right-0 mb-1 rounded-xl overflow-hidden border scrollbar-brand"
      style={{
        background: 'var(--card)',
        borderColor: 'var(--line)',
        boxShadow: '0 -4px 20px rgba(0,0,0,0.12)',
        maxHeight: '220px',
        overflowY: 'auto',
      }}
    >
      {presets.map((p, i) => (
        <button
          key={i}
          className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--champ-bg)] transition-colors"
          style={{ color: 'var(--ink)', borderBottom: '1px solid var(--line-soft)' }}
          onMouseDown={e => { e.preventDefault(); onSelect(p) }}
        >
          <span style={{ color: 'var(--champ)' }} className="mr-2 text-xs">✦</span>
          {p}
        </button>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AquaChat — FAB + panel flotante
// ---------------------------------------------------------------------------

export function AquaChat() {
  const [open,       setOpen]       = useState(false)
  const [messages,   setMessages]   = useState<Msg[]>([])
  const [input,      setInput]      = useState('')
  const [loading,    setLoading]    = useState(false)
  const [showMenu,   setShowMenu]   = useState(false)

  const inputRef  = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Focus input when panel opens
  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 200)
      return () => clearTimeout(t)
    }
  }, [open])

  const sendQuestion = async (pregunta: string) => {
    const q = pregunta.trim()
    if (!q || loading) return
    setInput('')
    setShowMenu(false)
    setMessages(prev => [...prev, { role: 'user', text: q }])
    setLoading(true)
    try {
      const { data } = await apiClient.post<InsightsResponse>('/insights/ask', { pregunta: q })
      setMessages(prev => [...prev, { role: 'aqua', text: data.respuesta, datos: data.datos }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'aqua',
        text: 'No pude conectarme con el servidor. Intenta de nuevo en un momento.',
        datos: null,
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!showMenu) sendQuestion(input)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setInput(val)
    setShowMenu(val.startsWith('/'))
  }

  const presetFilter    = input.startsWith('/') ? input.slice(1).toLowerCase() : ''
  const filteredPresets = PRESETS.filter(p =>
    !presetFilter || p.toLowerCase().includes(presetFilter)
  )

  const panelVisible = open

  return (
    <>
      {/* Animación keyframes — inyectada una vez */}
      <style>{`
        @keyframes aqua-bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
          40% { transform: translateY(-5px); opacity: 1; }
        }
        @keyframes aqua-panel-in {
          from { opacity: 0; transform: translateY(12px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0)  scale(1); }
        }
      `}</style>

      {/* ── Panel flotante ─────────────────────────────────────────────── */}
      {panelVisible && (
        <div
          style={{
            position:      'fixed',
            bottom:        '72px',
            right:         '24px',
            width:         '380px',
            maxWidth:      'calc(100vw - 48px)',
            height:        '520px',
            maxHeight:     'calc(100vh - 120px)',
            background:    'var(--card)',
            border:        '1px solid var(--line)',
            borderRadius:  '20px',
            boxShadow:     '0 8px 40px rgba(0,0,0,0.18)',
            display:       'flex',
            flexDirection: 'column',
            overflow:      'hidden',
            zIndex:        50,
            animation:     'aqua-panel-in 0.22s ease-out',
          }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-4 py-3 flex-shrink-0"
            style={{ borderBottom: '1px solid var(--line)', background: 'var(--card)' }}
          >
            <div className="flex items-center gap-2">
              <span style={{ color: 'var(--champ)', fontSize: '15px' }}>✦</span>
              <span className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
                Aqua<span className="italic" style={{ color: 'var(--champ)' }}>marine</span>
                <span className="font-normal" style={{ color: 'var(--gray-soft)' }}> · Asistente</span>
              </span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="w-7 h-7 flex items-center justify-center rounded-lg text-sm transition-colors hover:bg-[var(--line-soft)]"
              style={{ color: 'var(--gray-soft)' }}
              aria-label="Cerrar"
            >
              ✕
            </button>
          </div>

          {/* Messages */}
          <div
            className="flex-1 overflow-y-auto scrollbar-brand px-4 py-3 flex flex-col gap-3"
            style={{ background: 'var(--bg)' }}
          >
            {/* Saludo inicial */}
            {messages.length === 0 && (
              <>
                <div
                  className="px-3 py-2 rounded-2xl rounded-bl-sm text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--line)', color: 'var(--ink)', width: 'fit-content', maxWidth: '86%' }}
                >
                  Hola, Claudia 👋 ¿Qué quieres saber hoy?
                </div>
                {/* Chips de sugerencias */}
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {PRESETS.slice(0, 4).map((p, i) => (
                    <button
                      key={i}
                      onClick={() => sendQuestion(p)}
                      disabled={loading}
                      className="px-2.5 py-1 rounded-full text-xs border transition-colors hover:border-[var(--champ)] hover:text-[var(--champ)]"
                      style={{
                        background:   'var(--card)',
                        borderColor:  'var(--line)',
                        color:        'var(--gray)',
                        whiteSpace:   'nowrap',
                        maxWidth:     '100%',
                        textOverflow: 'ellipsis',
                        overflow:     'hidden',
                      }}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </>
            )}

            {messages.map((msg, i) => <AquaBubble key={i} msg={msg} />)}

            {loading && (
              <div className="flex justify-start">
                <TypingDots />
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div
            className="flex-shrink-0 px-3 py-3 relative"
            style={{ borderTop: '1px solid var(--line)', background: 'var(--card)' }}
          >
            {showMenu && filteredPresets.length > 0 && (
              <PresetMenu presets={filteredPresets} onSelect={sendQuestion} />
            )}
            <form onSubmit={handleSubmit} className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={handleInputChange}
                onKeyDown={e => {
                  if (e.key === 'Escape') { setShowMenu(false); setInput('') }
                }}
                disabled={loading}
                placeholder="Pregunta o escribe / para sugerencias…"
                className="flex-1 text-sm px-3 py-2 rounded-xl border outline-none transition-colors"
                style={{
                  background:   'var(--bg)',
                  borderColor:  'var(--line)',
                  color:        'var(--ink)',
                }}
                onFocus={e => (e.target.style.borderColor = 'var(--champ)')}
                onBlur={e  => (e.target.style.borderColor = 'var(--line)')}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="w-8 h-8 rounded-xl flex items-center justify-center text-sm font-bold flex-shrink-0 transition-opacity disabled:opacity-40"
                style={{ background: 'var(--charcoal)', color: 'var(--champ)' }}
                aria-label="Enviar"
              >
                ↑
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ── FAB ─────────────────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen(prev => !prev)}
        style={{
          position:     'fixed',
          bottom:       '24px',
          right:        '24px',
          background:   'var(--charcoal)',
          color:        '#fff',
          borderRadius: '24px',
          padding:      '10px 18px',
          display:      'flex',
          alignItems:   'center',
          gap:          '8px',
          zIndex:       50,
          border:       'none',
          cursor:       'pointer',
          boxShadow:    '0 4px 20px rgba(0,0,0,0.25)',
          transition:   'box-shadow 0.2s',
        }}
        onMouseEnter={e => ((e.currentTarget as HTMLElement).style.boxShadow = '0 6px 28px rgba(0,0,0,0.35)')}
        onMouseLeave={e => ((e.currentTarget as HTMLElement).style.boxShadow = '0 4px 20px rgba(0,0,0,0.25)')}
      >
        <span style={{ color: 'var(--champ)', fontSize: '14px', lineHeight: 1 }}>✦</span>
        <span style={{ fontSize: '13px', fontWeight: 600, letterSpacing: '0.01em' }}>
          {open ? 'Cerrar' : 'Asistente'}
        </span>
      </button>
    </>
  )
}
