"""Pydantic v2 request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---- Auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class EmailVerifyRequest(BaseModel):
    email: EmailStr


class EmailVerifyConfirm(BaseModel):
    token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token lifetime in seconds


# ---- Users ----
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    email_verified_at: datetime | None
    created_at: datetime


class MembershipSummary(BaseModel):
    company_id: uuid.UUID
    company_name: str
    company_slug: str
    role_slug: str
    status: str


class MeResponse(BaseModel):
    user: UserResponse
    memberships: list[MembershipSummary]


# ---- Companies ----
class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_at: datetime


class MemberAddRequest(BaseModel):
    email: EmailStr
    role_slug: str = Field(pattern=r"^(owner|admin|member|viewer)$")


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: str | None
    role_slug: str
    status: str


class RoleContextResponse(BaseModel):
    company_id: uuid.UUID
    role_slug: str
    permissions: list[str]


# ---- Dev helper (only populated outside production) ----
class DevTokenResponse(BaseModel):
    detail: str
    dev_token: str | None = None


# ---- Chatbots ----
class ChatbotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")


class ChatbotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    public_key: str
    created_at: datetime

    @field_validator("status", mode="before")
    @classmethod
    def _enum_value(cls, v):
        return v.value if hasattr(v, "value") else v


# ---- Documents ----
class DocumentResponse(BaseModel):
    id: uuid.UUID
    chatbot_id: uuid.UUID
    title: str | None
    source_type: str
    mime_type: str | None
    file_size: int | None
    status: str
    token_count: int
    chunk_count: int
    error: str | None
    created_at: datetime


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None
    token_count: int
    char_count: int


# ---- Search ----
class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    score: float
    chunk_id: str | None
    document_id: str | None
    chunk_index: int | None
    text: str | None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


# ---- Crawler ----
class CrawlCreate(BaseModel):
    start_url: str = Field(min_length=8, max_length=2048)
    mode: str = Field(default="crawl", pattern=r"^(crawl|sitemap)$")
    max_pages: int = Field(default=50, ge=1, le=500)
    max_depth: int = Field(default=3, ge=0, le=10)
    same_domain_only: bool = True


class CrawlJobResponse(BaseModel):
    id: uuid.UUID
    chatbot_id: uuid.UUID
    start_url: str
    status: str
    mode: str
    pages_discovered: int
    pages_processed: int
    pages_failed: int
    error: str | None
    created_at: datetime

    @classmethod
    def from_job(cls, job) -> "CrawlJobResponse":
        return cls(
            id=job.id,
            chatbot_id=job.chatbot_id,
            start_url=job.start_url,
            status=job.status.value if hasattr(job.status, "value") else job.status,
            mode=(job.config or {}).get("mode", "crawl"),
            pages_discovered=job.pages_discovered,
            pages_processed=job.pages_processed,
            pages_failed=job.pages_failed,
            error=job.error,
            created_at=job.created_at,
        )


# ---- RAG / Chat ----
class ConversationCreate(BaseModel):
    channel: str = Field(default="api", pattern=r"^(api|widget|playground)$")
    visitor_id: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=512)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chatbot_id: uuid.UUID
    channel: str
    status: str
    title: str | None
    message_count: int
    started_at: datetime

    @field_validator("channel", "status", mode="before")
    @classmethod
    def _enum_val(cls, v):
        return v.value if hasattr(v, "value") else v


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    top_k: int | None = Field(default=None, ge=1, le=50)


class SourceRef(BaseModel):
    document_id: str | None
    chunk_id: str | None
    chunk_index: int | None
    title: str | None
    source_uri: str | None
    page_number: int | None
    score: float
    snippet: str | None


class AnswerResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    sources: list[SourceRef]


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list
    created_at: datetime

    @field_validator("role", mode="before")
    @classmethod
    def _role_val(cls, v):
        return v.value if hasattr(v, "value") else v


# ---- Leads (CRM) ----
class LeadCreate(BaseModel):
    chatbot_id: uuid.UUID
    name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    company: str | None = Field(default=None, max_length=255)
    source: str = Field(default="manual", max_length=128)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class LeadUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    status: str | None = Field(default=None, pattern=r"^(new|contacted|qualified|proposal|converted|won|lost)$")
    tags: list[str] | None = None
    metadata: dict | None = None


class LeadAssign(BaseModel):
    assignee_id: uuid.UUID | None = None


class LeadNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    chatbot_id: uuid.UUID
    conversation_id: uuid.UUID | None
    name: str | None
    email: str | None
    phone: str | None
    company: str | None
    status: str
    source: str | None
    tags: list
    assigned_to: uuid.UUID | None
    captured_at: datetime

    @field_validator("status", mode="before")
    @classmethod
    def _st(cls, v):
        return v.value if hasattr(v, "value") else v


class LeadListResponse(BaseModel):
    total: int
    items: list[LeadResponse]


# ---- Billing ----
class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    price_cents: int
    interval: str
    entitlements: dict


class ChangePlanRequest(BaseModel):
    plan_code: str = Field(pattern=r"^(free|starter|pro|business|enterprise)$")


class SubscriptionResponse(BaseModel):
    plan_code: str
    status: str
    entitlements: dict
    usage: dict
    current_period_end: datetime | None


# ---- Admin ----
class TenantStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(active|suspended)$")
