'use client'
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Mail, Shield, Calendar, MapPin,
  Briefcase, Trophy, Edit2, Camera, X, Check, Loader2,
  UserCircle, ExternalLink, AlertCircle, ChevronLeft, Save
} from 'lucide-react'
import { useRouter } from 'next/navigation'
import database from '@/lib/neon-data-client'
import { buildBackendUrl } from '@/lib/backend-url'
import { useI18n } from '@/lib/i18n'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'


export default function ProfilePage() {
  const { t } = useI18n()
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const [user, setUser] = useState<any>(null)
  const [profile, setProfile] = useState<any>(null)
  const [org, setOrg] = useState<any>(null)
  /* eslint-enable @typescript-eslint/no-explicit-any */
  const [loading, setLoading] = useState(true)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [errorStatus, setErrorStatus] = useState<string | null>(null)

  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [formData, setFormData] = useState({
    full_name: '',
    job_title: '',
    location: '',
    bio: '',
    specialization: [] as string[],
    achievements: [] as string[]
  })

  useEffect(() => {
    fetchProfile()
  }, [])

  const fetchProfile = async () => {
    try {
      setLoading(true)
      const { data: { user: authUser } } = await database.auth.getUser()

      if (authUser) {
        setUser(authUser)

        // 1. Fetch User Profile
        let { data: profileData } = await database
          .from('user_profiles')
          .select('*')
          .eq('id', authUser.id)
          .maybeSingle()

        // 2. If no profile, create it using any available organization
        if (!profileData) {
          const { data: orgs } = await database.from('organizations').select('id').limit(1)
          const orgId = orgs?.[0]?.id || '00000000-0000-0000-0000-000000000000'

          const { data: newProfile } = await database
            .from('user_profiles')
            .upsert({
              id: authUser.id,
              org_id: orgId,
              email: authUser.email,
              full_name: authUser.user_metadata?.full_name || authUser.email?.split('@')[0],
              job_title: 'Luxury Estate Consultant',
              location: 'Mallorca, ES'
            })
            .select('*')
            .single()

          if (newProfile) profileData = newProfile
        }

        if (profileData) {
          // 3. Fetch Organization
          const { data: orgData } = await database
            .from('organizations')
            .select('*')
            .eq('id', profileData.org_id)
            .maybeSingle()

          setProfile(profileData)
          setOrg(orgData)
          setFormData({
            full_name: profileData.full_name || '',
            job_title: profileData.job_title || 'Luxury Estate Consultant',
            location: profileData.location || 'Mallorca, ES',
            bio: profileData.bio || '',
            specialization: profileData.specialization || [],
            achievements: profileData.achievements || []
          })
        }
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (error: any) {
      console.error('Fetch error:', error)
      setErrorStatus(`Error loading profile: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user?.id) return

    setIsSaving(true)
    try {
      const { error } = await database
        .from('user_profiles')
        .update({
          full_name: formData.full_name,
          job_title: formData.job_title,
          location: formData.location,
          bio: formData.bio,
          specialization: formData.specialization,
          achievements: formData.achievements
        })
        .eq('id', user.id)

      if (error) throw error
      await fetchProfile()
      setIsEditModalOpen(false)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (error: any) {
      alert(`Update failed: ${error.message}`)
    } finally {
      setIsSaving(false)
    }
  }

  const handleUpload = async (file: File) => {
    if (!user || !file) return
    setIsUploading(true)
    setErrorStatus(null)

    try {
      const { data: { session } } = await database.auth.getSession()
      if (!session?.access_token) throw new Error('No authenticated session')
      const body = new FormData()
      body.set('file', file)
      const uploadResponse = await fetch(buildBackendUrl('/api/profile/avatar'), {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
        body,
      })
      const uploadResult = await uploadResponse.json()
      if (!uploadResponse.ok || typeof uploadResult.avatar_url !== 'string') {
        throw new Error(uploadResult.detail || 'Avatar upload failed')
      }
      const publicUrl = uploadResult.avatar_url

      const { error: profileError } = await database.from('user_profiles').update({ avatar_url: publicUrl }).eq('id', user.id)
      if (profileError) throw profileError
      await fetchProfile()
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (error: any) {
      console.error('Upload process error:', error)
      setErrorStatus(`Upload failed: ${error.message}`)
    } finally {
      setIsUploading(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-12 h-12 border-4 border-gold/20 border-t-gold rounded-full animate-spin" />
    </div>
  )

  const avatarUrl = profile?.avatar_url || user?.user_metadata?.avatar_url
  const userNameString = formData.full_name || user?.email?.split('@')[0] || 'Toni'

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-12">
      {errorStatus && (
        <div className="bg-red-500/10 border border-red-500/20 p-4 rounded-2xl flex items-center gap-3 text-red-400 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p>{errorStatus}</p>
          <button onClick={() => setErrorStatus(null)} className="ml-auto text-red-400/50 hover:text-red-400"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Header Profile Section */}
      <div className="flex items-center gap-4 mb-2">
        <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full hover:bg-navy-surface text-soft-muted">
            <ChevronLeft className="w-6 h-6" />
        </Button>
        <span className="text-soft-muted text-sm uppercase tracking-widest font-bold">Volver</span>
      </div>

      <div className="relative group">
        <div className="absolute -inset-0.5 bg-gradient-to-r from-gold/50 via-blue-light/50 to-gold/50 rounded-[2rem] blur opacity-20 transition duration-1000 group-hover:opacity-40"></div>
        <div className="relative bg-navy-surface border border-soft-subtle/30 rounded-[2rem] p-8 md:p-12 overflow-hidden">
          <div className="flex flex-col md:flex-row items-center gap-10">
            {/* Avatar Section */}
            <div className="relative">
              <div className="w-32 h-32 md:w-40 md:h-40 rounded-full border-2 border-gold/30 p-1 bg-navy-deep/50 shadow-2xl overflow-hidden">
                <div className="w-full h-full rounded-full bg-gold/10 flex items-center justify-center">
                  {isUploading ? (
                    <Loader2 className="w-8 h-8 text-gold animate-spin" />
                  ) : avatarUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={avatarUrl} alt="Profile" className="w-full h-full object-cover" />
                  ) : (
                    <span className="text-5xl md:text-6xl font-black text-gold opacity-80">{userNameString.charAt(0).toUpperCase()}</span>
                  )}
                </div>
              </div>
              <button onClick={() => fileInputRef.current?.click()} className="absolute bottom-1 right-1 p-2.5 bg-gold rounded-full text-[#0F1629] hover:scale-110 shadow-lg z-10">
                <Camera className="w-4 h-4" />
              </button>
              <input type="file" ref={fileInputRef} onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} className="hidden" accept="image/*" />
            </div>



            <div className="flex-1 text-center md:text-left space-y-4">
              <div className="space-y-1">
                <h1 className="page-title">{userNameString}</h1>
                <p className="text-lg text-soft-muted font-medium flex items-center justify-center md:justify-start gap-2">
                  <Briefcase className="w-4 h-4 text-blue-light/60" />
                  {profile?.job_title || t('luxuryEstateConsultant')} @ {org?.name || 'Anclora Private Estates'}
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-center md:justify-start gap-6 text-sm text-soft-muted">
                <div className="flex items-center gap-2"><Mail className="w-4 h-4 text-gold/60" /> {user?.email}</div>
                <div className="flex items-center gap-2"><MapPin className="w-4 h-4 text-gold/60" /> {profile?.location}</div>
                <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-gold/60" /> {t('memberSince')} {new Date(user?.created_at).toLocaleDateString()}</div>
              </div>

              <div className="pt-4 flex flex-wrap justify-center md:justify-start gap-4">
                <Button onClick={() => setIsEditModalOpen(true)} className="bg-gold hover:bg-gold-muted text-[#0F1629] font-bold px-8 rounded-xl shadow-lg">
                  <Edit2 className="w-4 h-4 mr-2" />{t('editProfile')}
                </Button>
                <Button variant="outline" onClick={() => window.open(`/public/${user?.id}`, '_blank')} className="border-soft-subtle/50 text-soft-white px-8 rounded-xl">
                  <ExternalLink className="w-4 h-4 mr-2" />{t('viewPublicProfile')}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-8">
          <Card className="bg-navy-surface border-soft-subtle/30 p-8 space-y-6">
            <h3 className="text-xl font-bold text-soft-white flex items-center gap-3">
              <Shield className="w-5 h-5 text-gold" /> {t('professionalSummary')}
            </h3>
            <p className="text-soft-muted leading-relaxed">
              {profile?.bio || t('professionalBio')}
            </p>
          </Card>

          {/* Specializations & Achievements */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <Card className="bg-navy-surface border-soft-subtle/30 p-8 space-y-6">
              <h3 className="text-xl font-bold text-soft-white flex items-center gap-3">
                <Trophy className="w-5 h-5 text-gold" /> {t('specializationsLabel')}
              </h3>
              <div className="flex flex-wrap gap-2">
                {profile?.specialization && profile.specialization.length > 0 ? (
                  profile.specialization.map((spec: string, index: number) => (
                    <span key={index} className="px-3 py-1 bg-navy-deep/50 border border-gold/20 rounded-full text-sm text-gold/80">
                      {spec}
                    </span>
                  ))
                ) : (
                  <p className="text-soft-muted italic text-sm">No specializations added.</p>
                )}
              </div>
            </Card>

            <Card className="bg-navy-surface border-soft-subtle/30 p-8 space-y-6">
              <h3 className="text-xl font-bold text-soft-white flex items-center gap-3">
                <Shield className="w-5 h-5 text-gold" /> {t('achievementsLabel')}
              </h3>
              <ul className="space-y-3">
                {profile?.achievements && profile.achievements.length > 0 ? (
                  profile.achievements.map((achievement: string, index: number) => (
                    <li key={index} className="flex items-center gap-3 text-soft-muted">
                      <Check className="w-4 h-4 text-gold" />
                      <span>{achievement}</span>
                    </li>
                  ))
                ) : (
                  <p className="text-soft-muted italic text-sm">No achievements added.</p>
                )}
              </ul>
            </Card>
          </div>
        </div>
        <div className="space-y-8">
          <Card className="bg-navy-surface border-soft-subtle/30 p-8 space-y-8 relative overflow-hidden">
            <h3 className="text-xl font-bold text-soft-white">{t('accountInfo')}</h3>
            <div className="space-y-6">
              <div><p className="text-xs font-bold text-gold uppercase tracking-widest mb-1">{t('organization')}</p><p className="text-soft-white font-medium">{org?.name}</p></div>
              <div><p className="text-xs font-bold text-gold uppercase tracking-widest mb-1">{t('role')}</p><p className="text-soft-white font-medium">{profile?.role}</p></div>
              <div><p className="text-xs font-bold text-gold uppercase tracking-widest mb-1">Nexus ID</p><p className="text-[10px] font-mono text-blue-light">{user?.id}</p></div>
            </div>
          </Card>
        </div>
      </div>

      {/* Edit Profile Modal (simplified for fix) */}
      <AnimatePresence>
        {isEditModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setIsEditModalOpen(false)} className="absolute inset-0 bg-navy-deep/80 backdrop-blur-md" />
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="relative w-full max-w-7xl bg-navy-surface border border-soft-subtle/30 rounded-[1.5rem] p-8 shadow-2xl overflow-hidden">
              <div className="flex justify-between items-center mb-6 border-b border-soft-subtle/10 pb-4">
                <h2 className="text-2xl font-bold text-soft-white flex items-center gap-3"><Edit2 className="w-6 h-6 text-gold" /> {t('editProfile')}</h2>
                <button onClick={() => setIsEditModalOpen(false)} className="text-soft-muted hover:text-soft-white transition-colors"><X className="w-6 h-6" /></button>
              </div>
              <form onSubmit={handleUpdateProfile} className="flex flex-col gap-6">

                {/* Row 1: Core Info */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-gold uppercase tracking-wider">{t('fullName')}</label>
                    <div className="relative">
                        <UserCircle className="absolute left-3 top-3.5 w-4 h-4 text-soft-muted" />
                        <input type="text" value={formData.full_name} onChange={(e) => setFormData({...formData, full_name: e.target.value})} className="ui-input pl-10" placeholder="John Doe" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-gold uppercase tracking-wider">{t('jobTitle')}</label>
                    <div className="relative">
                        <Briefcase className="absolute left-3 top-3.5 w-4 h-4 text-soft-muted" />
                        <input type="text" value={formData.job_title} onChange={(e) => setFormData({...formData, job_title: e.target.value})} className="ui-input pl-10" placeholder="Real Estate Agent" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-gold uppercase tracking-wider">{t('locationLabel')}</label>
                    <div className="relative">
                        <MapPin className="absolute left-3 top-3.5 w-4 h-4 text-soft-muted" />
                        <input type="text" value={formData.location} onChange={(e) => setFormData({...formData, location: e.target.value})} className="ui-input pl-10" placeholder="City, Country" />
                    </div>
                  </div>
                 </div>

                {/* Row 2: Metadata */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-gold uppercase tracking-wider">{t('specializationsLabel')} (comma separated)</label>
                    <div className="relative">
                        <Trophy className="absolute left-3 top-3.5 w-4 h-4 text-soft-muted" />
                        <input
                          type="text"
                          value={Array.isArray(formData.specialization) ? formData.specialization.join(', ') : formData.specialization}
                          onChange={(e) => setFormData({...formData, specialization: e.target.value.split(',').map(s => s.trim())})}
                          className="ui-input pl-10"
                          placeholder="Luxury, Waterfront, Investments"
                        />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-gold uppercase tracking-wider">{t('achievementsLabel')} (comma separated)</label>
                     <div className="relative">
                        <Shield className="absolute left-3 top-3.5 w-4 h-4 text-soft-muted" />
                        <input
                          type="text"
                          value={Array.isArray(formData.achievements) ? formData.achievements.join(', ') : formData.achievements}
                          onChange={(e) => setFormData({...formData, achievements: e.target.value.split(',').map(s => s.trim())})}
                          className="ui-input pl-10"
                          placeholder="Top Seller 2025, 50+ Deals Closed"
                        />
                    </div>
                  </div>
                </div>

                {/* Row 3: Bio */}
                <div className="space-y-2 flex-1">
                  <label className="text-xs font-bold text-gold uppercase tracking-wider">{t('professionalSummary')}</label>
                  <textarea rows={3} value={formData.bio} onChange={(e) => setFormData({...formData, bio: e.target.value})} className="ui-textarea h-24 resize-none" placeholder="Tell us about yourself..." />
                </div>

                <div className="flex justify-end gap-4 pt-4 border-t border-soft-subtle/10 mt-auto">
                  <Button type="button" variant="ghost" onClick={() => setIsEditModalOpen(false)} className="text-soft-muted hover:text-soft-white hover:bg-white/5">{t('cancel')}</Button>
                  <Button type="submit" disabled={isSaving} className="bg-gold hover:bg-gold-muted text-[#0F1629] font-bold px-8 rounded-xl shadow-lg transition-transform active:scale-95">
                    {isSaving ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                    {isSaving ? 'Saving...' : t('saveChanges')}
                  </Button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}
