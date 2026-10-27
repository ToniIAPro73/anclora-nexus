'use client'
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Eye, EyeOff } from 'lucide-react'
import { useRouter } from 'next/navigation'
import supabase from '@/lib/supabase'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { BrandLogo } from '@/components/brand/BrandLogo'
import { normalizeNextPath } from '@/lib/private-area-access'
import { useI18n } from '@/lib/i18n'

function resolveAppUrl() {
  const configured = (process.env.NEXT_PUBLIC_APP_URL || '').trim().replace(/\/$/, '')
  if (typeof window === 'undefined') return configured

  if (!configured) return window.location.origin

  try {
    const configuredUrl = new URL(configured)
    const currentUrl = new URL(window.location.origin)
    const isConfiguredLocalhost = configuredUrl.hostname === 'localhost' || configuredUrl.hostname === '127.0.0.1'
    const isCurrentLocalhost = currentUrl.hostname === 'localhost' || currentUrl.hostname === '127.0.0.1'

    if (isConfiguredLocalhost && !isCurrentLocalhost) {
      return window.location.origin
    }

    return configuredUrl.toString().replace(/\/$/, '')
  } catch {
    return window.location.origin
  }
}

export default function LoginPage() {
  const router = useRouter()
  const { t } = useI18n()
  type Particle = {
    id: number
    x: number
    y: number
    offsetY: number
    duration: number
  }

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [isError, setIsError] = useState(false)
  const [mode, setMode] = useState<'login' | 'signup' | 'reset'>(() => {
    if (typeof window === 'undefined') return 'login'
    const params = new URLSearchParams(window.location.search)
    return params.get('mode') === 'reset' ? 'reset' : 'login'
  })
  const [confirmPassword, setConfirmPassword] = useState('')
  const identityEnabled = process.env.NEXT_PUBLIC_ANCLORA_IDENTITY_ENABLED === 'true'
  const [nextPath] = useState(() => {
    if (typeof window === 'undefined') return '/dashboard'
    const params = new URLSearchParams(window.location.search)
    return normalizeNextPath(params.get('next'), '/dashboard')
  })
  const particles: Particle[] = [...Array(12)].map((_, i) => ({
    id: i,
    x: (i * 97) % 1000,
    y: (i * 173) % 1000,
    offsetY: -40 - (i % 7) * 10,
    duration: 5 + (i % 5),
  }))

  useEffect(() => {
    if (identityEnabled && typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const inviteCode = params.get('invite')
      const next = params.get('next') || (inviteCode ? `/invite/${encodeURIComponent(inviteCode)}` : '/dashboard')
      window.location.replace(`/api/auth/anclora-identity/login?next=${encodeURIComponent(next)}`)
      return
    }
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const tokenHash = params.get('token_hash')
    const type = params.get('type')

    if (code) {
      const next = encodeURIComponent('/login?mode=reset')
      router.replace(`/auth/callback?code=${encodeURIComponent(code)}&next=${next}`)
      return
    }

    if (tokenHash && type) {
      const next = encodeURIComponent('/login?mode=reset')
      router.replace(`/auth/callback?token_hash=${encodeURIComponent(tokenHash)}&type=${encodeURIComponent(type)}&next=${next}`)
      return
    }

  }, [identityEnabled, router])

  if (identityEnabled) {
    return <main className="flex min-h-screen items-center justify-center bg-navy-deep p-6 text-soft-white"><p>Conectando con Anclora Identity…</p></main>
  }

  useEffect(() => {
    if (identityEnabled) return
    const rawHash = typeof window !== 'undefined' ? window.location.hash.replace(/^#/, '') : ''
    if (!rawHash) return
    const hashParams = new URLSearchParams(rawHash)
    const accessToken = hashParams.get('access_token')
    const refreshToken = hashParams.get('refresh_token')
    const type = hashParams.get('type')

    if (type === 'recovery' && accessToken && refreshToken) {
      void supabase.auth
        .setSession({ access_token: accessToken, refresh_token: refreshToken })
        .finally(() => {
          const base = `${window.location.pathname}?mode=reset`
          window.location.replace(base)
        })
    }
  }, [identityEnabled])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (mode === 'reset') {
      if (!password || !confirmPassword) {
        setMessage('Introduce y confirma la nueva contraseña.')
        setIsError(true)
        return
      }
      if (password.length < 8) {
        setMessage('La contraseña debe tener al menos 8 caracteres.')
        setIsError(true)
        return
      }
      if (password !== confirmPassword) {
        setMessage('Las contraseñas no coinciden.')
        setIsError(true)
        return
      }
      setLoading(true)
      setMessage('')
      setIsError(false)
      const response = await fetch('/auth/callback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        setMessage(payload?.message || 'No se pudo actualizar la contraseña.')
        setIsError(true)
      } else {
        setMessage('Contraseña actualizada correctamente. Ya puedes iniciar sesión.')
        setIsError(false)
        setMode('login')
        setPassword('')
        setConfirmPassword('')
        router.replace('/login')
      }
      setLoading(false)
      return
    }

    setLoading(true)
    setMessage('')
    setIsError(false)

    try {
      if (mode === 'login') {
        const response = await fetch('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })

        if (!response.ok) {
          const payload = await response.json().catch(() => ({}))
          const raw = String(payload?.message || '').toLowerCase()
          if (raw.includes('invalid login credentials')) {
            setMessage('Email o contraseña incorrectos.')
          } else if (raw.includes('email not confirmed')) {
            setMessage('Debes confirmar tu email antes de iniciar sesión.')
          } else if (raw.includes('invitation_required')) {
            setMessage('Solo puedes crear cuenta si has sido invitado por tu organización.')
          } else {
            setMessage(payload?.message || 'No se pudo iniciar sesión.')
          }
          setIsError(true)
          setLoading(false)
          return
        }

        setMessage('Acceso correcto')
        setIsError(false)
        router.replace(nextPath)
        router.refresh()
      } else {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
        })

        if (error) {
          const raw = (error.message || '').toLowerCase()
          if (raw.includes('invitation_required')) {
            setMessage('Solo puedes crear cuenta si has sido invitado por tu organización.')
          } else {
            setMessage(error.message)
          }
          setIsError(true)
          setLoading(false)
          return
        }

        setMessage('Cuenta creada. Si tu invitación era válida, ya puedes iniciar sesión.')
        setIsError(false)
        setMode('login')
      }
    } catch {
      setMessage('No se pudo conectar con el servicio de acceso. Revisa tu conexión o vuelve a intentarlo.')
      setIsError(true)
    }

    setLoading(false)
  }

  const handleForgotPassword = async () => {
    if (!email) {
      setMessage('Introduce primero tu email.')
      setIsError(true)
      return
    }
    setLoading(true)
    setMessage('')
    setIsError(false)
    const appUrl = resolveAppUrl()
    const resetNext = encodeURIComponent('/login?mode=reset')
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${appUrl}/auth/callback?next=${resetNext}`,
    })
    if (error) {
      setMessage(error.message)
      setIsError(true)
    } else {
      setMessage('Te hemos enviado un email para restablecer la contraseña.')
      setIsError(false)
    }
    setLoading(false)
  }

  const handleOAuth = async (provider: 'google' | 'github') => {
    setLoading(true)
    setMessage('')
    setIsError(false)
    const appUrl = resolveAppUrl()
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${appUrl}/auth/callback?next=${encodeURIComponent(nextPath)}`,
      },
    })
    if (error) {
      setMessage(error.message)
      setIsError(true)
      setLoading(false)
    }
  }

  const isGoogleAuthEnabled = process.env.NEXT_PUBLIC_ENABLE_GOOGLE_AUTH === 'true'
  const isGithubAuthEnabled = process.env.NEXT_PUBLIC_ENABLE_GITHUB_AUTH === 'true'
  const showOAuthSection = isGoogleAuthEnabled || isGithubAuthEnabled

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-y-auto bg-[radial-gradient(circle_at_top,_rgba(212,168,67,0.10),_transparent_38%),linear-gradient(135deg,_rgba(8,12,24,1)_0%,_rgba(13,19,35,0.98)_50%,_rgba(10,16,30,0.96)_100%)] p-4">
      {/* Abstract Background Particles */}
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className="absolute w-1 h-1 bg-blue-light/10 rounded-full"
          initial={{
            x: p.x,
            y: p.y,
            opacity: 0.1
          }}
          animate={{
            y: [null, p.y + p.offsetY],
            opacity: [0.1, 0.3, 0.1]
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            ease: "linear"
          }}
        />
      ))}

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="w-full max-w-[460px]"
      >
        <Card className="widget-card w-full border-soft-subtle/20 bg-navy-surface backdrop-blur-xl hover:shadow-[0_48px_100px_-35px_rgba(212,168,67,0.50)] hover:scale-[1.018] transition-[transform,box-shadow] duration-300 ease-out rounded-3xl" style={{minHeight: "560px", boxShadow: "0 32px 80px -40px rgba(212, 168, 67, 0.35)"}}>
          <div className="flex flex-col items-center pt-8 pb-5">
            <div style={{width: "50px", height: "50px"}} className="mb-2 drop-shadow-[0_12px_24px_rgba(0,0,0,0.30)]">
              <BrandLogo size={50} src="/brand/anclora-nexus.png" />
            </div>
            <div className="h-[1px] w-[50px] bg-gradient-to-r from-transparent via-gold/70 to-transparent mb-2" />
            <h1 className="font-display text-sm font-bold text-soft-white">Anclora Nexus</h1>
          </div>

          <div className="px-6 sm:px-8 pb-6 sm:pb-8">
            <form onSubmit={handleLogin} className="space-y-2.5">
              {mode === 'reset' && (
                <p className="text-xs text-soft-muted text-center mb-3">
                  {t('loginResetCopy')}
                </p>
              )}

              <div className="space-y-1">
                <label htmlFor="email" className="text-xs font-semibold text-soft-muted">
                  {t('loginEmail')}
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="correo@ejemplo.es"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="bg-navy-darker/50 border-soft-subtle/20 focus:border-gold focus:ring-1 focus:ring-gold/30 text-soft-white h-10 rounded-2xl"
                />
              </div>

              {mode !== 'reset' && (
                <div className="space-y-1">
                  <label htmlFor="password" className="text-xs font-semibold text-soft-muted">
                    {t('loginPassword')}
                  </label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="bg-navy-darker/50 border-soft-subtle/20 focus:border-gold focus:ring-1 focus:ring-gold/30 text-soft-white h-10 pr-10 rounded-2xl"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-soft-muted hover:text-gold transition-colors"
                      aria-label={showPassword ? t('loginHidePassword') : t('loginShowPassword')}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              )}

              {mode === 'reset' && (
                <div className="space-y-1">
                  <label htmlFor="confirm-password" className="text-xs font-semibold text-soft-muted">
                    {t('loginPassword')}
                  </label>
                  <div className="relative">
                    <Input
                      id="confirm-password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="bg-navy-darker/50 border-soft-subtle/20 focus:border-gold focus:ring-1 focus:ring-gold/30 text-soft-white h-10 rounded-2xl"
                    />
                  </div>
                </div>
              )}

              {message && (
                <div className={`rounded-2xl border p-3 text-xs ${isError ? 'border-danger/30 bg-danger/10 text-danger' : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-400'}`} role="alert">
                  {message}
                </div>
              )}

              <Button
                type="submit"
                disabled={loading}
                className="w-full h-10 bg-gold hover:bg-gold-muted text-[#0F1629] font-bold rounded-2xl transition-all"
              >
                {loading ? '…' : mode === 'reset' ? t('loginPassword') : t('loginSignIn')}
              </Button>
            </form>

            {mode !== 'reset' && (
              <div className="mt-1.5 text-center">
                <Button
                  type="button"
                  variant="ghost"
                  disabled={loading}
                  onClick={handleForgotPassword}
                  className="text-xs text-soft-muted hover:text-gold p-0 h-auto"
                >
                  {t('loginForgot')}
                </Button>
              </div>
            )}

            {mode === 'login' && (
              <div className="mt-1.5 rounded-2xl border border-soft-subtle/20 bg-navy-darker/40 px-4 py-2 text-center">
                <p className="text-xs text-soft-muted">
                  {t('loginNoAccount')}{' '}
                  <button
                    type="button"
                    onClick={() => setMode('signup')}
                    className="font-semibold text-gold hover:text-gold-muted transition"
                  >
                    {t('loginSignUp')}
                  </button>
                </p>
              </div>
            )}

            {mode === 'signup' && (
              <div className="mt-1.5 text-center">
                <button
                  type="button"
                  onClick={() => setMode('login')}
                  className="text-xs text-soft-muted hover:text-gold transition"
                >
                  {t('loginBackToSignIn')}
                </button>
              </div>
            )}

            {showOAuthSection && mode !== 'reset' ? (
              <>
                <div className="my-2.5 flex items-center gap-3">
                  <div className="h-px flex-1 bg-soft-subtle/20" />
                  <span className="text-[10px] uppercase tracking-widest text-soft-muted">{t('loginSocialSeparator')}</span>
                  <div className="h-px flex-1 bg-soft-subtle/20" />
                </div>

                <div className={`grid gap-2 ${isGoogleAuthEnabled && isGithubAuthEnabled ? 'grid-cols-2' : 'grid-cols-1'}`}>
                  {isGoogleAuthEnabled ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={loading}
                      onClick={() => handleOAuth('google')}
                      className="h-9 border-soft-subtle/30 text-soft-white hover:bg-white/5 rounded-2xl text-xs"
                    >
                      {t('loginGoogle')}
                    </Button>
                  ) : null}
                  {isGithubAuthEnabled ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={loading}
                      onClick={() => handleOAuth('github')}
                      className="h-9 border-soft-subtle/30 text-soft-white hover:bg-white/5 rounded-2xl text-xs"
                    >
                      {t('loginGithub')}
                    </Button>
                  ) : null}
                </div>
              </>
            ) : (
              !showOAuthSection && mode !== 'reset' && (
                <div>
                  <div className="my-2.5 flex items-center gap-3">
                    <div className="h-px flex-1 bg-soft-subtle/20" />
                    <span className="text-[10px] uppercase tracking-widest text-soft-muted">{t('loginSocialSeparator')}</span>
                    <div className="h-px flex-1 bg-soft-subtle/20" />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <button disabled className="h-9 rounded-2xl border border-soft-subtle/20 text-xs text-soft-muted opacity-50 cursor-not-allowed">{t('loginGoogle')}</button>
                    <button disabled className="h-9 rounded-2xl border border-soft-subtle/20 text-xs text-soft-muted opacity-50 cursor-not-allowed">{t('loginGithub')}</button>
                  </div>
                </div>
              )
            )}

            <p className="mt-2 text-center text-[10px] leading-relaxed text-soft-muted">
              {t('loginLegalPrefix')}{' '}
              <a href="/terms" className="underline underline-offset-2 hover:text-gold">{t('loginTerms')}</a>
              {' '}{t('loginLegalMiddle')}{' '}
              <a href="/privacy" className="underline underline-offset-2 hover:text-gold">{t('loginPrivacy')}</a>.
            </p>
          </div>
        </Card>
      </motion.div>
    </div>
  )
}
