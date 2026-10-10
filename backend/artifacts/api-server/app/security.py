import re
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select, and_, or_

from app.models import Record, RecordType

EMERGENCY_VISIBLE_TYPES = {
    RecordType.diagnostic_report,
    RecordType.discharge_summary,
    RecordType.diagnosis,
}
ALLOWED_SOS_TEMPLATE_FIELDS = {
    "doctor_name",
    "nmc_reg_no",
    "facility_name",
    "reason",
    "one_time_link",
    "otp",
}


def assert_non_emergency_write(encounter_mode: str | None) -> None:
    if encounter_mode == "EMERGENCY":
        raise HTTPException(
            status_code=403,
            detail={"code": "emergency_session_read_only"},
        )


def apply_record_scope(
    query: Select,
    *,
    patient_id: str,
    allowed_types: list[str],
    scope_from: date | None,
    scope_to: date | None,
    expires_at: datetime,
    emergency: bool = False,
) -> Select:
    """Build record filters exclusively from server-verified consent/session state."""
    if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
        return query.where(False)
    type_values = set(allowed_types)
    if emergency:
        type_values &= {record_type.value for record_type in EMERGENCY_VISIBLE_TYPES}
    if not type_values:
        return query.where(False)
    criteria: list[Any] = [
        Record.patient_id == patient_id,
        Record.type.in_(type_values),
        Record.soft_deleted_at.is_(None),
    ]
    if scope_from:
        criteria.append(Record.record_date >= scope_from)
    if scope_to:
        criteria.append(Record.record_date <= scope_to)
    return query.where(and_(*criteria))


def validate_outbound_template(payload: dict[str, str]) -> None:
    """Only approved SOS template fields may leave the service; PHI fields fail closed."""
    extra = set(payload) - ALLOWED_SOS_TEMPLATE_FIELDS
    if extra:
        raise ValueError("Outbound message contains a non-approved field")
    for key, value in payload.items():
        if not isinstance(value, str) or len(value) > 500:
            raise ValueError("Outbound message field is invalid")
        if re.search(r"(?i)\b(patient|diagnosis|medication|abha|dob|address)\b", value):
            raise ValueError("Outbound message may contain patient health information")
