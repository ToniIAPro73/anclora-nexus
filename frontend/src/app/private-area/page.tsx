'use client'

import { Building2, LockKeyhole, Sparkles } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useI18n } from '@/lib/i18n'
import database from '@/lib/neon-data-client'
import { PrivateAreaShell } from '@/components/private-area/PrivateAreaShell'
import { resolvePortalEntryHref } from '@/lib/private-area-access'
import { useEffect, useState } from 'react'
import type { IdentitySession } from '@/lib/neon-data-client'
import Link from 'next/link'

const PORTAL_META = [
  { key: 'agent', icon: LockKeyhole },
] as const

export default function PrivateAreaPage() {
  const { t } = useI18n()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    let mounted = true
    void database.auth.getSession().then(({ data }: { data: { session: IdentitySession | null } }) => {
      if (mounted) setIsAuthenticated(Boolean(data.session))
    })
    return () => {
      mounted = false
    }
  }, [])

  return (
    <PrivateAreaShell
      eyebrow={t('privateAreaEyebrow')}
      title={t('privateAreaTitle')}
      subtitle={t('privateAreaSubtitle')}
    >
      <div className="grid gap-5 lg:grid-cols-1 max-w-xl mx-auto">
        {PORTAL_META.map(({ key, icon: Icon }) => (
          <Card key={key} className="surface-primary border-soft-subtle/15 bg-navy-deep/55">
            <CardHeader className="gap-3">
              <div className="flex items-center justify-between gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-gold/20 bg-gold/10 text-gold">
                  <Icon className="h-5 w-5" />
                </div>
                <span className="rounded-full border border-soft-subtle/20 bg-navy-darker/60 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-soft-muted">
                  {t(`privateAreaPortalStatus_${key}`)}
                </span>
              </div>
              <CardTitle className="text-2xl text-soft-white">{t(`privateAreaPortalTitle_${key}`)}</CardTitle>
              <CardDescription className="text-sm leading-6 text-soft-muted">
                {t(`privateAreaPortalDescription_${key}`)}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="surface-secondary rounded-2xl border border-soft-subtle/15 bg-navy-darker/40 p-4">
                <p className="kpi-label">{t('privateAreaPortalAudienceLabel')}</p>
                <p className="mt-2 text-sm leading-6 text-soft-white">{t(`privateAreaPortalAudience_${key}`)}</p>
              </div>
              <Link
                href={resolvePortalEntryHref(key, isAuthenticated)}
                className="inline-flex w-full items-center justify-center rounded-full border border-gold/40 bg-gold px-5 py-3 text-sm font-semibold text-[#0F1629] transition hover:brightness-110"
              >
                {t(`privateAreaPortalAction_${key}`)}
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-8 grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <Card className="surface-primary border-soft-subtle/15 bg-navy-deep/45">
          <CardHeader>
            <div className="flex items-center gap-3">
              <Building2 className="h-5 w-5 text-gold" />
              <CardTitle className="text-soft-white">{t('privateAreaArchitectureTitle')}</CardTitle>
            </div>
            <CardDescription className="text-soft-muted">{t('privateAreaArchitectureSubtitle')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="surface-secondary rounded-2xl border border-soft-subtle/15 bg-navy-darker/40 p-4">
              <p className="kpi-label">{t('privateAreaArchitectureCoreTitle')}</p>
              <p className="mt-2 text-sm leading-6 text-soft-muted">{t('privateAreaArchitectureCoreCopy')}</p>
            </div>
            <div className="surface-secondary rounded-2xl border border-soft-subtle/15 bg-navy-darker/40 p-4">
              <p className="kpi-label">{t('privateAreaArchitectureAccessTitle')}</p>
              <p className="mt-2 text-sm leading-6 text-soft-muted">{t('privateAreaArchitectureAccessCopy')}</p>
            </div>
          </CardContent>
        </Card>

        <Card className="surface-primary border-soft-subtle/15 bg-navy-deep/45">
          <CardHeader>
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-gold" />
              <CardTitle className="text-soft-white">{t('privateAreaRoadmapTitle')}</CardTitle>
            </div>
            <CardDescription className="text-soft-muted">{t('privateAreaRoadmapSubtitle')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(['agent'] as const).map((key) => (
              <div key={key} className="surface-secondary rounded-2xl border border-soft-subtle/15 bg-navy-darker/40 p-4">
                <p className="text-sm font-semibold text-soft-white">{t(`privateAreaPortalTitle_${key}`)}</p>
                <p className="mt-2 text-sm leading-6 text-soft-muted">{t(`privateAreaPortalRoadmap_${key}`)}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </PrivateAreaShell>
  )
}
