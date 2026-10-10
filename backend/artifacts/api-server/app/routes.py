import base64
import hashlib
import hmac
import logging
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
import pyotp
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import append_audit, verify_audit_chain
from app.auth import (
    AuthContext,
    current_auth,
    hash_password,
    issue_access_token,
    issue_refresh_token,
    password_hasher,
    require_roles,
    token_fingerprint,
    verify_password,
)
from app.config import settings
from app.crypto import EMERGENCY_RECORD_TYPES, record_aad
from app.database import get_session, set_patient_rls
from app.models import (
    AccessRequest,
    AbuseFlag,
    AuditLog,
    AuthSession,
    Consent,
    ConsentKey,
    Doctor,
    Encounter,
    IngestionJob,
    Medication,
    Nominee,
    Notification,
    Patient,
    Record,
    RecordSource,
    RecordType,
    Role,
    SosEvent,
    SosNotification,
    Treatment,
    User,
    Verification,
)
from app.schemas import (
    AccessDecision,
    AccessRequestCreate,
    ConsentCreate,
    ConsentKeyGrant,
    DoctorVerificationRequest,
    EncounterCreate,
    LoginRequest,
    PatientPatch,
    PrescriptionCreate,
    RefreshRequest,
    SosInitiateRequest,
    SosReportRequest,
    SosResponseRequest,
    TotpRequest,
)
from app.security import (
    apply_record_scope,
    assert_non_emergency_write,
    validate_outbound_template,
)

log = logging.getLogger("quikpatient.api")
router = APIRouter(prefix="/api")
Db = Annotated[AsyncSession, Depends(get_session)]


def _token_response(user: User, session: AuthSession, refresh_token: str) -> dict:
    return {
        "access_token": issue_access_token(user, session.id),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
    }


async def _create_session(
    db: AsyncSession, user: User, encounter_id: UUID | None = None
) -> dict:
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_days)
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash="pending",
        expires_at=expires_at,
        encounter_id=encounter_id,
    )
    db.add(session)
    await db.flush()
    refresh = issue_refresh_token(user, session.id)
    session.refresh_token_hash = token_fingerprint(refresh)
    await db.flush()
    return _token_response(user, session, refresh)


async def _patient_for_user(db: AsyncSession, user: User) -> Patient:
    patient = await db.scalar(select(Patient).where(Patient.user_id == user.id))
    if patient is None or patient.closed_at is not None:
        raise HTTPException(status_code=404, detail={"code": "patient_profile_not_found"})
    await set_patient_rls(db, str(patient.id))
    return patient


async def _assert_session_write_allowed(auth: AuthContext, db: AsyncSession) -> None:
    if auth.session.encounter_id is None:
        return
    encounter = await db.get(Encounter, auth.session.encounter_id)
    if encounter is not None:
        assert_non_emergency_write(encounter.mode)


async def _doctor_for_user(db: AsyncSession, user: User, *, require_verified: bool = True) -> Doctor:
    doctor = await db.scalar(select(Doctor).where(Doctor.user_id == user.id))
    if (
        doctor is None
        or (require_verified and not doctor.verified)
        or (
            require_verified
            and doctor.verified_at is not None
            and doctor.verified_at < datetime.now(UTC) - timedelta(days=180)
        )
    ):
        raise HTTPException(status_code=403, detail={"code": "doctor_verification_required"})
    return doctor


def _ist(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("Naive datetime rejected")
    from zoneinfo import ZoneInfo

    return value.astimezone(ZoneInfo("Asia/Kolkata")).isoformat()


async def _active_doctor_consent(
    db: AsyncSession,
    *,
    doctor_id: UUID,
    patient_id: UUID,
    encounter_id: UUID | None = None,
    allow_emergency: bool = False,
) -> Consent:
    now = datetime.now(UTC)
    query = select(Consent).where(
        Consent.doctor_id == doctor_id,
        Consent.patient_id == patient_id,
        Consent.status == "active",
        Consent.expires_at > now,
        Consent.legal_basis.in_(
            ["PATIENT_CONSENT", "NOMINEE_EMERGENCY", "BREAK_GLASS"]
            if allow_emergency
            else ["PATIENT_CONSENT"]
        ),
    )
    if encounter_id:
        query = query.where(Consent.encounter_id == encounter_id)
    consent = await db.scalar(query.order_by(Consent.expires_at.desc()).limit(1))
    if consent is None:
        raise HTTPException(status_code=403, detail={"code": "active_consent_required"})
    return consent


@router.get("/healthz", include_in_schema=True)
async def healthz():
    return {
        "status": "ok",
        "mode": "MOCK" if settings.mock_mode else "LIVE",
        "database": "configured" if settings.database_url else "not_configured",
        "worker": "separate_service",
    }


@router.post("/auth/patient/login")
@router.post("/auth/doctor/login")
async def login(body: LoginRequest, request: Request, db: Db):
    user = await db.scalar(select(User).where(User.login_id == body.login_id))
    if user is None or user.status != "active" or not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials"})
    expected_role = "patient" if request.url.path.endswith("patient/login") else "doctor"
    if user.role.value != expected_role:
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials"})
    if expected_role == "doctor":
        doctor = await _doctor_for_user(db, user)
        if doctor.verified_at is None:
            raise HTTPException(status_code=403, detail={"code": "doctor_verification_required"})
    if user.totp_secret_enc:
        now = datetime.now(UTC)
        challenge = jwt.encode(
            {
                "sub": str(user.id),
                "kind": "totp_challenge",
                "exp": now + timedelta(minutes=5),
                "iat": now,
            },
            settings.session_secret.get_secret_value(),
            algorithm="HS256",
        )
        return {"totp_required": True, "challenge_token": challenge}
    tokens = await _create_session(db, user)
    await db.commit()
    return tokens


@router.post("/auth/totp/verify")
async def verify_totp(body: TotpRequest, db: Db):
    try:
        claims = jwt.decode(
            body.challenge_token,
            settings.session_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "kind"]},
        )
        if claims.get("kind") != "totp_challenge":
            raise ValueError("invalid challenge")
        user_id = UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail={"code": "invalid_totp_challenge"}) from None
    user = await db.get(User, user_id)
    from app.crypto import decrypt_server_secret

    if user is None or not user.totp_secret_enc or not pyotp.TOTP(
        decrypt_server_secret(
            user.totp_secret_enc,
            settings.session_secret.get_secret_value(),
            "totp",
        )
    ).verify(body.code, valid_window=1):
        raise HTTPException(status_code=401, detail={"code": "invalid_totp_code"})
    tokens = await _create_session(db, user)
    await db.commit()
    return tokens


