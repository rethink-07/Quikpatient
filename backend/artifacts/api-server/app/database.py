from collections.abc import AsyncIterator

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.models import Base


def _async_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


engine = (
    create_async_engine(_async_url(settings.database_url), pool_pre_ping=True)
    if settings.database_url
    else None
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False) if engine else None


async def get_session() -> AsyncIterator[AsyncSession]:
    if SessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Database is not configured."},
        )
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def set_patient_rls(session: AsyncSession, patient_id: str) -> None:
    """Set the transaction-local tenant for PostgreSQL RLS policies."""
    await session.execute(
        text("SELECT set_config('app.patient_id', :patient_id, true)"),
        {"patient_id": patient_id},
    )


async def set_user_rls(session: AsyncSession, user_id: str) -> None:
    await session.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": user_id},
    )


async def create_schema_for_tests() -> None:
    """Explicit test helper only; production schema is managed by Alembic."""
    if engine is None:
        raise RuntimeError("DATABASE_URL is required to create the schema")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
