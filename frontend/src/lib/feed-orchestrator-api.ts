import database from './neon-data-client'
import { buildBackendUrl } from './backend-url'

export type FeedChannelName = 'idealista' | 'fotocasa' | 'rightmove' | 'kyero'

export interface FeedChannelSummary {
  channel: FeedChannelName
  format: 'xml' | 'json'
  is_enabled: boolean
  status: 'healthy' | 'warning' | 'blocked'
  total_candidates: number
  ready_to_publish: number
  warnings: number
  errors: number
  latest_run_at: string | null
}

export interface FeedWorkspaceResponse {
  generated_at: string
  channels: FeedChannelSummary[]
  totals: {
    channels: number
    candidates: number
    ready: number
    errors: number
    warnings: number
  }
}

export interface FeedValidationIssue {
  property_id: string
  field: string
  severity: 'warning' | 'error'
  message: string
}

export interface FeedValidationResponse {
  channel: FeedChannelName
  generated_at: string
  total_candidates: number
  ready_to_publish: number
  warnings: number
  errors: number
  issues: FeedValidationIssue[]
}

export interface FeedPublishResponse {
  run_id: string
  channel: FeedChannelName
  dry_run: boolean
  status: 'success' | 'partial' | 'failed'
  published_count: number
  rejected_count: number
  error_count: number
  generated_at: string
  sample_payload: Record<string, unknown>
  issues: FeedValidationIssue[]
}

export interface FeedRunItem {
  run_id: string
  channel: FeedChannelName
  status: string
  dry_run: boolean
  published_count: number
  rejected_count: number
  generated_at: string
}

export interface FeedRunListResponse {
  items: FeedRunItem[]
  total: number
}

export interface FeedChannelConfig {
  channel: FeedChannelName
  format: 'xml' | 'json'
  is_enabled: boolean
  max_items_per_run: number
  rules_json: Record<string, unknown>
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await database.auth.getSession()
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${session?.access_token || ''}`,
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

export async function getFeedWorkspace(): Promise<FeedWorkspaceResponse> {
  return apiRequest('/api/feeds/workspace')
}

export async function validateFeedChannel(channel: FeedChannelName): Promise<FeedValidationResponse> {
  return apiRequest(`/api/feeds/channels/${channel}/validate`, {
    method: 'POST',
  })
}

export async function publishFeedChannel(
  channel: FeedChannelName,
  payload: { dry_run?: boolean; max_items?: number } = {},
): Promise<FeedPublishResponse> {
  return apiRequest(`/api/feeds/channels/${channel}/publish`, {
    method: 'POST',
    body: JSON.stringify({
      dry_run: Boolean(payload.dry_run),
      max_items: payload.max_items ?? 100,
    }),
  })
}

export async function getFeedChannelConfig(channel: FeedChannelName): Promise<FeedChannelConfig> {
  return apiRequest(`/api/feeds/channels/${channel}/config`)
}

export async function updateFeedChannelConfig(
  channel: FeedChannelName,
  payload: Partial<Pick<FeedChannelConfig, 'is_enabled' | 'max_items_per_run' | 'rules_json'>>,
): Promise<FeedChannelConfig> {
  return apiRequest(`/api/feeds/channels/${channel}/config`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function listFeedRuns(params?: {
  channel?: FeedChannelName
  limit?: number
}): Promise<FeedRunListResponse> {
  const query = new URLSearchParams()
  if (params?.channel) query.set('channel', params.channel)
  if (params?.limit) query.set('limit', String(params.limit))
  const qs = query.toString()
  return apiRequest(`/api/feeds/runs${qs ? `?${qs}` : ''}`)
}
