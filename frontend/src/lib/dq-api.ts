import { api } from './api'
import database from './neon-data-client'

export type EntityType = 'lead' | 'property'
export type IssueStatus = 'open' | 'in_review' | 'resolved' | 'ignored'
export type CandidateStatus = 'auto_link' | 'suggested_merge' | 'approved_merge' | 'rejected_merge'
export type ResolutionAction = 'approve_merge' | 'reject_merge' | 'mark_duplicate' | 'undo_merge'

export interface DQQualityIssue {
  id: string
  org_id: string
  entity_type: EntityType
  entity_id: string
  issue_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  issue_payload: Record<string, unknown>
  status: IssueStatus
  created_at: string
  updated_at: string
}

export interface DQEntityCandidate {
  id: string
  org_id: string
  entity_type: EntityType
  left_entity_id: string
  right_entity_id: string
  similarity_score: number
  signals: Record<string, unknown>
  status: CandidateStatus
  created_at: string
  updated_at: string
}

export interface DQMetrics {
  total_issues: number
  open_issues: number
  critical_issues: number
  total_candidates: number
  suggested_merges: number
  last_recompute_at?: string
}

export interface DQIssuesResponse {
  issues: DQQualityIssue[]
  total_count: number
}

export const dqApi = {
  getIssues: (params: {
    entity_type?: EntityType,
    status?: IssueStatus,
    limit?: number,
    offset?: number
  } = {}) => {
    const query = new URLSearchParams()
    if (params.entity_type) query.append('entity_type', params.entity_type)
    if (params.status) query.append('status', params.status)
    if (params.limit) query.append('limit', params.limit.toString())
    if (params.offset) query.append('offset', params.offset.toString())
    
    return api.get<DQIssuesResponse>(`/api/dq/issues?${query.toString()}`)
  },

  getMetrics: () => api.get<DQMetrics>('/api/dq/metrics'),

  getCandidates: async (entityType?: EntityType) => {
    let query = database.from('dq_entity_candidates').select('*')
    if (entityType) query = query.eq('entity_type', entityType)
    const { data, error } = await query.order('similarity_score', { ascending: false })
    if (error) throw new Error(error.message)
    return data as DQEntityCandidate[]
  },

  resolveCandidate: (candidateId: string, action: ResolutionAction, details?: Record<string, unknown>) => 
    api.post('/api/dq/resolve', {
      candidate_id: candidateId,
      action,
      details
    }),

  recompute: () => api.post('/api/dq/recompute', {})
}
