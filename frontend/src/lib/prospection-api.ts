/**
 * Prospection & Buyer Matching API Client.
 * Feature: ANCLORA-PBM-001
 *
 * Wraps all /api/prospection endpoints with typed interfaces.
 */

import database from './neon-data-client'
import { buildBackendUrl } from './backend-url'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface ProspectedProperty {
  id: string
  org_id: string
  title: string | null
  city: string | null
  zone: string | null
  property_type: string | null
  price: number | null
  area_m2: number | null
  bedrooms: number | null
  source: string
  source_url: string | null
  status: 'new' | 'contacted' | 'negotiating' | 'listed' | 'discarded'
  high_ticket_score: number | null
  score_breakdown: Record<string, number> | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface BuyerProfile {
  id: string
  org_id: string
  full_name: string | null
  email: string | null
  phone: string | null
  budget_min: number | null
  budget_max: number | null
  preferred_zones: string[]
  preferred_types: string[]
  purchase_horizon: string | null
  motivation_score: number | null
  source_type: 'partner_referral' | 'crm_reactivation' | 'web_inbound' | 'paid_lead' | 'manual' | 'portal_signal'
  source_platform: 'exp_agent' | 'external_agent' | 'crm' | 'web' | 'meta' | 'google' | 'whatsapp' | 'email' | 'idealista' | 'manual' | 'other'
  referral_partner_name: string | null
  referral_partner_contact: string | null
  referral_partner_type: 'exp_agent' | 'external_agent' | 'broker' | 'partner' | 'family_office' | 'relocation' | null
  referral_terms: string | null
  buyer_intro_status: 'new' | 'introduced' | 'qualified' | 'viewing' | 'closed'
  trust_score: number | null
  intent_score: number | null
  capacity_score: number | null
  intelligence_pack_id: string | null
  source_details: Record<string, unknown> | null
  last_partner_touch_at: string | null
  memory_preview?: string[]
  memory_status?: 'ready' | 'empty' | 'migration_missing' | string
  status: 'active' | 'inactive' | 'closed'
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PropertyBuyerMatch {
  id: string
  org_id: string
  property_id: string
  buyer_id: string
  match_score: number
  score_breakdown: Record<string, number> | null
  match_status: 'candidate' | 'contacted' | 'viewing' | 'negotiating' | 'offer' | 'closed' | 'discarded'
  commission_estimate: number | null
  notes: string | null
  property_title?: string
  buyer_name?: string
  created_at: string
  updated_at: string
}

export interface MatchActivity {
  id: string
  org_id: string
  match_id: string
  activity_type: string
  outcome: string | null
  details: Record<string, unknown> | null
  created_by: string | null
  created_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface RecomputeResult {
  matches_created: number
  matches_updated: number
  total_computed: number
}

export interface WorkspaceScope {
  org_id: string
  role: string
  user_id: string | null
}

export interface ProspectionWorkspaceResponse {
  scope: WorkspaceScope
  properties: PaginatedResponse<ProspectedProperty>
  buyers: PaginatedResponse<BuyerProfile>
  matches: PaginatedResponse<PropertyBuyerMatch>
  totals: {
    properties: number
    buyers: number
    matches: number
  }
  buyer_source_summary?: {
    by_source_type: Record<string, number>
    by_source_platform: Record<string, number>
    partner_referrals: number
    crm_reactivation: number
    web_inbound: number
  }
}

export type WorkspaceEntityType = 'property' | 'buyer' | 'match'

export interface WorkspaceActionResponse {
  ok: boolean
  action: 'followup_task' | 'mark_reviewed' | string
  entity_type: WorkspaceEntityType
  entity_id: string
  task_id?: string | null
  message: string
}

export interface OpportunityRankingItem {
  match_id: string
  property_id: string
  buyer_id: string
  property_title: string
  buyer_name: string
  match_status: string
  match_score: number
  commission_estimate: number | null
  opportunity_score: number
  priority_band: 'hot' | 'warm' | 'cold'
  next_action: string
  explanation: {
    drivers: {
      match_score: number
      commission_potential: number
      buyer_motivation: number
    }
    top_factors: Array<{ factor: string; value: number }>
    confidence: number
  }
  updated_at: string
}

export interface OpportunityRankingResponse {
  items: OpportunityRankingItem[]
  total: number
  limit: number
  scope: {
    org_id: string
  }
  totals: {
    hot: number
    warm: number
    cold: number
  }
}

export interface BuyerWorkbenchInteraction {
  id: string
  tipo: string
  contenido: string
  estado: string
  resultado?: string | null
  metadata?: Record<string, unknown>
  created_at: string
}

export interface BuyerWorkbenchPayload {
  buyer: BuyerProfile
  matches: PropertyBuyerMatch[]
  activities: MatchActivity[]
  interactions: BuyerWorkbenchInteraction[]
  latest_artifacts: {
    buyer_brief?: BuyerWorkbenchInteraction | null
    email_draft?: BuyerWorkbenchInteraction | null
    whatsapp_draft?: BuyerWorkbenchInteraction | null
  }
  memory: {
    version: string
    buyer_id: string
    status: string
    query: string
    total_records: number
    vector_ready_records?: number
    retrieval_mode?: string
    retrieval_summary: string
    matches: Array<{
      score: number
      matched_keywords: string[]
      reasons: Array<{ type: string; value: string }>
      record: {
        id: string
        memory_kind: string
        source_type: string
        source_artifact?: string | null
        summary: string
        redacted_content: string
        source_created_at: string
      }
    }>
  }
  console: {
    readiness: string
    recommended_channel: string
    next_action: string
    reasons: string[]
    last_touch_at?: string | null
    memory_highlights: Array<{ summary: string; score: number }>
  }
  snapshot: {
    interactions_count: number
    matches_count: number
    semantic_memory_count: number
    semantic_memory_ready: boolean
    recommended_channel: string
    readiness: string
    email_native_available: boolean
    latest_email_delivery?: BuyerWorkbenchInteraction | null
    latest_whatsapp_delivery?: BuyerWorkbenchInteraction | null
  }
}

export interface BuyerSupervisedSendPayload {
  channel: 'email' | 'whatsapp'
  buyer_id: string
  interaction_id: string
  target: string
  subject: string
  body: string
  launch_url: string | null
  status: 'ready_for_human_send' | 'sent_natively'
  transport: string
  delivery?: Record<string, unknown> | null
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

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

// ─── Properties ──────────────────────────────────────────────────────────────

export async function listProperties(params?: {
  zone?: string
  status?: string
  min_score?: number
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<ProspectedProperty>> {
  const query = new URLSearchParams()
  if (params?.zone) query.set('zone', params.zone)
  if (params?.status) query.set('status', params.status)
  if (params?.min_score !== undefined) query.set('min_score', String(params.min_score))
  if (params?.limit) query.set('limit', String(params.limit))
  if (params?.offset) query.set('offset', String(params.offset))
  const qs = query.toString()
  return apiRequest(`/api/prospection/properties${qs ? `?${qs}` : ''}`)
}

export async function createProspectedProperty(data: {
  title: string
  city?: string
  zone: string
  property_type: string
  price?: number
  area_m2?: number
  bedrooms?: number
  source: string
  source_url?: string
  notes?: string
}): Promise<ProspectedProperty> {
  return apiRequest('/api/prospection/properties', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateProperty(
  propertyId: string,
  data: Partial<ProspectedProperty>,
): Promise<ProspectedProperty> {
  return apiRequest(`/api/prospection/properties/${propertyId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function rescoreProperty(propertyId: string): Promise<ProspectedProperty> {
  return apiRequest(`/api/prospection/properties/${propertyId}/score`, {
    method: 'POST',
  })
}

// ─── Buyers ──────────────────────────────────────────────────────────────────

export async function listBuyers(params?: {
  status?: string
  source_type?: string
  source_platform?: string
  min_budget?: number
  max_budget?: number
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<BuyerProfile>> {
  const query = new URLSearchParams()
  if (params?.status) query.set('status', params.status)
  if (params?.source_type) query.set('source_type', params.source_type)
  if (params?.source_platform) query.set('source_platform', params.source_platform)
  if (params?.min_budget !== undefined) query.set('min_budget', String(params.min_budget))
  if (params?.max_budget !== undefined) query.set('max_budget', String(params.max_budget))
  if (params?.limit) query.set('limit', String(params.limit))
  if (params?.offset) query.set('offset', String(params.offset))
  const qs = query.toString()
  return apiRequest(`/api/prospection/buyers${qs ? `?${qs}` : ''}`)
}

export async function createBuyer(data: {
  full_name: string
  email?: string
  phone?: string
  budget_min?: number
  budget_max?: number
  preferred_zones?: string[]
  preferred_types?: string[]
  purchase_horizon?: string
  motivation_score?: number
  source_type?: string
  source_platform?: string
  referral_partner_name?: string
  referral_partner_contact?: string
  referral_partner_type?: string
  referral_terms?: string
  buyer_intro_status?: string
  trust_score?: number
  intent_score?: number
  capacity_score?: number
  intelligence_pack_id?: string
  source_details?: Record<string, unknown>
  last_partner_touch_at?: string
  notes?: string
}): Promise<BuyerProfile> {
  return apiRequest('/api/prospection/buyers', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateBuyer(
  buyerId: string,
  data: Partial<BuyerProfile>,
): Promise<BuyerProfile> {
  return apiRequest(`/api/prospection/buyers/${buyerId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

// ─── Matches ─────────────────────────────────────────────────────────────────

export async function listMatches(params?: {
  status?: string
  min_score?: number
  property_id?: string
  buyer_id?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<PropertyBuyerMatch>> {
  const query = new URLSearchParams()
  if (params?.status) query.set('status', params.status)
  if (params?.min_score !== undefined) query.set('min_score', String(params.min_score))
  if (params?.property_id) query.set('property_id', params.property_id)
  if (params?.buyer_id) query.set('buyer_id', params.buyer_id)
  if (params?.limit) query.set('limit', String(params.limit))
  if (params?.offset) query.set('offset', String(params.offset))
  const qs = query.toString()
  return apiRequest(`/api/prospection/matches${qs ? `?${qs}` : ''}`)
}

export async function recomputeMatches(data?: {
  property_ids?: string[]
  buyer_ids?: string[]
}): Promise<RecomputeResult> {
  return apiRequest('/api/prospection/matches/recompute', {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
}

export async function updateMatch(
  matchId: string,
  data: Partial<PropertyBuyerMatch>,
): Promise<PropertyBuyerMatch> {
  return apiRequest(`/api/prospection/matches/${matchId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

// ─── Activities ──────────────────────────────────────────────────────────────

export async function logActivity(
  matchId: string,
  data: {
    activity_type: string
    outcome?: string
    details?: string
  },
): Promise<MatchActivity> {
  return apiRequest(`/api/prospection/matches/${matchId}/activity`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function listActivities(
  matchId: string,
): Promise<{ items: MatchActivity[]; total: number }> {
  return apiRequest(`/api/prospection/matches/${matchId}/activities`)
}

export async function getProspectionWorkspace(params?: {
  source_system?: string
  property_status?: string
  buyer_status?: string
  match_status?: string
  min_property_score?: number
  min_match_score?: number
  limit?: number
  offset?: number
}): Promise<ProspectionWorkspaceResponse> {
  const query = new URLSearchParams()
  if (params?.source_system) query.set('source_system', params.source_system)
  if (params?.property_status) query.set('property_status', params.property_status)
  if (params?.buyer_status) query.set('buyer_status', params.buyer_status)
  if (params?.match_status) query.set('match_status', params.match_status)
  if (params?.min_property_score !== undefined) query.set('min_property_score', String(params.min_property_score))
  if (params?.min_match_score !== undefined) query.set('min_match_score', String(params.min_match_score))
  if (params?.limit) query.set('limit', String(params.limit))
  if (params?.offset) query.set('offset', String(params.offset))
  const qs = query.toString()
  return apiRequest(`/api/prospection/workspace${qs ? `?${qs}` : ''}`)
}

export async function createWorkspaceFollowupTask(data: {
  entity_type: WorkspaceEntityType
  entity_id: string
  title?: string
  description?: string
  due_date?: string
  assigned_user_id?: string
}): Promise<WorkspaceActionResponse> {
  return apiRequest('/api/prospection/workspace/actions/followup-task', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getBuyerWorkbench(buyerId: string, interactionLimit = 20): Promise<BuyerWorkbenchPayload> {
  return apiRequest(`/api/prospection/buyers/${buyerId}/workbench?interaction_limit=${interactionLimit}`)
}

export async function generateBuyerOutreach(buyerId: string): Promise<{
  buyer_id: string
  brief: string
  email_subject: string
  email_body: string
  whatsapp_body: string
}> {
  return apiRequest(`/api/prospection/buyers/${buyerId}/generate-outreach`, {
    method: 'POST',
  })
}

export async function sendBuyerSupervised(
  buyerId: string,
  channel: 'email' | 'whatsapp',
  transport: 'auto' | 'mailto' | 'native_email' = 'auto',
): Promise<BuyerSupervisedSendPayload> {
  return apiRequest(`/api/prospection/buyers/${buyerId}/send-supervised/${channel}`, {
    method: 'POST',
    body: JSON.stringify({ transport }),
  })
}

export async function confirmBuyerSupervisedSend(buyerId: string, interactionId: string): Promise<BuyerWorkbenchInteraction> {
  return apiRequest(`/api/prospection/buyers/${buyerId}/interactions/${interactionId}/confirm-send`, {
    method: 'POST',
  })
}

export async function markWorkspaceItemReviewed(data: {
  entity_type: WorkspaceEntityType
  entity_id: string
  note?: string
}): Promise<WorkspaceActionResponse> {
  return apiRequest('/api/prospection/workspace/actions/mark-reviewed', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getOpportunityRanking(params?: {
  limit?: number
  min_opportunity_score?: number
  match_status?: string
}): Promise<OpportunityRankingResponse> {
  const query = new URLSearchParams()
  if (params?.limit) query.set('limit', String(params.limit))
  if (params?.min_opportunity_score !== undefined) query.set('min_opportunity_score', String(params.min_opportunity_score))
  if (params?.match_status) query.set('match_status', params.match_status)
  const qs = query.toString()
  return apiRequest(`/api/prospection/opportunities/ranking${qs ? `?${qs}` : ''}`)
}