@router.post("/auth/refresh")
async def refresh(body: RefreshRequest, db: Db):
    try:
        claims = jwt.decode(
            body.refresh_token,
            settings.session_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "sid", "kind"]},
        )
        if claims.get("kind") != "refresh":
            raise ValueError("wrong token kind")
        session_id = UUID(claims["sid"])
        user_id = UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail={"code": "invalid_refresh_token"}) from None
    auth_session = await db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
            AuthSession.refresh_token_hash == token_fingerprint(body.refresh_token),
        )
    )
    user = await db.get(User, user_id)
    if auth_session is None or user is None or user.status != "active":
        raise HTTPException(status_code=401, detail={"code": "invalid_refresh_token"})
    if auth_session.encounter_id is not None:
        encounter = await db.get(Encounter, auth_session.encounter_id)
        if encounter is not None:
            assert_non_emergency_write(encounter.mode)
    auth_session.refresh_token_hash = "rotating"
    refresh_token = issue_refresh_token(user, auth_session.id)
    auth_session.refresh_token_hash = token_fingerprint(refresh_token)
    await db.commit()
    return _token_response(user, auth_session, refresh_token)


@router.post("/auth/logout")
async def logout(auth: Annotated[AuthContext, Depends(current_auth)], db: Db):
    await _assert_session_write_allowed(auth, db)
    auth.session.revoked_at = datetime.now(UTC)
    await db.commit()
    return {"ok": True}


@router.post("/auth/doctor/verify")
async def verify_doctor(body: DoctorVerificationRequest, db: Db):
    doctor = await db.scalar(
        select(Doctor).where(
            Doctor.nmc_reg_no == body.reg_no,
            Doctor.council == body.council,
        )
    )
    if doctor is None:
        return {"verified": False, "source": "mock" if settings.mock_mode else "provider"}
    if settings.mock_mode:
        fixture = doctor.verification_payload or {}
        if fixture.get("mock_verified") is not True:
            return {"verified": False, "source": "mock"}
        doctor.verified = True
        doctor.verified_at = datetime.now(UTC)
        doctor.verification_payload = {
            **fixture,
            "source": "mock",
            "verified_at": doctor.verified_at.isoformat(),
        }
        await db.commit()
        return {
            "verified": True,
            "name": doctor.name,
            "council": doctor.council,
            "reg_no": doctor.nmc_reg_no,
            "valid_till": (doctor.verified_at + timedelta(days=180)).date().isoformat(),
            "source": "mock",
        }
    raise HTTPException(
        status_code=503,
        detail={"code": "doctor_verification_provider_not_configured"},
    )


@router.get("/patients/me")
async def get_patient_me(auth: Annotated[AuthContext, Depends(require_roles(Role.patient))], db: Db):
    patient = await _patient_for_user(db, auth.user)
    await set_patient_rls(db, str(patient.id))
    return {
        "id": str(patient.id),
        "name": patient.name,
        "abha_address": patient.abha_address,
        "dob": patient.dob.isoformat() if patient.dob else None,
        "sex": patient.sex,
        "blood_group": patient.blood_group,
        "height_cm": patient.height_cm,
        "weight_kg": patient.weight_kg,
        "emergency_contact": patient.emergency_contact,
        "allergies": patient.allergies,
        "chronic_conditions": patient.chronic_conditions,
        "is_minor": patient.is_minor,
        "general_info_updated_at": patient.general_info_updated_at.isoformat()
        if patient.general_info_updated_at
        else None,
        "general_info_updated_at_ist": _ist(patient.general_info_updated_at),
    }


