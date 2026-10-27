-- Switch existing row-security policies from legacy JWT helper functions to Neon Data API claims.
-- Neon Data API verifies external Anclora Identity JWTs and exposes auth.user_id()/auth.session().
DO $$
DECLARE
  policy_row RECORD;
  using_expr TEXT;
  check_expr TEXT;
  alter_sql TEXT;
BEGIN
  FOR policy_row IN
    SELECT schemaname, tablename, policyname, qual, with_check
    FROM pg_policies
    WHERE schemaname = 'public'
      AND (position('auth.uid()' in coalesce(qual, '')) > 0
        OR position('auth.role()' in coalesce(qual, '')) > 0
        OR position('auth.uid()' in coalesce(with_check, '')) > 0
        OR position('auth.role()' in coalesce(with_check, '')) > 0)
  LOOP
    using_expr := CASE WHEN policy_row.qual IS NULL THEN NULL ELSE
      replace(replace(policy_row.qual, 'auth.uid()', 'auth.user_id()'), 'auth.role()', '(auth.session()->>''role'')') END;
    check_expr := CASE WHEN policy_row.with_check IS NULL THEN NULL ELSE
      replace(replace(policy_row.with_check, 'auth.uid()', 'auth.user_id()'), 'auth.role()', '(auth.session()->>''role'')') END;

    alter_sql := format('ALTER POLICY %I ON %I.%I', policy_row.policyname, policy_row.schemaname, policy_row.tablename);
    IF using_expr IS NOT NULL THEN
      alter_sql := alter_sql || format(' USING (%s)', using_expr);
    END IF;
    IF check_expr IS NOT NULL THEN
      alter_sql := alter_sql || format(' WITH CHECK (%s)', check_expr);
    END IF;
    EXECUTE alter_sql;
  END LOOP;
END;
$$;
