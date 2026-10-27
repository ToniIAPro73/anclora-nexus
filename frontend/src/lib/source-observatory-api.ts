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

export interface SourceScorecard {
  source_key: string
  total_events: number
  success_events: number
  duplicate_events: number
  error_events: number
  success_rate_pct: number
  lead_count: number
  property_count: number
  seller_count: number
  processed_events: number
  rejected_events: number
  failed_events: number
  created_entities: number
  freshness_hours: number | null
  latest_event_at: string | null
  operational_status: string
  entity_types: string[]
  heartbeat_age_hours?: number | null
  latency_ms?: number | null
  retry_count?: number
  ops_message?: string | null
}

export interface ObservatorySummary {
  total_sources: number
  healthy_sources: number
  warning_sources: number
  critical_sources: number
  stale_sources: number
  total_events: number
  total_created_entities: number
  total_failures: number
  cloud_checks_total: number
  cloud_checks_healthy: number
  cloud_checks_warning: number
  cloud_checks_critical: number
}

export interface RankingItem {
  source_key: string
  score: number
  success_rate_pct: number
  lead_count: number
  created_entities: number
  freshness_hours: number | null
  operational_status: string
}

export interface TrendPoint {
  period: string
  source_key: string
  events: number
  success_rate_pct: number
  processed_events: number
  failed_events: number
  created_entities: number
}

export async function getSourceOverview(): Promise<{ version: string; scope: { org_id: string; role: string }; summary: ObservatorySummary; items: SourceScorecard[]; total: number }> {
  return apiRequest('/api/source-observatory/overview')
}

export async function getSourceRanking(): Promise<{ version: string; scope: { org_id: string; role: string }; items: RankingItem[]; total: number }> {
  return apiRequest('/api/source-observatory/ranking')
}

export async function getSourceTrends(months = 6): Promise<{ version: string; scope: { org_id: string; role: string }; months: number; points: TrendPoint[] }> {
  return apiRequest(`/api/source-observatory/trends?months=${months}`)
}