@router.patch("/patients/me")
async def patch_patient_me(
    body: PatientPatch,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_roles(Role.patient))],
    db: Db,
):
    await _assert_session_write_allowed(auth, db)
    patient = await _patient_for_user(db, auth.user)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "no_changes"})
    for key, value in changes.items():
        setattr(patient, key, value)
    patient.general_info_updated_at = datetime.now(UTC)
    await set_patient_rls(db, str(patient.id))
    await append_audit(
        db,
        patient_id=patient.id,
        actor_user_id=auth.user.id,
        actor_role="patient",
        action="patient_profile_updated",
        object_type="patient",
        object_id=str(patient.id),
        scope={"fields": sorted(changes)},
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    return {"ok": True, "updated_at_ist": _ist(patient.general_info_updated_at)}


@router.get("/patients/me/guardians")
@router.post("/patients/me/guardians")
async def guardian_flow_not_implemented(
    auth: Annotated[AuthContext, Depends(current_auth)],
):
    raise HTTPException(
        status_code=403,
        detail={"reason": "guardian_flow_not_implemented"},
    )


@router.get("/patients/me/nominees")
async def list_nominees(
    auth: Annotated[AuthContext, Depends(require_roles(Role.patient))], db: Db
):
    patient = await _patient_for_user(db, auth.user)
    nominees = await db.scalars(
        select(Nominee).where(Nominee.patient_id == patient.id, Nominee.revoked_at.is_(None))
        .order_by(Nominee.priority)
    )
    return [
        {
            "id": str(n.id),
            "name": n.name,
            "relationship": n.relationship,
            "phone_e164": n.phone_e164,
            "email": n.email,
            "phone_verified": n.phone_verified_at is not None,
            "may_approve_emergency": n.may_approve_emergency,
            "priority": n.priority,
        }
        for n in nominees
    ]


@router.get("/records")
async def list_my_records(
    auth: Annotated[AuthContext, Depends(require_roles(Role.patient))],
    db: Db,
    record_type: str | None = Query(default=None, alias="type"),
    from_date: date | None = None,
    to_date: date | None = None,
):
    patient = await _patient_for_user(db, auth.user)
    await set_patient_rls(db, str(patient.id))
    query = select(Record).where(
        Record.patient_id == patient.id, Record.soft_deleted_at.is_(None)
    )
    if record_type:
        query = query.where(Record.type == record_type)
    if from_date:
        query = query.where(Record.record_date >= from_date)
    if to_date:
        query = query.where(Record.record_date <= to_date)
    rows = await db.scalars(query.order_by(Record.record_date.desc()).limit(500))
    return [_record_json(row) for row in rows]


@router.get("/consents")
async def list_consents(
    auth: Annotated[AuthContext, Depends(current_auth)], db: Db
):
    if auth.user.role == Role.patient:
        patient = await _patient_for_user(db, auth.user)
        query = select(Consent).where(Consent.patient_id == patient.id)
    elif auth.user.role == Role.doctor:
        doctor = await _doctor_for_user(db, auth.user)
        query = select(Consent).where(Consent.doctor_id == doctor.id)
    else:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    rows = await db.scalars(query.order_by(Consent.expires_at.desc()).limit(200))
    return [
        {
            "id": str(row.id),
            "patient_id": str(row.patient_id),
            "doctor_id": str(row.doctor_id),
            "kind": row.kind,
            "legal_basis": row.legal_basis,
            "scope_types": row.scope_types,
            "scope_from": row.scope_from.isoformat() if row.scope_from else None,
            "scope_to": row.scope_to.isoformat() if row.scope_to else None,
            "expires_at": row.expires_at.isoformat(),
            "expires_at_ist": _ist(row.expires_at),
            "status": row.status,
        }
        for row in rows
    ]


def _record_json(record: Record) -> dict:
    return {
        "id": str(record.id),
        "patient_id": str(record.patient_id),
        "type": record.type.value,
        "record_date": record.record_date.isoformat(),
        "source": record.source.value,
        "verification": record.verification.value,
        "ciphertext": base64.b64encode(record.ciphertext).decode("ascii"),
        "nonce": base64.b64encode(record.nonce).decode("ascii"),
        "aad": base64.b64encode(record.aad).decode("ascii"),
        "wrapped_dek": base64.b64encode(record.wrapped_dek).decode("ascii"),
        "key_version": record.key_version,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "created_at_ist": _ist(record.created_at),
    }


@router.get("/records/{record_id}")
async def get_record(
    record_id: UUID,
    auth: Annotated[AuthContext, Depends(current_auth)],
    db: Db,
):
    encounter_for_scope = None
    if auth.user.role == Role.patient:
        own_patient = await _patient_for_user(db, auth.user)
        await set_patient_rls(db, str(own_patient.id))
    elif auth.user.role == Role.doctor:
        if auth.session.encounter_id is None:
            raise HTTPException(status_code=403, detail={"code": "doctor_unlock_required"})
        encounter_for_scope = await db.get(Encounter, auth.session.encounter_id)
        if encounter_for_scope is None:
            raise HTTPException(status_code=403, detail={"code": "active_encounter_required"})
        await set_patient_rls(db, str(encounter_for_scope.patient_id))
    record = await db.get(Record, record_id)
    if record is None or record.soft_deleted_at is not None:
        raise HTTPException(status_code=404, detail={"code": "record_not_found"})
    if auth.user.role == Role.patient:
        patient = own_patient
        if patient.id != record.patient_id:
            raise HTTPException(status_code=404, detail={"code": "record_not_found"})
    elif auth.user.role == Role.doctor:
        doctor = await _doctor_for_user(db, auth.user)
        consent = await _active_doctor_consent(
            db,
            doctor_id=doctor.id,
            patient_id=record.patient_id,
            encounter_id=auth.session.encounter_id,
            allow_emergency=encounter_for_scope.mode == "EMERGENCY",
        )
        emergency = consent.legal_basis == "NOMINEE_EMERGENCY"
        if (
            record.type.value not in consent.scope_types
            or (consent.scope_from and record.record_date < consent.scope_from)
            or (consent.scope_to and record.record_date > consent.scope_to)
            or (
                emergency
                and record.type.value
                not in {"diagnosis", "discharge_summary", "diagnostic_report"}
            )
            or await db.scalar(
                select(ConsentKey).where(
                    ConsentKey.consent_id == consent.id,
                    ConsentKey.record_id == record.id,
                    ConsentKey.key_version == record.key_version,
                )
            )
            is None
        ):
            raise HTTPException(status_code=404, detail={"code": "record_not_found"})
    else:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    await append_audit(
        db,
        patient_id=record.patient_id,
        actor_user_id=auth.user.id,
        actor_role=auth.user.role.value,
        action="record_read",
        object_type="record",
        object_id=str(record.id),
        scope={"type": record.type.value, "record_date": record.record_date.isoformat()},
        legal_basis="PATIENT_CONSENT" if auth.user.role == Role.doctor else None,
    )
    await db.commit()
    return _record_json(record)


@router.post("/consents")
async def create_consent(
    body: ConsentCreate,
    request: Request,
    auth: Annotated[AuthContext, Depends(current_auth)],
    db: Db,
):
    await _assert_session_write_allowed(auth, db)
    if auth.user.role != Role.patient:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    patient = await _patient_for_user(db, auth.user)
    if patient.is_minor:
        raise HTTPException(status_code=403, detail={"reason": "guardian_flow_not_implemented"})
    doctor = await db.get(Doctor, body.doctor_id)
    if (
        doctor is None
        or not doctor.verified
        or doctor.verified_at is None
        or doctor.verified_at < datetime.now(UTC) - timedelta(days=180)
    ):
        raise HTTPException(status_code=403, detail={"code": "doctor_verification_required"})
    if body.encounter_id is not None:
        encounter = await db.get(Encounter, body.encounter_id)
        if (
            encounter is None
            or encounter.patient_id != patient.id
            or encounter.doctor_id != doctor.id
            or encounter.mode != "CONSENTED"
            or encounter.ended_at is not None
        ):
            raise HTTPException(status_code=422, detail={"code": "invalid_encounter"})
    if body.scope_from and body.scope_to and body.scope_from > body.scope_to:
        raise HTTPException(status_code=422, detail={"code": "invalid_scope_interval"})
    try:
        expires_at = datetime.fromisoformat(body.expires_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "invalid_expiry"}) from None
    if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail={"code": "invalid_expiry"})
    consent = Consent(
        patient_id=patient.id,
        doctor_id=doctor.id,
        encounter_id=body.encounter_id,
        kind=body.kind,
        legal_basis="PATIENT_CONSENT",
        scope_types=body.scope_types,
        scope_from=body.scope_from,
        scope_to=body.scope_to,
        expires_at=expires_at.astimezone(UTC),
        status="active",
    )
    db.add(consent)
    await db.flush()
    await append_audit(
        db,
        patient_id=patient.id,
        actor_user_id=auth.user.id,
        actor_role="patient",
        action="consent_granted",
        object_type="consent",
        object_id=str(consent.id),
        scope={"types": body.scope_types, "from": str(body.scope_from), "to": str(body.scope_to)},
        legal_basis="PATIENT_CONSENT",
    )
    await db.commit()
    return {"id": str(consent.id), "status": consent.status, "expires_at": consent.expires_at.isoformat()}


