'use client'
import { useState, useRef, useEffect } from 'react'
import { Bell, Check, Info, AlertTriangle, XCircle, CheckCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Notification } from '@/lib/notifications'
import { useI18n } from '@/lib/i18n'
import database from '@/lib/neon-data-client'

const ITEMS_PER_PAGE = 3
type NotificationWithCreatedAt = Notification & { createdAt: number }

export function NotificationPanel() {
  const [isOpen, setIsOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [currentPage, setCurrentPage] = useState(1)
  const panelRef = useRef<HTMLDivElement>(null)
  const { t } = useI18n()

  const unreadCount = notifications.filter(n => !n.read).length
  const totalPages = Math.ceil(notifications.length / ITEMS_PER_PAGE)
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
  const endIndex = startIndex + ITEMS_PER_PAGE
  const currentNotifications = notifications.slice(startIndex, endIndex)

  // Close panel when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    const formatRelative = (isoDate?: string): string => {
      if (!isoDate) return 'ahora'
      const date = new Date(isoDate)
      if (Number.isNaN(date.getTime())) return 'ahora'

      const diffMs = date.getTime() - Date.now()
      const diffMin = Math.round(diffMs / 60000)
      const absMin = Math.abs(diffMin)
      const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

      if (absMin < 60) return rtf.format(diffMin, 'minute')
      const diffHours = Math.round(diffMin / 60)
      const absHours = Math.abs(diffHours)
      if (absHours < 24) return rtf.format(diffHours, 'hour')
      const diffDays = Math.round(diffHours / 24)
      return rtf.format(diffDays, 'day')
    }

    const toLeadNotification = (lead: Record<string, unknown>): NotificationWithCreatedAt => {
      const priority = Number(lead.ai_priority || 3)
      const leadId = String(lead.id || '')
      const createdAtIso = String(lead.created_at || '')
      const createdAt = Date.parse(createdAtIso)
      return {
        id: `lead-${leadId}`,
        type: priority >= 4 ? 'success' : 'info',
        title: t('newLead'),
        message: `${String(lead.name || t('noName'))} · P${priority}`,
        timestamp: formatRelative(createdAtIso),
        read: false,
        actionUrl: leadId ? `/leads?highlight=${leadId}` : '/leads',
        createdAt: Number.isNaN(createdAt) ? Date.now() : createdAt,
      }
    }

    const toTaskNotification = (task: Record<string, unknown>): NotificationWithCreatedAt => {
      const taskId = String(task.id || '')
      const createdAtIso = String(task.created_at || task.due_date || '')
      const createdAt = Date.parse(createdAtIso)
      return {
        id: `task-${taskId}`,
        type: 'warning',
        title: t('tasks'),
        message: String(task.title || t('noTitle')),
        timestamp: formatRelative(createdAtIso),
        read: false,
        actionUrl: '/tasks',
        createdAt: Number.isNaN(createdAt) ? Date.now() : createdAt,
      }
    }

    const resolveScope = async (): Promise<{ orgId?: string; role?: string; userId?: string }> => {
      const { data: { user } } = await database.auth.getUser()
      const userId = user?.id
      if (!userId) return {}

      const { data: profile } = await database
        .from('user_profiles')
        .select('org_id')
        .eq('id', userId)
        .maybeSingle()

      const preferredOrgId = profile?.org_id || null
      const { data: memberships } = await database
        .from('organization_members')
        .select('org_id,role')
        .eq('user_id', userId)
        .eq('status', 'active')
        .order('updated_at', { ascending: false })

      const rows = (memberships || []) as Array<{ org_id: string; role: string }>
      const selected = preferredOrgId
        ? (rows.find((row) => row.org_id === preferredOrgId) || rows[0])
        : rows[0]

      return {
        orgId: selected?.org_id || preferredOrgId || undefined,
        role: selected?.role || undefined,
        userId,
      }
    }

    const loadInitialNotifications = async () => {
      const scope = await resolveScope()

      let leadsQuery = database
        .from('leads')
        .select('id,name,ai_priority,created_at,assigned_user_id,org_id')
        .order('created_at', { ascending: false })
        .limit(10)

      let tasksQuery = database
        .from('tasks')
        .select('id,title,created_at,due_date,status,assigned_user_id,org_id')
        .order('created_at', { ascending: false })
        .limit(10)

      if (scope.orgId) {
        leadsQuery = leadsQuery.eq('org_id', scope.orgId)
        tasksQuery = tasksQuery.eq('org_id', scope.orgId)
      }
      if (scope.role === 'agent' && scope.userId) {
        leadsQuery = leadsQuery.eq('assigned_user_id', scope.userId)
        tasksQuery = tasksQuery.eq('assigned_user_id', scope.userId)
      }

      const [{ data: leads }, { data: tasks }] = await Promise.all([leadsQuery, tasksQuery])

      const leadNotifications = ((leads || []) as Array<Record<string, unknown>>)
        .map((lead) => toLeadNotification(lead))
      const taskNotifications = ((tasks || []) as Array<Record<string, unknown>>)
        .map((task) => toTaskNotification(task))

      const combined = [...leadNotifications, ...taskNotifications]
        .sort((a, b) => b.createdAt - a.createdAt)
        .map(({ createdAt, ...notification }) => {
          void createdAt
          return notification
        })
        .slice(0, 30)

      setNotifications(combined)
    }

    void loadInitialNotifications()
    const refreshTimer = window.setInterval(() => { void loadInitialNotifications() }, 30_000)
    return () => window.clearInterval(refreshTimer)
  }, [t])

  const handleToggle = () => {
    const newState = !isOpen
    setIsOpen(newState)
    if (newState) {
      setCurrentPage(1)
    }
  }

  const markAsRead = (id: string) => {
    setNotifications(prev =>
      prev.map(n => (n.id === id ? { ...n, read: true } : n))
    )
  }

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
  }

  const nextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(prev => prev + 1)
    }
  }

  const prevPage = () => {
    if (currentPage > 1) {
      setCurrentPage(prev => prev - 1)
    }
  }

  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-emerald-400" />
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-amber-400" />
      case 'error':
        return <XCircle className="w-5 h-5 text-red-400" />
      default:
        return <Info className="w-5 h-5 text-blue-light" />
    }
  }

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell Button */}
      <button
        onClick={handleToggle}
        className="relative p-2.5 rounded-full bg-white/[0.03] border border-soft-subtle text-soft-muted hover:text-soft-white hover:border-soft-muted transition-all"
        aria-label="Notifications"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute top-2 right-2 w-2 h-2 bg-gold rounded-full border-2 border-navy-deep"
          />
        )}
      </button>

      {/* Notification Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="absolute right-0 mt-2 w-96 bg-navy-deep backdrop-blur-xl border-2 border-soft-muted/30 rounded-2xl shadow-2xl overflow-hidden z-50"
          >
            {/* Header */}
            <div className="p-4 border-b border-soft-subtle flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-soft-white">{t('notifications')}</h3>
                {unreadCount > 0 && (
                  <p className="text-xs text-soft-muted mt-0.5">
                    {unreadCount} {t('unread')}
                  </p>
                )}
              </div>
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs text-gold hover:text-gold/80 transition-colors flex items-center gap-1"
                >
                  <Check className="w-3 h-3" />
                  {t('markAllAsRead')}
                </button>
              )}
            </div>

            {/* Notifications List */}
            <div className="min-h-[300px] max-h-[400px]">
              {notifications.length === 0 ? (
                <div className="p-8 text-center">
                  <Bell className="w-12 h-12 text-soft-muted mx-auto mb-3 opacity-30" />
                  <p className="text-sm text-soft-muted">{t('noNotifications')}</p>
                </div>
              ) : (
                <>
                  <div className="divide-y divide-soft-subtle">
                    {currentNotifications.map((notification, index) => (
                      <motion.div
                        key={notification.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className={`p-4 hover:bg-white/[0.02] transition-colors cursor-pointer ${
                          !notification.read ? 'bg-white/[0.05]' : ''
                        }`}
                        onClick={() => markAsRead(notification.id)}
                      >
                        <div className="flex gap-3">
                          <div className="flex-shrink-0 mt-0.5">
                            {getIcon(notification.type)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-2 mb-1">
                              <h4 className={`text-sm font-semibold ${
                                !notification.read ? 'text-soft-white' : 'text-soft-muted'
                              }`}>
                                {notification.title}
                              </h4>
                              {!notification.read && (
                                <div className="w-2 h-2 rounded-full bg-gold flex-shrink-0 mt-1.5" />
                              )}
                            </div>
                            <p className="text-xs text-soft-muted leading-relaxed mb-2">
                              {notification.message}
                            </p>
                            <span className="text-[10px] text-soft-muted uppercase tracking-wider">
                              {notification.timestamp}
                            </span>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>

                  {/* Pagination Controls */}
                  {totalPages > 1 && (
                    <div className="p-3 border-t border-soft-subtle bg-navy-deep/50 flex items-center justify-between">
                      <button
                        onClick={prevPage}
                        disabled={currentPage === 1}
                        className="p-1.5 rounded-lg hover:bg-white/[0.05] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        <ChevronLeft className="w-4 h-4 text-soft-white" />
                      </button>

                      <div className="flex items-center gap-2">
                        {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                          <button
                            key={page}
                            onClick={() => setCurrentPage(page)}
                            className={`w-6 h-6 rounded-full text-xs font-medium transition-all ${
                              currentPage === page
                                ? 'bg-gold text-[#0F1629]'
                                : 'text-soft-muted hover:bg-white/[0.05] hover:text-soft-white'
                            }`}
                          >
                            {page}
                          </button>
                        ))}
                      </div>

                      <button
                        onClick={nextPage}
                        disabled={currentPage === totalPages}
                        className="p-1.5 rounded-lg hover:bg-white/[0.05] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        <ChevronRight className="w-4 h-4 text-soft-white" />
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
