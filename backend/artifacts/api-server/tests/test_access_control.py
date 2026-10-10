from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import Record
from app.security import apply_record_scope, assert_non_emergency_write


def test_expired_scope_fails_closed():
    statement = apply_record_scope(
        select(Record),
        patient_id="00000000-0000-0000-0000-000000000001",
        allowed_types=["diagnosis"],
        scope_from=None,
        scope_to=None,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert "false" in str(statement.compile(dialect=postgresql.dialect())).lower()


def test_record_query_uses_server_scope_and_emergency_allowlist():
    statement = apply_record_scope(
        select(Record),
        patient_id="00000000-0000-0000-0000-000000000001",
        allowed_types=["diagnosis", "prescription"],
        scope_from=date(2025, 1, 1),
        scope_to=date(2025, 12, 31),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        emergency=True,
    )
    rendered = str(statement.compile(dialect=postgresql.dialect()))
    assert "patient_id" in rendered
    assert "record_date" in rendered
    assert "diagnosis" in rendered
    assert "prescription" not in rendered


def test_emergency_encounter_rejects_writes():
    try:
        assert_non_emergency_write("EMERGENCY")
    except HTTPException as error:
        assert error.status_code == 403
        assert error.detail["code"] == "emergency_session_read_only"
    else:
        raise AssertionError("Emergency-mode writes must be rejected")
