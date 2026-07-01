export type Lead = {
  id: string
  tenant_id: string
  nombre: string | null
  contacto: string | null
  origen: string | null
  idioma: string | null
  score: number | null
  temperatura: string
  estado: string
  perfil: Record<string, unknown>
  asesor_id: string | null
  creado_en: string
  actualizado_en: string
  // E07
  atendido_por_humano: boolean
  asignado_en: string | null
  notificaciones_count: number
}

export type LeadConMensajes = Lead & {
  mensajes: Mensaje[]
}

export type Mensaje = {
  id: string
  lead_id: string
  rol: 'lead' | 'agente' | 'asesor'
  contenido: string
  metadata: Record<string, unknown> | null
  creado_en: string
}

export type Asesor = {
  id: string
  nombre: string
  disponible: boolean
  carga: number
}

export type NotificacionOut = {
  evento_id: string
  lead_id: string
  tipo: string
  temperatura: string | null
  perfil_resumen: Record<string, unknown>
  creado_en: string
}

// ── Métricas ──────────────────────────────────────────────────────────────

export type Rate = {
  pct: number
  num: number
  den: number
}

export type FunnelStep = {
  etapa: string
  count: number
  pct_paso_previo: Rate | null
}

export type MetricsOverview = {
  total_leads: number
  leads_calientes: { count: number; rate: Rate }
  pct_calificados: Rate
  primera_respuesta_seg: number | null
  funnel: FunnelStep[]
  conversion: { lead_a_cita: Rate; cita_a_negociacion: Rate }
  pipeline_ponderado_cop: number
  negocios_ganados: { count: number; valor_cerrado_cop: number }
  por_temperatura: Record<string, number>
  por_origen: Record<string, number>
}

// ── E07: métricas por asesor y propiedades ─────────────────────────────────

export type AsesorMetrics = {
  id: string
  nombre: string
  disponible: boolean
  leads_asignados: number
  en_cola: number
  tomados: number
  ganados: number
  valor_cerrado_cop: number
  primera_respuesta_seg: number | null
  tiempo_en_tomar_seg: number | null
  ratio_conversion: Rate
}

export type PropiedadesMetrics = {
  activas: number
  en_negociacion: number
  cerradas: number
  valor_cerrado_cop: number
}

// ── E08: insights de gerencia ──────────────────────────────────────────────

export type InsightsResponse = {
  respuesta: string
  datos: Record<string, unknown> | null
}
