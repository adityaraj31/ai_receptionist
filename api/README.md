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
DATABASE_URL=postgresql+asyncpg://receptionist:receptionist_dev_password@localhost:5432/receptionist
```

Then:

```bash
cd api
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed
uv run uvicorn app.main:app --reload --port 8000
```

OpenAPI docs: <http://localhost:8000/docs>

The seed is idempotent and creates:

- Clinic: `Demo Family Clinic` (`Asia/Kolkata`)
- Staff: `admin@demo-clinic.example.com` / `DemoClinic123!`
- Agent service key: `demo-agent-key-change-me`
- Doctors with weekly availability:
  - Dr. Asha Rao, General Medicine
  - Dr. Vikram Shah, Pediatrics
  - Dr. Meera Iyer, Dermatology

Change the demo password and service key before any shared or production deployment.

## Cloud Postgres

Use Supabase Mumbai or Neon and put the connection string in `.env`:

```dotenv
DATABASE_URL=postgresql://postgres:<password>@<host>:5432/postgres?sslmode=require
```

The app accepts `postgresql://` or `postgresql+asyncpg://`, converts it for asyncpg,
and extracts `sslmode` into the asyncpg SSL setting. Migrations and tests never use
SQLite because the schema relies on PostgreSQL constraints.

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

Agent-facing booking and slot endpoints accept either a staff JWT or:

```http
X-Service-Key: <service-key>
```

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | none | API and database health |
| `POST` | `/api/v1/auth/login` | none | Staff login |
| `GET` | `/api/v1/auth/me` | staff | Current staff user |
| `GET` | `/api/v1/clinic` | staff | Logged-in staff member's clinic |
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
| `DELETE` | `/api/v1/doctors/{id}/time-off/{time_off_id}` | staff | Delete time off |
| `GET` | `/api/v1/doctors/{id}/free-slots?date=YYYY-MM-DD` | staff or agent | Computed free slots |
| `POST` | `/api/v1/appointments` | staff or agent | Book appointment |
| `GET` | `/api/v1/appointments?date=...` | staff | Daily appointment list |
| `GET` | `/api/v1/appointments/{id}` | staff | Get appointment |
| `PATCH` | `/api/v1/appointments/{id}/reschedule` | staff or agent | Move appointment |
| `POST` | `/api/v1/appointments/{id}/cancel` | staff or agent | Cancel appointment |

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
uv run pytest
```

Tests create a separate `receptionist_test` database, apply the real Alembic migration,
and truncate between tests. Override the test server with `TEST_DATABASE_URL` if needed.
