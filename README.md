**# QuikPatient**



**Patient-owned health records with a consent model that still works when the patient is unconscious.**



**> ⚠️ Prototype. Synthetic data only. Not a medical device.**



**---**



**## The problem**



**Indian health records are fragmented across hospitals and labs, and every consent system assumes a conscious patient. In trauma the patient cannot tap "approve" — so clinicians either get nothing, or systems quietly grant everything.**



**## The approach**



**| Role | Can do |**

**|---|---|**

**| Patient | Owns the keys, reads everything, grants and revokes scoped access, adds \*self-reported\* notes |**

**| Doctor | Reads only within a granted scope; writes and attests clinical records |**

**| Nominee | Approves time-boxed emergency access on the patient's behalf |**



**Three invariants:**



**- Patients never write clinical data — self-reported entries are permanently labelled**

**- Nothing is deleted; corrections are append-only amendments**

**- Emergency access is read-only, scoped, time-boxed and logged**



**---**



**## Security design**



**\*\*Envelope encryption.\*\* The passphrase and master key never reach the server in plaintext:**



**```**

**passphrase ──Argon2id──▶ KEK ──wraps──▶ master key ──▶ per-record DEK (AES-256-GCM)**

**```**



**\*\*AAD binding.\*\* Each ciphertext is bound to `record\_id | patient\_id | record\_type | record\_date | key\_version`. Move it to another patient's row and decryption fails loudly instead of silently returning wrong data.**



**\*\*Per-consent key sealing.\*\* Granting access seals that record's DEK to the doctor's X25519 key, so revocation is a cryptographic fact rather than a UI flag.**



**\*\*Shamir 2-of-3 emergency key\*\* — one share on the server, one sealed to each nominee, one printed on the patient's emergency card. Any single share is useless; any two reconstruct.**



**\*\*Hash-chained audit log\*\*, append-only at three layers: the module never issues `UPDATE`/`DELETE`, a Postgres trigger raises on attempts, and the app role has those rights revoked. `/audit/verify` re-walks the chain and reports the first broken link.**



**---**



**## Emergency access (SOS)**



**```**

**Doctor declares emergency (reason + facility, registration checked)**

&#x20; **→ nominees notified with OTP**

&#x20; **→ approved      ──▶ scoped read-only grant, server-side TTL**

&#x20; **→ no response   ──▶ MINIMUM SET only**

&#x20; **→ patient gets a high-severity alert + full access trail**

**```**



**Scope is capped server-side to diagnoses, prescriptions, discharge summaries and diagnostic reports. Outbound messages carry no clinical content. Writes under an emergency session return `403 emergency\_mode\_is\_read\_only` and are logged.**



**---**



**## Honest limitations**



**- \*\*Searchable encryption leaks query equality and term frequency.\*\* Deterministic tokens let the server infer which records share terms. Encrypted search, not zero-knowledge search — a deliberate trade for usable clinical search.**

**- \*\*Guardian / minor consent is not implemented\*\* — returns `403 guardian\_flow\_not\_implemented` rather than doing something wrong silently.**

**- A compromised session is a compromised record set, since decryption happens in-session.**

**- ABDM, NMC and SMS run mocked (`MOCK\_MODE=true`).**



**---**



**## Stack**



**FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Redis · Celery · `cryptography` (AES-GCM) · PyNaCl (X25519/Ed25519) · argon2-cffi · Streamlit · Docker Compose**



**---**



**## Run locally**



**```bash**

**git clone https://github.com/rethink-07/Quikpatient.git**

**cd Quikpatient**

**cp .env.example .env          # Windows: copy .env.example .env**



**docker compose up --build api**

**docker compose exec api alembic upgrade head**

**```**



**API docs at http://localhost:8000/docs**



**> Note: the API source currently sits at `backend/artifacts/api-server/`. `docker-compose.yml` points at it via an explicit `dockerfile:` path — flattening this into `backend/` is a planned cleanup.**



**## Repo layout**



**```**

**backend/artifacts/api-server/**

&#x20; **app/{main,config,models,routes,crypto,audit,auth}**

&#x20; **migrations/            alembic.ini**

&#x20; **Dockerfile             requirements.txt**

**frontend/**

**docker-compose.yml       .env.example**

**```**

