"""seed rbac (global permissions + system roles)

Revision ID: 0002_seed_rbac
Revises: 0001_initial_schema
Create Date: 2026-06-08

Seeds the global permission catalog and the four system roles (owner, admin,
member, viewer) with their permission grants. Runs under the migration role,
which bypasses RLS, so the company-less system roles insert cleanly.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_seed_rbac"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (code, resource, action, description)
PERMISSIONS = [
    ("bots:create", "bots", "create", "Create chatbots"),
    ("bots:read", "bots", "read", "View chatbots"),
    ("bots:update", "bots", "update", "Edit chatbots"),
    ("bots:delete", "bots", "delete", "Delete chatbots"),
    ("documents:create", "documents", "create", "Upload/ingest documents"),
    ("documents:read", "documents", "read", "View documents"),
    ("documents:delete", "documents", "delete", "Delete documents"),
    ("conversations:read", "conversations", "read", "View conversations"),
    ("leads:read", "leads", "read", "View leads"),
    ("leads:update", "leads", "update", "Edit leads"),
    ("leads:export", "leads", "export", "Export leads"),
    ("analytics:read", "analytics", "read", "View analytics"),
    ("members:invite", "members", "invite", "Invite members"),
    ("members:update", "members", "update", "Update members"),
    ("members:remove", "members", "remove", "Remove members"),
    ("roles:manage", "roles", "manage", "Manage roles"),
    ("billing:read", "billing", "read", "View billing"),
    ("billing:manage", "billing", "manage", "Manage billing"),
    ("apikeys:manage", "apikeys", "manage", "Manage API keys"),
    ("settings:manage", "settings", "manage", "Manage company settings"),
]

ROLES = [
    ("00000000-0000-0000-0000-000000000001", "Owner", "owner", "Full access including billing"),
    ("00000000-0000-0000-0000-000000000002", "Admin", "admin", "Full access except billing management"),
    ("00000000-0000-0000-0000-000000000003", "Member", "member", "Day-to-day operational access"),
    ("00000000-0000-0000-0000-000000000004", "Viewer", "viewer", "Read-only access"),
]

OWNER_ID, ADMIN_ID, MEMBER_ID, VIEWER_ID = (r[0] for r in ROLES)

MEMBER_CODES = (
    "bots:create", "bots:read", "bots:update",
    "documents:create", "documents:read", "documents:delete",
    "conversations:read", "leads:read", "leads:update", "leads:export",
    "analytics:read",
)
ADMIN_EXCLUDE = ("billing:manage",)


def upgrade() -> None:
    for code, resource, action, desc in PERMISSIONS:
        op.execute(
            "INSERT INTO permissions (code, resource, action, description) "
            f"VALUES ('{code}', '{resource}', '{action}', '{desc}') "
            "ON CONFLICT (code) DO NOTHING;"
        )
    for rid, name, slug, desc in ROLES:
        op.execute(
            "INSERT INTO roles (id, company_id, name, slug, description, is_system) "
            f"VALUES ('{rid}', NULL, '{name}', '{slug}', '{desc}', true) "
            "ON CONFLICT DO NOTHING;"
        )

    # Owner: every permission.
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id) "
        f"SELECT '{OWNER_ID}', id FROM permissions "
        "ON CONFLICT (role_id, permission_id) DO NOTHING;"
    )
    # Admin: everything except billing management.
    admin_not = ", ".join(f"'{c}'" for c in ADMIN_EXCLUDE)
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id) "
        f"SELECT '{ADMIN_ID}', id FROM permissions WHERE code NOT IN ({admin_not}) "
        "ON CONFLICT (role_id, permission_id) DO NOTHING;"
    )
    # Member: operational subset.
    member_in = ", ".join(f"'{c}'" for c in MEMBER_CODES)
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id) "
        f"SELECT '{MEMBER_ID}', id FROM permissions WHERE code IN ({member_in}) "
        "ON CONFLICT (role_id, permission_id) DO NOTHING;"
    )
    # Viewer: all read permissions.
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id) "
        f"SELECT '{VIEWER_ID}', id FROM permissions WHERE action = 'read' "
        "ON CONFLICT (role_id, permission_id) DO NOTHING;"
    )


def downgrade() -> None:
    role_ids = ", ".join(f"'{r[0]}'" for r in ROLES)
    op.execute(f"DELETE FROM role_permissions WHERE role_id IN ({role_ids});")
    op.execute(f"DELETE FROM roles WHERE id IN ({role_ids});")
    codes = ", ".join(f"'{p[0]}'" for p in PERMISSIONS)
    op.execute(f"DELETE FROM permissions WHERE code IN ({codes});")
