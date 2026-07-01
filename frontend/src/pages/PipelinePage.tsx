import { useCallback, useEffect, useState } from 'react'
import apiClient from '../api/client'
import type { Asesor, Lead } from '../api/types'
import { KanbanBoard, type ColDef } from '../components/KanbanBoard'
import { LeadDetailModal } from '../components/LeadDetailModal'
import { ConsolaNav } from '../components/ConsolaNav'

const KANBAN_COLS: ColDef[] = [
  { estado: 'nuevo',           label: 'Nuevo',             color: 'var(--cold)'  },
  { estado: 'contactado',      label: 'Contactado',        color: 'var(--warm)'  },
  { estado: 'calificado',      label: 'Calificado',        color: '#5A6E3B'      },
  { estado: 'negociando',      label: 'Negociando',        color: '#6B4C9E'      },
  { estado: 'cerrado_ganado',  label: 'Cerrado · ganado',  color: '#2D7A4F'      },
  { estado: 'cerrado_perdido', label: 'Cerrado · perdido', color: '#7A3D2D'      },
]

export default function PipelinePage() {
  const [leads, setLeads]         = useState<Lead[]>([])
  const [asesores, setAsesores]   = useState<Asesor[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [cargando, setCargando]   = useState(true)

  const cargarLeads = useCallback(async () => {
    const { data } = await apiClient.get<Lead[]>('/leads')
    setLeads(data)
  }, [])

  useEffect(() => {
    Promise.all([
      cargarLeads(),
      apiClient.get<Asesor[]>('/asesores').then(({ data }) => setAsesores(data)),
    ]).finally(() => setCargando(false))
  }, [cargarLeads])

  // Polling lista ~5 s
  useEffect(() => {
    const id = setInterval(cargarLeads, 5000)
    return () => clearInterval(id)
  }, [cargarLeads])

  const handleMoverEstado = async (leadId: string, estado: string) => {
    // Optimistic update
    setLeads(prev => prev.map(l => l.id === leadId ? { ...l, estado } : l))
    try {
      await apiClient.patch(`/leads/${leadId}/estado`, { estado })
      await cargarLeads()
    } catch {
      await cargarLeads()  // revert via refetch on error
    }
  }

  const handleAsignarAsesor = (_leadId: string, asesorId: string | null) => {
    setLeads(prev => prev.map(l => l.id === _leadId ? { ...l, asesor_id: asesorId } : l))
  }

  if (cargando) {
    return (
      <div className="flex items-center justify-center h-screen" style={{ background: 'var(--bg)' }}>
        <p className="text-sm" style={{ color: 'var(--gray-soft)' }}>Cargando pipeline…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <header
        className="flex-shrink-0 border-b px-5 py-3 flex items-center justify-between"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        <h1 className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
          Aqua<span className="italic" style={{ color: 'var(--champ)' }}>marine</span>
          <span className="font-normal" style={{ color: 'var(--gray-soft)' }}> · Pipeline</span>
        </h1>
        <ConsolaNav active="/pipeline" />
      </header>

      {/* Kanban board — scroll horizontal */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden p-4 scrollbar-brand">
        <KanbanBoard
          columnas={KANBAN_COLS}
          leads={leads}
          asesores={asesores}
          selectedId={selectedId}
          onCardClick={setSelectedId}
          onMoverEstado={handleMoverEstado}
        />
      </div>

      {/* Modal de detalle */}
      {selectedId && (
        <LeadDetailModal
          leadId={selectedId}
          asesores={asesores}
          onClose={() => setSelectedId(null)}
          onMoverEstado={handleMoverEstado}
          onAsignarAsesor={handleAsignarAsesor}
        />
      )}
    </div>
  )
}
