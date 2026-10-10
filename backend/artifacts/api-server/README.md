# QuikPatient API

FastAPI backend foundation for QuikPatient. The API is mounted under `/api`.
OpenAPI is available at `/api/openapi.json`; interactive docs are at
`/api/docs`.

## Local development

The API starts without a database so its health endpoint remains available.
Database-backed routes fail explicitly with `database_unavailable` until a
PostgreSQL URL is configured.

```sh
cd artifacts/api-server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --no-access-log
```

Use `docker compose up --build` for the local service stack. Copy `.env.example`
to `.env`, replace every local-only password with random values, and keep `.env`
out of version control. The Compose database uses a restricted `qp_app` runtime
role; the one-shot `migrate` service uses the admin role.

## API capabilities

- Patient and doctor login, TOTP verification, refresh/logout, mock doctor
  verification, patient profile reads/updates, and nominee listing.
- Patient consent grants/revocation and per-record sealed DEK grants.
- Doctor encounter unlock, consent-scoped encrypted record reads, and
  append-only encrypted prescription creation.
- Doctor SOS initiation with Redis rate limits and audited state; key release
  and nominee approval fail closed until the emergency ceremony is configured.
- Audit listing, notification/job status reads, and mock
  ABDM sync job creation.

The source schema includes the wider QuikPatient domain model. See
`SECURITY_STATUS.md` for unavailable endpoints and cryptographic prerequisites;
database presence does not imply that unfinished workflows are enabled.
Global audit verification fails closed until a verifier path can inspect the
whole chain without bypassing tenant RLS.

## Migrations and tests

```sh
cd artifacts/api-server
alembic upgrade head
pytest tests
```

PostgreSQL is required for migrations and RLS; SQLite is intentionally not
treated as a security-equivalent test database.
