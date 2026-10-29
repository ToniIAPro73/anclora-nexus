'use client'

import { useCallback, useEffect, useState } from 'react'
import { Filter, Inbox, RefreshCw, ShieldCheck } from 'lucide-react'
import { useI18n } from '@/lib/i18n'
import {
  ApiError,
  approveAccessRequest,
  getAccessRequestAnalyticsSummary,
  getAccessRequestAudit,
  getAccessRequest,
  getAccessRequestLifecycle,
  listAccessRequests,
  rejectAccessRequest,
  retryAccessRequestDecisionEmail,
  retryAccessRequestProvisioning,
  type AccessRequest,
  type AccessRequestAuditEvent,
  type AccessRequestAnalyticsSummary,
  type AccessRequestLifecycle,
  type AccessRequestProduct,
  type AccessRequestSource,
  type AccessRequestStatus,
} from '@/lib/access-requests-api'
import { AccessRequestDecisionDialog } from '@/components/access-requests/AccessRequestDecisionDialog'
import { AccessRequestDetailPanel } from '@/components/access-requests/AccessRequestDetailPanel'
import { AccessRequestOperationsDashboard } from '@/components/access-requests/AccessRequestOperationsDashboard'
import { AccessRequestSlaPanel } from '@/components/access-requests/AccessRequestSlaPanel'
import { AccessRequestsTable } from '@/components/access-requests/AccessRequestsTable'
import { approveSyncXmlPilot, rejectSyncXmlPilot } from '@/lib/syncxml-pilot-api'

