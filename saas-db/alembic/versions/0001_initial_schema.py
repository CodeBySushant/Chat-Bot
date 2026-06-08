"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-08

Frozen, hand-verified initial schema: 21 tables, 13 enum types, time-range
partitioning for messages/analytics_events/activity_logs, updated_at triggers,
and Row-Level Security tenant-isolation policies. Generated from the validated
SQLAlchemy metadata and frozen here so the migration is immutable.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        'CREATE EXTENSION IF NOT EXISTS pgcrypto;'
    )
    op.execute(
        'CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$\nBEGIN\n    NEW.updated_at = now();\n    RETURN NEW;\nEND;\n$$ LANGUAGE plpgsql;'
    )
    op.execute(
        "CREATE TYPE company_status AS ENUM ('active', 'suspended');"
    )
    op.execute(
        "CREATE TYPE member_status AS ENUM ('invited', 'active', 'suspended');"
    )
    op.execute(
        "CREATE TYPE document_source_type AS ENUM ('upload', 'crawl', 'url', 'text');"
    )
    op.execute(
        "CREATE TYPE processing_status AS ENUM ('pending', 'processing', 'ready', 'failed');"
    )
    op.execute(
        "CREATE TYPE chatbot_status AS ENUM ('draft', 'active', 'archived');"
    )
    op.execute(
        "CREATE TYPE conversation_channel AS ENUM ('widget', 'api', 'playground');"
    )
    op.execute(
        "CREATE TYPE conversation_status AS ENUM ('open', 'closed');"
    )
    op.execute(
        "CREATE TYPE message_role AS ENUM ('system', 'user', 'assistant', 'tool');"
    )
    op.execute(
        "CREATE TYPE lead_status AS ENUM ('new', 'contacted', 'qualified', 'converted', 'lost');"
    )
    op.execute(
        "CREATE TYPE crawler_status AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled');"
    )
    op.execute(
        "CREATE TYPE subscription_status AS ENUM ('trialing', 'active', 'past_due', 'canceled', 'incomplete');"
    )
    op.execute(
        "CREATE TYPE invoice_status AS ENUM ('draft', 'open', 'paid', 'void', 'uncollectible');"
    )
    op.execute(
        "CREATE TYPE actor_type AS ENUM ('user', 'system', 'api_key');"
    )
    op.execute(
        "CREATE TABLE companies (\n\tname VARCHAR(255) NOT NULL, \n\tslug VARCHAR(100) NOT NULL, \n\tstatus company_status DEFAULT 'active' NOT NULL, \n\tsettings JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_companies PRIMARY KEY (id)\n);"
    )
    op.execute(
        'CREATE TABLE permissions (\n\tcode VARCHAR(100) NOT NULL, \n\tresource VARCHAR(64) NOT NULL, \n\taction VARCHAR(64) NOT NULL, \n\tdescription TEXT, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_permissions PRIMARY KEY (id), \n\tCONSTRAINT uq_permissions_resource_action UNIQUE (resource, action), \n\tCONSTRAINT uq_permissions_code UNIQUE (code)\n);'
    )
    op.execute(
        'CREATE TABLE users (\n\temail VARCHAR(320) NOT NULL, \n\thashed_password VARCHAR(255) NOT NULL, \n\tfull_name VARCHAR(255), \n\tavatar_url VARCHAR(1024), \n\tis_active BOOLEAN DEFAULT true NOT NULL, \n\tis_superuser BOOLEAN DEFAULT false NOT NULL, \n\temail_verified_at TIMESTAMP WITH TIME ZONE, \n\tlast_login_at TIMESTAMP WITH TIME ZONE, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_users PRIMARY KEY (id)\n);'
    )
    op.execute(
        "CREATE TABLE activity_logs (\n\tcompany_id UUID, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tactor_type actor_type NOT NULL, \n\tactor_user_id UUID, \n\taction VARCHAR(128) NOT NULL, \n\tresource_type VARCHAR(64), \n\tresource_id UUID, \n\tip_address INET, \n\tuser_agent VARCHAR(512), \n\tchanges JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tCONSTRAINT pk_activity_logs PRIMARY KEY (id, created_at), \n\tCONSTRAINT fk_activity_logs_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_activity_logs_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL\n)\n PARTITION BY RANGE (created_at);"
    )
    op.execute(
        "CREATE TABLE api_keys (\n\tname VARCHAR(255) NOT NULL, \n\tkey_prefix VARCHAR(12) NOT NULL, \n\tkey_hash VARCHAR(255) NOT NULL, \n\tscopes VARCHAR[] DEFAULT '{}'::text[] NOT NULL, \n\tlast_used_at TIMESTAMP WITH TIME ZONE, \n\texpires_at TIMESTAMP WITH TIME ZONE, \n\trevoked_at TIMESTAMP WITH TIME ZONE, \n\tcreated_by_id UUID, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_api_keys PRIMARY KEY (id), \n\tCONSTRAINT uq_api_keys_key_hash UNIQUE (key_hash), \n\tCONSTRAINT fk_api_keys_created_by_id_users FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL, \n\tCONSTRAINT fk_api_keys_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        "CREATE TABLE chatbots (\n\tname VARCHAR(255) NOT NULL, \n\tslug VARCHAR(120) NOT NULL, \n\tdescription TEXT, \n\tstatus chatbot_status DEFAULT 'draft' NOT NULL, \n\tsystem_prompt TEXT, \n\tgreeting TEXT, \n\tprovider VARCHAR(64) DEFAULT 'openai' NOT NULL, \n\tmodel VARCHAR(128) DEFAULT 'gpt-4o-mini' NOT NULL, \n\tembedding_model VARCHAR(128) DEFAULT 'text-embedding-3-small' NOT NULL, \n\ttemperature NUMERIC(3, 2) DEFAULT 0.20 NOT NULL, \n\ttop_k INTEGER DEFAULT 8 NOT NULL, \n\tmax_tokens INTEGER DEFAULT 1024 NOT NULL, \n\tpublic_key VARCHAR(64) NOT NULL, \n\tsettings JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_chatbots PRIMARY KEY (id), \n\tCONSTRAINT ck_chatbots_temperature_range CHECK (temperature >= 0 AND temperature <= 2), \n\tCONSTRAINT ck_chatbots_top_k_range CHECK (top_k > 0 AND top_k <= 50), \n\tCONSTRAINT uq_chatbots_public_key UNIQUE (public_key), \n\tCONSTRAINT fk_chatbots_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        'CREATE TABLE roles (\n\tcompany_id UUID, \n\tname VARCHAR(100) NOT NULL, \n\tslug VARCHAR(100) NOT NULL, \n\tdescription TEXT, \n\tis_system BOOLEAN DEFAULT false NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_roles PRIMARY KEY (id), \n\tCONSTRAINT fk_roles_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);'
    )
    op.execute(
        "CREATE TABLE subscriptions (\n\tplan_code VARCHAR(64) NOT NULL, \n\tstatus subscription_status DEFAULT 'trialing' NOT NULL, \n\tprovider VARCHAR(32) DEFAULT 'stripe' NOT NULL, \n\tprovider_subscription_id VARCHAR(255), \n\tseats INTEGER DEFAULT 1 NOT NULL, \n\tlimits JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tcurrent_period_start TIMESTAMP WITH TIME ZONE, \n\tcurrent_period_end TIMESTAMP WITH TIME ZONE, \n\ttrial_ends_at TIMESTAMP WITH TIME ZONE, \n\tcanceled_at TIMESTAMP WITH TIME ZONE, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_subscriptions PRIMARY KEY (id), \n\tCONSTRAINT uq_subscriptions_provider_subscription_id UNIQUE (provider_subscription_id), \n\tCONSTRAINT fk_subscriptions_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        "CREATE TABLE analytics_daily (\n\tchatbot_id UUID, \n\tday DATE NOT NULL, \n\tconversations_count BIGINT DEFAULT 0 NOT NULL, \n\tmessages_count BIGINT DEFAULT 0 NOT NULL, \n\tleads_count BIGINT DEFAULT 0 NOT NULL, \n\ttokens_used BIGINT DEFAULT 0 NOT NULL, \n\tmetrics JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_analytics_daily PRIMARY KEY (id), \n\tCONSTRAINT rollup_grain UNIQUE (company_id, chatbot_id, day), \n\tCONSTRAINT fk_analytics_daily_chatbot_id_chatbots FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_analytics_daily_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        "CREATE TABLE analytics_events (\n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\toccurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tchatbot_id UUID, \n\tconversation_id UUID, \n\tevent_type VARCHAR(64) NOT NULL, \n\tevent_name VARCHAR(128) NOT NULL, \n\tvisitor_id VARCHAR(64), \n\tsession_id VARCHAR(64), \n\tproperties JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tCONSTRAINT pk_analytics_events PRIMARY KEY (id, occurred_at), \n\tCONSTRAINT fk_analytics_events_chatbot_id_chatbots FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE SET NULL, \n\tCONSTRAINT fk_analytics_events_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n)\n PARTITION BY RANGE (occurred_at);"
    )
    op.execute(
        "CREATE TABLE company_members (\n\tcompany_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\trole_id UUID NOT NULL, \n\tstatus member_status DEFAULT 'invited' NOT NULL, \n\tinvited_by_id UUID, \n\tjoined_at TIMESTAMP WITH TIME ZONE, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_company_members PRIMARY KEY (id), \n\tCONSTRAINT fk_company_members_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_company_members_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_company_members_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_company_members_invited_by_id_users FOREIGN KEY(invited_by_id) REFERENCES users (id) ON DELETE SET NULL\n);"
    )
    op.execute(
        "CREATE TABLE conversations (\n\tchatbot_id UUID NOT NULL, \n\tvisitor_id VARCHAR(64), \n\tsession_id VARCHAR(64), \n\tchannel conversation_channel DEFAULT 'widget' NOT NULL, \n\tstatus conversation_status DEFAULT 'open' NOT NULL, \n\ttitle VARCHAR(512), \n\tmessage_count INTEGER DEFAULT 0 NOT NULL, \n\tstarted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tended_at TIMESTAMP WITH TIME ZONE, \n\tmetadata JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_conversations PRIMARY KEY (id), \n\tCONSTRAINT fk_conversations_chatbot_id_chatbots FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_conversations_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        "CREATE TABLE crawler_jobs (\n\tchatbot_id UUID NOT NULL, \n\tstart_url VARCHAR(2048) NOT NULL, \n\tstatus crawler_status DEFAULT 'queued' NOT NULL, \n\tconfig JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tpages_discovered INTEGER DEFAULT 0 NOT NULL, \n\tpages_processed INTEGER DEFAULT 0 NOT NULL, \n\tpages_failed INTEGER DEFAULT 0 NOT NULL, \n\terror TEXT, \n\tstarted_at TIMESTAMP WITH TIME ZONE, \n\tfinished_at TIMESTAMP WITH TIME ZONE, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_crawler_jobs PRIMARY KEY (id), \n\tCONSTRAINT fk_crawler_jobs_chatbot_id_chatbots FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_crawler_jobs_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        "CREATE TABLE invoices (\n\tsubscription_id UUID, \n\tnumber VARCHAR(64) NOT NULL, \n\tstatus invoice_status DEFAULT 'draft' NOT NULL, \n\tcurrency VARCHAR(3) DEFAULT 'USD' NOT NULL, \n\tamount_due NUMERIC(12, 2) DEFAULT 0 NOT NULL, \n\tamount_paid NUMERIC(12, 2) DEFAULT 0 NOT NULL, \n\tprovider_invoice_id VARCHAR(255), \n\tperiod_start TIMESTAMP WITH TIME ZONE, \n\tperiod_end TIMESTAMP WITH TIME ZONE, \n\tdue_date TIMESTAMP WITH TIME ZONE, \n\tpaid_at TIMESTAMP WITH TIME ZONE, \n\tline_items JSONB DEFAULT '[]'::jsonb NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_invoices PRIMARY KEY (id), \n\tCONSTRAINT fk_invoices_subscription_id_subscriptions FOREIGN KEY(subscription_id) REFERENCES subscriptions (id) ON DELETE SET NULL, \n\tCONSTRAINT uq_invoices_number UNIQUE (number), \n\tCONSTRAINT uq_invoices_provider_invoice_id UNIQUE (provider_invoice_id), \n\tCONSTRAINT fk_invoices_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        'CREATE TABLE role_permissions (\n\trole_id UUID NOT NULL, \n\tpermission_id UUID NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_role_permissions PRIMARY KEY (id), \n\tCONSTRAINT uq_role_permissions_role_id_permission_id UNIQUE (role_id, permission_id), \n\tCONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE\n);'
    )
    op.execute(
        "CREATE TABLE widget_configurations (\n\tchatbot_id UUID NOT NULL, \n\tis_enabled BOOLEAN DEFAULT true NOT NULL, \n\ttheme JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tprimary_color VARCHAR(9) DEFAULT '#2563eb' NOT NULL, \n\tposition VARCHAR(16) DEFAULT 'bottom-right' NOT NULL, \n\tlauncher_icon_url VARCHAR(1024), \n\tgreeting TEXT, \n\tsuggested_prompts JSONB DEFAULT '[]'::jsonb NOT NULL, \n\tlead_capture JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tlocale VARCHAR(10) DEFAULT 'en' NOT NULL, \n\tallowed_domains VARCHAR[] DEFAULT '{}'::text[] NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_widget_configurations PRIMARY KEY (id), \n\tCONSTRAINT one_config_per_chatbot UNIQUE (chatbot_id), \n\tCONSTRAINT fk_widget_configurations_chatbot_id_chatbots FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_widget_configurations_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        "CREATE TABLE documents (\n\tchatbot_id UUID NOT NULL, \n\tcrawler_job_id UUID, \n\tsource_type document_source_type NOT NULL, \n\ttitle VARCHAR(1024), \n\tsource_uri VARCHAR(2048), \n\tstorage_key VARCHAR(1024), \n\tmime_type VARCHAR(128), \n\tfile_size BIGINT, \n\tcontent_hash VARCHAR(64), \n\tstatus processing_status DEFAULT 'pending' NOT NULL, \n\terror TEXT, \n\ttoken_count INTEGER DEFAULT 0 NOT NULL, \n\tmetadata JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_documents PRIMARY KEY (id), \n\tCONSTRAINT fk_documents_chatbot_id_chatbots FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_documents_crawler_job_id_crawler_jobs FOREIGN KEY(crawler_job_id) REFERENCES crawler_jobs (id) ON DELETE SET NULL, \n\tCONSTRAINT fk_documents_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        "CREATE TABLE leads (\n\tchatbot_id UUID NOT NULL, \n\tconversation_id UUID, \n\tname VARCHAR(255), \n\temail VARCHAR(320), \n\tphone VARCHAR(32), \n\tstatus lead_status DEFAULT 'new' NOT NULL, \n\tsource VARCHAR(128), \n\tscore INTEGER DEFAULT 0 NOT NULL, \n\tfields JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tnotes TEXT, \n\tcaptured_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_leads PRIMARY KEY (id), \n\tCONSTRAINT ck_leads_score_range CHECK (score >= 0 AND score <= 100), \n\tCONSTRAINT fk_leads_chatbot_id_chatbots FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_leads_conversation_id_conversations FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE SET NULL, \n\tCONSTRAINT fk_leads_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        "CREATE TABLE messages (\n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tconversation_id UUID NOT NULL, \n\trole message_role NOT NULL, \n\tcontent TEXT NOT NULL, \n\ttoken_count INTEGER DEFAULT 0 NOT NULL, \n\tmodel VARCHAR(128), \n\tlatency_ms INTEGER, \n\tretrieved_chunk_ids JSONB DEFAULT '[]'::jsonb NOT NULL, \n\tcitations JSONB DEFAULT '[]'::jsonb NOT NULL, \n\tfeedback SMALLINT, \n\tmetadata JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tCONSTRAINT pk_messages PRIMARY KEY (id, created_at), \n\tCONSTRAINT ck_messages_feedback_range CHECK (feedback IN (-1, 0, 1)), \n\tCONSTRAINT fk_messages_conversation_id_conversations FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_messages_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n)\n PARTITION BY RANGE (created_at);"
    )
    op.execute(
        "CREATE TABLE document_chunks (\n\tdocument_id UUID NOT NULL, \n\tchunk_index INTEGER NOT NULL, \n\tcontent TEXT NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\ttoken_count INTEGER DEFAULT 0 NOT NULL, \n\tchar_count INTEGER DEFAULT 0 NOT NULL, \n\tpage_number INTEGER, \n\theading_path TEXT, \n\tmetadata JSONB DEFAULT '{}'::jsonb NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_document_chunks PRIMARY KEY (id), \n\tCONSTRAINT chunk_position UNIQUE (document_id, chunk_index), \n\tCONSTRAINT fk_document_chunks_document_id_documents FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_document_chunks_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        "CREATE TABLE embeddings (\n\tchunk_id UUID NOT NULL, \n\tprovider VARCHAR(64) NOT NULL, \n\tmodel VARCHAR(128) NOT NULL, \n\tdimensions INTEGER NOT NULL, \n\tcollection_name VARCHAR(255) NOT NULL, \n\tvector_id VARCHAR(64) NOT NULL, \n\tstatus processing_status DEFAULT 'pending' NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tdeleted_at TIMESTAMP WITH TIME ZONE, \n\tCONSTRAINT pk_embeddings PRIMARY KEY (id), \n\tCONSTRAINT one_embedding_per_chunk UNIQUE (chunk_id), \n\tCONSTRAINT fk_embeddings_chunk_id_document_chunks FOREIGN KEY(chunk_id) REFERENCES document_chunks (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_embeddings_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE\n);"
    )
    op.execute(
        'CREATE INDEX ix_companies_deleted_at ON companies (deleted_at);'
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_companies_slug_active ON companies (slug) WHERE deleted_at IS NULL;'
    )
    op.execute(
        'CREATE INDEX ix_users_deleted_at ON users (deleted_at);'
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_users_email_active ON users (lower(email)) WHERE deleted_at IS NULL;'
    )
    op.execute(
        'CREATE INDEX ix_activity_logs_company_created ON activity_logs (company_id, created_at);'
    )
    op.execute(
        'CREATE INDEX ix_activity_logs_resource ON activity_logs (resource_type, resource_id);'
    )
    op.execute(
        'CREATE INDEX ix_activity_logs_company_id ON activity_logs (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_api_keys_company_active ON api_keys (company_id, revoked_at);'
    )
    op.execute(
        'CREATE INDEX ix_api_keys_company_id ON api_keys (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_api_keys_key_prefix ON api_keys (key_prefix);'
    )
    op.execute(
        'CREATE INDEX ix_api_keys_deleted_at ON api_keys (deleted_at);'
    )
    op.execute(
        'CREATE INDEX ix_chatbots_company_id ON chatbots (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_chatbots_deleted_at ON chatbots (deleted_at);'
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_chatbots_company_slug ON chatbots (company_id, slug) WHERE deleted_at IS NULL;'
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_roles_company_slug ON roles (company_id, slug) WHERE company_id IS NOT NULL AND deleted_at IS NULL;'
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_roles_system_slug ON roles (slug) WHERE company_id IS NULL AND deleted_at IS NULL;'
    )
    op.execute(
        'CREATE INDEX ix_roles_company_id ON roles (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_roles_deleted_at ON roles (deleted_at);'
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_subscriptions_company_live ON subscriptions (company_id) WHERE status IN ('trialing','active','past_due') AND deleted_at IS NULL;"
    )
    op.execute(
        'CREATE INDEX ix_subscriptions_company_id ON subscriptions (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_subscriptions_deleted_at ON subscriptions (deleted_at);'
    )
    op.execute(
        'CREATE INDEX ix_analytics_daily_company_id ON analytics_daily (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_analytics_daily_company_day ON analytics_daily (company_id, day);'
    )
    op.execute(
        'CREATE INDEX ix_analytics_events_company_type_time ON analytics_events (company_id, event_type, occurred_at);'
    )
    op.execute(
        'CREATE INDEX ix_analytics_events_chatbot_time ON analytics_events (chatbot_id, occurred_at);'
    )
    op.execute(
        'CREATE INDEX ix_analytics_events_company_id ON analytics_events (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_company_members_company_id ON company_members (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_company_members_deleted_at ON company_members (deleted_at);'
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_company_members_company_user ON company_members (company_id, user_id) WHERE deleted_at IS NULL;'
    )
    op.execute(
        'CREATE INDEX ix_company_members_user_id ON company_members (user_id);'
    )
    op.execute(
        'CREATE INDEX ix_conversations_company_chatbot_created ON conversations (company_id, chatbot_id, created_at);'
    )
    op.execute(
        'CREATE INDEX ix_conversations_visitor_id ON conversations (visitor_id);'
    )
    op.execute(
        'CREATE INDEX ix_conversations_deleted_at ON conversations (deleted_at);'
    )
    op.execute(
        'CREATE INDEX ix_conversations_company_id ON conversations (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_crawler_jobs_company_id ON crawler_jobs (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_crawler_jobs_company_status ON crawler_jobs (company_id, status);'
    )
    op.execute(
        'CREATE INDEX ix_crawler_jobs_chatbot_id ON crawler_jobs (chatbot_id);'
    )
    op.execute(
        'CREATE INDEX ix_crawler_jobs_deleted_at ON crawler_jobs (deleted_at);'
    )
    op.execute(
        'CREATE INDEX ix_invoices_subscription_id ON invoices (subscription_id);'
    )
    op.execute(
        'CREATE INDEX ix_invoices_deleted_at ON invoices (deleted_at);'
    )
    op.execute(
        'CREATE INDEX ix_invoices_company_status ON invoices (company_id, status);'
    )
    op.execute(
        'CREATE INDEX ix_invoices_company_id ON invoices (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_widget_configurations_deleted_at ON widget_configurations (deleted_at);'
    )
    op.execute(
        'CREATE INDEX ix_widget_configurations_company_id ON widget_configurations (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_documents_chatbot_status ON documents (chatbot_id, status);'
    )
    op.execute(
        'CREATE INDEX ix_documents_deleted_at ON documents (deleted_at);'
    )
    op.execute(
        'CREATE INDEX ix_documents_company_id ON documents (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_documents_crawler_job_id ON documents (crawler_job_id);'
    )
    op.execute(
        'CREATE INDEX ix_documents_content_hash ON documents (content_hash);'
    )
    op.execute(
        'CREATE INDEX ix_documents_chatbot_id ON documents (chatbot_id);'
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_leads_conversation ON leads (conversation_id) WHERE conversation_id IS NOT NULL;'
    )
    op.execute(
        'CREATE INDEX ix_leads_company_status ON leads (company_id, status);'
    )
    op.execute(
        'CREATE INDEX ix_leads_company_id ON leads (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_leads_chatbot_id ON leads (chatbot_id);'
    )
    op.execute(
        'CREATE INDEX ix_leads_deleted_at ON leads (deleted_at);'
    )
    op.execute(
        'CREATE INDEX ix_leads_email ON leads (email);'
    )
    op.execute(
        'CREATE INDEX ix_messages_company_created ON messages (company_id, created_at);'
    )
    op.execute(
        'CREATE INDEX ix_messages_company_id ON messages (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_messages_conversation_created ON messages (conversation_id, created_at);'
    )
    op.execute(
        'CREATE INDEX ix_document_chunks_content_hash ON document_chunks (content_hash);'
    )
    op.execute(
        'CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id);'
    )
    op.execute(
        'CREATE INDEX ix_document_chunks_deleted_at ON document_chunks (deleted_at);'
    )
    op.execute(
        'CREATE INDEX ix_document_chunks_company_id ON document_chunks (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_embeddings_vector_id ON embeddings (vector_id);'
    )
    op.execute(
        'CREATE INDEX ix_embeddings_company_id ON embeddings (company_id);'
    )
    op.execute(
        'CREATE INDEX ix_embeddings_deleted_at ON embeddings (deleted_at);'
    )
    op.execute(
        'CREATE TABLE messages_default PARTITION OF messages DEFAULT;'
    )
    op.execute(
        "CREATE TABLE messages_2026_06 PARTITION OF messages FOR VALUES FROM ('2026-06-01 00:00:00+00') TO ('2026-07-01 00:00:00+00');"
    )
    op.execute(
        "CREATE TABLE messages_2026_07 PARTITION OF messages FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');"
    )
    op.execute(
        "CREATE TABLE messages_2026_08 PARTITION OF messages FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');"
    )
    op.execute(
        'CREATE TABLE analytics_events_default PARTITION OF analytics_events DEFAULT;'
    )
    op.execute(
        "CREATE TABLE analytics_events_2026_06 PARTITION OF analytics_events FOR VALUES FROM ('2026-06-01 00:00:00+00') TO ('2026-07-01 00:00:00+00');"
    )
    op.execute(
        "CREATE TABLE analytics_events_2026_07 PARTITION OF analytics_events FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');"
    )
    op.execute(
        "CREATE TABLE analytics_events_2026_08 PARTITION OF analytics_events FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');"
    )
    op.execute(
        'CREATE TABLE activity_logs_default PARTITION OF activity_logs DEFAULT;'
    )
    op.execute(
        "CREATE TABLE activity_logs_2026_06 PARTITION OF activity_logs FOR VALUES FROM ('2026-06-01 00:00:00+00') TO ('2026-07-01 00:00:00+00');"
    )
    op.execute(
        "CREATE TABLE activity_logs_2026_07 PARTITION OF activity_logs FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');"
    )
    op.execute(
        "CREATE TABLE activity_logs_2026_08 PARTITION OF activity_logs FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');"
    )
    op.execute(
        'CREATE TRIGGER trg_companies_set_updated_at BEFORE UPDATE ON companies FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_permissions_set_updated_at BEFORE UPDATE ON permissions FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_users_set_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_api_keys_set_updated_at BEFORE UPDATE ON api_keys FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_chatbots_set_updated_at BEFORE UPDATE ON chatbots FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_roles_set_updated_at BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_subscriptions_set_updated_at BEFORE UPDATE ON subscriptions FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_analytics_daily_set_updated_at BEFORE UPDATE ON analytics_daily FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_company_members_set_updated_at BEFORE UPDATE ON company_members FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_conversations_set_updated_at BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_crawler_jobs_set_updated_at BEFORE UPDATE ON crawler_jobs FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_invoices_set_updated_at BEFORE UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_role_permissions_set_updated_at BEFORE UPDATE ON role_permissions FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_widget_configurations_set_updated_at BEFORE UPDATE ON widget_configurations FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_documents_set_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_leads_set_updated_at BEFORE UPDATE ON leads FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_document_chunks_set_updated_at BEFORE UPDATE ON document_chunks FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'CREATE TRIGGER trg_embeddings_set_updated_at BEFORE UPDATE ON embeddings FOR EACH ROW EXECUTE FUNCTION set_updated_at();'
    )
    op.execute(
        'ALTER TABLE companies ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE companies FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON companies USING (id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE activity_logs ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE activity_logs FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON activity_logs USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE api_keys FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON api_keys USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE chatbots ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE chatbots FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON chatbots USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE roles ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE roles FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON roles USING (company_id IS NULL OR company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON subscriptions USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE analytics_daily ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE analytics_daily FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON analytics_daily USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE analytics_events ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE analytics_events FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON analytics_events USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE company_members ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE company_members FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON company_members USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE conversations FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON conversations USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE crawler_jobs ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE crawler_jobs FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON crawler_jobs USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE invoices FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON invoices USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE widget_configurations ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE widget_configurations FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON widget_configurations USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE documents ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE documents FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON documents USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE leads ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE leads FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON leads USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE messages ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE messages FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON messages USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON document_chunks USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'ALTER TABLE embeddings ENABLE ROW LEVEL SECURITY;'
    )
    op.execute(
        'ALTER TABLE embeddings FORCE ROW LEVEL SECURITY;'
    )
    op.execute(
        "CREATE POLICY tenant_isolation ON embeddings USING (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.current_company', true), '')::uuid);"
    )
    op.execute(
        'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_rw;'
    )
    op.execute(
        'GRANT USAGE ON SCHEMA public TO app_rw;'
    )


def downgrade() -> None:
    op.execute(
        'DROP TABLE IF EXISTS embeddings CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS document_chunks CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS messages CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS leads CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS documents CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS widget_configurations CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS role_permissions CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS invoices CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS crawler_jobs CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS conversations CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS company_members CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS analytics_events CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS analytics_daily CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS subscriptions CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS roles CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS chatbots CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS api_keys CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS activity_logs CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS users CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS permissions CASCADE;'
    )
    op.execute(
        'DROP TABLE IF EXISTS companies CASCADE;'
    )
    op.execute(
        'DROP FUNCTION IF EXISTS set_updated_at();'
    )
    op.execute(
        'DROP TYPE IF EXISTS company_status;'
    )
    op.execute(
        'DROP TYPE IF EXISTS member_status;'
    )
    op.execute(
        'DROP TYPE IF EXISTS document_source_type;'
    )
    op.execute(
        'DROP TYPE IF EXISTS processing_status;'
    )
    op.execute(
        'DROP TYPE IF EXISTS chatbot_status;'
    )
    op.execute(
        'DROP TYPE IF EXISTS conversation_channel;'
    )
    op.execute(
        'DROP TYPE IF EXISTS conversation_status;'
    )
    op.execute(
        'DROP TYPE IF EXISTS message_role;'
    )
    op.execute(
        'DROP TYPE IF EXISTS lead_status;'
    )
    op.execute(
        'DROP TYPE IF EXISTS crawler_status;'
    )
    op.execute(
        'DROP TYPE IF EXISTS subscription_status;'
    )
    op.execute(
        'DROP TYPE IF EXISTS invoice_status;'
    )
    op.execute(
        'DROP TYPE IF EXISTS actor_type;'
    )
