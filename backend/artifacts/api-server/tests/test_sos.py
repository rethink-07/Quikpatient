import pytest
from fastapi import HTTPException

from app.security import validate_outbound_template


def test_sos_template_accepts_only_approved_fields():
    validate_outbound_template(
        {
            "doctor_name": "Dr Demo",
            "nmc_reg_no": "DEMO-001",
            "facility_name": "Sample Hospital",
            "reason": "cardiac",
            "one_time_link": "https://example.invalid/one-time",
            "otp": "123456",
        }
    )


def test_sos_template_rejects_patient_data_fields_and_health_terms():
    with pytest.raises(ValueError):
        validate_outbound_template({"patient_name": "Synthetic Person"})
    with pytest.raises(ValueError):
        validate_outbound_template({"reason": "patient diagnosis"})
