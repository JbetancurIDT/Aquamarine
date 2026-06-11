import React, { useEffect, useRef, useState, KeyboardEvent } from 'react'
import { useParams } from 'react-router-dom'
import { useChatSession, type Mensaje } from '../hooks/useChatSession'
import { PropertyCardList } from '../components/PropertyCard'

type TemperaturaKey = 'desconocido' | 'frio' | 'tibio' | 'caliente'

const TEMPERATURA_BADGE: Record<TemperaturaKey, { style: React.CSSProperties; etiqueta: string }> = {
  desconocido: { style: { color: 'var(--unknown)', background: 'var(--unknown-bg)' }, etiqueta: '—' },
  frio:        { style: { color: 'var(--cold)',    background: 'var(--cold-bg)'    }, etiqueta: 'Frío' },
  tibio:       { style: { color: 'var(--warm)',    background: 'var(--warm-bg)'    }, etiqueta: 'Tibio' },
  caliente:    { style: { color: 'var(--hot)',     background: 'var(--hot-bg)'     }, etiqueta: 'Caliente' },
}

function formatHHMM(date: Date): string {
  return date.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function BurbujaMensaje({ mensaje }: { mensaje: Mensaje }) {
  const esLead = mensaje.rol === 'lead'
  return (
    <div className={`flex ${esLead ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className={`max-w-[85%] ${esLead ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        <div
          className="px-4 py-2 rounded-2xl text-sm whitespace-pre-wrap break-words"
          style={
            esLead
              ? { background: 'var(--charcoal)', color: 'var(--card)', borderBottomRightRadius: '5px' }
              : { background: 'var(--card)', color: 'var(--ink)', borderBottomLeftRadius: '5px',
                  boxShadow: '0 1px 3px rgba(26,26,26,.08)' }
          }
        >
          {mensaje.contenido}
        </div>
        {!esLead && mensaje.inmuebles && mensaje.inmuebles.length > 0 && (
          <PropertyCardList inmuebles={mensaje.inmuebles} />
        )}
        <span className="text-xs px-1" style={{ color: 'var(--gray-soft)' }}>
          {formatHHMM(mensaje.timestamp)}
        </span>
      </div>
    </div>
  )
}

function IndicadorEscribiendo() {
  return (
    <div className="flex justify-start mb-3">
      <div
        className="rounded-2xl px-4 py-3 flex gap-1 items-center"
        style={{ background: 'var(--card)', boxShadow: '0 1px 3px rgba(26,26,26,.08)' }}
      >
        <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:0ms]"
              style={{ background: 'var(--gray-soft)' }} />
        <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:150ms]"
              style={{ background: 'var(--gray-soft)' }} />
        <span className="w-2 h-2 rounded-full animate-bounce [animation-delay:300ms]"
              style={{ background: 'var(--gray-soft)' }} />
      </div>
    </div>
  )
}

export default function ChatPage() {
  const { origen } = useParams<{ origen?: string }>()
  const { mensajes, temperatura, cargando, error, handoff, enviar } = useChatSession(origen)
  const [texto, setTexto] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes, cargando])

  const badge =
    TEMPERATURA_BADGE[(temperatura as TemperaturaKey)] ?? TEMPERATURA_BADGE.desconocido

  function handleEnviar() {
    const contenido = texto.trim()
    if (!contenido || cargando) return
    setTexto('')
    void enviar(contenido)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleEnviar()
    }
  }

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>

      {/* Header */}
      <header
        className="flex-shrink-0 border-b px-4 py-3 flex items-center gap-3"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        {/* Avatar "A" serif itálico */}
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
          style={{ background: 'var(--charcoal)' }}
        >
          <span
            className="italic text-base leading-none"
            style={{ color: 'var(--card)', fontFamily: 'Newsreader, Georgia, serif', fontWeight: 600 }}
          >
            A
          </span>
        </div>

        <div className="flex-1 min-w-0">
          <h1 className="text-sm font-semibold leading-tight" style={{ color: 'var(--ink)' }}>
            Aqua<span className="italic" style={{ color: 'var(--champ)' }}>marine</span>
            <span style={{ color: 'var(--gray-soft)' }}> · Asistente Inmobiliario</span>
          </h1>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--gray-soft)' }}>
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
              en línea
            </span>
            {origen && (
              <span
                className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border"
                style={{
                  borderColor: 'var(--champ-soft)',
                  color: 'var(--gray)',
                  background: 'var(--bg)',
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full inline-block"
                  style={{ background: 'var(--champ-soft)' }}
                />
                vía {origen}
              </span>
            )}
          </div>
        </div>

        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0"
          style={badge.style}
        >
          {badge.etiqueta}
        </span>
      </header>

      {/* Lista de mensajes */}
      <main className="flex-1 overflow-y-auto px-4 py-4">
        {mensajes.length === 0 && !cargando && (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-center" style={{ color: 'var(--gray-soft)' }}>
              Hola, soy Aqua. Cuéntame qué tipo de inmueble estás buscando.
            </p>
          </div>
        )}

        {mensajes.map((m) => (
          <BurbujaMensaje key={m.id} mensaje={m} />
        ))}

        {cargando && <IndicadorEscribiendo />}

        {/* Bloque de handoff */}
        {handoff && (
          <div className="flex justify-start mb-3">
            <div
              className="rounded-2xl p-4 flex flex-col gap-3 max-w-[80%]"
              style={{
                background: 'var(--card)',
                border: '1px solid var(--line)',
                boxShadow: '0 1px 3px rgba(26,26,26,.08)',
              }}
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ background: 'var(--wa)' }} />
                <span className="text-sm font-medium" style={{ color: 'var(--ink)' }}>
                  Conectando con un asesor
                </span>
              </div>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--gray)' }}>
                Un asesor de IDEAL Real Estate se comunicará contigo pronto.
              </p>
              <a
                href="https://wa.me/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-center text-sm font-semibold py-2.5 px-4 rounded-xl w-full"
                style={{ background: 'var(--wa)', color: '#FFFFFF' }}
              >
                Continuar por WhatsApp
              </a>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      {/* Zona inferior: error + input */}
      <div
        className="flex-shrink-0 border-t"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        {error && (
          <div className="px-4 pt-2">
            <p
              className="text-xs rounded-lg px-3 py-2"
              style={{ color: '#B4543A', background: '#F6E9E4', border: '1px solid #E8C4B8' }}
            >
              {error}
            </p>
          </div>
        )}
        <div className="flex items-end gap-2 px-4 py-3">
          <textarea
            ref={textareaRef}
            rows={1}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={cargando}
            placeholder="Escribe un mensaje…"
            className="flex-1 resize-none text-sm focus:outline-none disabled:opacity-50 max-h-20 leading-snug bg-transparent"
            style={{
              minHeight: '2.5rem',
              border: '1px solid var(--line)',
              borderRadius: '999px',
              padding: '0.5rem 1rem',
              color: 'var(--ink)',
            }}
          />
          <button
            onClick={handleEnviar}
            disabled={cargando || !texto.trim()}
            className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: 'var(--charcoal)', color: 'var(--card)' }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-4 h-4"
            >
              <path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