@router.post("/consent-keys", status_code=201)
async def grant_consent_key(
    body: ConsentKeyGrant,
    auth: Annotated[AuthContext, Depends(require_roles(Role.patient))],
    db: Db,
):
    await _assert_session_write_allowed(auth, db)
    patient = await _patient_for_user(db, auth.user)
    consent = await db.scalar(
        select(Consent).where(
            Consent.id == body.consent_id,
            Consent.patient_id == patient.id,
            Consent.status == "active",
            Consent.expires_at > datetime.now(UTC),
        )
    )
    doctor = await db.get(Doctor, consent.doctor_id) if consent else None
    record = await db.get(Record, body.record_id)
    if (
        consent is None
        or doctor is None
        or not doctor.verified
        or doctor.verified_at is None
        or doctor.verified_at < datetime.now(UTC) - timedelta(days=180)
        or record is None
        or record.patient_id != patient.id
    ):
        raise HTTPException(status_code=404, detail={"code": "consent_or_record_not_found"})
    if (
        record.type.value not in consent.scope_types
        or (consent.scope_from and record.record_date < consent.scope_from)
        or (consent.scope_to and record.record_date > consent.scope_to)
        or record.key_version != body.key_version
    ):
        raise HTTPException(status_code=403, detail={"code": "record_outside_consent_scope"})
    try:
        sealed_key = base64.b64decode(body.dek_sealed_to_doctor, validate=True)
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "invalid_sealed_key"}) from None
    if len(sealed_key) < 48:
        raise HTTPException(status_code=422, detail={"code": "invalid_sealed_key"})
    key_row = await db.get(ConsentKey, (consent.id, record.id))
    if key_row is None:
        db.add(
            ConsentKey(
                consent_id=consent.id,
                record_id=record.id,
                dek_sealed_to_doctor=sealed_key,
                key_version=body.key_version,
            )
        )
    else:
        key_row.dek_sealed_to_doctor = sealed_key
        key_row.key_version = body.key_version
    await db.commit()
    return {"ok": True}


