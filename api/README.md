# API

FastAPI backend for clinics, staff, the voice agent, and appointment booking.

## Stack

- FastAPI + Pydantic v2
- SQLAlchemy 2 async + asyncpg
- PostgreSQL (local, Supabase, or Neon)
- Alembic migrations
- Staff auth: email/password with Argon2, JWT bearer tokens
- Agent auth: `X-Service-Key`, stored as a SHA-256 hash in `agent_api_keys`

## Local setup

From the repository root:

```bash
docker compose up -d
cp .env.example .env
```

Set these values in `.env`:

```dotenv
SECRET_KEY=<long-random-value>
DATABASE_URL=postgresql+asyncpg://receptionist:<postgres-password>@localhost:5432/receptionist
DEMO_STAFF_PASSWORD=<strong-demo-password>
DEMO_AGENT_KEY=<long-random-agent-key>
```

`DATABASE_URL` is required; the application has no default credentials. Use the same
password as `POSTGRES_PASSWORD` from `.env`.

Then:

```bash
cd api
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed
uv run uvicorn app.main:app --reload --port 8000
```

OpenAPI docs: <http://localhost:8000/docs>

CORS allows the dashboard origin from `DASHBOARD_URL` plus `http://127.0.0.1:3000`.
Private-network preflights are enabled so recent Chrome versions can call a local API
from a local dashboard in development; the origin allow-list still applies.

The seed is idempotent and reads credentials from `.env`:

- Staff email: `DEMO_STAFF_EMAIL` (defaults to `admin@demo-clinic.example.com`)
- Staff password: `DEMO_STAFF_PASSWORD` (required, minimum 12 characters)
- Agent service key: `DEMO_AGENT_KEY` (required, minimum 24 characters)
- Clinic: `Demo Family Clinic` (`Asia/Kolkata`)
- Doctors with weekly availability:
  - Dr. Asha Rao, General Medicine
  - Dr. Vikram Shah, Pediatrics
  - Dr. Meera Iyer, Dermatology

The seed replaces the demo staff password and deactivates the previous demo agent key
when either value changes. Credentials are never written to source code or seed output.

## Cloud Postgres

Use Supabase Mumbai or Neon and put the connection string in `.env`:

```dotenv
DATABASE_URL=postgresql://postgres:<password>@<host>:5432/postgres?sslmode=require
```

The app accepts `postgresql://` or `postgresql+asyncpg://`, converts it for asyncpg,
and extracts `sslmode` into the asyncpg SSL setting. Migrations and tests never use
SQLite because the schema relies on PostgreSQL constraints.

The Alembic migrations enable `btree_gist` and `vector` (pgvector). Supabase and Neon
support both extensions; no manual extension setup is required.

Apply the schema and seed once against the cloud database:

```bash
cd api
uv run alembic upgrade head
uv run python -m scripts.seed
```

## Auth

Staff endpoints require:

```http
Authorization: Bearer <JWT>
```

Get a token from `POST /api/v1/auth/login`. Every staff query is scoped to the
`clinic_id` in the token.

Admin-only routes require `role = "admin"` on the current staff account. Staff can
manage doctors, availability, and appointments but cannot list staff, change roles, or
invite people. An admin cannot deactivate or demote their own account.

Agent-facing booking and slot endpoints accept either a staff JWT or:

```http
X-Service-Key: <service-key>
```

## Staff invitations

Invitations are created by a clinic admin. The API stores only a SHA-256 hash of the
random token, so the raw link is returned once at creation. Invitations expire after 7
days and can be revoked. Accepting one creates an active staff account in the inviting
clinic, marks the invitation as accepted, and returns a normal staff JWT. Email delivery
is not wired yet; the dashboard shows the link for the admin to copy.

