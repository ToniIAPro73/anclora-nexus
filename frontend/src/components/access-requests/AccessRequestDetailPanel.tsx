'use client'

import { CheckCircle2, ClipboardList, XCircle } from 'lucide-react'
import type { TranslationKey } from '@/lib/i18n'
import type { AccessRequest, AccessRequestAuditEvent, AccessRequestLifecycle } from '@/lib/access-requests-api'
import { AccessRequestLifecyclePanel } from './AccessRequestLifecyclePanel'
import { productLabel, sourceLabel, statusLabel } from './AccessRequestsTable'

type Translate = (key: TranslationKey) => string

interface AccessRequestDetailPanelProps {
  request: AccessRequest | null
  auditEvents: AccessRequestAuditEvent[]
  auditLoading: boolean
  auditError: string | null
  lifecycle: AccessRequestLifecycle | null
  lifecycleLoading: boolean
  lifecycleError: string | null
  retryingEmail: boolean
  onApprove: () => void
  onReject: () => void
  onRetryDecisionEmail: () => void
  t: Translate
}

function formatDate(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="surface-secondary surface-copy-safe rounded-xl border border-soft-subtle/50 bg-navy-deep/30 p-3">
      <p className="kpi-label">{label}</p>
      <p className="mt-2 text-sm text-soft-white">{value || '-'}</p>
    </div>
  )
}

function formatDetails(details: Record<string, unknown>): string {
  const entries = Object.entries(details).filter(([, value]) => value !== null && value !== undefined && value !== '')
  if (entries.length === 0) return '-'
  return entries.map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`).join(' · ')
}

export function AccessRequestDetailPanel({
  request,
  auditEvents,
  auditLoading,
  auditError,
  lifecycle,
  lifecycleLoading,
  lifecycleError,
  retryingEmail,
  onApprove,
  onReject,
  onRetryDecisionEmail,
  t,
}: AccessRequestDetailPanelProps) {
  if (!request) {
    return (
      <section className="surface-primary rounded-2xl border border-soft-subtle bg-navy-surface/35 p-5">
        <div className="flex items-start gap-3">
          <ClipboardList className="mt-1 h-5 w-5 text-blue-light" />
          <div>
            <h2 className="section-title">{t('accessRequestsDetailTitle')}</h2>
            <p className="section-subtitle mt-1">{t('accessRequestsSelectPrompt')}</p>
          </div>
        </div>
      </section>
    )
  }

  const isPending = request.status === 'pending'

  return (
    <section className="surface-primary surface-copy-safe rounded-2xl border border-soft-subtle bg-navy-surface/35 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="kpi-label">{t('accessRequestsDetailTitle')}</p>
          <h2 className="section-title mt-2">{request.full_name}</h2>
          <p className="section-subtitle mt-1">{request.email}</p>
        </div>
        {isPending ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={onApprove} className="btn-action h-10 px-4">
              <CheckCircle2 className="h-4 w-4" />
              {t('accessRequestsApprove')}
            </button>
            <button type="button" onClick={onReject} className="btn-create h-10 px-4 text-rose-200 border-rose-400/35">
              <XCircle className="h-4 w-4" />
              {t('accessRequestsReject')}
            </button>
          </div>
        ) : null}
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <Field label={t('accessRequestsColumnProduct')} value={productLabel(request.product)} />
        <Field label={t('accessRequestsColumnStatus')} value={statusLabel(request.status, t)} />
        <Field label={t('accessRequestsColumnSource')} value={sourceLabel(request.source, t)} />
        <Field label={t('accessRequestsLanguage')} value={request.submission_language} />
        <Field label={t('accessRequestsCompany')} value={request.company || request.profile_type} />
        <Field label={t('accessRequestsPhone')} value={request.phone} />
        <Field label={t('accessRequestsCaptchaVerified')} value={request.captcha_verified ? t('accessRequestsYes') : t('accessRequestsNo')} />
        <Field label={t('accessRequestsCreatedAt')} value={formatDate(request.created_at)} />
      </div>

      <div className="mt-5 grid gap-3">
        <Field label={t('accessRequestsServiceCategory')} value={request.service_category} />
        <Field label={t('accessRequestsServiceSummary')} value={request.service_summary} />
        <Field label={t('accessRequestsIntendedUse')} value={request.intended_use} />
        <Field label={t('accessRequestsRequestedScope')} value={request.requested_scope} />
        <Field label={t('accessRequestsMessage')} value={request.message} />
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <Field label={t('accessRequestsReviewedAt')} value={formatDate(request.reviewed_at)} />
        <Field label={t('accessRequestsReviewedBy')} value={request.reviewed_by} />
        <Field label={t('accessRequestsAdminNotes')} value={request.admin_notes} />
        <Field label={t('accessRequestsRejectionReason')} value={request.rejection_reason} />
        {request.provisioning_status ? (
          <Field label="Provisioning Status" value={request.provisioning_status} />
        ) : null}
        {request.identity_subject_id ? (
          <Field label="Identity User ID" value={request.identity_subject_id} />
        ) : null}
        {request.identity_invitation_id ? (
          <Field label="Identity Invitation ID" value={request.identity_invitation_id} />
        ) : null}
        {request.membership_id ? (
          <Field label="Membership ID" value={request.membership_id} />
        ) : null}
      </div>

      {request.decision_email?.status ? (
        <div className="mt-5 rounded-xl border border-blue-light/25 bg-blue-light/10 p-3 text-sm text-blue-light">
          {t('accessRequestsEmailStatus')}: {request.decision_email.status}
        </div>
      ) : null}

      <AccessRequestLifecyclePanel
        lifecycle={lifecycle}
        loading={lifecycleLoading}
        error={lifecycleError}
        retrying={retryingEmail}
        onRetry={onRetryDecisionEmail}
        t={t}
      />

      <div className="mt-5">
        <div className="mb-3">
          <h3 className="section-title text-base">{t('accessRequestsAuditTitle')}</h3>
          <p className="section-subtitle mt-1">{t('accessRequestsAuditSubtitle')}</p>
        </div>
        {auditLoading ? (
          <div className="surface-secondary rounded-xl border border-soft-subtle/50 bg-navy-deep/30 p-3 text-sm text-soft-muted">
            {t('accessRequestsAuditLoading')}
          </div>
        ) : auditError ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-navy-surface/50 dark:text-rose-200">
            {auditError}
          </div>
        ) : auditEvents.length === 0 ? (
          <div className="surface-secondary rounded-xl border border-soft-subtle/50 bg-navy-deep/30 p-3 text-sm text-soft-muted">
            {t('accessRequestsAuditEmpty')}
          </div>
        ) : (
          <div className="space-y-2">
            {auditEvents.map((event) => (
              <div key={event.id} className="surface-secondary surface-copy-safe rounded-xl border border-soft-subtle/50 bg-navy-deep/30 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="text-sm font-semibold text-soft-white">{event.action}</p>
                  <p className="text-xs text-soft-muted">{formatDate(event.timestamp)}</p>
                </div>
                <p className="mt-2 text-xs text-soft-muted">
                  {t('accessRequestsAuditActor')}: {event.actor_type} / {event.actor_id}
                </p>
                <p className="mt-2 text-xs text-soft-muted">{formatDetails(event.details)}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