@router.delete("/consents/{consent_id}")
async def revoke_consent(
    consent_id: UUID,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_roles(Role.patient))],
    db: Db,
    mode: str = Query(default="soft", pattern=r"^(soft|hard)$"),
):
    await _assert_session_write_allowed(auth, db)
    patient = await _patient_for_user(db, auth.user)
    consent = await db.scalar(
        select(Consent).where(Consent.id == consent_id, Consent.patient_id == patient.id)
    )
    if consent is None:
        raise HTTPException(status_code=404, detail={"code": "consent_not_found"})
    if consent.status != "revoked":
        consent.status = "revoked"
        consent.revoke_mode = mode
        await db.execute(delete(ConsentKey).where(ConsentKey.consent_id == consent.id))
        if mode == "hard":
            db.add(
                IngestionJob(
                    patient_id=patient.id,
                    kind="DEK_ROTATION",
                    status="queued",
                    payload={"consent_id": str(consent.id)},
                )
            )
        await append_audit(
            db,
            patient_id=patient.id,
            actor_user_id=auth.user.id,
            actor_role="patient",
            action="consent_revoked",
            object_type="consent",
            object_id=str(consent.id),
            scope={"mode": mode},
            legal_basis="PATIENT_CONSENT",
            severity="high" if mode == "hard" else "info",
        )
    await db.commit()
    return {"ok": True, "status": "revoked", "mode": mode}


@router.get("/doctor/patients")
async def doctor_patients(
    auth: Annotated[AuthContext, Depends(require_roles(Role.doctor))], db: Db
):
    doctor = await _doctor_for_user(db, auth.user)
    rows = await db.scalars(
        select(Consent)
        .where(
            Consent.doctor_id == doctor.id,
            Consent.status == "active",
            Consent.expires_at > datetime.now(UTC),
            Consent.legal_basis == "PATIENT_CONSENT",
        )
        .order_by(Consent.expires_at.desc())
    )
    return [
        {
            "patient_id": str(consent.patient_id),
            "consent_id": str(consent.id),
            "expires_at": consent.expires_at.isoformat(),
            "expires_at_ist": _ist(consent.expires_at),
        }
        for consent in rows
    ]


@router.post("/access-requests", status_code=201)
async def create_access_request(
    body: AccessRequestCreate,
    auth: Annotated[AuthContext, Depends(require_roles(Role.doctor))],
    db: Db,
):
    doctor = await _doctor_for_user(db, auth.user)
    await set_patient_rls(db, str(body.patient_id))
    patient = await db.get(Patient, body.patient_id)
    if patient is None or patient.closed_at is not None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    if body.requested_from and body.requested_to and body.requested_from > body.requested_to:
        raise HTTPException(status_code=422, detail={"code": "invalid_scope_interval"})
    request_row = AccessRequest(
        doctor_id=doctor.id,
        patient_id=patient.id,
        requested_from=body.requested_from,
        requested_to=body.requested_to,
        types=body.types,
        reason=body.reason,
        requested_duration=body.requested_duration,
        status="pending",
    )
    db.add(request_row)
    await db.flush()
    db.add(
        Notification(
            user_id=patient.user_id,
            kind="access_requested",
            payload={"access_request_id": str(request_row.id)},
        )
    )
    await append_audit(
        db,
        patient_id=patient.id,
        actor_user_id=auth.user.id,
        actor_role="doctor",
        action="access_requested",
        object_type="access_request",
        object_id=str(request_row.id),
        scope={"types": body.types},
        severity="info",
    )
    await db.commit()
    return {"id": str(request_row.id), "status": request_row.status}


@router.get("/access-requests")
async def list_access_requests(
    auth: Annotated[AuthContext, Depends(current_auth)], db: Db
):
    if auth.user.role == Role.patient:
        patient = await _patient_for_user(db, auth.user)
        query = select(AccessRequest).where(AccessRequest.patient_id == patient.id)
    elif auth.user.role == Role.doctor:
        doctor = await _doctor_for_user(db, auth.user)
        query = select(AccessRequest).where(AccessRequest.doctor_id == doctor.id)
    else:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    rows = await db.scalars(query.order_by(AccessRequest.id.desc()).limit(200))
    return [
        {
            "id": str(row.id),
            "patient_id": str(row.patient_id),
            "doctor_id": str(row.doctor_id),
            "requested_from": row.requested_from.isoformat() if row.requested_from else None,
            "requested_to": row.requested_to.isoformat() if row.requested_to else None,
            "types": row.types,
            "reason": row.reason,
            "requested_duration": row.requested_duration,
            "status": row.status,
        }
        for row in rows
    ]


