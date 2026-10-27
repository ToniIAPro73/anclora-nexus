-- ============================================================
-- 002_core_schema.sql — Core tables for Anclora Nexus v0
-- Tables: organizations, user_profiles, agents, tasks
-- ============================================================

-- organizations: single-tenant pero mantiene estructura
CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- user_profiles: link a Supabase Auth (full schema)
CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  org_id UUID NOT NULL REFERENCES organizations(id),
  email TEXT NOT NULL,
  full_name TEXT,
  role TEXT DEFAULT 'owner',
  bio TEXT,
  specialization JSONB DEFAULT '[]',
  achievements JSONB DEFAULT '[]',
  location TEXT DEFAULT 'Mallorca, ES',
  job_title TEXT DEFAULT 'Luxury Estate Consultant',
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- agents: registro de agentes IA disponibles
CREATE TABLE IF NOT EXISTS agents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id),
  name TEXT NOT NULL,
  description TEXT,
  skill_name TEXT NOT NULL,
  status TEXT DEFAULT 'active',
  config JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, skill_name)
);

-- tasks: tareas generadas por agentes o manuales
CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id),
  title TEXT NOT NULL,
  description TEXT,
  type TEXT, -- follow_up, prospection, dossier, admin
  status TEXT DEFAULT 'pending', -- pending, done, cancelled
  due_date TIMESTAMPTZ,
  related_lead_id UUID,
  related_property_id UUID,
  ai_generated BOOLEAN DEFAULT false,
  agent_id UUID REFERENCES agents(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);
