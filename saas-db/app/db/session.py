"""Async engines and session helpers.

Two engines back the two database roles:
  * ``engine`` / ``SessionFactory``       -> app_rw, subject to RLS.
  * ``admin_engine`` / ``AdminSessionFactory`` -> app_admin, BYPASSRLS, used only
    for pre-tenant bootstrap (registration, login lookup, company creation,
    "list my organizations").

RLS policies read ``current_setting('app.current_company')``; ``tenant_session``
sets it with ``SET LOCAL`` so it is scoped to the transaction and cannot leak
across pooled connections.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=settings.SQL_ECHO,
)
admin_engine = create_async_engine(
    settings.DATABASE_ADMIN_URL,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    echo=settings.SQL_ECHO,
)

SessionFactory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
AdminSessionFactory = async_sessionmaker(
    bind=admin_engine, expire_on_commit=False, autoflush=False
)


@asynccontextmanager
async def tenant_session(company_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """app_rw session with RLS tenant context set for the transaction."""
    async with SessionFactory() as session:
        await session.execute(
            text("SELECT set_config('app.current_company', :cid, true)"),
            {"cid": str(company_id)},
        )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def global_session() -> AsyncIterator[AsyncSession]:
    """app_rw session with no tenant context (for RLS-free global tables)."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def admin_session() -> AsyncIterator[AsyncSession]:
    """BYPASSRLS session for bootstrap/platform operations."""
    async with AdminSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engines() -> None:
    await engine.dispose()
    await admin_engine.dispose()
