# Security and implementation status

This repository contains an initial backend foundation, not a production-ready
medical-record system. Do not use real patient information or connect live
clinical, messaging, or registry providers until the items below are resolved
and independently reviewed.

## Implemented in this foundation

- FastAPI routing with request/validation logs that omit request bodies, query
  strings, path values, and exception text.
- Argon2id password hashing, short-lived access tokens, rotating refresh-token
  hashes, optional encrypted-at-rest TOTP secrets, and persisted idle-session
  expiry.
- Patient/doctor role checks, API-side append-only clinical write patterns,
  consent/date/type filters, emergency-session write denial, and restricted
  doctor record reads requiring sealed per-record consent keys.
- AES-256-GCM record envelopes with record-bound AAD, Argon2id key derivation,
  HMAC search tokens, X25519 sealed-box helpers, BIP39 recovery phrase
  generation, and a 2-of-3 Shamir primitive.
- PostgreSQL tenant RLS policies, an audit mutation trigger, a restricted
  Compose app role, audit hash/signature helpers, and periodic anchor task.
- Local-only Postgres, Redis, MinIO, Celery worker/beat, and status-only
  Streamlit service definitions.

## Not implemented; fail closed

- Patient and doctor client key enrollment, passphrase/recovery flows, per-record
  client encryption integration, doctor key wrapping, and encrypted emergency
  share provisioning.
- The full SOS notification/nominee approval/key-release flow. SOS initiation is
  recorded and audited; confirmation currently returns 503 rather than claiming
  a key was released. The minimum-set timeout flow is also not active.
- ABDM HIU sandbox callbacks, encrypted FHIR transfer, mapper versions, fixture
  replay, and consent revocation callbacks.
- Live NMC/HPR verification, SMS/push/IVR/email adapters, outbound receipts, and
  notification retries.
- Encrypted object storage adapter, upload/OCR pipeline, field-confidence
  drafts, drug fuzzy matching, and merge review.
- Full record amendments, medication stop/amendment workflows, account
  erasure, and the complete synthetic five-year demo seed.

## Required security follow-up

1. The audit signature helper currently produces a domain-separated service
   signature derived from `SESSION_SECRET`; this is not an actor-held Ed25519
   signature. Replace it with signed client audit assertions and a separately
   managed verifier key before production.
2. Audit anchoring and whole-chain verification need a least-privilege verifier
   path that can read the complete chain without bypassing tenant RLS for normal
   API requests.
3. Hard revoke is queued but not executable as specified: rewrapping record
   DEKs requires a cryptographic design that works while the patient's MK is
   unavailable. The current worker does not claim the rotation succeeded.
4. TOTP encryption is derived from `SESSION_SECRET`; rotating that secret
   requires a planned re-encryption procedure. Use a dedicated key-management
   integration for production.
5. The local Compose role separation is a development reference. Production
   roles, TLS, PostgreSQL encryption-at-rest, backup/restore, retention,
   monitoring, and incident procedures still need configuration and review.
6. Although the API defines an emergency scope filter, it does not yet implement
   release of the EAK-derived, single-use doctor key. No emergency-mode record
   content should be considered available until that ceremony is implemented.

## Trust boundary

The intended model keeps passphrases, KEKs, and master keys on patient devices.
Only wrapped keys, ciphertext, nonces, AAD, and sealed consent keys should reach
the API. The cryptography module documents query-equality and term-frequency
leakage from HMAC search tokens; searchable encryption is not zero-knowledge.
Losing both passphrase and recovery code is unrecoverable by design.
