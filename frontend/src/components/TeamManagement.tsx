'use client'

import React, { useState, useEffect } from 'react'
import { useOrgMembership } from '@/lib/hooks/useOrgMembership'
import { useTeamManagement } from '@/lib/hooks/useTeamManagement'
import { useI18n } from '@/lib/i18n'
import database from '@/lib/neon-data-client'
import { motion, AnimatePresence } from 'framer-motion'
import {
  UserPlus,
  Trash2,
  UserCog,
  Mail,
  CheckCircle2,
  AlertCircle,
  ChevronRight
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { OrgRole, OrgMembership } from '@/lib/contexts/OrgContext'

type TeamMember = OrgMembership & {
  email?: string
  full_name?: string
  avatar_url?: string
}

export default function TeamManagement() {
  const { t } = useI18n()
  const { canManageTeam, org_id, user_id: currentUserId } = useOrgMembership()
  const {
    inviteMember,
    changeMemberRole,
    removeMember,
    fetchMembers,
    loading: actionLoading,
    error: teamApiError
  } = useTeamManagement()

  const [members, setMembers] = useState<TeamMember[]>([])
  const [loading, setLoading] = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<OrgRole>('manager')
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [selfProfile, setSelfProfile] = useState<{ full_name?: string; email?: string; avatar_url?: string } | null>(null)

  const mapTeamError = (rawMessage?: string) => {
    const msg = (rawMessage || '').trim()
    if (!msg) return t('teamErrGeneric')

    if (msg.includes('No active session')) return t('teamErrNoSession')
    if (msg.includes('No user found with this email')) return t('teamErrUserNotFound')
    if (msg.includes('already an active member')) return t('teamErrAlreadyActive')
    if (msg.includes('already has a pending invitation')) return t('teamErrAlreadyPending')
    if (msg.includes("Invitations for role 'owner' are not allowed")) return t('teamErrInviteOwnerNotAllowed')
    if (msg.includes("Invitations for role 'agent' are disabled")) return t('teamErrInviteAgentDisabled')
    if (msg.includes('Organization already has an owner')) return t('teamErrOwnerExists')
    if (msg.includes('Insufficient permissions')) return t('teamErrForbidden')
    if (msg.includes('Member not found')) return t('teamErrMemberNotFound')
    if (msg.includes('Cannot change role of the last owner')) return t('teamErrLastOwnerLocked')
    if (msg.includes('Cannot remove the last owner')) return t('teamErrLastOwnerLocked')
    if (msg.includes('Cannot remove owner member')) return t('teamErrLastOwnerLocked')
    if (msg.includes('Failed to invite member')) return t('teamErrGeneric')
    if (msg.includes('Failed to update role')) return t('teamErrGeneric')
    if (msg.includes('Failed to remove member')) return t('teamErrGeneric')
    if (msg.includes('Failed to fetch members')) return t('teamErrGeneric')

    return msg
  }

  const getMembershipStatusLabel = (status: string) => {
    const normalized = String(status || '').toLowerCase()
    if (normalized === 'active') return t('membershipStatusActive')
    if (normalized === 'pending') return t('membershipStatusPending')
    if (normalized === 'suspended') return t('membershipStatusSuspended')
    if (normalized === 'removed') return t('membershipStatusRemoved')
    return status
  }

  const loadMembers = React.useCallback(async () => {
    setLoading(true)
    const data = await fetchMembers()
    setMembers(data)
    setLoading(false)
  }, [fetchMembers])

  useEffect(() => {
    if (org_id) {
      const timer = setTimeout(() => { loadMembers() }, 0)
      return () => clearTimeout(timer)
    }
  }, [org_id, loadMembers])

  useEffect(() => {
    const loadSelfProfile = async () => {
      if (!currentUserId) return

      const { data: { user } } = await database.auth.getUser()
      const { data: profile } = await database
        .from('user_profiles')
        .select('full_name,email,avatar_url')
        .eq('id', currentUserId)
        .maybeSingle()

      setSelfProfile({
        full_name: profile?.full_name || user?.user_metadata?.full_name,
        email: profile?.email || user?.email || undefined,
        avatar_url: profile?.avatar_url || user?.user_metadata?.avatar_url
      })
    }

    loadSelfProfile()
  }, [currentUserId])

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)
    setSuccessMessage(null)
    try {
      await inviteMember(inviteEmail, inviteRole)
      setSuccessMessage(`${t('invitationSent')} ${inviteEmail}`)
      setInviteEmail('')
      loadMembers()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setErrorMessage(mapTeamError(message))
    }
  }

  const activeOwnersCount = members.filter((m) => m.role === 'owner' && m.status === 'active').length

  const handleRoleChange = async (memberId: string, newRole: OrgRole) => {
    try {
      await changeMemberRole(memberId, newRole)
      setSuccessMessage(t('roleUpdated'))
      loadMembers()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setErrorMessage(mapTeamError(message))
    }
  }

  const handleRemove = async (memberId: string) => {
    if (!confirm(t('confirmRemoveMember'))) return
    try {
      await removeMember(memberId)
      setSuccessMessage(t('memberRemoved'))
      loadMembers()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setErrorMessage(mapTeamError(message))
    }
  }

  if (!canManageTeam) {
    return (
      <div className="p-8 text-center text-soft-muted">
        {t('accessRestricted')}. {t('onlyOwner')}
      </div>
    )
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto p-6">
      {/* Header section with Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-navy-surface/30 border border-soft-subtle/20 rounded-3xl p-6 backdrop-blur-xl">
          <p className="text-xs font-bold text-gold uppercase tracking-widest mb-1">{t('totalTeam')}</p>
          <h3 className="text-3xl font-bold text-soft-white">{members.length} {t('members')}</h3>
        </div>
        <div className="bg-navy-surface/30 border border-soft-subtle/20 rounded-3xl p-6 backdrop-blur-xl col-span-2">
           <form onSubmit={handleInvite} className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1 relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gold/50" />
                <Input
                  type="email"
                  placeholder={t('emailPlaceholder')}
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="pl-10"
                  required
                />
              </div>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as OrgRole)}
                className="ui-select min-w-[220px]"
              >
                <option value="manager">{t('teamRoleManager')}</option>
              </select>
              <Button
                type="submit"
                disabled={actionLoading}
                className="bg-gold hover:bg-gold-muted text-[#0F1629] font-bold px-6 h-12 rounded-xl transition-all flex items-center gap-2"
              >
                <UserPlus className="w-4 h-4" />
                {t('invite')}
              </Button>
           </form>
        </div>
      </div>

      <AnimatePresence>
        {successMessage && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl text-emerald-400 text-sm"
          >
            <CheckCircle2 className="w-5 h-5" />
            {successMessage}
            <button onClick={() => setSuccessMessage(null)} className="ml-auto opacity-50 hover:opacity-100">✕</button>
          </motion.div>
        )}
        {errorMessage && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-400 text-sm"
          >
            <AlertCircle className="w-5 h-5" />
            {errorMessage}
            <button onClick={() => setErrorMessage(null)} className="ml-auto opacity-50 hover:opacity-100">✕</button>
          </motion.div>
        )}
        {!errorMessage && teamApiError && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-400 text-sm"
          >
            <AlertCircle className="w-5 h-5" />
            {mapTeamError(teamApiError)}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="bg-navy-surface/30 border border-soft-subtle/20 rounded-3xl overflow-hidden backdrop-blur-xl">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-soft-subtle/10 bg-navy-deep/40">
              <th className="px-6 py-4 text-xs font-bold text-gold uppercase tracking-widest">{t('member')}</th>
              <th className="px-6 py-4 text-xs font-bold text-gold uppercase tracking-widest whitespace-nowrap">{t('role')}</th>
              <th className="px-6 py-4 text-xs font-bold text-gold uppercase tracking-widest">{t('status')}</th>
              <th className="px-6 py-4 text-xs font-bold text-gold uppercase tracking-widest text-right">{t('actions')}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              [...Array(3)].map((_, i) => (
                <tr key={i} className="animate-pulse border-b border-soft-subtle/5">
                  <td className="px-6 py-8"><div className="h-4 bg-white/5 rounded w-32" /></td>
                  <td className="px-6 py-8"><div className="h-4 bg-white/5 rounded w-20" /></td>
                  <td className="px-6 py-8"><div className="h-4 bg-white/5 rounded w-16" /></td>
                  <td className="px-6 py-8"><div className="h-4 bg-white/5 rounded w-10 ml-auto" /></td>
                </tr>
              ))
            ) : members.map((member) => {
              const isOwnerMember = member.role === 'owner'
              const isLastOwner =
                member.role === 'owner' &&
                member.status === 'active' &&
                activeOwnersCount <= 1
              const canPromoteToOwner = member.role === 'owner'
              const isCurrentUser = Boolean(currentUserId && member.user_id === currentUserId)
              const displayName = isCurrentUser
                ? (member.full_name || selfProfile?.full_name || member.email || selfProfile?.email || t('teamMemberNameFallback'))
                : (member.full_name || member.email || t('teamMemberNameFallback'))
              const displayEmail = isCurrentUser
                ? (member.email || selfProfile?.email)
                : member.email
              const displayAvatar = isCurrentUser
                ? (member.avatar_url || selfProfile?.avatar_url)
                : member.avatar_url
              const subline = displayEmail || `${t('teamMemberIdLabel')}: ${member.id.substring(0,8)}`
              const avatarInitial = (displayName || 'U').charAt(0).toUpperCase()
              return (
              <motion.tr
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                key={member.id}
                className="group border-b border-soft-subtle/5 hover:bg-white/[0.02] transition-colors"
              >
                <td className="px-6 py-5">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gold/10 border border-gold/20 flex items-center justify-center text-gold font-bold overflow-hidden">
                      {displayAvatar ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={displayAvatar} alt={displayName} className="w-full h-full object-cover" />
                      ) : (
                        avatarInitial
                      )}
                    </div>
                    <div>
                      <p className="text-soft-white font-medium text-sm flex items-center gap-2">
                        {displayName}
                        {isCurrentUser && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-gold/15 border border-gold/30 text-gold">
                            {t('teamCurrentUserBadge')}
                          </span>
                        )}
                      </p>
                      <p className="text-soft-muted text-xs opacity-60">{subline}</p>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-5">
                  <select
                    value={member.role}
                    onChange={(e) => handleRoleChange(member.id, e.target.value as OrgRole)}
                    disabled={isLastOwner}
                    title={isLastOwner ? t('teamLastOwnerLockedHint') : ''}
                    className={`ui-select min-h-[2.25rem] px-3 py-1.5 text-xs hover:bg-navy-surface ${
                      isLastOwner ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'
                    }`}
                  >
                    <option value="agent">{t('teamRoleAgent')}</option>
                    <option value="manager">{t('teamRoleManager')}</option>
                    {canPromoteToOwner && <option value="owner">{t('teamRoleOwner')}</option>}
                  </select>
                </td>
                <td className="px-6 py-5">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                    member.status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                    member.status === 'pending' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                    'bg-red-500/10 text-red-400 border-red-500/20'
                  }`}>
                    {getMembershipStatusLabel(member.status)}
                  </span>
                </td>
                <td className="px-6 py-5 text-right">
                  <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled={isOwnerMember}
                      title={isOwnerMember ? t('teamLastOwnerLockedHint') : ''}
                      className="h-8 w-8 text-soft-muted hover:text-red-400 hover:bg-red-500/10"
                      onClick={() => handleRemove(member.id)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-soft-muted hover:text-gold hover:bg-gold/10">
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </td>
              </motion.tr>
            )})}
          </tbody>
        </table>
        {!loading && members.length === 0 && (
          <div className="p-12 text-center text-soft-muted">
            <UserCog className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p className="text-sm">{t('noMembersFound')}</p>
          </div>
        )}
      </div>
    </div>
  )
}
