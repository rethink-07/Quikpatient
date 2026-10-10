import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import canonical_json
from app.models import AuditLog, AuditAnchor


def _audit_signing_key() -> bytes:
    # A separate, domain-separated key is derived for service-originated signatures.
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"quikpatient/audit-signature/v1",
    ).derive(settings.session_secret.get_secret_value().encode("utf-8"))


def _entry_data(row: AuditLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "patient_id": str(row.patient_id) if row.patient_id else None,
        "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
        "actor_role": row.actor_role,
        "action": row.action,
        "object_type": row.object_type,
        "object_id": row.object_id,
        "scope": row.scope,
        "legal_basis": row.legal_basis,
        "severity": row.severity,
        "ts": row.ts.astimezone(UTC).isoformat(),
        "prev_hash": row.prev_hash,
    }


async def append_audit(
    db: AsyncSession,
    *,
    patient_id: UUID | None,
    actor_user_id: UUID | None,
    actor_role: str,
    action: str,
    object_type: str,
    object_id: str | None = None,
    scope: dict | None = None,
    legal_basis: str | None = None,
    severity: str = "info",
    ip: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    await db.execute(text("SELECT pg_advisory_xact_lock(721144203)"))
    previous = await db.scalar(
        select(AuditLog).order_by(AuditLog.ts.desc(), AuditLog.id.desc()).limit(1)
    )
    previous_hash = previous.entry_hash if previous else "0" * 64
    row = AuditLog(
        patient_id=patient_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        object_type=object_type,
        object_id=object_id,
        scope=scope,
        legal_basis=legal_basis,
        severity=severity,
        ip=ip,
        user_agent=user_agent,
        ts=datetime.now(UTC),
        prev_hash=previous_hash,
        entry_hash="pending",
        actor_signature=b"",
    )
    db.add(row)
    await db.flush()
    entry_bytes = canonical_json(_entry_data(row))
    row.entry_hash = hashlib.sha256(bytes.fromhex(previous_hash) + entry_bytes).hexdigest()
    from nacl.signing import SigningKey

    row.actor_signature = bytes(SigningKey(_audit_signing_key()).sign(bytes.fromhex(row.entry_hash)).signature)
    await db.flush()
    return row


async def verify_audit_chain(db: AsyncSession) -> dict[str, Any]:
    from nacl.exceptions import BadSignatureError
    from nacl.signing import SigningKey

    rows = list(
        (
            await db.scalars(
                select(AuditLog).order_by(AuditLog.ts.asc(), AuditLog.id.asc())
            )
        ).all()
    )
    expected_prev = "0" * 64
    verify_key = SigningKey(_audit_signing_key()).verify_key
    for row in rows:
        if row.prev_hash != expected_prev:
            return {"valid": False, "checked": len(rows), "failed_entry": str(row.id)}
        expected = hashlib.sha256(
            bytes.fromhex(expected_prev) + canonical_json(_entry_data(row))
        ).hexdigest()
        if expected != row.entry_hash:
            return {"valid": False, "checked": len(rows), "failed_entry": str(row.id)}
        try:
            verify_key.verify(bytes.fromhex(row.entry_hash), row.actor_signature)
        except BadSignatureError:
            return {"valid": False, "checked": len(rows), "failed_entry": str(row.id)}
        expected_prev = row.entry_hash

    anchor = await db.scalar(
        select(AuditAnchor).order_by(AuditAnchor.anchored_at.desc()).limit(1)
    )
    anchored_row = next((row for row in rows if row.entry_hash == anchor.chain_head_hash), None) if anchor else None
    if anchor and (
        anchored_row is None
        or rows.index(anchored_row) + 1 != anchor.entry_count
    ):
        return {"valid": False, "checked": len(rows), "failed_entry": "anchor_mismatch"}
    return {
        "valid": True,
        "checked": len(rows),
        "head": expected_prev if rows else "0" * 64,
    }
