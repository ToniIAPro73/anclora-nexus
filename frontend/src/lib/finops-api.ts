/**
 * Cost Governance Foundation API Client.
 * Feature: ANCLORA-CGF-001
 *
 * Wraps /api/finops endpoints.
 */

import database from './neon-data-client'
import { buildBackendUrl } from './backend-url'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface BudgetPolicy {
  org_id: string
  monthly_budget_eur: number
  warning_threshold_pct: number
  hard_stop_threshold_pct: number
  hard_stop_enabled: boolean
  current_usage_eur: number
  usage_updated_at: string
  status: 'ok' | 'warning' | 'hard_stop'
  created_at: string
  updated_at: string
}

export interface UsageEvent {
  id: string
  org_id: string
  capability_code: string
  provider: string | null
  units: number
  cost_eur: number
  request_id: string | null
  created_at: string
}

export interface CostAlert {
  id: string
  org_id: string
  alert_type: 'warning' | 'hard_stop'
  message: string
  is_active: boolean
  resolved_at: string | null
  created_at: string
}

export interface UsageFilterParams {
  capability?: string
  from?: string
  to?: string
  limit?: number
  offset?: number
}

// ─── API Methods ─────────────────────────────────────────────────────────────

async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await database.auth.getSession()
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session?.access_token || ''}`,
  }
}

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
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

export async function getBudget(): Promise<BudgetPolicy> {
  return apiRequest('/api/finops/budget')
}

export async function updateBudget(data: Partial<BudgetPolicy>): Promise<BudgetPolicy> {
  return apiRequest('/api/finops/budget', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function getUsage(params?: UsageFilterParams): Promise<{ items: UsageEvent[]; total: number }> {
    const query = new URLSearchParams()
    if (params?.capability) query.set('capability', params.capability)
    if (params?.from) query.set('from', params.from)
    if (params?.to) query.set('to', params.to)
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.offset) query.set('offset', String(params.offset))

    const qs = query.toString()
    return apiRequest(`/api/finops/usage${qs ? `?${qs}` : ''}`)
}

export async function getAlerts(): Promise<CostAlert[]> {
  return apiRequest('/api/finops/alerts')
}
