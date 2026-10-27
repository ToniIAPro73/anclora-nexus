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

export interface AutomationRule {
  id: string
  org_id: string
  name: string
  status: 'active' | 'paused' | 'disabled'
  event_type: string
  channel: string
  action_type: string
  schedule_cron?: string | null
  max_cost_eur_per_run: number
  requires_human_checkpoint: boolean
  conditions: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface RuleListResponse {
  version: string
  scope: ScopeMeta
  items: AutomationRule[]
  total: number
}

export interface ExecutionItem {
  id: string
  org_id: string
  rule_id: string
  status: 'executed' | 'blocked'
  decision: 'allow' | 'blocked'
  reasons: string[]
  cost_estimate_eur: number
  trace_id: string
  created_at: string
}

export interface ExecutionListResponse {
  version: string
  scope: ScopeMeta
  items: ExecutionItem[]
  total: number
}

export interface AlertItem {
  id: string
  org_id: string
  rule_id?: string | null
  alert_scope: string
  severity: 'warning' | 'critical'
  alert_type: string
  message: string
  dedupe_key?: string | null
  metadata_json: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at?: string | null
  resolved_at?: string | null
}

export interface AlertListResponse {
  version: string
  scope: ScopeMeta
  items: AlertItem[]
  total: number
}

export interface DryRunResponse {
  version: string
  scope: ScopeMeta
  rule_id: string
  decision: 'allow' | 'blocked'
  reasons: string[]
  guardrails: Record<string, unknown>
}

export interface ExecuteResponse {
  version: string
  scope: ScopeMeta
  rule_id: string
  execution_id: string
  status: 'executed' | 'blocked'
  decision: 'allow' | 'blocked'
  reasons: string[]
  trace_id: string
}

export async function listAutomationRules(): Promise<RuleListResponse> {
  return apiRequest('/api/automation/rules')
}

export async function createAutomationRule(payload: {
  name: string
  event_type: string
  channel: string
  action_type: string
  schedule_cron?: string
  max_cost_eur_per_run?: number
  requires_human_checkpoint?: boolean
  conditions?: Record<string, unknown>
}): Promise<AutomationRule> {
  return apiRequest('/api/automation/rules', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function dryRunAutomationRule(ruleId: string, payload: {
  event_payload?: Record<string, unknown>
  cost_estimate_eur?: number
}): Promise<DryRunResponse> {
  return apiRequest(`/api/automation/rules/${ruleId}/dry-run`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function executeAutomationRule(ruleId: string, payload: {
  event_payload?: Record<string, unknown>
  cost_estimate_eur?: number
  confirm_human_checkpoint?: boolean
}): Promise<ExecuteResponse> {
  return apiRequest(`/api/automation/rules/${ruleId}/execute`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listAutomationExecutions(): Promise<ExecutionListResponse> {
  return apiRequest('/api/automation/executions')
}

export async function listAutomationAlerts(): Promise<AlertListResponse> {
  return apiRequest('/api/automation/alerts')
}

export async function acknowledgeAutomationAlert(alertId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/automation/alerts/${alertId}/ack`, { method: 'POST' })
}
