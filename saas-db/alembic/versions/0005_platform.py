"""platform features: CRM, plans, usage metering, durable jobs

Revision ID: 0005_platform
Revises: 0004_refresh_family
Create Date: 2026-06-08

Adds: lead CRM columns + lead_notes + lead_activities; plans (global);
usage_counters + usage_records (metering); jobs (durable queue w/ retries + DLQ).
New lead_status enum values 'proposal' and 'won' are added here and used only by
later migrations/runtime (Postgres requires the ADD VALUE to be committed first).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_platform"
down_revision: Union[str, None] = "0004_refresh_family"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = ("lead_notes", "lead_activities", "usage_counters", "usage_records")


def upgrade() -> None:
    # --- extend lead_status enum (new pipeline stages) ---
    op.execute("ALTER TYPE lead_status ADD VALUE IF NOT EXISTS 'proposal' AFTER 'qualified';")
    op.execute("ALTER TYPE lead_status ADD VALUE IF NOT EXISTS 'won' AFTER 'converted';")

    # --- lead CRM columns ---
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS company VARCHAR(255);")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;")
    op.execute(
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_to UUID "
        "REFERENCES users(id) ON DELETE SET NULL;"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_company_status ON leads (company_id, status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_assigned_to ON leads (assigned_to);")

    # --- lead_notes ---
    op.execute(
        "CREATE TABLE lead_notes (\n"
        "  id UUID DEFAULT gen_random_uuid() NOT NULL,\n"
        "  company_id UUID NOT NULL,\n"
        "  lead_id UUID NOT NULL,\n"
        "  author_id UUID,\n"
        "  body TEXT NOT NULL,\n"
        "  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,\n"
        "  updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,\n"
        "  CONSTRAINT pk_lead_notes PRIMARY KEY (id),\n"
        "  CONSTRAINT fk_lead_notes_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,\n"
        "  CONSTRAINT fk_lead_notes_lead FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,\n"
        "  CONSTRAINT fk_lead_notes_author FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL\n"
        ");"
    )
    op.execute("CREATE INDEX ix_lead_notes_lead ON lead_notes (lead_id, created_at);")

    # --- lead_activities (timeline) ---
    op.execute(
        "CREATE TABLE lead_activities (\n"
        "  id UUID DEFAULT gen_random_uuid() NOT NULL,\n"
        "  company_id UUID NOT NULL,\n"
        "  lead_id UUID NOT NULL,\n"
        "  actor_type actor_type NOT NULL DEFAULT 'system',\n"
        "  actor_user_id UUID,\n"
        "  activity_type VARCHAR(48) NOT NULL,\n"
        "  description TEXT,\n"
        "  data JSONB NOT NULL DEFAULT '{}'::jsonb,\n"
        "  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,\n"
        "  CONSTRAINT pk_lead_activities PRIMARY KEY (id),\n"
        "  CONSTRAINT fk_lead_activities_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,\n"
        "  CONSTRAINT fk_lead_activities_lead FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,\n"
        "  CONSTRAINT fk_lead_activities_actor FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL\n"
        ");"
    )
    op.execute("CREATE INDEX ix_lead_activities_lead ON lead_activities (lead_id, created_at);")

    # --- plans (global catalog, no RLS) ---
    op.execute(
        "CREATE TABLE plans (\n"
        "  code VARCHAR(32) NOT NULL,\n"
        "  name VARCHAR(64) NOT NULL,\n"
        "  price_cents INTEGER NOT NULL DEFAULT 0,\n"
        "  currency VARCHAR(3) NOT NULL DEFAULT 'USD',\n"
        "  interval VARCHAR(8) NOT NULL DEFAULT 'month',\n"
        "  entitlements JSONB NOT NULL DEFAULT '{}'::jsonb,\n"
        "  is_public BOOLEAN NOT NULL DEFAULT true,\n"
        "  sort_order INTEGER NOT NULL DEFAULT 0,\n"
        "  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,\n"
        "  CONSTRAINT pk_plans PRIMARY KEY (code)\n"
        ");"
    )

    # --- usage_counters (current-period aggregates) ---
    op.execute(
        "CREATE TABLE usage_counters (\n"
        "  id UUID DEFAULT gen_random_uuid() NOT NULL,\n"
        "  company_id UUID NOT NULL,\n"
        "  metric VARCHAR(32) NOT NULL,\n"
        "  period_start DATE NOT NULL,\n"
        "  period_end DATE NOT NULL,\n"
        "  value BIGINT NOT NULL DEFAULT 0,\n"
        "  updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,\n"
        "  CONSTRAINT pk_usage_counters PRIMARY KEY (id),\n"
        "  CONSTRAINT uq_usage_counter UNIQUE (company_id, metric, period_start),\n"
        "  CONSTRAINT fk_usage_counters_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE\n"
        ");"
    )
    op.execute("CREATE INDEX ix_usage_counters_company ON usage_counters (company_id);")

    # --- usage_records (append-only metering events) ---
    op.execute(
        "CREATE TABLE usage_records (\n"
        "  id UUID DEFAULT gen_random_uuid() NOT NULL,\n"
        "  company_id UUID NOT NULL,\n"
        "  metric VARCHAR(32) NOT NULL,\n"
        "  quantity BIGINT NOT NULL DEFAULT 1,\n"
        "  chatbot_id UUID,\n"
        "  occurred_at TIMESTAMPTZ DEFAULT now() NOT NULL,\n"
        "  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,\n"
        "  CONSTRAINT pk_usage_records PRIMARY KEY (id),\n"
        "  CONSTRAINT fk_usage_records_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE\n"
        ");"
    )
    op.execute("CREATE INDEX ix_usage_records_company_metric_time ON usage_records (company_id, metric, occurred_at);")

    # --- jobs (durable queue: retries + dead-letter) ---
    op.execute(
        "CREATE TABLE jobs (\n"
        "  id UUID DEFAULT gen_random_uuid() NOT NULL,\n"
        "  queue VARCHAR(64) NOT NULL,\n"
        "  task VARCHAR(128) NOT NULL,\n"
        "  payload JSONB NOT NULL DEFAULT '{}'::jsonb,\n"
        "  status VARCHAR(16) NOT NULL DEFAULT 'pending',\n"
        "  attempts INTEGER NOT NULL DEFAULT 0,\n"
        "  max_attempts INTEGER NOT NULL DEFAULT 5,\n"
        "  run_at TIMESTAMPTZ DEFAULT now() NOT NULL,\n"
        "  locked_at TIMESTAMPTZ,\n"
        "  locked_by VARCHAR(64),\n"
        "  last_error TEXT,\n"
        "  dedupe_key VARCHAR(160),\n"
        "  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,\n"
        "  updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,\n"
        "  CONSTRAINT pk_jobs PRIMARY KEY (id)\n"
        ");"
    )
    op.execute("CREATE INDEX ix_jobs_claim ON jobs (status, run_at);")
    op.execute("CREATE UNIQUE INDEX uq_jobs_dedupe ON jobs (dedupe_key) WHERE dedupe_key IS NOT NULL AND status IN ('pending','running');")

    # --- RLS for new tenant tables (mirror existing tenant_isolation policy) ---
    for tbl in TENANT_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {tbl} "
            "USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) "
            "WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
        )

    # --- grants for the application roles (match 0001 grant pattern) ---
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON lead_notes, lead_activities, "
        "usage_counters, usage_records TO app_rw;"
    )
    op.execute("GRANT SELECT ON plans TO app_rw;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON lead_notes, lead_activities, "
        "usage_counters, usage_records, plans, jobs TO app_admin;"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS jobs;")
    op.execute("DROP TABLE IF EXISTS usage_records;")
    op.execute("DROP TABLE IF EXISTS usage_counters;")
    op.execute("DROP TABLE IF EXISTS plans;")
    op.execute("DROP TABLE IF EXISTS lead_activities;")
    op.execute("DROP TABLE IF EXISTS lead_notes;")
    op.execute("DROP INDEX IF EXISTS ix_leads_assigned_to;")
    op.execute("DROP INDEX IF EXISTS ix_leads_company_status;")
    for col in ("assigned_to", "metadata", "tags", "company"):
        op.execute(f"ALTER TABLE leads DROP COLUMN IF EXISTS {col};")
    # enum values are not removed (Postgres has no DROP VALUE); harmless to keep.
