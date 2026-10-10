"""Initial QuikPatient schema, tenant RLS, and append-only audit enforcement."""

from alembic import op

from app.models import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


PATIENT_TABLES = (
    "patients",
    "guardians",
    "nominees",
    "patient_keys",
    "records",
    "medications",
    "treatments",
    "encounters",
    "consents",
    "consent_keys",
    "access_requests",
    "sos_events",
    "sos_notifications",
    "abuse_flags",
    "ingestion_jobs",
    "audit_log",
)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    for table in PATIENT_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        if table == "patients":
            tenant_expr = (
                "id = NULLIF(current_setting('app.patient_id', true), '')::uuid "
                "OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
            )
        elif table == "patient_keys":
            tenant_expr = (
                "patient_id = NULLIF(current_setting('app.patient_id', true), '')::uuid "
                "OR patient_id IN (SELECT id FROM patients WHERE "
                "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"
            )
        elif table == "consent_keys":
            tenant_expr = (
                "consent_id IN (SELECT id FROM consents WHERE "
                "patient_id = NULLIF(current_setting('app.patient_id', true), '')::uuid)"
            )
        elif table == "audit_log":
            tenant_expr = (
                "patient_id = NULLIF(current_setting('app.patient_id', true), '')::uuid "
                "OR actor_user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
            )
        elif table in {"consents", "access_requests"}:
            tenant_expr = (
                "patient_id = NULLIF(current_setting('app.patient_id', true), '')::uuid "
                "OR doctor_id IN (SELECT id FROM doctors WHERE "
                "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"
            )
        elif table == "encounters":
            tenant_expr = (
                "patient_id = NULLIF(current_setting('app.patient_id', true), '')::uuid "
                "OR doctor_id IN (SELECT id FROM doctors WHERE "
                "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"
            )
        elif table == "sos_events":
            tenant_expr = (
                "patient_id = NULLIF(current_setting('app.patient_id', true), '')::uuid "
                "OR doctor_id IN (SELECT id FROM doctors WHERE "
                "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"
            )
        elif table == "sos_notifications":
            tenant_expr = (
                "sos_event_id IN (SELECT id FROM sos_events WHERE "
                "patient_id = NULLIF(current_setting('app.patient_id', true), '')::uuid "
                "OR doctor_id IN (SELECT id FROM doctors WHERE "
                "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid))"
            )
        elif table == "abuse_flags":
            tenant_expr = (
                "reported_by_patient_id = NULLIF(current_setting('app.patient_id', true), '')::uuid"
            )
        else:
            tenant_expr = "patient_id = NULLIF(current_setting('app.patient_id', true), '')::uuid"
        policy = f"tenant_{table}"
        op.execute(
            f'CREATE POLICY "{policy}" ON "{table}" USING ({tenant_expr}) WITH CHECK ({tenant_expr})'
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_audit_log_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only'
                USING ERRCODE = '55000';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
        """
    )
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qp_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO qp_app;
                GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO qp_app;
                REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM qp_app;
            END IF;
        END $$;
        """
    )
    op.execute(
        "INSERT INTO retention_policies (entity, retain_years, basis) "
        "VALUES ('audit_log', 6, 'Operational integrity and statutory retention') "
        "ON CONFLICT (entity) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update_delete ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation()")
    for table in reversed(PATIENT_TABLES):
        op.execute(f'DROP POLICY IF EXISTS "tenant_{table}" ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    Base.metadata.drop_all(bind=op.get_bind())