@router.post("/access-requests/{request_id}/approve")
async def decide_access_request(
    request_id: UUID,
    body: AccessDecision,
    auth: Annotated[AuthContext, Depends(require_roles(Role.patient))],
    db: Db,
):
    await _assert_session_write_allowed(auth, db)
    patient = await _patient_for_user(db, auth.user)
    request_row = await db.scalar(
        select(AccessRequest).where(
            AccessRequest.id == request_id,
            AccessRequest.patient_id == patient.id,
            AccessRequest.status == "pending",
        )
    )
    if request_row is None:
        raise HTTPException(status_code=404, detail={"code": "pending_request_not_found"})
    request_row.status = body.decision
    consent_id = None
    if body.decision == "approved":
        consent = Consent(
            patient_id=patient.id,
            doctor_id=request_row.doctor_id,
            kind="DOCTOR_GRANT",
            legal_basis="PATIENT_CONSENT",
            scope_types=request_row.types,
            scope_from=request_row.requested_from,
            scope_to=request_row.requested_to,
            expires_at=datetime.now(UTC) + timedelta(minutes=request_row.requested_duration),
            status="active",
        )
        db.add(consent)
        await db.flush()
        consent_id = str(consent.id)
    await append_audit(
        db,
        patient_id=patient.id,
        actor_user_id=auth.user.id,
        actor_role="patient",
        action=f"access_request_{body.decision}",
        object_type="access_request",
        object_id=str(request_row.id),
        scope={"types": request_row.types},
        legal_basis="PATIENT_CONSENT" if body.decision == "approved" else None,
    )
    await db.commit()
    return {"id": str(request_row.id), "status": request_row.status, "consent_id": consent_id}


@router.post("/doctor/unlock")
async def doctor_unlock(
    patient_id: UUID,
    encounter_id: UUID,
    auth: Annotated[AuthContext, Depends(require_roles(Role.doctor))],
    db: Db,
):
    await _assert_session_write_allowed(auth, db)
    doctor = await _doctor_for_user(db, auth.user)
    await set_patient_rls(db, str(patient_id))
    encounter = await db.get(Encounter, encounter_id)
    if (
        encounter is None
        or encounter.patient_id != patient_id
        or encounter.doctor_id != doctor.id
        or encounter.ended_at is not None
        or encounter.started_at + timedelta(hours=8) <= datetime.now(UTC)
    ):
        raise HTTPException(status_code=403, detail={"code": "active_encounter_required"})
    if encounter.mode not in {"CONSENTED", "EMERGENCY"}:
        raise HTTPException(status_code=403, detail={"code": "invalid_encounter_mode"})
    consent = await _active_doctor_consent(
        db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        encounter_id=encounter_id,
        allow_emergency=encounter.mode == "EMERGENCY",
    )
    # The resulting bearer token is server-bound to this encounter. Every
    # mutating endpoint checks the persisted encounter mode, never client input.
    tokens = await _create_session(db, auth.user, encounter_id=encounter.id)
    await db.commit()
    return {**tokens, "consent_id": str(consent.id), "mode": encounter.mode}


