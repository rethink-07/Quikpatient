import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"
    nominee = "nominee"
    guardian = "guardian"


class RecordType(str, enum.Enum):
    prescription = "prescription"
    diagnostic_report = "diagnostic_report"
    op_consultation = "op_consultation"
    discharge_summary = "discharge_summary"
    immunization = "immunization"
    scan = "scan"
    vitals = "vitals"
    diagnosis = "diagnosis"
    treatment = "treatment"


class RecordSource(str, enum.Enum):
    ABDM_HIU = "ABDM_HIU"
    PROVIDER_DIRECT = "PROVIDER_DIRECT"
    SELF_REPORTED = "SELF_REPORTED"


class Verification(str, enum.Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False)
    login_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    totp_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    public_signing_key: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encounters.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    abha_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    abha_address: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dob: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(32))
    blood_group: Mapped[str | None] = mapped_column(String(8))
    height_cm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    emergency_contact: Mapped[dict | None] = mapped_column(JSONB)
    allergies: Mapped[list | None] = mapped_column(JSONB)
    chronic_conditions: Mapped[list | None] = mapped_column(JSONB)
    general_info_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_minor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Guardian(Base):
    __tablename__ = "guardians"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    relationship: Mapped[str] = mapped_column(String(80))
    legal_authority: Mapped[str | None] = mapped_column(String(200))
    may_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    hfr_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    address: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Doctor(Base):
    __tablename__ = "doctors"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    nmc_reg_no: Mapped[str] = mapped_column(String(100), index=True)
    council: Mapped[str] = mapped_column(String(200))
    specialty: Mapped[str | None] = mapped_column(String(120))
    facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_payload: Mapped[dict | None] = mapped_column(JSONB)
    public_key: Mapped[bytes | None] = mapped_column(LargeBinary)
    enc_private_key: Mapped[bytes | None] = mapped_column(LargeBinary)
    sos_suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Nominee(Base):
    __tablename__ = "nominees"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    relationship: Mapped[str | None] = mapped_column(String(80))
    phone_e164: Mapped[str | None] = mapped_column(String(24))
    email: Mapped[str | None] = mapped_column(String(255))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    may_approve_emergency: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    push_token: Mapped[str | None] = mapped_column(Text)
    last_delivery_status: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PatientKey(Base):
    __tablename__ = "patient_keys"
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), primary_key=True)
    kdf_salt: Mapped[bytes] = mapped_column(LargeBinary)
    wrapped_master_key: Mapped[bytes] = mapped_column(LargeBinary)
    recovery_wrapped_master_key: Mapped[bytes] = mapped_column(LargeBinary)
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    enc_private_key: Mapped[bytes] = mapped_column(LargeBinary)
    search_key_wrapped: Mapped[bytes] = mapped_column(LargeBinary)
    eak_share_a_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Encounter(Base):
    __tablename__ = "encounters"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("doctors.id"))
    facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"))
    mode: Mapped[str] = mapped_column(String(16), default="CONSENTED")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    general_info_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(Text)


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doctors.id"))
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encounters.id"))
    sos_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sos_events.id"))
    kind: Mapped[str] = mapped_column(String(32))
    legal_basis: Mapped[str] = mapped_column(String(32))
    scope_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    scope_from: Mapped[date | None] = mapped_column(Date)
    scope_to: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="active")
    revoke_mode: Mapped[str | None] = mapped_column(String(8))
    abdm_consent_id: Mapped[str | None] = mapped_column(String(128))
    artefact: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Record(Base):
    __tablename__ = "records"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encounters.id"))
    type: Mapped[RecordType] = mapped_column(Enum(RecordType, name="record_type"), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[RecordSource] = mapped_column(Enum(RecordSource, name="record_source"), nullable=False)
    verification: Mapped[Verification] = mapped_column(Enum(Verification, name="verification"), nullable=False)
    corroborated_by_record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    merged_into_record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    attested_by_doctor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("doctors.id"))
    fhir_resource_type: Mapped[str | None] = mapped_column(String(80))
    raw_bundle_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    aad: Mapped[bytes] = mapped_column(LargeBinary)
    wrapped_dek: Mapped[bytes] = mapped_column(LargeBinary)
    blob_key: Mapped[str | None] = mapped_column(String(512))
    search_tokens: Mapped[list[bytes] | None] = mapped_column(ARRAY(LargeBinary))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    soft_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Medication(Base):
    __tablename__ = "medications"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("records.id"))
    prescribed_by_doctor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("doctors.id"))
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str | None] = mapped_column(String(200), index=True)
    code: Mapped[str | None] = mapped_column(String(100))
    dose: Mapped[str | None] = mapped_column(String(120))
    frequency: Mapped[str | None] = mapped_column(String(120))
    route: Mapped[str | None] = mapped_column(String(80))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active")
    stop_reason: Mapped[str | None] = mapped_column(Text)
    stopped_by_doctor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("doctors.id"))
    amends_medication_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    source: Mapped[RecordSource] = mapped_column(Enum(RecordSource, name="medication_source"))
    verification: Mapped[Verification] = mapped_column(Enum(Verification, name="medication_verification"))
    confirmed_with_patient: Mapped[bool] = mapped_column(Boolean, default=False)


