'use client'
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { LogOut, Settings, UserCircle, ChevronDown } from 'lucide-react'
import database from '@/lib/neon-data-client'
import type { IdentityUser } from '@/lib/neon-data-client'
import { useI18n } from '@/lib/i18n'
import { useRouter } from 'next/navigation'

export function UserMenu() {
  const [isOpen, setIsOpen] = useState(false)
  const [user, setUser] = useState<IdentityUser | null>(null)
  const [avatarUrl, setAvatarUrl] = useState<string>('/brand/anclora-nexus.png')
  const { t } = useI18n()
  const router = useRouter()
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const getUser = async () => {
      const { data: { user } } = await database.auth.getUser()
      setUser(user)
      if (!user) return

      const { data: profile } = await database
        .from('user_profiles')
        .select('avatar_url')
        .eq('id', user.id)
        .maybeSingle()

      setAvatarUrl(profile?.avatar_url || user.user_metadata?.avatar_url || '/brand/anclora-nexus.png')
    }
    getUser()

    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLogout = async () => {
    await database.auth.signOut()
    router.push('/login')
  }

  const userName = String(user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'Toni')

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-full border border-gold/30 bg-navy-surface hover:bg-gold/10 transition-all group"
      >
        <div className="w-8 h-8 rounded-full bg-gold/20 flex items-center justify-center text-gold border border-gold/20">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={avatarUrl}
            alt="User avatar"
            className="w-full h-full rounded-full object-cover"
            onError={(e) => {
              const target = e.currentTarget
              if (target.src !== `${window.location.origin}/brand/anclora-nexus.png`) {
                target.src = '/brand/anclora-nexus.png'
              }
            }}
          />
        </div>
        <ChevronDown className={`w-3.5 h-3.5 text-soft-muted transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="absolute right-0 mt-3 w-56 rounded-2xl border border-soft-subtle/30 bg-navy-deep shadow-[0_20px_50px_rgba(0,0,0,0.5)] z-50 overflow-hidden"
          >
            <div className="p-4 border-b border-soft-subtle/50 bg-gold/5">
              <p className="text-xs font-bold text-gold uppercase tracking-widest mb-0.5">Nexus User</p>
              <p className="text-sm font-medium text-soft-white truncate">{userName}</p>
              <p className="text-[10px] text-soft-muted truncate opacity-80">{user?.email || 'toni@anclora.es'}</p>
            </div>

            <div className="p-2">
              <button 
                onClick={() => {
                  router.push('/profile')
                  setIsOpen(false)
                }}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-soft-muted hover:text-soft-white hover:bg-white/5 transition-colors group text-left"
              >
                <UserCircle className="w-4 h-4 text-gold/60 group-hover:text-gold transition-colors" />
                <span>{t('profile')}</span>
              </button>
              <button 
                onClick={() => {
                  router.push('/settings')
                  setIsOpen(false)
                }}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-soft-muted hover:text-soft-white hover:bg-white/5 transition-colors group text-left"
              >
                <Settings className="w-4 h-4 text-gold/60 group-hover:text-gold transition-colors" />
                <span>{t('settings')}</span>
              </button>
            </div>

            <div className="p-2 border-t border-soft-subtle/50">
              <button
                onClick={() => {
                  handleLogout()
                  setIsOpen(false)
                }}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-danger hover:bg-danger/10 transition-colors group text-left"
              >
                <LogOut className="w-4 h-4 opacity-70 group-hover:opacity-100 transition-opacity" />
                <span>{t('logout')}</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
