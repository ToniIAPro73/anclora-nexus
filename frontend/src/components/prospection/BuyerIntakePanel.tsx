'use client'

import { useEffect, useMemo, useState } from 'react'
import { Globe2, Network, RefreshCw, Users } from 'lucide-react'
import database from '@/lib/neon-data-client'
import { buildBackendUrl } from '@/lib/backend-url'
import { createBuyer, type ProspectionWorkspaceResponse } from '@/lib/prospection-api'
import { useI18n } from '@/lib/i18n'
import type { TranslationKey } from '@/lib/i18n'

type IntelligencePack = {
  id: string
  pack_label: string
  is_default: boolean
  market_scope: string
}

type Props = {
  sourceSummary?: ProspectionWorkspaceResponse['buyer_source_summary']
  onCreated: () => Promise<void>
}

function inputClassName() {
  return 'ui-input'
}

export function BuyerIntakePanel({ sourceSummary, onCreated }: Props) {
  const { t } = useI18n()
  const [packs, setPacks] = useState<IntelligencePack[]>([])
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    budget_min: '',
    budget_max: '',
    preferred_zones: '',
    purchase_horizon: '0_3m',
    source_type: 'partner_referral',
    source_platform: 'exp_agent',
    referral_partner_name: '',
    referral_partner_contact: '',
    referral_partner_type: 'exp_agent',
    intelligence_pack_id: '',
    notes: '',
  })

  useEffect(() => {
    let cancelled = false
    const loadPacks = async () => {
      try {
        const { data } = await database.auth.getSession()
        const res = await fetch(buildBackendUrl('/api/intelligence/packs'), {
          headers: {
            Authorization: `Bearer ${data.session?.access_token || ''}`,
          },
          cache: 'no-store',
        })
        if (!res.ok) return
        const body = await res.json()
        if (!cancelled) setPacks(body.items || [])
      } catch {
        if (!cancelled) setPacks([])
      }
    }
    void loadPacks()
    return () => {
      cancelled = true
    }
  }, [])

  const sourceTypeCards = useMemo(() => ([
    { key: 'partner_referral', count: sourceSummary?.partner_referrals || 0 },
    { key: 'crm_reactivation', count: sourceSummary?.crm_reactivation || 0 },
    { key: 'web_inbound', count: sourceSummary?.web_inbound || 0 },
  ]), [sourceSummary])

  const showPartnerFields = form.source_type === 'partner_referral'

  const submit = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await createBuyer({
        full_name: form.full_name,
        email: form.email || undefined,
        phone: form.phone || undefined,
        budget_min: form.budget_min ? Number(form.budget_min) : undefined,
        budget_max: form.budget_max ? Number(form.budget_max) : undefined,
        preferred_zones: form.preferred_zones.split(',').map((item) => item.trim()).filter(Boolean),
        purchase_horizon: form.purchase_horizon,
        source_type: form.source_type,
        source_platform: form.source_platform,
        referral_partner_name: showPartnerFields ? form.referral_partner_name || undefined : undefined,
        referral_partner_contact: showPartnerFields ? form.referral_partner_contact || undefined : undefined,
        referral_partner_type: showPartnerFields ? form.referral_partner_type || undefined : undefined,
        intelligence_pack_id: form.intelligence_pack_id || undefined,
        notes: form.notes || undefined,
      })
      setForm({
        full_name: '',
        email: '',
        phone: '',
        budget_min: '',
        budget_max: '',
        preferred_zones: '',
        purchase_horizon: '0_3m',
        source_type: 'partner_referral',
        source_platform: 'exp_agent',
        referral_partner_name: '',
        referral_partner_contact: '',
        referral_partner_type: 'exp_agent',
        intelligence_pack_id: '',
        notes: '',
      })
      setMessage(t('buyersIntakeCreated'))
      await onCreated()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('buyersIntakeCreateError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="surface-primary surface-copy-safe rounded-2xl border border-soft-subtle bg-navy-surface/35 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <Users className="h-4 w-4 text-gold" />
            {t('buyersIntakeTitle')}
          </h2>
          <p className="page-subtitle">{t('buyersIntakeSubtitle')}</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-gold/25 bg-gold/10 px-3 py-1 text-xs font-semibold text-gold">
          <Network className="h-3.5 w-3.5" />
          {t('buyersIntakeContractReady')}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
        {sourceTypeCards.map((item) => (
          <div key={item.key} className="surface-secondary rounded-xl border border-soft-subtle/30 bg-navy-deep/25 p-3">
            <p className="kpi-label">{t(`buyersSourceType_${item.key}` as TranslationKey)}</p>
            <p className="kpi-value text-gold mt-1">{item.count}</p>
          </div>
        ))}
      </div>

      {message ? (
        <div className="surface-secondary rounded-xl border border-soft-subtle/30 bg-navy-deep/25 p-3 mt-4 text-sm text-soft-white break-words">
          {message}
        </div>
      ) : null}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4">
        <div className="surface-secondary surface-copy-safe rounded-xl border border-soft-subtle/30 bg-navy-deep/25 p-4 space-y-3">
          <label className="block">
            <span className="kpi-label">{t('buyersIntakeFullName')}</span>
            <input className={inputClassName()} value={form.full_name} onChange={(e) => setForm((prev) => ({ ...prev, full_name: e.target.value }))} />
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="block">
              <span className="kpi-label">{t('sourceEmail')}</span>
              <input className={inputClassName()} value={form.email} onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))} />
            </label>
            <label className="block">
              <span className="kpi-label">{t('sourcePhone')}</span>
              <input className={inputClassName()} value={form.phone} onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))} />
            </label>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="block">
              <span className="kpi-label">{t('buyersBudgetMin')}</span>
              <input className={inputClassName()} inputMode="numeric" value={form.budget_min} onChange={(e) => setForm((prev) => ({ ...prev, budget_min: e.target.value }))} />
            </label>
            <label className="block">
              <span className="kpi-label">{t('buyersBudgetMax')}</span>
              <input className={inputClassName()} inputMode="numeric" value={form.budget_max} onChange={(e) => setForm((prev) => ({ ...prev, budget_max: e.target.value }))} />
            </label>
          </div>
          <label className="block">
            <span className="kpi-label">{t('buyersPreferredZones')}</span>
            <input className={inputClassName()} value={form.preferred_zones} onChange={(e) => setForm((prev) => ({ ...prev, preferred_zones: e.target.value }))} placeholder={t('buyersPreferredZonesPlaceholder')} />
          </label>
          <label className="block">
              <span className="kpi-label">{t('buyersPurchaseHorizon')}</span>
              <select className="ui-select" value={form.purchase_horizon} onChange={(e) => setForm((prev) => ({ ...prev, purchase_horizon: e.target.value }))}>
                {['immediate', '0_3m', '3_6m', '6_12m', '12m_plus'].map((value) => (
                  <option key={value} value={value}>{t(`buyersPurchaseHorizon_${value}` as TranslationKey)}</option>
                ))}
              </select>
            </label>
        </div>

        <div className="surface-secondary surface-copy-safe rounded-xl border border-soft-subtle/30 bg-navy-deep/25 p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="block">
              <span className="kpi-label">{t('buyersSourceType')}</span>
              <select className="ui-select" value={form.source_type} onChange={(e) => setForm((prev) => ({ ...prev, source_type: e.target.value }))}>
                {['partner_referral', 'crm_reactivation', 'web_inbound'].map((value) => (
                  <option key={value} value={value}>{t(`buyersSourceType_${value}` as TranslationKey)}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="kpi-label">{t('buyersSourcePlatform')}</span>
              <select className="ui-select" value={form.source_platform} onChange={(e) => setForm((prev) => ({ ...prev, source_platform: e.target.value }))}>
                {['exp_agent', 'external_agent', 'crm', 'web'].map((value) => (
                  <option key={value} value={value}>{t(`buyersSourcePlatform_${value}` as TranslationKey)}</option>
                ))}
              </select>
            </label>
          </div>

          {showPartnerFields ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="block">
                <span className="kpi-label">{t('buyersReferralPartnerName')}</span>
                <input className={inputClassName()} value={form.referral_partner_name} onChange={(e) => setForm((prev) => ({ ...prev, referral_partner_name: e.target.value }))} />
              </label>
              <label className="block">
                <span className="kpi-label">{t('buyersReferralPartnerContact')}</span>
                <input className={inputClassName()} value={form.referral_partner_contact} onChange={(e) => setForm((prev) => ({ ...prev, referral_partner_contact: e.target.value }))} />
              </label>
              <label className="block md:col-span-2">
                <span className="kpi-label">{t('buyersReferralPartnerType')}</span>
                <select className="ui-select" value={form.referral_partner_type} onChange={(e) => setForm((prev) => ({ ...prev, referral_partner_type: e.target.value }))}>
                  {['exp_agent', 'external_agent', 'broker', 'partner', 'family_office', 'relocation'].map((value) => (
                    <option key={value} value={value}>{t(`buyersSourcePlatform_${value}` as TranslationKey)}</option>
                  ))}
                </select>
              </label>
            </div>
          ) : null}

          <label className="block">
            <span className="kpi-label">{t('buyersIntelligencePack')}</span>
            <select className="ui-select" value={form.intelligence_pack_id} onChange={(e) => setForm((prev) => ({ ...prev, intelligence_pack_id: e.target.value }))}>
              <option value="">{t('buyersIntelligencePackNone')}</option>
              {packs
                .filter((pack) => pack.market_scope === 'buyer' || pack.market_scope === 'mixed')
                .map((pack) => (
                  <option key={pack.id} value={pack.id}>
                    {pack.pack_label}{pack.is_default ? ` · ${t('intelligencePacksActive')}` : ''}
                  </option>
                ))}
            </select>
          </label>

          <label className="block">
            <span className="kpi-label">{t('notes')}</span>
            <textarea className="ui-textarea min-h-24" value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} />
          </label>

          <button
            type="button"
            disabled={saving || !form.full_name.trim()}
            onClick={() => void submit()}
            className="btn-action"
          >
            {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Globe2 className="h-4 w-4" />}
            {saving ? t('buyersIntakeSaving') : t('buyersIntakeCreate')}
          </button>
        </div>
      </div>
    </section>
  )
}
