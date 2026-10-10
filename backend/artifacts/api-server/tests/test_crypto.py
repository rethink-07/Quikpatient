from datetime import date

import pytest

from app.crypto import (
    decrypt_record,
    encrypt_record,
    record_aad,
    shamir_recover_2_of_3,
    shamir_split_2_of_3,
)


def test_record_envelope_round_trips_and_binds_aad():
    master_key = b"k" * 32
    payload = {"type": "synthetic", "value": 42}
    record_date = date(2025, 4, 2)
    envelope = encrypt_record(
        payload, master_key, "r-1", "p-1", "diagnosis", record_date, 1
    )
    assert decrypt_record(envelope, master_key) == payload
    envelope["aad"] = record_aad("r-2", "p-1", "diagnosis", record_date, 1)
    with pytest.raises(Exception):
        decrypt_record(envelope, master_key)


def test_any_two_of_three_shamir_shares_reconstruct_secret():
    secret = b"synthetic-emergency-key"
    a, b, c = shamir_split_2_of_3(secret)
    assert shamir_recover_2_of_3(a, b) == secret
    assert shamir_recover_2_of_3(a, c) == secret
    assert shamir_recover_2_of_3(b, c) == secret


def test_shamir_rejects_duplicate_and_malformed_shares():
    a, b, _ = shamir_split_2_of_3(b"demo")
    with pytest.raises(ValueError):
        shamir_recover_2_of_3(a, a)
    with pytest.raises(ValueError):
        shamir_recover_2_of_3(b"\x01", b"\x02")