export default function AccessRequestsPage() {
  const { t } = useI18n()
  const [requests, setRequests] = useState<AccessRequest[]>([])
  const [selected, setSelected] = useState<AccessRequest | null>(null)
  const [analytics, setAnalytics] = useState<AccessRequestAnalyticsSummary | null>(null)
  const [statusFilter, setStatusFilter] = useState<AccessRequestStatus | ''>('pending')
  const [productFilter, setProductFilter] = useState<AccessRequestProduct | ''>('')
  const [sourceFilter, setSourceFilter] = useState<AccessRequestSource | ''>('')
  const [emailFilter, setEmailFilter] = useState('')
  const [auditEvents, setAuditEvents] = useState<AccessRequestAuditEvent[]>([])
  const [lifecycle, setLifecycle] = useState<AccessRequestLifecycle | null>(null)
  const [loading, setLoading] = useState(true)
  const [analyticsLoading, setAnalyticsLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [auditLoading, setAuditLoading] = useState(false)
  const [lifecycleLoading, setLifecycleLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [retryingEmail, setRetryingEmail] = useState(false)
  const [retryingProvisioning, setRetryingProvisioning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [analyticsError, setAnalyticsError] = useState<string | null>(null)
  const [auditError, setAuditError] = useState<string | null>(null)
  const [lifecycleError, setLifecycleError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [decisionError, setDecisionError] = useState<string | null>(null)
  const [decisionMode, setDecisionMode] = useState<'approve' | 'reject' | null>(null)
  const [adminNotes, setAdminNotes] = useState('')
  const [rejectionReason, setRejectionReason] = useState('')

  const selectedId = selected?.id ?? null
  const pendingVisibleCount = requests.filter((request) => request.status === 'pending').length
  const decidedVisibleCount = requests.filter((request) => request.status === 'approved' || request.status === 'rejected').length

  const formatApiError = useCallback((err: unknown, fallbackKey: Parameters<typeof t>[0]) => {
    if (err instanceof ApiError) {
      if (err.status === 403) return t('accessRequestsPermissionDenied')
      if (err.status === 404) return t('accessRequestsNotFound')
      if (err.status === 409) return t('accessRequestsInvalidTransition')
      if (err.status === 401) return t('accessRequestsAuthRequired')
    }
    return err instanceof Error ? err.message : t(fallbackKey)
  }, [t])

  const loadList = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listAccessRequests({
        status: statusFilter,
        product: productFilter,
        source: sourceFilter,
        email: emailFilter,
        intake_domain: 'access_request',
        limit: 50,
      })
      setRequests(payload)
      setSelected((current) => payload.find((request) => request.id === current?.id) ?? payload[0] ?? null)
    } catch (err) {
      setError(formatApiError(err, 'accessRequestsLoadError'))
      setRequests([])
      setSelected(null)
    } finally {
      setLoading(false)
    }
  }, [emailFilter, formatApiError, productFilter, sourceFilter, statusFilter])

  useEffect(() => {
    void loadList()
  }, [loadList])

  const loadAnalytics = useCallback(async () => {
    setAnalyticsLoading(true)
    setAnalyticsError(null)
    try {
      setAnalytics(await getAccessRequestAnalyticsSummary(500))
    } catch (err) {
      setAnalytics(null)
      setAnalyticsError(formatApiError(err, 'accessRequestsAnalyticsLoadError'))
    } finally {
      setAnalyticsLoading(false)
    }
  }, [formatApiError])

  useEffect(() => {
    void loadAnalytics()
  }, [loadAnalytics])

  const loadAudit = useCallback(async (requestId: string) => {
    setAuditLoading(true)
    setAuditError(null)
    try {
      setAuditEvents(await getAccessRequestAudit(requestId))
    } catch (err) {
      setAuditEvents([])
      setAuditError(formatApiError(err, 'accessRequestsAuditLoadError'))
    } finally {
      setAuditLoading(false)
    }
  }, [formatApiError])

  const loadLifecycle = useCallback(async (requestId: string) => {
    setLifecycleLoading(true)
    setLifecycleError(null)
    try {
      setLifecycle(await getAccessRequestLifecycle(requestId))
    } catch (err) {
      setLifecycle(null)
      setLifecycleError(formatApiError(err, 'accessRequestsLifecycleLoadError'))
    } finally {
      setLifecycleLoading(false)
    }
  }, [formatApiError])

  useEffect(() => {
    if (!selectedId) {
      setAuditEvents([])
      setAuditError(null)
      setLifecycle(null)
      setLifecycleError(null)
      return
    }
    void loadAudit(selectedId)
    void loadLifecycle(selectedId)
  }, [loadAudit, loadLifecycle, selectedId])

  async function selectRequest(request: AccessRequest) {
    await openRequestById(request.id, request)
  }

  async function openRequestById(requestId: string, fallback?: AccessRequest) {
    if (fallback) {
      setSelected(fallback)
    }
    setDetailLoading(true)
    setError(null)
    try {
      setSelected(await getAccessRequest(requestId))
    } catch (err) {
      setError(formatApiError(err, 'accessRequestsDetailLoadError'))
    } finally {
      setDetailLoading(false)
    }
  }

  function openDecision(mode: 'approve' | 'reject') {
    setDecisionMode(mode)
    setDecisionError(null)
    setAdminNotes('')
    setRejectionReason('')
  }

  async function submitDecision() {
    if (!selected || !decisionMode) return

    setSubmitting(true)
    setDecisionError(null)
    setSuccess(null)
    try {
      let payload: AccessRequest
      if (selected.product === 'syncxml') {
        const syncXmlPayload =
          decisionMode === 'approve'
            ? await approveSyncXmlPilot(selected.id, {
                admin_notes: adminNotes.trim() || undefined,
              })
            : await rejectSyncXmlPilot(selected.id, {
                internal_reason: adminNotes.trim() || rejectionReason.trim(),
                user_reason: rejectionReason.trim(),
              })
        payload = syncXmlPayload.record
      } else {
        payload =
          decisionMode === 'approve'
            ? await approveAccessRequest(selected.id, {
                admin_notes: adminNotes.trim() || undefined,
              })
            : await rejectAccessRequest(selected.id, {
                admin_notes: adminNotes.trim() || undefined,
                rejection_reason: rejectionReason.trim(),
              })
      }

      setSelected(payload)
      setDecisionMode(null)
      const emailStatus = payload.decision_email?.status
      setSuccess(
        emailStatus
          ? `${t('accessRequestsDecisionSaved')} ${t('accessRequestsEmailStatus')}: ${emailStatus}`
          : t('accessRequestsDecisionSaved'),
      )
      await loadList()
      await loadAnalytics()
      setSelected(payload)
      if (payload.lifecycle) {
        setLifecycle(payload.lifecycle)
      } else {
        await loadLifecycle(payload.id)
      }
      await loadAudit(payload.id)
    } catch (err) {
      setDecisionError(formatApiError(err, 'accessRequestsDecisionError'))
    } finally {
      setSubmitting(false)
    }
  }

  async function retryDecisionEmail() {
    if (!selected) return

    setRetryingEmail(true)
    setError(null)
    setSuccess(null)
    try {
      const payload = await retryAccessRequestDecisionEmail(selected.id)
      setSelected(payload)
      const emailStatus = payload.decision_email?.status
      setSuccess(
        emailStatus
          ? `${t('accessRequestsDecisionEmailRetrySaved')} ${t('accessRequestsEmailStatus')}: ${emailStatus}`
          : t('accessRequestsDecisionEmailRetrySaved'),
      )
      if (payload.lifecycle) {
        setLifecycle(payload.lifecycle)
      } else {
        await loadLifecycle(payload.id)
      }
      await loadAudit(payload.id)
      await loadList()
      await loadAnalytics()
      setSelected(payload)
    } catch (err) {
      setError(formatApiError(err, 'accessRequestsDecisionEmailRetryError'))
    } finally {
      setRetryingEmail(false)
    }
  }

  async function retryProvisioning() {
    if (!selected) return
    setRetryingProvisioning(true)
    setError(null)
    setSuccess(null)
    try {
      const payload = await retryAccessRequestProvisioning(selected.id)
      setSelected(payload)
      setSuccess(
        payload.lifecycle?.provisioning_status === 'invite_ready'
          ? t('accessRequestsInvitationResendSaved')
          : t('accessRequestsProvisioningRetrySaved'),
      )
      if (payload.lifecycle) setLifecycle(payload.lifecycle)
      else await loadLifecycle(payload.id)
      await Promise.all([loadAudit(payload.id), loadList(), loadAnalytics()])
      setSelected(payload)
    } catch (err) {
      setError(formatApiError(err, 'accessRequestsProvisioningRetryError'))
    } finally {
      setRetryingProvisioning(false)
    }
  }

  return (
    <div className="min-h-full p-6">
      <div className="mx-auto flex max-w-screen-2xl flex-col gap-5">
        <section className="surface-primary rounded-2xl border border-soft-subtle bg-navy-surface/35 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="page-title">{t('accessRequestsTitle')}</h1>
              <p className="page-subtitle mt-2">{t('accessRequestsSubtitle')}</p>
            </div>
            <button
              type="button"
              onClick={() => void Promise.all([loadList(), loadAnalytics()])}
              className="btn-action"
              disabled={loading || analyticsLoading}
            >
              <RefreshCw className={`h-4 w-4 ${loading || analyticsLoading ? 'animate-spin' : ''}`} />
              {t('refresh')}
            </button>
          </div>
        </section>

        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-navy-surface/50 dark:text-rose-200">
            {error}
          </div>
        ) : null}
        {success ? (
          <div className="rounded-xl border border-emerald-400/30 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-200">
            {success}
          </div>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
          <section className="surface-primary rounded-2xl border border-soft-subtle bg-navy-surface/35 p-5">
            <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-gold">
                  <Inbox className="h-5 w-5" />
                  <h2 className="section-title">{t('accessRequestsQueueTitle')}</h2>
                </div>
                <p className="section-subtitle mt-1">{t('accessRequestsQueueSubtitle')}</p>
              </div>
              <div className="grid min-w-60 grid-cols-3 gap-2 text-center">
                <div>
                  <p className="kpi-label">{t('accessRequestsVisibleTotal')}</p>
                  <p className="mt-1 text-xl font-semibold text-soft-white">{requests.length}</p>
                </div>
                <div>
                  <p className="kpi-label">{t('accessRequestsStatusPending')}</p>
                  <p className="mt-1 text-xl font-semibold text-gold">{pendingVisibleCount}</p>
                </div>
                <div>
                  <p className="kpi-label">{t('accessRequestsResolved')}</p>
                  <p className="mt-1 text-xl font-semibold text-emerald-200">{decidedVisibleCount}</p>
                </div>
              </div>
            </div>

            <div className="mb-5 border-y border-soft-subtle/50 py-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-soft-white">
                <Filter className="h-4 w-4 text-blue-light" />
                {t('accessRequestsFilterHint')}
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-4">
                <label className="min-w-0">
                  <span className="mb-2 block text-sm font-semibold text-soft-white">{t('status')}</span>
                  <select className="ui-select min-w-0" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as AccessRequestStatus | '')}>
                    <option value="">{t('accessRequestsAllStatuses')}</option>
                    <option value="pending">{t('accessRequestsStatusPending')}</option>
                    <option value="approved">{t('accessRequestsStatusApproved')}</option>
                    <option value="rejected">{t('accessRequestsStatusRejected')}</option>
                    <option value="cancelled">{t('accessRequestsStatusCancelled')}</option>
                  </select>
                </label>
                <label className="min-w-0">
                  <span className="mb-2 block text-sm font-semibold text-soft-white">{t('accessRequestsColumnProduct')}</span>
                  <select className="ui-select min-w-0" value={productFilter} onChange={(event) => setProductFilter(event.target.value as AccessRequestProduct | '')}>
                    <option value="">{t('accessRequestsAllProducts')}</option>
                    <option value="synergi">Synergi</option>
                    <option value="data_lab">Data Lab</option>
                    <option value="syncxml">GuestHub</option>
                  </select>
                </label>
                <label className="min-w-0">
                  <span className="mb-2 block text-sm font-semibold text-soft-white">{t('accessRequestsColumnSource')}</span>
                  <select className="ui-select min-w-0" value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as AccessRequestSource | '')}>
                    <option value="">{t('accessRequestsAllSources')}</option>
                    <option value="synergi_app">{t('accessRequestsSourceSynergiApp')}</option>
                    <option value="data_lab_app">{t('accessRequestsSourceDataLabApp')}</option>
                    <option value="syncxml_landing">{t('accessRequestsSourceSyncXmlLanding')}</option>
                    <option value="nexus_manual">{t('accessRequestsSourceNexusManual')}</option>
                    <option value="external_api">{t('accessRequestsSourceExternalApi')}</option>
                  </select>
                </label>
                <label className="min-w-0">
                  <span className="mb-2 block text-sm font-semibold text-soft-white">{t('accessRequestsEmailFilter')}</span>
                  <input
                    className="ui-input min-w-0"
                    value={emailFilter}
                    onChange={(event) => setEmailFilter(event.target.value)}
                    placeholder={t('accessRequestsEmailFilterPlaceholder')}
                  />
                </label>
              </div>
            </div>
            <AccessRequestsTable
              requests={requests}
              selectedId={selectedId}
              loading={loading}
              onSelect={(request) => void selectRequest(request)}
              t={t}
            />
          </section>

          <div className="min-w-0 space-y-3">
            {detailLoading ? (
              <div className="surface-primary rounded-2xl border border-soft-subtle bg-navy-surface/35 p-5 text-sm text-soft-muted">
                {t('accessRequestsDetailLoading')}
              </div>
            ) : null}
            <AccessRequestDetailPanel
              request={selected}
              auditEvents={auditEvents}
              auditLoading={auditLoading}
              auditError={auditError}
              lifecycle={lifecycle}
              lifecycleLoading={lifecycleLoading}
              lifecycleError={lifecycleError}
              retryingEmail={retryingEmail}
              retryingProvisioning={retryingProvisioning}
              onApprove={() => openDecision('approve')}
              onReject={() => openDecision('reject')}
              onRetryDecisionEmail={() => void retryDecisionEmail()}
              onRetryProvisioning={() => void retryProvisioning()}
              t={t}
            />
            <AccessRequestSlaPanel onSelectRequest={(id) => void openRequestById(id)} t={t} />
          </div>
        </div>

        <div className="flex items-center gap-2 px-1 text-sm font-semibold text-soft-white">
          <ShieldCheck className="h-4 w-4 text-blue-light" />
          {t('accessRequestsAnalyticsTitle')}
        </div>
        <AccessRequestOperationsDashboard
          analytics={analytics}
          loading={analyticsLoading}
          error={analyticsError}
          onSelectAttentionItem={(requestId) => void openRequestById(requestId)}
          t={t}
        />
      </div>

      <AccessRequestDecisionDialog
        request={selected}
        mode={decisionMode}
        adminNotes={adminNotes}
        rejectionReason={rejectionReason}
        submitting={submitting}
        error={decisionError}
        onAdminNotesChange={setAdminNotes}
        onRejectionReasonChange={setRejectionReason}
        onClose={() => setDecisionMode(null)}
        onSubmit={() => void submitDecision()}
        t={t}
      />
    </div>
  )
}
