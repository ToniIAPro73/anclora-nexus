'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle2,
  AlertCircle,
  Loader2,
  UserPlus,
  Building2,
  ArrowRight
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import database from '@/lib/neon-data-client'

interface InvitationAcceptProps {
  code: string
}

interface InvitationData {
  valid: boolean
  email: string
  role: string
  org_name: string
  expires_at: string
}

export function InvitationAccept({ code }: InvitationAcceptProps) {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [invitation, setInvitation] = useState<InvitationData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [accepting, setAccepting] = useState(false)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    const validateCode = async () => {
      try {
        const response = await fetch(`/api/invitations/${code}`)
        if (!response.ok) {
          throw new Error('This invitation code is invalid or has expired.')
        }
        const data = await response.json()
        setInvitation(data)
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'An error occurred')
      } finally {
        setLoading(false)
      }
    }

    if (code) {
      validateCode()
    }
  }, [code])

  const handleAccept = async () => {
    setAccepting(true)
    setError(null)
    try {
      const { data: { user } } = await database.auth.getUser()
      if (!user) {
        // Redirect to login if not authenticated, keeping the invite code
        router.push(`/login?invite=${code}`)
        return
      }

      const { data: { session } } = await database.auth.getSession()
      const token = session?.access_token

      const response = await fetch(`/api/invitations/${code}/accept`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token || ''}`
        },
        body: JSON.stringify({ user_id: user.id })
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to accept invitation')
      }

      setSuccess(true)
      setTimeout(() => {
        router.push('/dashboard')
      }, 2000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setAccepting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <Loader2 className="w-10 h-10 text-gold animate-spin mb-4" />
        <p className="text-soft-muted animate-pulse">Validating Invitation...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-md mx-auto p-8 text-center bg-navy-surface border border-danger/20 rounded-3xl backdrop-blur-xl">
        <div className="w-16 h-16 bg-danger/10 rounded-full flex items-center justify-center mx-auto mb-6">
          <AlertCircle className="w-8 h-8 text-danger" />
        </div>
        <h2 className="text-2xl font-bold text-soft-white mb-2">Invitation Error</h2>
        <p className="text-soft-muted mb-8">{error}</p>
        <Button
          onClick={() => router.push('/')}
          className="w-full bg-navy-deep border-soft-subtle text-soft-white hover:bg-navy-surface"
        >
          Return Home
        </Button>
      </div>
    )
  }

  if (success) {
    return (
      <div className="max-w-md mx-auto p-12 text-center bg-navy-surface border border-emerald-500/20 rounded-3xl backdrop-blur-xl shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', damping: 12 }}
          className="w-20 h-20 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-8"
        >
          <CheckCircle2 className="w-10 h-10 text-emerald-400" />
        </motion.div>
        <h2 className="text-2xl font-bold text-soft-white mb-2">Welcome to {invitation?.org_name}!</h2>
        <p className="text-soft-muted mb-8">Your account has been successfully linked to the organization. Redirecting to your dashboard...</p>
        <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: '100%' }}
            transition={{ duration: 2 }}
            className="h-full bg-emerald-500"
          />
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto relative group">
      <div className="absolute -inset-1 bg-gradient-to-r from-gold/20 via-blue-light/20 to-gold/20 rounded-[34px] blur opacity-25 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"></div>
      <div className="relative p-10 bg-navy-deep border border-gold/20 rounded-[32px] backdrop-blur-3xl shadow-2xl">
        <div className="flex justify-between items-start mb-10">
          <div className="w-14 h-14 bg-gold/10 rounded-2xl flex items-center justify-center border border-gold/20">
            <UserPlus className="w-7 h-7 text-gold" />
          </div>
          <div className="text-right">
            <p className="text-[10px] font-bold text-gold uppercase tracking-[0.2em] mb-1">Invitation</p>
            <p className="text-xs text-soft-muted">Expires {invitation && new Date(invitation.expires_at).toLocaleDateString()}</p>
          </div>
        </div>

        <div className="space-y-6 mb-10">
          <div>
            <h2 className="text-3xl font-extrabold text-soft-white leading-tight mb-2">Join the Team</h2>
            <p className="text-soft-muted text-sm leading-relaxed">
              You&apos;ve been invited to join <span className="text-gold font-bold">{invitation?.org_name}</span> as an <span className="text-blue-light font-bold uppercase tracking-wider">{invitation?.role}</span>.
            </p>
          </div>

          <div className="p-5 bg-navy-surface/50 border border-soft-subtle/20 rounded-2xl flex items-center gap-4">
            <div className="w-10 h-10 bg-blue-light/10 rounded-xl flex items-center justify-center">
              <Building2 className="w-5 h-5 text-blue-light" />
            </div>
            <div>
              <p className="text-xs font-bold text-gold/60 uppercase tracking-widest">Target Org</p>
              <p className="text-sm font-medium text-soft-white">{invitation?.org_name}</p>
            </div>
          </div>
        </div>

        <Button
          onClick={handleAccept}
          disabled={accepting}
          className="w-full h-14 bg-gold hover:bg-gold-muted text-[#0F1629] font-black rounded-2xl transition-all shadow-lg shadow-gold/10 flex items-center justify-center gap-3 overflow-hidden relative group"
        >
          <AnimatePresence mode="wait">
            {accepting ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-3"
              >
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Processing...</span>
              </motion.div>
            ) : (
              <motion.div
                key="default"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-3"
              >
                <span>Accept Invitation</span>
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </motion.div>
            )}
          </AnimatePresence>
        </Button>
      </div>
    </div>
  )
}