The schema change is in Alembic revision `0003_staff_invitations`. Staff deactivation
takes effect on the next request because dependencies load the current staff row, not
just the JWT claims.

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | none | API and database health |
| `POST` | `/api/v1/auth/login` | none | Staff login |
| `GET` | `/api/v1/auth/me` | staff | Current staff user |
| `GET` | `/api/v1/clinic` | staff | Logged-in staff member's clinic |
| `PATCH` | `/api/v1/clinic` | staff | Update clinic details |
| `GET` | `/api/v1/staff` | admin | List staff in the clinic |
| `PATCH` | `/api/v1/staff/{id}` | admin | Update role, name, or active status |
| `GET` | `/api/v1/staff/invitations` | admin | List pending invitations |
| `POST` | `/api/v1/staff/invitations` | admin | Create a 7-day invitation link |
| `DELETE` | `/api/v1/staff/invitations/{id}` | admin | Revoke an invitation |
| `GET` | `/api/v1/invitations/{token}` | none | Preview an invitation |
| `POST` | `/api/v1/invitations/{token}/accept` | none | Set a password and create the account |
| `GET` | `/api/v1/doctors` | staff | List doctors |
| `POST` | `/api/v1/doctors` | staff | Create doctor |
| `GET` | `/api/v1/doctors/{id}` | staff | Get doctor |
| `PATCH` | `/api/v1/doctors/{id}` | staff | Update doctor |
| `DELETE` | `/api/v1/doctors/{id}` | staff | Deactivate doctor |
| `GET` | `/api/v1/doctors/{id}/availability` | staff | List weekly rules |
| `POST` | `/api/v1/doctors/{id}/availability` | staff | Create rule |
| `PATCH` | `/api/v1/doctors/{id}/availability/{rule_id}` | staff | Update rule |
| `DELETE` | `/api/v1/doctors/{id}/availability/{rule_id}` | staff | Delete rule |
| `GET` | `/api/v1/doctors/{id}/time-off` | staff | List time off |
| `POST` | `/api/v1/doctors/{id}/time-off` | staff | Create time off |
| `PATCH` | `/api/v1/doctors/{id}/time-off/{time_off_id}` | staff | Update time off |
| `DELETE` | `/api/v1/doctors/{id}/time-off/{time_off_id}` | staff | Delete time off |
| `GET` | `/api/v1/doctors/{id}/free-slots?date=YYYY-MM-DD` | staff or agent | Computed free slots |
| `POST` | `/api/v1/appointments` | staff or agent | Book appointment |
| `GET` | `/api/v1/appointments?date=...` | staff | Daily appointment list |
| `GET` | `/api/v1/appointments/{id}` | staff | Get appointment |
| `PATCH` | `/api/v1/appointments/{id}/reschedule` | staff or agent | Move appointment |
| `POST` | `/api/v1/appointments/{id}/cancel` | staff or agent | Cancel appointment |
| `GET` | `/api/v1/faqs` | staff | List clinic FAQs (`include_inactive=true` optional) |
| `POST` | `/api/v1/faqs` | staff | Add and embed an FAQ |
| `PATCH` | `/api/v1/faqs/{id}` | staff | Edit and re-embed an FAQ |
| `DELETE` | `/api/v1/faqs/{id}` | staff | Deactivate an FAQ |
| `POST` | `/api/v1/agent/faq/search` | agent | Embed a query and return the closest FAQ |
| `GET` | `/api/v1/callbacks?status=pending` | staff | List callback tasks |
| `PATCH` | `/api/v1/callbacks/{id}` | staff | Mark a callback contacted/done/cancelled |
| `POST` | `/api/v1/agent/callbacks` | agent | Create a callback after a failed transfer |

## FAQ retrieval

`faq_chunks` stores a question embedding plus sentence-aligned answer embeddings per
clinic FAQ, with an HNSW cosine index. The API embeds on the host with the local
`fastembed` model, so no FAQ or caller text goes to an embeddings provider. The agent
endpoint trims answers to two sentences and returns `found=false` below the confidence
threshold. Bulk-load the seed corpus with
`uv run python -m scripts.ingest_faqs --clinic-id <uuid> --replace` and run
`../evals/run_faq_eval.py` against a running API. See [../docs/faq.md](../docs/faq.md).

## Human transfer and callbacks

`PATCH /api/v1/clinic` accepts `front_desk_number`, stored on `clinics` and returned to the
agent by `/api/v1/agent/clinic-config`. The `transfer_to_human` tool dials that number into
the live call with a LiveKit outbound trunk (`LIVEKIT_SIP_OUTBOUND_TRUNK`) and waits
`TRANSFER_RING_TIMEOUT_SECONDS`. If nobody answers, the agent takes a message and posts it
to `/api/v1/agent/callbacks`; staff see it on the dashboard Callbacks page. See
[../docs/telephony.md](../docs/telephony.md).

## Slot rules

Free slots are generated from active `availability_rules` for the requested weekday,
in the clinic timezone. A slot is removed when it:

- starts in the past,
- overlaps active `time_off`, or
- overlaps an appointment whose status is not `cancelled`.

Booking must match a generated slot exactly. This prevents unaligned or overlapping
requests before they reach the database.

Double booking is also blocked at the database level by:

- a partial unique index on `(doctor_id, starts_at)` for non-cancelled appointments,
- a GiST exclusion constraint on `tstzrange(starts_at, ends_at)` for non-cancelled
  appointments.

The `btree_gist` extension is created by the initial migration.

## Patient handling

`POST /api/v1/appointments` accepts either an existing `patient_id` or
`patient_name` + `patient_phone`. With name and phone, the API reuses the patient row
for that clinic and phone number, or creates one.

## Checks

```bash
cd api
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Tests load the repository-root `.env` and use either `TEST_DATABASE_URL` or a local
database built from `POSTGRES_*`. They create a separate `*_test` database, apply the
real Alembic migrations, and truncate between tests. Tests never fall back to the
production `DATABASE_URL`. No database credentials are hardcoded in the application or
test suite.
