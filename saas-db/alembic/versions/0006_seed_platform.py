"""seed platform: lead permissions + plans

Revision ID: 0006_seed_platform
Revises: 0005_platform
Create Date: 2026-06-08
"""
import json
from typing import Sequence, Union

from alembic import op

revision: str = "0006_seed_platform"
down_revision: Union[str, None] = "0005_platform"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OWNER_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_ID = "00000000-0000-0000-0000-000000000002"
MEMBER_ID = "00000000-0000-0000-0000-000000000003"

NEW_PERMS = [
    ("leads:create", "leads", "create", "Create leads"),
    ("leads:assign", "leads", "assign", "Assign leads to members"),
    ("leads:delete", "leads", "delete", "Delete leads"),
]
MEMBER_GETS = ("leads:create", "leads:assign")

U = -1  # unlimited
PLANS = [
    ("free", "Free", 0, 0, {"chatbots": 1, "documents": 50, "storage_bytes": 104857600,
        "monthly_conversations": 200, "monthly_messages": 1000, "ai_tokens": 100000, "leads": 100, "seats": 1}),
    ("starter", "Starter", 2900, 10, {"chatbots": 3, "documents": 500, "storage_bytes": 1073741824,
        "monthly_conversations": 2000, "monthly_messages": 10000, "ai_tokens": 1000000, "leads": 1000, "seats": 3}),
    ("pro", "Pro", 9900, 20, {"chatbots": 10, "documents": 5000, "storage_bytes": 10737418240,
        "monthly_conversations": 20000, "monthly_messages": 100000, "ai_tokens": 10000000, "leads": 10000, "seats": 10}),
    ("business", "Business", 29900, 30, {"chatbots": 50, "documents": 50000, "storage_bytes": 107374182400,
        "monthly_conversations": 200000, "monthly_messages": 1000000, "ai_tokens": 100000000, "leads": 100000, "seats": 50}),
    ("enterprise", "Enterprise", 0, 40, {"chatbots": U, "documents": U, "storage_bytes": U,
        "monthly_conversations": U, "monthly_messages": U, "ai_tokens": U, "leads": U, "seats": U}),
]


def upgrade() -> None:
    for code, resource, action, desc in NEW_PERMS:
        op.execute(
            "INSERT INTO permissions (code, resource, action, description) "
            f"VALUES ('{code}', '{resource}', '{action}', '{desc}') ON CONFLICT (code) DO NOTHING;"
        )
    # Owner + Admin get every new lead permission; Member gets create + assign.
    for rid in (OWNER_ID, ADMIN_ID):
        op.execute(
            "INSERT INTO role_permissions (role_id, permission_id) "
            f"SELECT '{rid}', id FROM permissions WHERE code IN ('leads:create','leads:assign','leads:delete') "
            "ON CONFLICT (role_id, permission_id) DO NOTHING;"
        )
    member_in = ", ".join(f"'{c}'" for c in MEMBER_GETS)
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id) "
        f"SELECT '{MEMBER_ID}', id FROM permissions WHERE code IN ({member_in}) "
        "ON CONFLICT (role_id, permission_id) DO NOTHING;"
    )

    for code, name, price, sort, ent in PLANS:
        ent_json = json.dumps(ent).replace("'", "''")
        op.execute(
            "INSERT INTO plans (code, name, price_cents, interval, entitlements, sort_order) "
            f"VALUES ('{code}', '{name}', {price}, 'month', '{ent_json}'::jsonb, {sort}) "
            "ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, price_cents=EXCLUDED.price_cents, "
            "entitlements=EXCLUDED.entitlements, sort_order=EXCLUDED.sort_order;"
        )


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE code IN ('free','starter','pro','business','enterprise');")
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code IN ('leads:create','leads:assign','leads:delete'));"
    )
    op.execute("DELETE FROM permissions WHERE code IN ('leads:create','leads:assign','leads:delete');")
