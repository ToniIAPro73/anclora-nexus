-- Keep service_role away from direct access_requests updates and audit_log access.
-- State transitions and audit operations are exposed through narrowly scoped RPCs.
BEGIN;

CREATE OR REPLACE FUNCTION public._nexus_insert_access_request_audit_event(
  p_org_id uuid,
  p_request_id uuid,
  p_audit_event jsonb
)
RETURNS uuid
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
  INSERT INTO public.audit_log (
    org_id, actor_type, actor_id, action, resource_type, resource_id,
    details, signature, timestamp
  )
  SELECT p_org_id,
         p_audit_event ->> 'actor_type',
         p_audit_event ->> 'actor_id',
         p_audit_event ->> 'action',
         'access_request',
         p_request_id::text,
         COALESCE(p_audit_event -> 'details', '{}'::jsonb),
         p_audit_event ->> 'signature',
         COALESCE((p_audit_event ->> 'timestamp')::timestamptz, pg_catalog.now())
    FROM public.access_requests AS request
   WHERE request.id = p_request_id
     AND request.org_id = p_org_id
     AND jsonb_typeof(p_audit_event) = 'object'
     AND p_audit_event ->> 'org_id' = p_org_id::text
     AND p_audit_event ->> 'resource_id' = p_request_id::text
     AND p_audit_event ->> 'resource_type' = 'access_request'
     AND p_audit_event ->> 'action' LIKE 'access_request.%'
     AND p_audit_event ->> 'actor_type' IN ('user', 'system', 'agent')
     AND COALESCE(p_audit_event ->> 'actor_id', '') <> ''
     AND COALESCE(p_audit_event ->> 'signature', '') <> ''
  RETURNING id
$function$;

CREATE OR REPLACE FUNCTION public.nexus_review_access_request(
  p_org_id uuid,
  p_request_id uuid,
  p_decision_status text,
  p_reviewer_id text,
  p_admin_notes text,
  p_rejection_reason text,
  p_reviewed_at timestamptz,
  p_audit_event jsonb
)
RETURNS SETOF public.access_requests
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
  WITH updated AS (
    UPDATE public.access_requests AS request
       SET status = p_decision_status,
           reviewed_at = p_reviewed_at,
           reviewed_by = p_reviewer_id,
           admin_notes = p_admin_notes,
           rejection_reason = p_rejection_reason,
           provisioning_status = CASE
             WHEN p_decision_status = 'approved' THEN 'pending'
             ELSE 'not_applicable'
           END,
           provisioning_error = NULL,
           updated_at = p_reviewed_at
     WHERE request.id = p_request_id
       AND request.org_id = p_org_id
       AND request.status = 'pending'
       AND p_decision_status IN ('approved', 'rejected')
       AND COALESCE(pg_catalog.btrim(p_reviewer_id), '') <> ''
       AND p_reviewed_at IS NOT NULL
       AND p_audit_event ->> 'action' = 'access_request.' || p_decision_status
       AND p_audit_event ->> 'actor_id' = p_reviewer_id
       AND p_audit_event ->> 'org_id' = p_org_id::text
       AND p_audit_event ->> 'resource_id' = p_request_id::text
       AND p_audit_event ->> 'resource_type' = 'access_request'
       AND p_audit_event ->> 'actor_type' = 'user'
       AND COALESCE(p_audit_event ->> 'signature', '') <> ''
    RETURNING request.*
  ), audit AS (
    INSERT INTO public.audit_log (
      org_id, actor_type, actor_id, action, resource_type, resource_id,
      details, signature, timestamp
    )
    SELECT p_org_id,
           p_audit_event ->> 'actor_type',
           p_reviewer_id,
           p_audit_event ->> 'action',
           'access_request',
           p_request_id::text,
           COALESCE(p_audit_event -> 'details', '{}'::jsonb),
           p_audit_event ->> 'signature',
           COALESCE((p_audit_event ->> 'timestamp')::timestamptz, p_reviewed_at)
      FROM updated
    RETURNING id
  )
  SELECT updated.* FROM updated CROSS JOIN audit
