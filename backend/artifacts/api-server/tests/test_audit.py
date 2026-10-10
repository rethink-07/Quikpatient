import hashlib

from app.crypto import canonical_json


def test_audit_hash_is_stable_for_canonical_entry():
    first = {"action": "record_read", "scope": {"type": "diagnosis"}, "id": "synthetic"}
    second = {"id": "synthetic", "scope": {"type": "diagnosis"}, "action": "record_read"}
    head = bytes.fromhex("00" * 32)
    assert hashlib.sha256(head + canonical_json(first)).digest() == hashlib.sha256(
        head + canonical_json(second)
    ).digest()
