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

export interface MarginAssumptions {
  deal_value_eur: number
  acquisition_cost_eur: number
  closing_cost_eur?: number
  renovation_cost_eur?: number
  holding_cost_eur?: number
  tax_cost_eur?: number
  commission_rate_pct?: number
  confidence_pct?: number
}

export interface SimulationResult {
  scenario_name: string
  gross_margin_eur: number
  gross_margin_pct: number
  expected_commission_eur: number
  expected_margin_eur: number
  recommendation_band: 'A' | 'B' | 'C' | 'D'
  drivers: Array<{ label: string; value_eur: number }>
}

export interface SimulationResponse {
  version: string
  scope: { org_id: string; role: string }
  result: SimulationResult
}

export interface CompareResponse {
  version: string
  scope: { org_id: string; role: string }
  results: SimulationResult[]
  best_scenario: string
}

export async function simulateDealMargin(payload: {
  scenario_name?: string
  assumptions: MarginAssumptions
}): Promise<SimulationResponse> {
  return apiRequest('/api/deal-margin/simulate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function compareDealMargins(payload: {
  scenarios: Array<{ scenario_name?: string; assumptions: MarginAssumptions }>
}): Promise<CompareResponse> {
  return apiRequest('/api/deal-margin/compare', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
