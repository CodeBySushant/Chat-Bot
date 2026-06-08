"""Centralized enumerations.

These are mapped to native PostgreSQL ENUM types. Native enums give strong
in-database validation and compact storage. Adding a value later is a one-line
migration (``ALTER TYPE ... ADD VALUE``); renaming/removing requires a type
rebuild, so keep these sets stable.
"""
from __future__ import annotations

import enum


class CompanyStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class MemberStatus(str, enum.Enum):
    invited = "invited"
    active = "active"
    suspended = "suspended"


class DocumentSourceType(str, enum.Enum):
    upload = "upload"
    crawl = "crawl"
    url = "url"
    text = "text"


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class ChatbotStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ConversationChannel(str, enum.Enum):
    widget = "widget"
    api = "api"
    playground = "playground"


class ConversationStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class MessageRole(str, enum.Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    proposal = "proposal"
    converted = "converted"
    won = "won"
    lost = "lost"


class CrawlerStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class SubscriptionStatus(str, enum.Enum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    incomplete = "incomplete"


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    paid = "paid"
    void = "void"
    uncollectible = "uncollectible"


class ActorType(str, enum.Enum):
    user = "user"
    system = "system"
    api_key = "api_key"


class TokenPurpose(str, enum.Enum):
    email_verification = "email_verification"
    password_reset = "password_reset"


# Helper: (python_enum, pg_type_name) pairs used by migrations to create types.
PG_ENUMS: list[tuple[type[enum.Enum], str]] = [
    (CompanyStatus, "company_status"),
    (MemberStatus, "member_status"),
    (DocumentSourceType, "document_source_type"),
    (ProcessingStatus, "processing_status"),
    (ChatbotStatus, "chatbot_status"),
    (ConversationChannel, "conversation_channel"),
    (ConversationStatus, "conversation_status"),
    (MessageRole, "message_role"),
    (LeadStatus, "lead_status"),
    (CrawlerStatus, "crawler_status"),
    (SubscriptionStatus, "subscription_status"),
    (InvoiceStatus, "invoice_status"),
    (ActorType, "actor_type"),
]


# ---- Platform features (leads, billing, jobs) added in 0005/0006 ----
class LeadActivityType(str, enum.Enum):
    created = "created"
    status_changed = "status_changed"
    assigned = "assigned"
    note_added = "note_added"
    contacted = "contacted"
    field_updated = "field_updated"


class BillingInterval(str, enum.Enum):
    month = "month"
    year = "year"


class UsageMetric(str, enum.Enum):
    conversations = "conversations"
    messages = "messages"
    ai_tokens = "ai_tokens"
    documents = "documents"
    chatbots = "chatbots"
    leads = "leads"
    storage_bytes = "storage_bytes"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"       # will be retried
    dead = "dead"           # exhausted retries -> dead-letter