class Treatment(Base):
    __tablename__ = "treatments"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("records.id"))
    name: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    amends_treatment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class ConsentKey(Base):
    __tablename__ = "consent_keys"
    consent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("consents.id"), primary_key=True)
    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("records.id"), primary_key=True)
    dek_sealed_to_doctor: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(Integer)


class AccessRequest(Base):
    __tablename__ = "access_requests"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doctors.id"))
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    requested_from: Mapped[date | None] = mapped_column(Date)
    requested_to: Mapped[date | None] = mapped_column(Date)
    types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    reason: Mapped[str] = mapped_column(Text)
    requested_duration: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending")


class SosEvent(Base):
    __tablename__ = "sos_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doctors.id"))
    facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"))
    identity_method: Mapped[str] = mapped_column(String(32))
    identity_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    declared_reason_code: Mapped[str] = mapped_column(String(40))
    declared_reason_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="INITIATED")
    legal_basis: Mapped[str | None] = mapped_column(String(32))
    approved_by_nominee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nominees.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scope_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    terminated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SosNotification(Base):
    __tablename__ = "sos_notifications"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    sos_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sos_events.id"), index=True)
    nominee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nominees.id"))
    channel: Mapped[str] = mapped_column(String(16))
    otp_hash: Mapped[str | None] = mapped_column(String(128))
    link_token_hash: Mapped[str | None] = mapped_column(String(64))
    attempt_no: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response: Mapped[str | None] = mapped_column(String(16))


class AbuseFlag(Base):
    __tablename__ = "abuse_flags"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    subject_doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doctors.id"))
    reported_by_patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"))
    sos_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sos_events.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(100))
    object_type: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[str | None] = mapped_column(String(80))
    scope: Mapped[dict | None] = mapped_column(JSONB)
    legal_basis: Mapped[str | None] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8), default="info")
    ip: Mapped[str | None] = mapped_column(String(48))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)
    actor_signature: Mapped[bytes] = mapped_column(LargeBinary)


class AuditAnchor(Base):
    __tablename__ = "audit_anchors"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    chain_head_hash: Mapped[str] = mapped_column(String(64))
    entry_count: Mapped[int] = mapped_column(Integer)
    anchored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetentionPolicy(Base):
    __tablename__ = "retention_policies"
    entity: Mapped[str] = mapped_column(String(80), primary_key=True)
    retain_years: Mapped[int] = mapped_column(Integer)
    basis: Mapped[str] = mapped_column(Text)


class DrugDictionary(Base):
    __tablename__ = "drug_dictionary"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), index=True)
    synonyms: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    strength_forms: Mapped[dict] = mapped_column(JSONB, default=dict)


class Interaction(Base):
    __tablename__ = "interactions"
    drug_a: Mapped[str] = mapped_column(String(200), primary_key=True)
    drug_b: Mapped[str] = mapped_column(String(200), primary_key=True)
    severity: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text)


class AllergyOverride(Base):
    __tablename__ = "allergy_overrides"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    medication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medications.id"))
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doctors.id"))
    allergy: Mapped[str] = mapped_column(String(200))
    justification: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("ix_consent_active_patient_expiry", Consent.patient_id, Consent.status, Consent.expires_at)
Index("ix_record_patient_date_type", Record.patient_id, Record.record_date, Record.type)
Index("ix_sos_event_status_expiry", SosEvent.status, SosEvent.expires_at)
