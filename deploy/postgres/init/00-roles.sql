-- Runs once on first Postgres init. Creates the RLS-bound application roles.
-- Passwords are injected from secrets in production (ALTER ROLE ... PASSWORD).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
    CREATE ROLE app_rw LOGIN PASSWORD 'app_rw';        -- override via secret in prod
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
    CREATE ROLE app_admin LOGIN PASSWORD 'app_admin' BYPASSRLS;
  END IF;
END $$;

GRANT CONNECT ON DATABASE chatbot_saas TO app_rw, app_admin;
GRANT USAGE ON SCHEMA public TO app_rw, app_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_rw;
