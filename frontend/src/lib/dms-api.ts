import database from './neon-data-client'

async function getJsonHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await database.auth.getSession()
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session?.access_token || ''}`,
  }
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await database.auth.getSession()
  return {
    'Authorization': `Bearer ${session?.access_token || ''}`,
  }
}

// DMS calls use the Next.js rewrite proxy (/api/* → Render backend) to avoid
// CORS issues when NEXT_PUBLIC_API_URL points to an absolute Render URL.
async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = await getJsonHeaders()
  const res = await fetch(path, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string> || {}) },
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = error.detail
    const message = Array.isArray(detail)
      ? detail.map((d: { loc?: unknown[]; msg?: string }) => [d.loc?.join('.'), d.msg].filter(Boolean).join(': ')).join('; ')
      : typeof detail === 'string'
        ? detail
        : detail && typeof detail === 'object'
          ? JSON.stringify(detail)
          : `DMS API error: ${res.status}`
    throw new Error(message)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export type OperationType = 'compraventa' | 'alquiler_temporada' | 'alquiler_turistico'
export type ComplianceStatus = 'pending' | 'approved' | 'rejected' | 'expired'

export interface DealFolder {
  id: string
  org_id: string
  operation_type: OperationType
  property_id?: string | null
  client_lead_id?: string | null
  seller_id?: string | null
  language?: string | null
  folder_status: string
  created_at?: string
}

export interface DealDocument {
  id: string
  folder_id: string
  org_id: string
  title: string
  document_category: string
  file_mime_type: string
  file_size_bytes: number
  sha256_hash?: string
  compliance_status: ComplianceStatus
  legal_metadata?: Record<string, unknown>
  created_at?: string
}

export interface SignatureFlow {
  id?: string
  document_id: string
  flow_status: string
  signer_email: string
  signer_name: string
  signer_role: string
  external_envelope_id?: string
}

export async function listDealFolders(): Promise<DealFolder[]> {
  return apiRequest('/api/dms/folders')
}

export async function createDealFolder(payload: {
  operation_type: OperationType
  property_id?: string | null
  client_lead_id?: string | null
  seller_id?: string | null
}): Promise<DealFolder> {
  return apiRequest('/api/dms/folders', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listDocuments(folderId: string): Promise<DealDocument[]> {
  return apiRequest(`/api/dms/folders/${folderId}/documents`)
}

export async function uploadDocument(payload: {
  folderId: string
  title: string
  documentCategory: string
  file: File
}): Promise<DealDocument> {
  const headers = await getAuthHeaders()
  const form = new FormData()
  form.append('folder_id', payload.folderId)
  form.append('title', payload.title)
  form.append('document_category', payload.documentCategory)
  form.append('file', payload.file)

  const res = await fetch('/api/dms/documents/upload', {
    method: 'POST',
    headers,
    body: form,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `DMS upload error: ${res.status}`)
  }
  return res.json()
}

export async function validateDocument(documentId: string): Promise<{
  document: DealDocument
  validation: Record<string, unknown>
}> {
  return apiRequest(`/api/dms/documents/${documentId}/validate`, {
    method: 'POST',
    body: JSON.stringify({ jurisdiction: 'ES-IB', language: 'es' }),
  })
}

export async function createSignatureFlow(documentId: string, payload: {
  signer_email: string
  signer_name: string
  signer_role: 'buyer' | 'seller' | 'agent' | 'witness'
}): Promise<SignatureFlow> {
  return apiRequest(`/api/dms/documents/${documentId}/signature-flows`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getDocumentWorkspace(documentId: string): Promise<{
  document: DealDocument
  download_url: string
  signature_flow: SignatureFlow | null
}> {
  return apiRequest(`/api/dms/documents/${documentId}/workspace`)
}

// ── Template library ───────────────────────────────────────────────────────────

export type TemplateDocumentType =
  | 'arras_penitenciales'
  | 'contrato_compraventa'
  | 'oferta_compra'
  | 'contrato_reserva_senal'
  | 'nota_encargo'
  | 'contrato_temporada'
  | 'contrato_arrendamiento'
  | 'contrato_alquiler_turistico'
  | 'recibo_fianza'
  | 'acta_entrega_llaves'
  | 'mandato_exclusiva'
  | 'kyc_identificacion_cliente'
  | 'acuerdo_confidencialidad'
  | 'hoja_visita'
  | 'inventario_estado_inmueble'
  | 'informacion_privacidad_cliente'
  | 'declaracion_origen_fondos'
  | 'generico'

export type TemplateStatus = 'draft' | 'published' | 'deprecated' | 'review_required'

export interface DocumentTemplate {
  id: string
  org_id: string
  name: string
  template_document_type: TemplateDocumentType
  description?: string
  jurisdiction: string
  language: string
  is_global: boolean
  status: TemplateStatus
  created_at?: string
  published_at?: string
}

export interface TemplateVersion {
  id: string
  template_id: string
  version_number: number
  sha256_hash: string
  canonical_text?: string
  change_summary?: string
  status?: TemplateStatus
  immutable: boolean
  created_at?: string
}

export interface TemplateField {
  id: string
  template_version_id: string
  field_key: string
  label: string
  field_type: 'text' | 'number' | 'date' | 'amount' | 'boolean' | 'select'
  required: boolean
  default_value?: string
  validation_rule?: string
  source_path?: string
}

export async function listTemplates(params?: {
  document_type?: TemplateDocumentType
  status?: TemplateStatus
}): Promise<DocumentTemplate[]> {
  const qs = params
    ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][]).toString()
    : ''
  return apiRequest(`/api/dms/templates${qs}`)
}

export async function createTemplate(payload: {
  name: string
  template_document_type: TemplateDocumentType
  description?: string
  jurisdiction?: string
  language?: string
}): Promise<DocumentTemplate> {
  return apiRequest('/api/dms/templates', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getTemplate(templateId: string): Promise<DocumentTemplate> {
  return apiRequest(`/api/dms/templates/${templateId}`)
}

export async function publishTemplate(templateId: string): Promise<DocumentTemplate> {
  return apiRequest(`/api/dms/templates/${templateId}/publish`, { method: 'PATCH' })
}

export async function listTemplateVersions(templateId: string): Promise<TemplateVersion[]> {
  return apiRequest(`/api/dms/templates/${templateId}/versions`)
}

export async function uploadTemplateVersion(templateId: string, file: File, changeSummary?: string): Promise<TemplateVersion> {
  const headers = await getAuthHeaders()
  const form = new FormData()
  form.append('file', file)
  if (changeSummary) form.append('change_summary', changeSummary)
  const res = await fetch(`/api/dms/templates/${templateId}/versions`, {
    method: 'POST',
    headers,
    body: form,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `Template version upload error: ${res.status}`)
  }
  return res.json()
}

export async function listTemplateFields(templateId: string, versionId: string): Promise<TemplateField[]> {
  return apiRequest(`/api/dms/templates/${templateId}/versions/${versionId}/fields`)
}

// ── Parties ────────────────────────────────────────────────────────────────────

export type PartyRole = 'buyer' | 'seller' | 'agent' | 'guarantor' | 'co_buyer' | 'co_seller' | 'notary'

export interface FolderParty {
  id: string
  folder_id: string
  org_id: string
  party_role: PartyRole
  full_name: string
  lead_id?: string
  seller_id?: string
  company_id?: string
  contact_id?: string
  source_entity?: string
  source_id?: string
  is_primary: boolean
  signing_order?: number
  representation_capacity?: string
  dni_nie_passport?: string
  email?: string
  phone?: string
  address?: string
  nationality?: string
  is_company: boolean
  company_name?: string
  company_cif?: string
  kyc_verified: boolean
  kyc_verified_at?: string
  created_at?: string
}

export interface PartyCandidate {
  id: string
  entity_type: 'lead' | 'seller' | 'company' | 'contact'
  label: string
  email?: string
  phone?: string
  role_hint?: PartyRole
  payload: Record<string, unknown>
}

export async function listParties(folderId: string): Promise<FolderParty[]> {
  return apiRequest(`/api/dms/folders/${folderId}/parties`)
}

export async function createParty(folderId: string, payload: {
  party_role: PartyRole
  full_name: string
  lead_id?: string
  seller_id?: string
  company_id?: string
  contact_id?: string
  source_entity?: string
  source_id?: string
  is_primary?: boolean
  signing_order?: number
  representation_capacity?: string
  dni_nie_passport?: string
  email?: string
  phone?: string
  address?: string
  nationality?: string
  is_company?: boolean
  company_name?: string
  company_cif?: string
}): Promise<FolderParty> {
  return apiRequest(`/api/dms/folders/${folderId}/parties`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateParty(folderId: string, partyId: string, payload: Partial<FolderParty>): Promise<FolderParty> {
  return apiRequest(`/api/dms/folders/${folderId}/parties/${partyId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteParty(folderId: string, partyId: string): Promise<void> {
  await apiRequest(`/api/dms/folders/${folderId}/parties/${partyId}`, { method: 'DELETE' })
}

export async function listPartyCandidates(params?: { q?: string; entity_type?: string }): Promise<PartyCandidate[]> {
  const qs = params
    ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== '') as [string, string][]).toString()
    : ''
  return apiRequest(`/api/dms/party-candidates${qs}`)
}

