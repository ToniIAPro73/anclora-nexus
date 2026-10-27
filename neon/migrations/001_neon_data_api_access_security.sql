-- Run after Neon Data API provisioning and role setup on the isolated branch.
-- The application exchanges verified Anclora Identity sessions for short-lived
-- ES256 Neon JWTs. Authenticated browser
-- requests use RLS. The server-only service_role is BYPASSRLS.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN BYPASSRLS;
  END IF;
END;
$$;

GRANT service_role TO authenticator;
GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER, TRUNCATE
  ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO service_role;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anonymous, authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anonymous, authenticated;
REVOKE ALL PRIVILEGES ON SCHEMA public FROM anonymous;

ALTER TABLE public.agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.automation_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.automation_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.automation_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.buyer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.constitutional_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dq_entity_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dq_quality_issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dq_resolution_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.match_activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_buyer_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prospected_properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.weekly_recaps ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON TABLE
  public.agent_logs,
  public.dq_entity_candidates,
  public.leads,
  public.organization_members,
  public.organizations,
  public.properties,
  public.tasks,
  public.user_profiles,
  public.weekly_recaps
TO authenticated;
GRANT INSERT ON TABLE public.properties TO authenticated;
GRANT INSERT (id, org_id, email, full_name, job_title, location)
  ON TABLE public.user_profiles TO authenticated;
GRANT UPDATE (full_name, job_title, location, bio, specialization, achievements, avatar_url)
  ON TABLE public.user_profiles TO authenticated;

DROP POLICY IF EXISTS nexus_members_read_self ON public.organization_members;
CREATE POLICY nexus_members_read_self
  ON public.organization_members FOR SELECT TO authenticated
  USING (user_id = auth.user_id());

DROP POLICY IF EXISTS nexus_organizations_read_member ON public.organizations;
CREATE POLICY nexus_organizations_read_member
  ON public.organizations FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.organization_members AS member
    WHERE member.org_id = organizations.id
      AND member.user_id = auth.user_id()
      AND member.status = 'active'
  ));

DROP POLICY IF EXISTS nexus_profiles_read_self ON public.user_profiles;
CREATE POLICY nexus_profiles_read_self
  ON public.user_profiles FOR SELECT TO authenticated
  USING (id = auth.user_id());

DROP POLICY IF EXISTS nexus_profiles_insert_self ON public.user_profiles;
CREATE POLICY nexus_profiles_insert_self
  ON public.user_profiles FOR INSERT TO authenticated
  WITH CHECK (
    id = auth.user_id()
    AND EXISTS (
      SELECT 1 FROM public.organization_members AS member
      WHERE member.org_id = user_profiles.org_id
        AND member.user_id = auth.user_id()
        AND member.status = 'active'
    )
  );

DROP POLICY IF EXISTS nexus_profiles_update_self ON public.user_profiles;
CREATE POLICY nexus_profiles_update_self
  ON public.user_profiles FOR UPDATE TO authenticated
  USING (id = auth.user_id())
  WITH CHECK (id = auth.user_id());

DROP POLICY IF EXISTS nexus_leads_read_org ON public.leads;
CREATE POLICY nexus_leads_read_org
  ON public.leads FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.organization_members AS member
    WHERE member.org_id = leads.org_id
      AND member.user_id = auth.user_id()
      AND member.status = 'active'
  ));

DROP POLICY IF EXISTS nexus_tasks_read_org ON public.tasks;
CREATE POLICY nexus_tasks_read_org
  ON public.tasks FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.organization_members AS member
    WHERE member.org_id = tasks.org_id
      AND member.user_id = auth.user_id()
      AND member.status = 'active'
  ));

DROP POLICY IF EXISTS nexus_properties_read_org ON public.properties;
CREATE POLICY nexus_properties_read_org
  ON public.properties FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.organization_members AS member
    WHERE member.org_id = properties.org_id
      AND member.user_id = auth.user_id()
      AND member.status = 'active'
  ));

DROP POLICY IF EXISTS nexus_properties_insert_org ON public.properties;
CREATE POLICY nexus_properties_insert_org
  ON public.properties FOR INSERT TO authenticated
  WITH CHECK (EXISTS (
    SELECT 1 FROM public.organization_members AS member
    WHERE member.org_id = properties.org_id
      AND member.user_id = auth.user_id()
      AND member.status = 'active'
  ));

DROP POLICY IF EXISTS nexus_agent_logs_read_org ON public.agent_logs;
CREATE POLICY nexus_agent_logs_read_org
  ON public.agent_logs FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.organization_members AS member
    WHERE member.org_id = agent_logs.org_id
      AND member.user_id = auth.user_id()
      AND member.status = 'active'
  ));

DROP POLICY IF EXISTS nexus_dq_candidates_read_org ON public.dq_entity_candidates;
CREATE POLICY nexus_dq_candidates_read_org
  ON public.dq_entity_candidates FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.organization_members AS member
    WHERE member.org_id = dq_entity_candidates.org_id
      AND member.user_id = auth.user_id()
      AND member.status = 'active'
  ));

DROP POLICY IF EXISTS nexus_weekly_recaps_read_org ON public.weekly_recaps;
CREATE POLICY nexus_weekly_recaps_read_org
  ON public.weekly_recaps FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.organization_members AS member
    WHERE member.org_id = weekly_recaps.org_id
      AND member.user_id = auth.user_id()
      AND member.status = 'active'
  ));