@router.post("/doctor/encounters", status_code=201)
async def start_doctor_encounter(
    body: EncounterCreate,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_roles(Role.doctor))],
    db: Db,
):
    await _assert_session_write_allowed(auth, db)
    doctor = await _doctor_for_user(db, auth.user)
    await set_patient_rls(db, str(body.patient_id))
    consent = await db.scalar(
        select(Consent).where(
            Consent.id == body.consent_id,
            Consent.patient_id == body.patient_id,
            Consent.doctor_id == doctor.id,
            Consent.status == "active",
            Consent.expires_at > datetime.now(UTC),
            Consent.legal_basis == "PATIENT_CONSENT",
        )
    )
    if consent is None:
        raise HTTPException(status_code=403, detail={"code": "active_consent_required"})
    encounter = Encounter(
        patient_id=body.patient_id,
        doctor_id=doctor.id,
        facility_id=doctor.facility_id,
        mode="CONSENTED",
        reason="authorized clinical consultation",
    )
    db.add(encounter)
    await db.flush()
    consent.encounter_id = encounter.id
    await append_audit(
        db,
        patient_id=body.patient_id,
        actor_user_id=auth.user.id,
        actor_role="doctor",
        action="encounter_started",
        object_type="encounter",
        object_id=str(encounter.id),
        scope={"consent_id": str(consent.id)},
        legal_basis="PATIENT_CONSENT",
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    return {"id": str(encounter.id), "mode": encounter.mode, "started_at_ist": _ist(encounter.started_at)}


@router.get("/doctor/patient/{patient_id}/records")
async def doctor_patient_records(
    patient_id: UUID,
    auth: Annotated[AuthContext, Depends(require_roles(Role.doctor))],
    db: Db,
):
    doctor = await _doctor_for_user(db, auth.user)
    await set_patient_rls(db, str(patient_id))
    active_encounter = (
        await db.get(Encounter, auth.session.encounter_id)
        if auth.session.encounter_id is not None
        else None
    )
    consent = await _active_doctor_consent(
        db,
        doctor_id=doctor.id,
        patient_id=patient_id,
        encounter_id=auth.session.encounter_id,
        allow_emergency=active_encounter is not None and active_encounter.mode == "EMERGENCY",
    )
    query = apply_record_scope(
        select(Record),
        patient_id=str(patient_id),
        allowed_types=consent.scope_types,
        scope_from=consent.scope_from,
        scope_to=consent.scope_to,
        expires_at=consent.expires_at,
        emergency=consent.legal_basis == "NOMINEE_EMERGENCY",
    )
    key_record_ids = select(ConsentKey.record_id).where(
        ConsentKey.consent_id == consent.id, ConsentKey.key_version == Record.key_version
    )
    query = query.where(Record.id.in_(key_record_ids)).order_by(Record.record_date.desc())
    records = await db.scalars(query.limit(300))
    result = [_record_json(row) for row in records]
    for row in result:
        await append_audit(
            db,
            patient_id=patient_id,
            actor_user_id=auth.user.id,
            actor_role="doctor",
            action="record_read",
            object_type="record",
            object_id=row["id"],
            scope={"type": row["type"], "record_date": row["record_date"]},
            legal_basis=consent.legal_basis,
        )
    await db.commit()
    return result


@router.post("/doctor/prescriptions", status_code=201)
async def create_prescription(
    body: PrescriptionCreate,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_roles(Role.doctor))],
    db: Db,
):
    await _assert_session_write_allowed(auth, db)
    doctor = await _doctor_for_user(db, auth.user)
    if auth.session.encounter_id != body.encounter_id:
        raise HTTPException(status_code=403, detail={"code": "doctor_unlock_required"})
    await set_patient_rls(db, str(body.patient_id))
    consent = await _active_doctor_consent(
        db, doctor_id=doctor.id, patient_id=body.patient_id, encounter_id=body.encounter_id
    )
    encounter = await db.get(Encounter, body.encounter_id)
    if (
        encounter is None
        or encounter.patient_id != body.patient_id
        or encounter.doctor_id != doctor.id
        or encounter.ended_at is not None
    ):
        raise HTTPException(status_code=403, detail={"code": "active_encounter_required"})
    assert_non_emergency_write(encounter.mode)
    if consent.legal_basis != "PATIENT_CONSENT":
        raise HTTPException(status_code=403, detail={"code": "clinical_consent_required"})
    try:
        ciphertext = base64.b64decode(body.ciphertext, validate=True)
        nonce = base64.b64decode(body.nonce, validate=True)
        aad = base64.b64decode(body.aad, validate=True)
        wrapped_dek = base64.b64decode(body.wrapped_dek, validate=True)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail={"code": "invalid_ciphertext_envelope"}) from None
    if len(nonce) != 12 or len(ciphertext) < 16 or len(wrapped_dek) < 28:
        raise HTTPException(status_code=422, detail={"code": "invalid_ciphertext_envelope"})
    expected_aad = record_aad(
        str(body.record_id),
        str(body.patient_id),
        RecordType.prescription.value,
        body.record_date,
        body.key_version,
    )
    if not hmac.compare_digest(aad, expected_aad):
        raise HTTPException(status_code=422, detail={"code": "record_aad_mismatch"})
    record = Record(
        id=body.record_id,
        patient_id=body.patient_id,
        encounter_id=body.encounter_id,
        type=RecordType.prescription,
        record_date=body.record_date,
        source=RecordSource.PROVIDER_DIRECT,
        verification=Verification.VERIFIED,
        attested_by_doctor_id=doctor.id,
        ciphertext=ciphertext,
        nonce=nonce,
        aad=aad,
        wrapped_dek=wrapped_dek,
        key_version=body.key_version,
    )
    db.add(record)
    await db.flush()
    await append_audit(
        db,
        patient_id=body.patient_id,
        actor_user_id=auth.user.id,
        actor_role="doctor",
        action="prescription_appended",
        object_type="record",
        object_id=str(record.id),
        scope={"type": "prescription", "record_date": body.record_date.isoformat()},
        legal_basis="PATIENT_CONSENT",
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    return {"id": str(record.id), "source": record.source.value, "verification": record.verification.value}


@router.post("/sos/initiate", status_code=202)
async def initiate_sos(
    body: SosInitiateRequest,
    auth: Annotated[AuthContext, Depends(require_roles(Role.doctor))],
    db: Db,
):
    await _assert_session_write_allowed(auth, db)
    doctor = await _doctor_for_user(db, auth.user)
    now = datetime.now(UTC)
    if doctor.sos_suspended_until and doctor.sos_suspended_until > now:
        raise HTTPException(status_code=403, detail={"code": "doctor_sos_suspended"})
    await set_patient_rls(db, str(body.patient_id))
    patient = await db.get(Patient, body.patient_id)
    if patient is None or patient.closed_at is not None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    # The Redis limiter is authoritative when configured; fail closed for SOS initiation.
    try:
        from redis.asyncio import Redis

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        day = now.date().isoformat()
        keys = [
            f"qp:sos:doctor:{doctor.id}:{day}",
            f"qp:sos:patient:{patient.id}:{day}",
            f"qp:sos:facility:{doctor.facility_id}:{day}",
        ]
        pipe = redis.pipeline()
        for key in keys:
            pipe.incr(key)
            pipe.expire(key, 86400)
        counts = await pipe.execute()
        await redis.aclose()
        doctor_count, patient_count, facility_count = counts[0], counts[2], counts[4]
        if doctor_count > settings.sos_rate_limit_per_doctor_day:
            raise HTTPException(status_code=429, detail={"code": "sos_doctor_rate_limit"})
        if facility_count > settings.sos_rate_limit_per_doctor_day:
            raise HTTPException(status_code=429, detail={"code": "sos_facility_rate_limit"})
        if patient_count > settings.sos_rate_limit_per_doctor_day:
            raise HTTPException(status_code=429, detail={"code": "sos_patient_rate_limit"})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail={"code": "sos_rate_limiter_unavailable"}) from None
    event = SosEvent(
        patient_id=patient.id,
        doctor_id=doctor.id,
        facility_id=doctor.facility_id,
        identity_method=body.identity_method,
        identity_confidence=0,
        declared_reason_code=body.declared_reason_code,
        declared_reason_text=body.declared_reason_text,
        status="INITIATED",
        expires_at=now + timedelta(minutes=settings.sos_ttl_minutes),
        scope_types=sorted(EMERGENCY_RECORD_TYPES),
    )
    db.add(event)
    await db.flush()
    db.add(
        Notification(
            user_id=patient.user_id,
            kind="sos_initiated",
            payload={"sos_event_id": str(event.id)},
        )
    )
    await append_audit(
        db,
        patient_id=patient.id,
        actor_user_id=auth.user.id,
        actor_role="doctor",
        action="sos_initiated",
        object_type="sos_event",
        object_id=str(event.id),
        scope={"types": event.scope_types},
        legal_basis="BREAK_GLASS",
        severity="high",
    )
    await db.commit()
    # Identity evidence is deliberately not echoed. The doctor confirms a masked
    # candidate in the next stage before any clinical information can be released.
    return {
        "sos_event_id": str(event.id),
        "status": "INITIATED",
        "candidate": {"patient_id": str(patient.id), "name": _mask_name(patient.name)},
        "expires_at": event.expires_at.isoformat(),
    }


