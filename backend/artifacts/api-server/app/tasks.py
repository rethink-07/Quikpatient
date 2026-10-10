import asyncio
from datetime import UTC, datetime

from celery.utils.log import get_task_logger
from sqlalchemy import delete, func, select

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models import AuditAnchor, AuditLog, Consent, ConsentKey, SosEvent


async def _expire_sos() -> int:
    if SessionLocal is None:
        return 0
    async with SessionLocal() as db:
        now = datetime.now(UTC)
        events = list(
            (
                await db.scalars(
                    select(SosEvent).where(
                        SosEvent.status.in_(["INITIATED", "NOTIFIED", "APPROVED"]),
                        SosEvent.expires_at <= now,
                    )
                )
            ).all()
        )
        for event in events:
            previous_status = event.status
            event.status = "EXPIRED"
            if previous_status == "APPROVED":
                consent_ids = select(Consent.id).where(
                    Consent.sos_event_id == event.id,
                    Consent.legal_basis == "NOMINEE_EMERGENCY",
                )
                await db.execute(
                    delete(ConsentKey).where(ConsentKey.consent_id.in_(consent_ids))
                )
        await db.commit()
        return len(events)


@celery_app.task(name="app.tasks.expire_sos")
def expire_sos() -> int:
    return asyncio.run(_expire_sos())


async def _anchor_audit_chain() -> int:
    if SessionLocal is None:
        return 0
    async with SessionLocal() as db:
        result = await db.execute(
            select(AuditLog.entry_hash, AuditLog.ts)
            .order_by(AuditLog.ts.desc(), AuditLog.id.desc())
            .limit(1)
        )
        head = result.first()
        if head is None:
            return 0
        count = await db.scalar(select(func.count()).select_from(AuditLog))
        db.add(
            AuditAnchor(
                chain_head_hash=head[0],
                entry_count=int(count or 0),
                anchored_at=datetime.now(UTC),
            )
        )
        await db.commit()
        return int(count or 0)


@celery_app.task(name="app.tasks.anchor_audit_chain")
def anchor_audit_chain() -> int:
    return asyncio.run(_anchor_audit_chain())


@celery_app.task(name="app.tasks.process_ingestion_job")
def process_ingestion_job(job_id: str) -> dict:
    """Dispatch point for workers; unsupported provider jobs fail explicitly."""
    if settings.mock_mode:
        return {"job_id": job_id, "status": "needs_fixture_or_client_payload"}
    return {"job_id": job_id, "status": "provider_not_configured"}
