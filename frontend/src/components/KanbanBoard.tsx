import React, { useRef } from 'react'
import type { Asesor, Lead } from '../api/types'
import { TemperaturaBadge } from './TemperaturaBadge'

// ---------------------------------------------------------------------------
// Tipos públicos
// ---------------------------------------------------------------------------

export type ColDef = {
  estado: string
  label: string
  color: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function copM(cop: number): string {
  return `$${(cop / 1_000_000).toLocaleString('es-CO', { maximumFractionDigits: 0 })} M`
}

function diasSinGestion(lead: Lead): number {
  return Math.floor((Date.now() - new Date(lead.actualizado_en).getTime()) / 86_400_000)
}

function inicialesAsesor(nombre: string): string {
  return nombre.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2)
}

// ---------------------------------------------------------------------------
// KanbanCard — draggable
// ---------------------------------------------------------------------------

function KanbanCard({
  lead, asesores, seleccionado, onDragStart, onClick,
}: {
  lead: Lead
  asesores: Asesor[]
  seleccionado: boolean
  onDragStart: (e: React.DragEvent) => void
  onClick: () => void
}) {
  const perfil  = lead.perfil ?? {}
  const valor   = typeof perfil.presupuesto_max === 'number' ? perfil.presupuesto_max : null
  const asesor  = asesores.find(a => a.id === lead.asesor_id)
  const dias    = diasSinGestion(lead)
  const resumen = [perfil['tipo'], perfil['zona']].filter(Boolean).join(' · ')
  const esHandoff = lead.estado === 'calificado'

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      className="p-3 rounded-xl border cursor-grab active:cursor-grabbing select-none transition-shadow hover:shadow-sm"
      style={{
        background: seleccionado ? 'var(--champ-bg)' : 'var(--card)',
        borderColor: seleccionado ? 'var(--champ-soft)' : esHandoff ? 'var(--hot)' : 'var(--line)',
      }}
    >
      {/* Nombre + temperatura */}
      <div className="flex items-start gap-2 mb-1">
        <span className="text-sm font-medium truncate flex-1" style={{ color: 'var(--ink)' }}>
          {lead.nombre ?? 'Sin nombre'}
        </span>
        <TemperaturaBadge temperatura={lead.temperatura} />
      </div>

      {/* Badge handoff */}
      {esHandoff && (
        <span
          className="inline-block text-xs px-1.5 py-0.5 rounded-full mb-1"
          style={{ background: 'var(--hot-bg)', color: 'var(--hot)' }}
        >
          Nuevo handoff
        </span>
      )}

      {/* Perfil resumen */}
      {resumen && (
        <p className="text-xs mb-1 truncate" style={{ color: 'var(--gray-soft)' }}>{resumen}</p>
      )}

      {/* origen · score · valor */}
      <div className="flex items-center gap-2 flex-wrap">
        {lead.origen && (
          <span
            className="text-xs px-1.5 py-0.5 rounded-full"
            style={{ background: 'var(--line-soft)', color: 'var(--gray)' }}
          >
            {lead.origen}
          </span>
        )}
        {lead.score != null && (
          <span className="text-xs font-mono" style={{ color: 'var(--charcoal)' }}>
            {lead.score}/100
          </span>
        )}
        {valor !== null && (
          <span className="text-xs font-medium ml-auto" style={{ color: 'var(--champ)' }}>
            {copM(valor)}
          </span>
        )}
      </div>

      {/* Footer: asesor + días sin gestión */}
      <div className="flex items-center gap-2 mt-2">
        {asesor ? (
          <span
            className="text-xs font-medium w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: 'var(--champ-bg)', color: 'var(--champ)', fontSize: '10px' }}
            title={asesor.nombre}
          >
            {inicialesAsesor(asesor.nombre)}
          </span>
        ) : (
          <span
            className="text-xs w-6 h-6 rounded-full border flex items-center justify-center flex-shrink-0"
            style={{ borderColor: 'var(--line)', color: 'var(--gray-soft)', fontSize: '10px' }}
          >
            ?
          </span>
        )}
        <span
          className="text-xs ml-auto"
          style={{ color: dias >= 4 ? 'var(--hot)' : 'var(--gray-soft)' }}
        >
          {dias === 0 ? 'Hoy' : `${dias}d sin gestión`}
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// KanbanCol
// ---------------------------------------------------------------------------

function KanbanCol({
  col, leads, asesores, selectedId, estadosDrop,
  onDragOver, onDrop, onDragStart, onCardClick,
}: {
  col: ColDef
  leads: Lead[]
  asesores: Asesor[]
  selectedId: string | null
  estadosDrop: Set<string>
  onDragOver: (e: React.DragEvent) => void
  onDrop: (e: React.DragEvent, estado: string) => void
  onDragStart: (e: React.DragEvent, leadId: string) => void
  onCardClick: (id: string) => void
}) {
  const totalValor = leads.reduce((s, l) => {
    const v = l.perfil?.presupuesto_max
    return s + (typeof v === 'number' ? v : 0)
  }, 0)

  const canDrop = estadosDrop.has(col.estado)

  return (
    <div
      className="flex flex-col rounded-xl transition-colors"
      style={{
        minWidth: '210px',
        width: '210px',
        background: 'var(--line-soft)',
      }}
      onDragOver={canDrop ? onDragOver : undefined}
      onDrop={canDrop ? e => onDrop(e, col.estado) : undefined}
    >
      {/* Header de columna (formato exacto conservado) */}
      <div className="px-3 py-2.5 flex-shrink-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: col.color }} />
          <span className="text-xs font-semibold truncate" style={{ color: 'var(--ink)' }}>
            {col.label}
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded-full ml-auto flex-shrink-0"
            style={{ background: 'var(--card)', color: 'var(--gray)' }}
          >
            {leads.length}
          </span>
        </div>
        {totalValor > 0 && (
          <p className="text-xs pl-3.5" style={{ color: 'var(--gray-soft)' }}>
            {copM(totalValor)}
          </p>
        )}
      </div>

      {/* Cards — scroll con marca */}
      <div
        className="flex-1 overflow-y-auto scrollbar-brand px-2 pb-2 flex flex-col gap-2"
        style={{ minHeight: '80px' }}
      >
        {leads.map(lead => (
          <KanbanCard
            key={lead.id}
            lead={lead}
            asesores={asesores}
            seleccionado={lead.id === selectedId}
            onDragStart={e => onDragStart(e, lead.id)}
            onClick={() => onCardClick(lead.id)}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// KanbanBoard — componente público
// ---------------------------------------------------------------------------

interface KanbanBoardProps {
  columnas: ColDef[]
  leads: Lead[]
  asesores: Asesor[]
  selectedId: string | null
  onCardClick: (leadId: string) => void
  onMoverEstado: (leadId: string, nuevoEstado: string) => void
  /** Si se da, solo se permite soltar en estas columnas. */
  estadosPermitidos?: string[]
}

export function KanbanBoard({
  columnas, leads, asesores, selectedId,
  onCardClick, onMoverEstado, estadosPermitidos,
}: KanbanBoardProps) {
  const dragLeadId = useRef<string | null>(null)
  const estadosDrop = new Set(estadosPermitidos ?? columnas.map(c => c.estado))

  const handleDragStart = (e: React.DragEvent, leadId: string) => {
    dragLeadId.current = leadId
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }

  const handleDrop = (e: React.DragEvent, nuevoEstado: string) => {
    e.preventDefault()
    const lid = dragLeadId.current
    if (!lid) return
    const lead = leads.find(l => l.id === lid)
    if (!lead || lead.estado === nuevoEstado) return
    onMoverEstado(lid, nuevoEstado)
  }

  const leadsPorEstado = (estado: string) => leads.filter(l => l.estado === estado)

  return (
    <div className="flex gap-3 h-full" style={{ minWidth: 'max-content' }}>
      {columnas.map(col => (
        <KanbanCol
          key={col.estado}
          col={col}
          leads={leadsPorEstado(col.estado)}
          asesores={asesores}
          selectedId={selectedId}
          estadosDrop={estadosDrop}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onDragStart={handleDragStart}
          onCardClick={onCardClick}
        />
      ))}
    </div>
  )
}
