"""QuikPatient cryptographic primitives.

This module is a reference for client-side record encryption and server-side
envelope storage. The API must never accept a patient passphrase, KEK, or MK.
HMAC search tokens disclose query equality and term frequency; this is not
zero-knowledge search.
"""

import hashlib
import hmac
import json
import os
from datetime import date
from typing import Any

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from mnemonic import Mnemonic
from nacl.public import PrivateKey, SealedBox

ARGON_MEMORY_KIB = 64 * 1024
ARGON_TIME_COST = 3
ARGON_PARALLELISM = 4
EMERGENCY_RECORD_TYPES = {
    "diagnosis",
    "discharge_summary",
    "diagnostic_report",
}


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def derive_kek(passphrase: str, salt: bytes) -> bytes:
    if len(salt) < 16:
        raise ValueError("KDF salt must contain at least 16 bytes")
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=ARGON_TIME_COST,
        memory_cost=ARGON_MEMORY_KIB,
        parallelism=ARGON_PARALLELISM,
        hash_len=32,
        type=Type.ID,
    )


def _seal(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    if len(key) != 32:
        raise ValueError("AES-256-GCM keys must be 32 bytes")
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def _open(key: bytes, sealed: bytes, aad: bytes = b"") -> bytes:
    if len(sealed) < 28:
        raise ValueError("Invalid AES-GCM envelope")
    return AESGCM(key).decrypt(sealed[:12], sealed[12:], aad)


def encrypt_server_secret(value: str, application_secret: str, context: str) -> bytes:
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=f"quikpatient/server-field/{context}/v1".encode("utf-8"),
    ).derive(application_secret.encode("utf-8"))
    return _seal(key, value.encode("utf-8"), context.encode("utf-8"))


def decrypt_server_secret(envelope: bytes, application_secret: str, context: str) -> str:
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=f"quikpatient/server-field/{context}/v1".encode("utf-8"),
    ).derive(application_secret.encode("utf-8"))
    return _open(key, envelope, context.encode("utf-8")).decode("utf-8")


def create_patient_key_bundle(passphrase: str) -> dict[str, bytes | str | int]:
    """Client-side bootstrap. Call only on the user's device, never from an API route."""
    master_key = os.urandom(32)
    search_key = os.urandom(32)
    salt = os.urandom(16)
    kek = derive_kek(passphrase, salt)
    recovery_phrase = Mnemonic("english").generate(strength=128)
    recovery_salt = os.urandom(16)
    recovery_kek = derive_kek(recovery_phrase, recovery_salt)
    return {
        "kdf_salt": salt,
        "wrapped_master_key": _seal(kek, master_key),
        "recovery_wrapped_master_key": recovery_salt
        + _seal(recovery_kek, master_key),
        "public_key": bytes(PrivateKey.generate().public_key),
        "enc_private_key": b"",  # Client encrypts its private key under the KEK.
        "search_key_wrapped": _seal(master_key, search_key),
        "eak_share_a_encrypted": b"",  # Populated by the emergency key ceremony.
        "recovery_code": recovery_phrase,
        "key_version": 1,
    }


def record_aad(
    record_id: str, patient_id: str, record_type: str, record_date: date, key_version: int
) -> bytes:
    return "||".join(
        [record_id, patient_id, record_type, record_date.isoformat(), str(key_version)]
    ).encode("utf-8")


def encrypt_record(
    payload: dict[str, Any],
    master_key: bytes,
    record_id: str,
    patient_id: str,
    record_type: str,
    record_date: date,
    key_version: int,
) -> dict[str, bytes]:
    if len(master_key) != 32:
        raise ValueError("Master key must be 32 bytes")
    aad = record_aad(record_id, patient_id, record_type, record_date, key_version)
    dek = os.urandom(32)
    ciphertext = _seal(dek, canonical_json(payload), aad)
    return {
        "ciphertext": ciphertext[12:],
        "nonce": ciphertext[:12],
        "aad": aad,
        "wrapped_dek": _seal(master_key, dek),
    }


def decrypt_record(
    encrypted: dict[str, bytes], master_key: bytes
) -> dict[str, Any]:
    dek = _open(master_key, encrypted["wrapped_dek"])
    plaintext = AESGCM(dek).decrypt(
        encrypted["nonce"], encrypted["ciphertext"], encrypted["aad"]
    )
    return json.loads(plaintext)


def search_token(search_key: bytes, term: str) -> bytes:
    normalized = " ".join(term.casefold().split())
    return hmac.new(search_key, normalized.encode("utf-8"), hashlib.sha256).digest()


def sealed_box_encrypt(public_key: bytes, plaintext: bytes) -> bytes:
    from nacl.public import PublicKey

    return SealedBox(PublicKey(public_key)).encrypt(plaintext)


def sealed_box_decrypt(private_key: bytes, ciphertext: bytes) -> bytes:
    return SealedBox(PrivateKey(private_key)).decrypt(ciphertext)


def shamir_split_2_of_3(secret: bytes) -> tuple[bytes, bytes, bytes]:
    """Split a byte string into three GF(256) shares; any two reconstruct it."""
    if not secret:
        raise ValueError("Secret cannot be empty")
    slope = os.urandom(len(secret))
    shares = []
    for x in (1, 2, 3):
        shares.append(bytes([x]) + bytes(s ^ _gf_mul(a, x) for s, a in zip(secret, slope)))
    return shares[0], shares[1], shares[2]


def shamir_recover_2_of_3(share_a: bytes, share_b: bytes) -> bytes:
    if (
        len(share_a) < 2
        or len(share_b) != len(share_a)
        or share_a[0] == share_b[0]
        or share_a[0] not in (1, 2, 3)
        or share_b[0] not in (1, 2, 3)
    ):
        raise ValueError("Invalid Shamir shares")
    x1, x2 = share_a[0], share_b[0]
    denominator = _gf_mul(x1 ^ x2, 1)  # Addition and subtraction are XOR in GF(256).
    scale = _gf_div(x1, denominator)
    return bytes(a ^ _gf_mul(a ^ b, scale) for a, b in zip(share_a[1:], share_b[1:]))


def _gf_mul(a: int, b: int) -> int:
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a & 0x100:
            a ^= 0x11B
    return result


def _gf_pow(value: int, exponent: int) -> int:
    result = 1
    while exponent:
        if exponent & 1:
            result = _gf_mul(result, value)
        value = _gf_mul(value, value)
        exponent >>= 1
    return result


def _gf_div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("Division by zero in GF(256)")
    return _gf_mul(a, _gf_pow(b, 254))
