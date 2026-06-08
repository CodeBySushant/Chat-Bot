"""Knowledge-base models: crawler jobs, documents, chunks, and embedding refs.

PostgreSQL is the system of record for *what* was ingested. The actual vectors
live in Qdrant; ``Embedding`` rows hold the link (Qdrant point id + collection)
plus provider/model/dimension metadata so re-embedding and cleanup are exact.
"""
from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.db.enums import CrawlerStatus, DocumentSourceType, ProcessingStatus


class CrawlerJob(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """A website crawl that produces documents for a chatbot."""

    __tablename__ = "crawler_jobs"

    chatbot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[CrawlerStatus] = mapped_column(
        PgEnum(CrawlerStatus, name="crawler_status", create_type=False),
        nullable=False,
        server_default=CrawlerStatus.queued.value,
    )
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    pages_discovered: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    pages_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    pages_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_crawler_jobs_company_status", "company_id", "status"),
    )


class Document(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """A single ingested unit (uploaded file, crawled page, URL, or raw text)."""

    __tablename__ = "documents"

    chatbot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    crawler_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawler_jobs.id", ondelete="SET NULL"),
        index=True,
    )
    source_type: Mapped[DocumentSourceType] = mapped_column(
        PgEnum(DocumentSourceType, name="document_source_type", create_type=False),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(1024))
    source_uri: Mapped[str | None] = mapped_column(String(2048))
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[ProcessingStatus] = mapped_column(
        PgEnum(ProcessingStatus, name="processing_status", create_type=False),
        nullable=False,
        server_default=ProcessingStatus.pending.value,
    )
    error: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_documents_chatbot_status", "chatbot_id", "status"),
    )


class DocumentChunk(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """A retrievable slice of a document."""

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    token_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    char_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    page_number: Mapped[int | None] = mapped_column(Integer)
    heading_path: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")
    embedding: Mapped["Embedding | None"] = relationship(
        back_populates="chunk", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="chunk_position"),
    )


class Embedding(
    UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base
):
    """Reference linking a chunk to its vector in Qdrant (1:1 with chunk)."""

    __tablename__ = "embeddings"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    collection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    vector_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ProcessingStatus] = mapped_column(
        PgEnum(ProcessingStatus, name="processing_status", create_type=False),
        nullable=False,
        server_default=ProcessingStatus.pending.value,
    )

    chunk: Mapped["DocumentChunk"] = relationship(back_populates="embedding")

    __table_args__ = (
        UniqueConstraint("chunk_id", name="one_embedding_per_chunk"),
        Index("ix_embeddings_vector_id", "vector_id"),
    )
