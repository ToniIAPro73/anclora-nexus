-- Migration 033: Role Scoped Workspace Visibility
-- Feature: ANCLORA-RSWV-001

-- 1) Assignment columns
ALTER TABLE public.leads
  ADD COLUMN IF NOT EXISTS assigned_user_id UUID REFERENCES auth.users(id);

ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS assigned_user_id UUID REFERENCES auth.users(id);

ALTER TABLE public.properties
  ADD COLUMN IF NOT EXISTS assigned_user_id UUID REFERENCES auth.users(id);

-- 2) Indexes
CREATE INDEX IF NOT EXISTS idx_leads_org_assigned_user
  ON public.leads (org_id, assigned_user_id);

CREATE INDEX IF NOT EXISTS idx_tasks_org_assigned_user
  ON public.tasks (org_id, assigned_user_id);

CREATE INDEX IF NOT EXISTS idx_properties_org_assigned_user
  ON public.properties (org_id, assigned_user_id);

-- 3) Backfill from legacy routing notes
UPDATE public.leads
SET assigned_user_id = (notes->'routing'->>'assigned_user_id')::uuid
WHERE assigned_user_id IS NULL
  AND notes IS NOT NULL
  AND (notes->'routing'->>'assigned_user_id') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

UPDATE public.tasks t
SET assigned_user_id = l.assigned_user_id
FROM public.leads l
WHERE t.assigned_user_id IS NULL
  AND t.related_lead_id = l.id
  AND l.assigned_user_id IS NOT NULL;

-- 4) RLS enable
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.properties ENABLE ROW LEVEL SECURITY;

-- 5) Policies - LEADS
DROP POLICY IF EXISTS leads_select_owner_manager ON public.leads;
CREATE POLICY leads_select_owner_manager ON public.leads
FOR SELECT USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = leads.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role IN ('owner', 'manager')
  )
);

DROP POLICY IF EXISTS leads_select_agent_assigned ON public.leads;
CREATE POLICY leads_select_agent_assigned ON public.leads
FOR SELECT USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = leads.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role = 'agent'
  )
  AND leads.assigned_user_id = auth.uid()
);

DROP POLICY IF EXISTS leads_modify_owner_manager ON public.leads;
CREATE POLICY leads_modify_owner_manager ON public.leads
FOR ALL USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = leads.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role IN ('owner', 'manager')
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = leads.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role IN ('owner', 'manager')
  )
);

DROP POLICY IF EXISTS leads_update_agent_assigned ON public.leads;
CREATE POLICY leads_update_agent_assigned ON public.leads
FOR UPDATE USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = leads.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role = 'agent'
  )
  AND leads.assigned_user_id = auth.uid()
)
WITH CHECK (
  leads.assigned_user_id = auth.uid()
);

-- 6) Policies - TASKS
DROP POLICY IF EXISTS tasks_select_owner_manager ON public.tasks;
CREATE POLICY tasks_select_owner_manager ON public.tasks
FOR SELECT USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = tasks.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role IN ('owner', 'manager')
  )
);

DROP POLICY IF EXISTS tasks_select_agent_assigned ON public.tasks;
CREATE POLICY tasks_select_agent_assigned ON public.tasks
FOR SELECT USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = tasks.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role = 'agent'
  )
  AND tasks.assigned_user_id = auth.uid()
);

DROP POLICY IF EXISTS tasks_modify_owner_manager ON public.tasks;
CREATE POLICY tasks_modify_owner_manager ON public.tasks
FOR ALL USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = tasks.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role IN ('owner', 'manager')
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = tasks.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role IN ('owner', 'manager')
  )
);

DROP POLICY IF EXISTS tasks_update_agent_assigned ON public.tasks;
CREATE POLICY tasks_update_agent_assigned ON public.tasks
FOR UPDATE USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = tasks.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role = 'agent'
  )
  AND tasks.assigned_user_id = auth.uid()
)
WITH CHECK (
  tasks.assigned_user_id = auth.uid()
);

-- 7) Policies - PROPERTIES
DROP POLICY IF EXISTS properties_select_owner_manager ON public.properties;
CREATE POLICY properties_select_owner_manager ON public.properties
FOR SELECT USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = properties.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role IN ('owner', 'manager')
  )
);

DROP POLICY IF EXISTS properties_select_agent_assigned ON public.properties;
CREATE POLICY properties_select_agent_assigned ON public.properties
FOR SELECT USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = properties.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role = 'agent'
  )
  AND properties.assigned_user_id = auth.uid()
);

DROP POLICY IF EXISTS properties_modify_owner_manager ON public.properties;
CREATE POLICY properties_modify_owner_manager ON public.properties
FOR ALL USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = properties.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role IN ('owner', 'manager')
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = properties.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role IN ('owner', 'manager')
  )
);

DROP POLICY IF EXISTS properties_update_agent_assigned ON public.properties;
CREATE POLICY properties_update_agent_assigned ON public.properties
FOR UPDATE USING (
  EXISTS (
    SELECT 1
    FROM public.organization_members om
    WHERE om.org_id = properties.org_id
      AND om.user_id = auth.uid()
      AND om.status = 'active'
      AND om.role = 'agent'
  )
  AND properties.assigned_user_id = auth.uid()
)
WITH CHECK (
  properties.assigned_user_id = auth.uid()
);

-- 8) Force PostgREST schema cache reload after DDL/RLS changes.
NOTIFY pgrst, 'reload schema';
