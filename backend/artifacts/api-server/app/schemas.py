from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


class TotpRequest(BaseModel):
    challenge_token: str = Field(min_length=20, max_length=4096)
    code: str = Field(pattern=r"^\d{6}$")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class PatientPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dob: date | None = None
    sex: str | None = Field(default=None, max_length=32)
    blood_group: str | None = Field(default=None, max_length=8)
    height_cm: float | None = Field(default=None, ge=20, le=300)
    weight_kg: float | None = Field(default=None, ge=1, le=700)
    emergency_contact: dict[str, Any] | None = None
    allergies: list[str] | None = Field(default=None, max_length=100)
    chronic_conditions: list[str] | None = Field(default=None, max_length=100)


class ConsentCreate(BaseModel):
    doctor_id: UUID
    encounter_id: UUID | None = None
    kind: str = Field(pattern=r"^(DOCTOR_GRANT|ABDM_ARTEFACT)$")
    scope_types: list[str] = Field(min_length=1, max_length=20)
    scope_from: date | None = None
    scope_to: date | None = None
    expires_at: str


class PrescriptionCreate(BaseModel):
    record_id: UUID
    patient_id: UUID
    encounter_id: UUID
    record_date: date
    ciphertext: str = Field(min_length=16, max_length=2_000_000)
    nonce: str = Field(min_length=16, max_length=128)
    aad: str = Field(min_length=1, max_length=512)
    wrapped_dek: str = Field(min_length=16, max_length=2048)
    key_version: int = Field(ge=1)


class SosInitiateRequest(BaseModel):
    patient_id: UUID
    identity_method: str = Field(min_length=1, max_length=32)
    declared_reason_code: str = Field(pattern=r"^(unconscious|trauma|cardiac|respiratory|other)$")
    declared_reason_text: str = Field(min_length=3, max_length=500)


class ConsentKeyGrant(BaseModel):
    consent_id: UUID
    record_id: UUID
    dek_sealed_to_doctor: str = Field(min_length=32, max_length=4096)
    key_version: int = Field(ge=1)


class AccessRequestCreate(BaseModel):
    patient_id: UUID
    requested_from: date | None = None
    requested_to: date | None = None
    types: list[str] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=3, max_length=1000)
    requested_duration: int = Field(ge=1, le=24 * 60)


class EncounterCreate(BaseModel):
    patient_id: UUID
    consent_id: UUID


class AccessDecision(BaseModel):
    decision: str = Field(pattern=r"^(approved|denied)$")


class DoctorVerificationRequest(BaseModel):
    reg_no: str = Field(min_length=2, max_length=100)
    council: str = Field(min_length=2, max_length=200)


class SosResponseRequest(BaseModel):
    signed_token: str = Field(min_length=20, max_length=4096)
    otp: str = Field(pattern=r"^\d{6}$")
    response: str = Field(pattern=r"^(APPROVED|DENIED)$")


class SosReportRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
