-- ============================================================
-- 003_audit_and_limits.sql — Audit, traceability & limits
-- Tables: audit_log, agent_logs, constitutional_limits, agent_executions
-- ============================================================

-- audit_log: inmutable (REVOKE UPDATE, DELETE) — Constitution Título XI
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id),
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  actor_type TEXT NOT NULL, -- 'user', 'agent', 'system'
  actor_id TEXT NOT NULL, -- UUID string
  action TEXT NOT NULL,
  resource_type TEXT,
  resource_id TEXT,
  details JSONB,
  signature TEXT -- HMAC-SHA256
);

-- Enforce immutability
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'audit_log' AND policyname = 'audit_no_update'
  ) THEN
    CREATE POLICY "audit_no_update" ON audit_log FOR UPDATE USING (false);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'audit_log' AND policyname = 'audit_no_delete'
  ) THEN
    CREATE POLICY "audit_no_delete" ON audit_log FOR DELETE USING (false);
  END IF;
END
$$;

REVOKE UPDATE, DELETE ON audit_log FROM authenticated, anon;

-- agent_logs: trazabilidad de ejecuciones IA
CREATE TABLE IF NOT EXISTS agent_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id),
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  agent_name TEXT NOT NULL,
  skill_name TEXT NOT NULL,
  input JSONB,
  output JSONB,
  llm_model TEXT,
  tokens_used INTEGER,
  duration_ms INTEGER,
  status TEXT DEFAULT 'success' -- success, error, timeout
);

-- constitutional_limits: límites operativos (no financieros)
CREATE TABLE IF NOT EXISTS constitutional_limits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id),
  limit_type TEXT NOT NULL,
  limit_value NUMERIC NOT NULL,
  description TEXT,
  UNIQUE(org_id, limit_type)
);

-- agent_executions: trazabilidad detallada de ejecuciones de skills
CREATE TABLE IF NOT EXISTS agent_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id),
  user_id UUID REFERENCES auth.users(id),
  skill_id UUID REFERENCES agents(id),
  agent_id UUID REFERENCES agents(id),
  status TEXT DEFAULT 'PENDING', -- PENDING, RUNNING, COMPLETED, FAILED, INTERRUPTED
  input JSONB,
  output JSONB,
  reasoning TEXT,
  tool_calls JSONB,
  iteration_count INT DEFAULT 0,
  tokens_used INT DEFAULT 0,
  execution_time_ms INT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_executions_org_id ON agent_executions(org_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_skill_id ON agent_executions(skill_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_created_at ON agent_executions(created_at DESC);

-- RLS for agent_executions
ALTER TABLE agent_executions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'agent_executions' AND policyname = 'org_isolation_agent_executions'
    ) THEN
        CREATE POLICY "org_isolation_agent_executions" ON agent_executions
          FOR ALL USING (
            org_id IN (
              SELECT id FROM organizations
            )
          );
    END IF;
END $$;