// ── Generated documents ────────────────────────────────────────────────────────

export type DocumentStatus = 'draft' | 'review_required' | 'approved' | 'signed' | 'archived'

export interface GeneratedDocument {
  id: string
  folder_id: string
  org_id: string
  template_version_id: string
  title: string
  status: DocumentStatus
  generation_payload: Record<string, unknown>
  storage_path?: string
  docx_storage_path?: string
  pdf_storage_path?: string
  preview_storage_path?: string
  variable_snapshot?: Record<string, unknown>
  current_version_id?: string
  generated_at?: string
  created_at?: string
}

export interface GeneratedDocumentEnvelope {
  document: GeneratedDocument
  version?: Record<string, unknown>
  preview?: string
  download_urls?: { docx: string; pdf: string }
}

export async function listAvailableTemplates(
  folderId: string,
  params?: { language?: string },
): Promise<Array<DocumentTemplate & { latest_version?: TemplateVersion | null }>> {
  const qs = params?.language ? `?${new URLSearchParams({ language: params.language }).toString()}` : ''
  return apiRequest(`/api/dms/folders/${folderId}/available-templates${qs}`)
}

export async function generateDocument(folderId: string, payload: {
  template_version_id: string
  title: string
  generation_payload: Record<string, unknown>
}): Promise<GeneratedDocumentEnvelope> {
  return apiRequest(`/api/dms/folders/${folderId}/generate-document`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listGeneratedDocuments(folderId: string): Promise<GeneratedDocument[]> {
  return apiRequest(`/api/dms/folders/${folderId}/generated`)
}

export async function getGeneratedDocument(generatedId: string): Promise<GeneratedDocumentEnvelope> {
  return apiRequest(`/api/dms/generated-documents/${generatedId}`)
}

export async function editGeneratedDocument(generatedId: string, payload: {
  edited_text: string
  title?: string
  change_summary?: string
}): Promise<Record<string, unknown>> {
  return apiRequest(`/api/dms/generated-documents/${generatedId}/versions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ── Legal review ───────────────────────────────────────────────────────────────

export async function triggerAutoReview(generatedId: string, payload: {
  jurisdiction?: string
  language?: string
  reviewer_notes?: string
}): Promise<Record<string, unknown>> {
  return apiRequest(`/api/dms/generated-documents/${generatedId}/validate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listReviewDecisions(generatedId: string): Promise<Record<string, unknown>[]> {
  return apiRequest(`/api/dms/generated-documents/${generatedId}/review-decisions`)
}

export type ReviewDecisionType =
  | 'approved'
  | 'approved_with_conditions'
  | 'review_required'
  | 'changes_required'
  | 'rejected'

export async function createManualReviewDecision(generatedId: string, payload: {
  decision: ReviewDecisionType
  notes?: string
  block_signing?: boolean
  version_id?: string | null
}): Promise<Record<string, unknown>> {
  return apiRequest(`/api/dms/generated-documents/${generatedId}/review-decisions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export interface SignerEntry {
  email: string
  name: string
  role?: string
}

export async function createGeneratedSignatureFlow(generatedId: string, payload: {
  signing_level?: string
  signers?: SignerEntry[]
  // Legacy single-signer fields
  signer_email?: string
  signer_name?: string
  signer_role?: 'buyer' | 'seller' | 'agent' | 'witness'
}): Promise<Record<string, unknown>> {
  return apiRequest(`/api/dms/generated-documents/${generatedId}/signature-flows`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ── Retention policies ─────────────────────────────────────────────────────────

export interface RetentionPolicy {
  id: string
  org_id: string
  template_document_type?: TemplateDocumentType
  retention_days: number
  auto_archive: boolean
  auto_delete: boolean
  created_at?: string
}

export async function listRetentionPolicies(): Promise<RetentionPolicy[]> {
  return apiRequest('/api/dms/retention')
}

export async function createRetentionPolicy(payload: {
  template_document_type?: TemplateDocumentType
  retention_days?: number
  auto_archive?: boolean
}): Promise<RetentionPolicy> {
  return apiRequest('/api/dms/retention', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function downloadGeneratedDocument(
  documentId: string,
  format: 'docx' | 'pdf' | 'txt' = 'pdf',
): Promise<Blob | string> {
  const headers = await getJsonHeaders()
  const res = await fetch(`/api/dms/generated-documents/${documentId}/download?format=${format}`, {
    headers,
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  if (format === 'txt') return res.text()
  return res.blob()
}

export async function listGeneratedDocumentVersions(
  documentId: string,
): Promise<Record<string, unknown>[]> {
  return apiRequest(`/api/dms/generated-documents/${documentId}/versions`)
}

export async function previewMissingFields(
  folderId: string,
  payload: { template_version_id: string; overrides?: Record<string, string> },
): Promise<{
  missing_fields: string[]
  prerequisite_issues?: {
    primary_client_required?: boolean
    missing_party_roles?: string[]
  }
  is_complete: boolean
  total_placeholders: number
}> {
  return apiRequest(`/api/dms/folders/${folderId}/preview-missing-fields`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function createDossierExport(
  folderId: string,
  options: {
    include_audit?: boolean
    include_drafts?: boolean
    include_personal_data?: boolean
    include_external_documents?: boolean
    encrypt_zip?: boolean
  } = {},
): Promise<Record<string, unknown>> {
  return apiRequest(`/api/dms/folders/${folderId}/exports`, {
    method: 'POST',
    body: JSON.stringify(options),
  })
}

export async function listDossierExports(
  folderId: string,
): Promise<Record<string, unknown>[]> {
  return apiRequest(`/api/dms/folders/${folderId}/exports`)
}

export async function getDossierExport(
  folderId: string,
  exportId: string,
): Promise<Record<string, unknown>> {
  return apiRequest(`/api/dms/folders/${folderId}/exports/${exportId}`)
}

export async function getFolderFieldVault(
  folderId: string,
): Promise<Record<string, string>> {
  return apiRequest(`/api/dms/folders/${folderId}/field-vault`)
}

export async function putFolderFieldVault(
  folderId: string,
  values: Record<string, string>,
): Promise<Record<string, string>> {
  return apiRequest(`/api/dms/folders/${folderId}/field-vault`, {
    method: 'PUT',
    body: JSON.stringify(values),
  })
}
