import database from './neon-data-client'
import { buildBackendUrl } from './backend-url'

async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await database.auth.getSession()
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session?.access_token || ''}`,
  }
}

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = await getAuthHeaders()
  const res = await fetch(buildBackendUrl(path), {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string> || {}) },
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `API Error: ${res.status}`)
  }
  return res.json()
}

export interface ScopeMeta {
  org_id: string
  role: string
}

export type CommandCenterKpiLabel =
  | 'leads_total'
  | 'lead_conversion_rate'
  | 'property_close_rate'
  | 'tasks_total'
  | 'tasks_completed'
  | 'task_completion_rate'

export interface KPIValue {
  label: CommandCenterKpiLabel
  value: number
  unit: 'count' | 'percent'
  trend?: number
}

export interface OperationalAlertPreview {
  id: string
  alert_scope: string
  severity: string
  alert_type: string
  message: string
  created_at: string
  metadata_json: Record<string, unknown>
}

export interface OperationalOverview {
  active_alerts: number
  critical_alerts: number
  degraded_sources: number
  stale_sources: number
  cloud_warning_checks: number
  cloud_critical_checks: number
  territorial_sync_status: string
  territorial_pipeline_status: string
  seller_signal_source_status: string
  ai_runtime_status: string
  top_alerts: OperationalAlertPreview[]
}

export interface PipelineOverview {
  seller_signals_processed: number
  sellers_total: number
  sellers_high_priority: number
  sellers_converted: number
  seller_conversion_rate: number
  supervised_sends_confirmed: number
  active_workbench_ready: number
}

export interface CommandCenterSnapshotResponse {
  version: string
  scope: ScopeMeta
  commercial_kpis: KPIValue[]
  productivity_kpis: KPIValue[]
  budget_status: 'ok' | 'warning' | 'hard_stop'
  burn_pct?: number | null
  monthly_budget_eur?: number | null
  current_usage_eur?: number | null
  cost_visibility: 'full' | 'limited'
  operational_overview: OperationalOverview
  pipeline_overview: PipelineOverview
}

export interface TrendPoint {
  period: string
  leads_created: number
  tasks_completed: number
  cost_eur: number
  active_alerts: number
  critical_alerts: number
  seller_signals_processed: number
  sellers_created: number
  supervised_sends_confirmed: number
}

export interface CommandCenterTrendsResponse {
  version: string
  scope: ScopeMeta
  months: number
  points: TrendPoint[]
}

export async function getCommandCenterSnapshot(): Promise<CommandCenterSnapshotResponse> {
  return apiRequest('/api/command-center/snapshot')
}

export async function getCommandCenterTrends(months = 6): Promise<CommandCenterTrendsResponse> {
  return apiRequest(`/api/command-center/trends?months=${months}`)
}
