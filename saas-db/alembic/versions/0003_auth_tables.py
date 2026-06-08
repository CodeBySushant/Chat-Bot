"""auth tables (user_sessions, verification_tokens)

Revision ID: 0003_auth_tables
Revises: 0002_seed_rbac
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_auth_tables"
down_revision: Union[str, None] = "0002_seed_rbac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE token_purpose AS ENUM ('email_verification', 'password_reset');")

    op.execute(
        """
        CREATE TABLE user_sessions (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            token_hash varchar(64) NOT NULL,
            user_agent varchar(512),
            ip_address inet,
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz,
            last_used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_user_sessions PRIMARY KEY (id),
            CONSTRAINT uq_user_sessions_token_hash UNIQUE (token_hash),
            CONSTRAINT fk_user_sessions_user_id_users
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """
    )
    op.execute("CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);")
    op.execute(
        "CREATE INDEX ix_user_sessions_user_active ON user_sessions (user_id) "
        "WHERE revoked_at IS NULL;"
    )

    op.execute(
        """
        CREATE TABLE verification_tokens (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            purpose token_purpose NOT NULL,
            token_hash varchar(64) NOT NULL,
            expires_at timestamptz NOT NULL,
            consumed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_verification_tokens PRIMARY KEY (id),
            CONSTRAINT uq_verification_tokens_token_hash UNIQUE (token_hash),
            CONSTRAINT fk_verification_tokens_user_id_users
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """
    )
    op.execute(
        "CREATE INDEX ix_verification_tokens_user_id ON verification_tokens (user_id);"
    )
    op.execute(
        "CREATE INDEX ix_verification_tokens_user_purpose "
        "ON verification_tokens (user_id, purpose);"
    )

    # These are global tables (no RLS); grant DML to the application role.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON user_sessions, verification_tokens "
        "TO app_rw;"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS verification_tokens CASCADE;")
    op.execute("DROP TABLE IF EXISTS user_sessions CASCADE;")
    op.execute("DROP TYPE IF EXISTS token_purpose;")
