-- The access_requests table was introduced after the initial Data API grants.
-- Keep the backend service role limited to the intake operations it needs.
GRANT SELECT, INSERT ON TABLE public.access_requests TO service_role;
