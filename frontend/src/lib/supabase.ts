import { createBrowserClient } from '@supabase/auth-helpers-nextjs'
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

function createNoopChannel() {
  return {
    on() {
      return this
    },
    subscribe() {
      return {
        unsubscribe() {
          return undefined
        },
      }
    },
  }
}

function createNoopSupabaseClient() {
  return {
    auth: {
      async getSession() {
        return { data: { session: null }, error: null }
      },
      async getUser() {
        return { data: { user: null }, error: null }
      },
      async signInWithPassword() {
        return { data: null, error: new Error('Supabase env not configured') }
      },
      async signOut() {
        return { error: null }
      },
      async exchangeCodeForSession() {
        return { data: null, error: new Error('Supabase env not configured') }
      },
      onAuthStateChange() {
        return { data: { subscription: { unsubscribe() {} } } }
      },
    },
    from() {
      const chain = {
        select() { return chain },
        insert() { return chain },
        update() { return chain },
        delete() { return chain },
        upsert() { return chain },
        eq() { return chain },
        neq() { return chain },
        in() { return chain },
        order() { return chain },
        limit() { return chain },
        single() { return chain },
        maybeSingle() { return chain },
        async then(resolve: (value: unknown) => unknown) {
          return resolve({ data: null, error: new Error('Supabase env not configured') })
        },
      }
      return chain
    },
    channel() {
      return createNoopChannel()
    },
  }
}

type SupabaseLike =
  | ReturnType<typeof createNoopSupabaseClient>
  | ReturnType<typeof createBrowserClient>

const authClient: SupabaseLike =
  typeof window !== 'undefined' && supabaseUrl && supabaseAnonKey
    ? (createBrowserClient(supabaseUrl, supabaseAnonKey) as SupabaseLike)
    : createNoopSupabaseClient()

const usesNeon = process.env.NEXT_PUBLIC_DATABASE_PROVIDER === 'neon'
const neonDataApiUrl = process.env.NEXT_PUBLIC_NEON_DATA_API_URL || ''
let neonToken: { value: string; expiresAt: number } | null = null
let neonTokenPromise: Promise<string> | null = null

async function getNeonToken() {
  if (neonToken && neonToken.expiresAt > Date.now() + 30_000) return neonToken.value
  if (!neonTokenPromise) {
    neonTokenPromise = fetch('/api/neon-token', { method: 'POST', cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to authorize Neon database access')
        const result = (await response.json()) as { token: string; expiresAt: number }
        neonToken = { value: result.token, expiresAt: result.expiresAt * 1000 }
        return result.token
      })
      .finally(() => { neonTokenPromise = null })
  }
  return neonTokenPromise
}

if (typeof window !== 'undefined' && 'auth' in authClient) {
  authClient.auth.onAuthStateChange(() => { neonToken = null })
}

const neonBaseUrl = neonDataApiUrl.replace(/\/rest\/v1\/?$/, '').replace(/\/$/, '')
const neonClient =
  typeof window !== 'undefined' && usesNeon && neonBaseUrl && supabaseAnonKey
    ? createClient(neonBaseUrl, supabaseAnonKey, {
        auth: { autoRefreshToken: false, persistSession: false, detectSessionInUrl: false },
        global: {
          fetch: async (input, init) => {
            const token = await getNeonToken()
            const headers = new Headers(init?.headers)
            headers.delete('apikey')
            headers.set('Authorization', `Bearer ${token}`)
            return fetch(input, { ...init, headers })
          },
        },
      })
    : null

const databaseClient = usesNeon && neonClient ? neonClient : authClient
const supabase: SupabaseLike = new Proxy(databaseClient as SupabaseLike, {
  get(target, property) {
    if (property === 'auth' || property === 'storage' || property === 'channel') {
      return Reflect.get(authClient, property, authClient)
    }
    const value = Reflect.get(target, property, target)
    return typeof value === 'function' ? value.bind(target) : value
  },
})

function subscribeByPolling(
  table: string,
  cb: (payload: Record<string, unknown>) => void,
  timestampColumn = 'created_at'
) {
  let active = true
  let initialized = false
  let knownRows = new Map<string, string>()
  let polling = false
  const poll = async (initialize = false) => {
    if (!active || polling) return
    polling = true
    try {
      const { data, error } = await supabase.from(table).select('*').order(timestampColumn, { ascending: false }).limit(50)
      if (error || !Array.isArray(data) || !active) return
      const rows = data as Array<Record<string, unknown>>
      const currentRows = new Map<string, string>()
      for (const row of rows) {
        const id = String(row.id || '')
        if (!id) continue
        const snapshot = JSON.stringify(row)
        currentRows.set(id, snapshot)
        if (initialized && !initialize) {
          const previousSnapshot = knownRows.get(id)
          if (!previousSnapshot) cb({ eventType: 'INSERT', new: row, old: {} })
          else if (previousSnapshot !== snapshot) cb({ eventType: 'UPDATE', new: row, old: JSON.parse(previousSnapshot) })
        }
      }
      knownRows = currentRows
      initialized = true
    } catch {
      // A transient token/API failure is retried by the next scheduled poll.
    } finally {
      polling = false
    }
  }
  void poll(true)
  const timer = setInterval(() => { void poll() }, 15_000)
  return { unsubscribe() { active = false; clearInterval(timer) } }
}

export function subscribeToLeads(cb: (payload: Record<string, unknown>) => void) {
  return subscribeByPolling('leads', cb)
}

export function subscribeToAgentLogs(cb: (payload: Record<string, unknown>) => void) {
  return subscribeByPolling('agent_logs', cb, 'timestamp')
}

export function subscribeToTasks(cb: (payload: Record<string, unknown>) => void) {
  return subscribeByPolling('tasks', cb)
}

export default supabase