def _mask_name(name: str) -> str:
    parts = name.split()
    return " ".join((part[:1] + "*" * max(1, len(part) - 1)) for part in parts)


@router.post("/sos/{event_id}/confirm", status_code=202)
async def confirm_sos(
    event_id: UUID,
    auth: Annotated[AuthContext, Depends(require_roles(Role.doctor))],
    db: Db,
):
    await _assert_session_write_allowed(auth, db)
    doctor = await _doctor_for_user(db, auth.user)
    event = await db.get(SosEvent, event_id)
    if event is None or event.doctor_id != doctor.id or event.status != "INITIATED":
        raise HTTPException(status_code=404, detail={"code": "sos_event_not_found"})
    # No nominee is told approval succeeded until encrypted share-release and
    # key-issuance are configured. A status-only mock could expose records later.
    raise HTTPException(
        status_code=503,
        detail={"code": "sos_notification_and_key_ceremony_not_configured"},
    )


@router.get("/notifications")
async def notifications(
    auth: Annotated[AuthContext, Depends(current_auth)],
    db: Db,
    limit: int = Query(default=50, ge=1, le=100),
):
    rows = await db.scalars(
        select(Notification)
        .where(Notification.user_id == auth.user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(row.id),
            "kind": row.kind,
            "payload": row.payload,
            "read_at": row.read_at.isoformat() if row.read_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "created_at_ist": _ist(row.created_at),
        }
        for row in rows
    ]


@router.get("/jobs/{job_id}")
async def job_status(
    job_id: UUID,
    auth: Annotated[AuthContext, Depends(current_auth)],
    db: Db,
    patient_id: UUID | None = None,
):
    if auth.user.role == Role.patient:
        patient = await _patient_for_user(db, auth.user)
        await set_patient_rls(db, str(patient.id))
        if patient_id is not None and patient_id != patient.id:
            raise HTTPException(status_code=404, detail={"code": "job_not_found"})
    elif auth.user.role == Role.doctor:
        if patient_id is None:
            raise HTTPException(status_code=422, detail={"code": "patient_id_required"})
        doctor = await _doctor_for_user(db, auth.user)
        await set_patient_rls(db, str(patient_id))
    else:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    job = await db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "job_not_found"})
    if auth.user.role == Role.doctor:
        await _active_doctor_consent(
            db,
            doctor_id=doctor.id,
            patient_id=job.patient_id,
        )
    return {"id": str(job.id), "kind": job.kind, "status": job.status, "progress": job.progress}


@router.get("/audit")
async def list_audit(
    auth: Annotated[AuthContext, Depends(current_auth)],
    db: Db,
    limit: int = Query(default=100, ge=1, le=500),
):
    if auth.user.role == Role.patient:
        patient = await _patient_for_user(db, auth.user)
        query = select(AuditLog).where(AuditLog.patient_id == patient.id)
    elif auth.user.role == Role.doctor:
        query = select(AuditLog).where(AuditLog.actor_user_id == auth.user.id)
    else:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    rows = await db.scalars(query.order_by(AuditLog.ts.desc()).limit(limit))
    return [
        {
            "id": str(row.id),
            "actor_role": row.actor_role,
            "action": row.action,
            "object_type": row.object_type,
            "object_id": row.object_id,
            "scope": row.scope,
            "legal_basis": row.legal_basis,
            "severity": row.severity,
            "ts": row.ts.isoformat(),
            "ts_ist": _ist(row.ts),
            "entry_hash": row.entry_hash,
        }
        for row in rows
    ]


@router.get("/audit/verify")
async def audit_verify(
    auth: Annotated[AuthContext, Depends(require_roles(Role.patient, Role.doctor))],
    db: Db,
):
    raise HTTPException(
        status_code=503,
        detail={"code": "global_audit_verifier_not_configured"},
    )


@router.post("/abdm/consent-requests")
async def abdm_consent_request(
    auth: Annotated[AuthContext, Depends(require_roles(Role.patient))],
    db: Db,
):
    if not settings.mock_mode:
        raise HTTPException(status_code=503, detail={"code": "abdm_provider_not_configured"})
    patient = await _patient_for_user(db, auth.user)
    job = IngestionJob(
        patient_id=patient.id,
        kind="ABDM_FETCH",
        status="queued",
        payload={"provider": "mock", "state": "awaiting_consent"},
    )
    db.add(job)
    await db.commit()
    return {"job_id": str(job.id), "status": job.status, "provider": "mock"}
