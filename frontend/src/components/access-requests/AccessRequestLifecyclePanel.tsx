'use client'

import { RefreshCw } from 'lucide-react'
import type { TranslationKey } from '@/lib/i18n'
import type { AccessRequestLifecycle } from '@/lib/access-requests-api'

type Translate = (key: TranslationKey) => string

interface AccessRequestLifecyclePanelProps {
  lifecycle: AccessRequestLifecycle | null
  loading: boolean
  error: string | null
  retrying: boolean
  retryingProvisioning: boolean
  onRetry: () => void
  onRetryProvisioning: () => void
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

function lifecycleLabel(prefix: string, value: string | null | undefined, t: Translate): string {
  if (!value) return '-'
  const key = `${prefix}${value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('')}` as TranslationKey
  return t(key)
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface-secondary surface-copy-safe rounded-xl border border-soft-subtle/50 bg-navy-deep/30 p-3">
      <p className="kpi-label">{label}</p>
      <p className="mt-2 text-sm text-soft-white">{value || '-'}</p>
    </div>
  )
}

export function AccessRequestLifecyclePanel({
  lifecycle,
  loading,
  error,
  retrying,
  retryingProvisioning,
  onRetry,
  onRetryProvisioning,
  t,
}: AccessRequestLifecyclePanelProps) {
  return (
    <div className="mt-5 rounded-xl border border-blue-light/20 bg-blue-light/5 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="section-title text-base">{t('accessRequestsLifecycleTitle')}</h3>
          <p className="section-subtitle mt-1">{t('accessRequestsLifecycleSubtitle')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {lifecycle?.provisioning_retry_available ? (
            <button type="button" className="btn-action h-10 px-4" onClick={onRetryProvisioning} disabled={retryingProvisioning}>
              <RefreshCw className={`h-4 w-4 ${retryingProvisioning ? 'animate-spin' : ''}`} />
              {retryingProvisioning ? t('accessRequestsProvisioningRetrying') : t('accessRequestsProvisioningRetry')}
            </button>
          ) : null}
          {lifecycle?.retry_available ? (
            <button type="button" className="btn-action h-10 px-4" onClick={onRetry} disabled={retrying}>
              <RefreshCw className={`h-4 w-4 ${retrying ? 'animate-spin' : ''}`} />
              {retrying ? t('accessRequestsDecisionEmailRetrying') : t('accessRequestsDecisionEmailRetry')}
            </button>
          ) : null}
        </div>
      </div>

      {loading ? (
        <div className="mt-3 surface-secondary rounded-xl border border-soft-subtle/50 bg-navy-deep/30 p-3 text-sm text-soft-muted">
          {t('accessRequestsLifecycleLoading')}
        </div>
      ) : error ? (
        <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-navy-surface/50 dark:text-rose-200">
          {error}
        </div>
      ) : lifecycle?.decision_status && lifecycle?.provisioning_status && lifecycle?.email_status ? (
        <>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Field
              label={t('accessRequestsLifecycleDecision')}
              value={lifecycleLabel('accessRequestsLifecycleDecision', lifecycle.decision_status, t)}
            />
            <Field
              label={t('accessRequestsLifecycleProvisioning')}
              value={lifecycleLabel('accessRequestsLifecycleProvisioning', lifecycle.provisioning_status, t)}
            />
            <Field
              label={t('accessRequestsLifecycleEmail')}
              value={lifecycleLabel('accessRequestsLifecycleEmail', lifecycle.email_status, t)}
            />
            <Field label={t('accessRequestsLifecycleLastEvent')} value={formatDate(lifecycle.last_event_at)} />
            <Field label={t('accessRequestsReviewedBy')} value={lifecycle.reviewed_by || '-'} />
            <Field label={t('accessRequestsReviewedAt')} value={formatDate(lifecycle.reviewed_at)} />
            <Field label={t('accessRequestsLifecycleInviteExpires')} value={formatDate(lifecycle.invite_expires_at)} />
            <Field label={t('accessRequestsLifecycleEmailRetryAvailable')} value={lifecycle.retry_available ? t('accessRequestsYes') : t('accessRequestsNo')} />
            <Field label={t('accessRequestsLifecycleProvisioningRetryAvailable')} value={lifecycle.provisioning_retry_available ? t('accessRequestsYes') : t('accessRequestsNo')} />
          </div>
          {!lifecycle.retry_available && !lifecycle.provisioning_retry_available ? (
            <p className="mt-3 text-xs text-soft-muted">{t('accessRequestsLifecycleRetryUnavailable')}</p>
          ) : null}
        </>
      ) : (
        <div className="mt-3 surface-secondary rounded-xl border border-soft-subtle/50 bg-navy-deep/30 p-3 text-sm text-soft-muted">
          {t('accessRequestsLifecycleEmpty')}
        </div>
      )}
    </div>
  )
}
