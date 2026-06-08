"""Import every model so ``Base.metadata`` is complete for Alembic."""
from app.db.base import Base  # noqa: F401
from app.models.analytics import (  # noqa: F401
    ActivityLog,
    AnalyticsDaily,
    AnalyticsEvent,
)
from app.models.auth import UserSession, VerificationToken  # noqa: F401
from app.models.billing import ApiKey, Invoice, Subscription  # noqa: F401
from app.models.bots import Chatbot, WidgetConfiguration  # noqa: F401
from app.models.chat import Conversation, Lead, Message  # noqa: F401
from app.models.knowledge import (  # noqa: F401
    CrawlerJob,
    Document,
    DocumentChunk,
    Embedding,
)
from app.models.tenancy import (  # noqa: F401
    Company,
    CompanyMember,
    Permission,
    Role,
    RolePermission,
    User,
)

__all__ = [
    "Base",
    "User",
    "Company",
    "CompanyMember",
    "Role",
    "Permission",
    "RolePermission",
    "Chatbot",
    "WidgetConfiguration",
    "CrawlerJob",
    "Document",
    "DocumentChunk",
    "Embedding",
    "Conversation",
    "Message",
    "Lead",
    "AnalyticsEvent",
    "AnalyticsDaily",
    "ActivityLog",
    "Subscription",
    "Invoice",
    "ApiKey",
    "UserSession",
    "VerificationToken",
]
from app.models.crm import LeadActivity, LeadNote  # noqa: E402,F401
from app.models.jobs import Job  # noqa: E402,F401
from app.models.billing import Plan, UsageCounter, UsageRecord  # noqa: E402,F401