$function$;

CREATE OR REPLACE FUNCTION public.nexus_begin_access_request_provisioning_retry(
  p_org_id uuid,
  p_request_id uuid,
  p_started_at timestamptz,
  p_audit_event jsonb
)
RETURNS SETOF public.access_requests
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
  WITH updated AS (
    UPDATE public.access_requests AS request
       SET provisioning_status = 'pending',
           updated_at = p_started_at
     WHERE request.id = p_request_id
       AND request.org_id = p_org_id
       AND request.status = 'approved'
       AND request.identity_subject_id IS NULL
       AND request.identity_invitation_id IS NULL
       AND request.membership_id IS NULL
       AND p_started_at IS NOT NULL
       AND p_audit_event ->> 'action' = 'access_request.provisioning_retry_started'
       AND p_audit_event ->> 'org_id' = p_org_id::text
       AND p_audit_event ->> 'resource_id' = p_request_id::text
       AND p_audit_event ->> 'resource_type' = 'access_request'
       AND p_audit_event ->> 'actor_type' = 'user'
       AND COALESCE(p_audit_event ->> 'actor_id', '') <> ''
       AND COALESCE(p_audit_event ->> 'signature', '') <> ''
       AND (
         request.provisioning_status = 'failed'
         OR (
           request.provisioning_status = 'pending'
           AND request.updated_at < pg_catalog.now() - interval '5 minutes'
         )
       )
    RETURNING request.*
  ), audit AS (
    INSERT INTO public.audit_log (
      org_id, actor_type, actor_id, action, resource_type, resource_id,
      details, signature, timestamp
    )
    SELECT p_org_id,
           p_audit_event ->> 'actor_type',
           p_audit_event ->> 'actor_id',
           p_audit_event ->> 'action',
           'access_request',
           p_request_id::text,
           COALESCE(p_audit_event -> 'details', '{}'::jsonb),
           p_audit_event ->> 'signature',
           COALESCE((p_audit_event ->> 'timestamp')::timestamptz, p_started_at)
      FROM updated
    RETURNING id
  )
  SELECT updated.* FROM updated CROSS JOIN audit
$function$;

CREATE OR REPLACE FUNCTION public.nexus_finalize_access_request_provisioning(
  p_org_id uuid,
  p_request_id uuid,
  p_provisioning_status text,
  p_provisioning_error text,
  p_identity_subject_id text,
  p_identity_invitation_id text,
  p_membership_id text,
  p_invite_token text,
  p_invite_expires_at timestamptz,
  p_updated_at timestamptz,
  p_audit_event jsonb
)
RETURNS SETOF public.access_requests
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
  WITH updated AS (
    UPDATE public.access_requests AS request
       SET provisioning_status = p_provisioning_status,
           provisioning_error = p_provisioning_error,
           identity_subject_id = p_identity_subject_id,
           identity_invitation_id = p_identity_invitation_id,
           membership_id = p_membership_id,
           invite_token = p_invite_token,
           invite_expires_at = p_invite_expires_at,
           updated_at = p_updated_at
     WHERE request.id = p_request_id
       AND request.org_id = p_org_id
       AND request.status = 'approved'
       AND request.provisioning_status = 'pending'
       AND p_provisioning_status IN ('provisioned', 'failed', 'invite_ready', 'pending')
       AND p_updated_at IS NOT NULL
       AND p_audit_event ->> 'action' IN (
         'access_request.provisioning_intent_prepared',
         'access_request.provisioning_retry'
       )
       AND p_audit_event ->> 'org_id' = p_org_id::text
       AND p_audit_event ->> 'resource_id' = p_request_id::text
       AND p_audit_event ->> 'resource_type' = 'access_request'
       AND p_audit_event ->> 'actor_type' = 'user'
       AND COALESCE(p_audit_event ->> 'actor_id', '') <> ''
       AND COALESCE(p_audit_event ->> 'signature', '') <> ''
    RETURNING request.*
  ), audit AS (
    INSERT INTO public.audit_log (
      org_id, actor_type, actor_id, action, resource_type, resource_id,
      details, signature, timestamp
    )
    SELECT p_org_id,
           p_audit_event ->> 'actor_type',
           p_audit_event ->> 'actor_id',
           p_audit_event ->> 'action',
           'access_request',
           p_request_id::text,
           COALESCE(p_audit_event -> 'details', '{}'::jsonb),
           p_audit_event ->> 'signature',
           COALESCE((p_audit_event ->> 'timestamp')::timestamptz, p_updated_at)
      FROM updated
    RETURNING id
  )
  SELECT updated.* FROM updated CROSS JOIN audit
