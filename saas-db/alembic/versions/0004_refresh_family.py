"""refresh token family lineage (family_id, rotated_from)

Revision ID: 0004_refresh_family
Revises: 0003_auth_tables
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_refresh_family"
down_revision: Union[str, None] = "0003_auth_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # family_id groups a refresh-token lineage (a login and all its rotations).
    # Backfill existing rows so each current session is its own family.
    op.execute("ALTER TABLE user_sessions ADD COLUMN family_id uuid;")
    op.execute("UPDATE user_sessions SET family_id = id WHERE family_id IS NULL;")
    op.execute("ALTER TABLE user_sessions ALTER COLUMN family_id SET NOT NULL;")
    op.execute(
        "ALTER TABLE user_sessions ADD COLUMN rotated_from uuid "
        "REFERENCES user_sessions (id) ON DELETE SET NULL;"
    )
    op.execute("CREATE INDEX ix_user_sessions_family_id ON user_sessions (family_id);")
    op.execute(
        "CREATE INDEX ix_user_sessions_family_active ON user_sessions (family_id) "
        "WHERE revoked_at IS NULL;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_sessions_family_active;")
    op.execute("DROP INDEX IF EXISTS ix_user_sessions_family_id;")
    op.execute("ALTER TABLE user_sessions DROP COLUMN IF EXISTS rotated_from;")
    op.execute("ALTER TABLE user_sessions DROP COLUMN IF EXISTS family_id;")