$function$;

CREATE OR REPLACE FUNCTION public.nexus_log_access_request_audit_event(
  p_org_id uuid,
  p_request_id uuid,
  p_audit_event jsonb
)
RETURNS uuid
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
  SELECT public._nexus_insert_access_request_audit_event(
    p_org_id, p_request_id, p_audit_event
  )
$function$;

CREATE OR REPLACE FUNCTION public.nexus_list_access_request_audit_events(
  p_org_id uuid,
  p_request_id uuid DEFAULT NULL,
  p_actions text[] DEFAULT NULL,
  p_since timestamptz DEFAULT NULL,
  p_limit integer DEFAULT 2000,
  p_descending boolean DEFAULT false
)
RETURNS TABLE (
  id uuid,
  "timestamp" timestamptz,
  actor_type text,
  actor_id text,
  action text,
  resource_type text,
  resource_id text,
  details jsonb
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
  SELECT event.id,
         event."timestamp",
         event.actor_type,
         event.actor_id,
         event.action,
         event.resource_type,
         event.resource_id,
         event.details
    FROM public.audit_log AS event
   WHERE event.org_id = p_org_id
     AND event.resource_type = 'access_request'
     AND (p_request_id IS NULL OR event.resource_id = p_request_id::text)
     AND (p_actions IS NULL OR event.action = ANY(p_actions))
     AND (p_since IS NULL OR event."timestamp" >= p_since)
     AND EXISTS (
       SELECT 1
         FROM public.access_requests AS request
        WHERE request.org_id = p_org_id
          AND (p_request_id IS NULL OR request.id = p_request_id)
     )
   ORDER BY CASE WHEN p_descending THEN event."timestamp" END DESC,
            CASE WHEN NOT p_descending THEN event."timestamp" END ASC
   LIMIT GREATEST(1, LEAST(COALESCE(p_limit, 2000), 2000))
$function$;

REVOKE ALL ON FUNCTION public._nexus_insert_access_request_audit_event(uuid, uuid, jsonb)
  FROM PUBLIC, service_role;
REVOKE ALL ON FUNCTION public.nexus_review_access_request(uuid, uuid, text, text, text, text, timestamptz, jsonb)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.nexus_begin_access_request_provisioning_retry(uuid, uuid, timestamptz, jsonb)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.nexus_finalize_access_request_provisioning(uuid, uuid, text, text, text, text, text, text, timestamptz, timestamptz, jsonb)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.nexus_log_access_request_audit_event(uuid, uuid, jsonb)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.nexus_list_access_request_audit_events(uuid, uuid, text[], timestamptz, integer, boolean)
  FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.nexus_review_access_request(uuid, uuid, text, text, text, text, timestamptz, jsonb)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.nexus_begin_access_request_provisioning_retry(uuid, uuid, timestamptz, jsonb)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.nexus_finalize_access_request_provisioning(uuid, uuid, text, text, text, text, text, text, timestamptz, timestamptz, jsonb)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.nexus_log_access_request_audit_event(uuid, uuid, jsonb)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.nexus_list_access_request_audit_events(uuid, uuid, text[], timestamptz, integer, boolean)
  TO service_role;

NOTIFY pgrst, 'reload schema';
COMMIT;
