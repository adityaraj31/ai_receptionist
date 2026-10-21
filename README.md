# AI Receptionist

A voice AI receptionist for clinics. It answers calls 24x7 in Hindi and English, books
appointments, sends confirmations (WhatsApp/SMS), and reports on every call.

See [AGENTS.md](AGENTS.md) for architecture, conventions, and the working agreement.

## Repository layout

```
/agent       LiveKit agent worker (voice pipeline, tools, prompts)
/api         FastAPI backend (appointments, calls, webhooks, dashboard API)
/dashboard   Next.js analytics dashboard
/infra       Dockerfiles, Postgres init, deploy configs, LiveKit SIP setup
/evals       Transcript and FAQ retrieval eval scripts plus test conversations
/docs        Architecture notes, runbooks
```

The local infrastructure (Postgres + pgvector, Redis) is ready to use. The voice agent
lives in [`/agent`](agent/README.md), the clinic API in [`/api`](api/README.md), and the
admin dashboard in [`/dashboard`](dashboard).

## Prerequisites

- Docker with the Compose plugin (`docker compose version`)
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (for the agent and API)
- Node.js 20+ and npm (for the dashboard)

## Local setup

1. **Configure environment**

   ```bash
   cp .env.example .env
   ```

   Fill in the provider keys you need. The defaults for Postgres and Redis work locally
   as-is. Set `SECRET_KEY`, `DATABASE_URL`, `DEMO_STAFF_PASSWORD`, and `DEMO_AGENT_KEY`
   before running the API or seed. Never commit `.env`.

2. **Start infrastructure**

   ```bash
   docker compose up -d
   ```

   This starts:
   | Service | Image | Host port |
   | --- | --- | --- |
   | `db` | `pgvector/pgvector:pg16` | `5432` |
   | `redis` | `redis:7-alpine` | `6379` |

3. **Verify Postgres and pgvector**

   ```bash
   docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dx"'
   ```

   The output should list the `vector` extension. The clinic schema is managed by
   Alembic from the API module:

   ```bash
   cd api
   uv sync
   uv run alembic upgrade head
   uv run python -m scripts.seed
   ```

   The seed creates a demo clinic, three doctors with availability, a staff login, and
   an agent service key. Load the sample FAQ corpus with the clinic id from the seed:

   ```bash
   uv run python -m scripts.ingest_faqs --clinic-id <uuid> --replace
   ```

   The agent loads clinic config from Postgres and falls back to
   `CLINIC_*` env values only when the database is unavailable or has no active clinic.
   See [api/README.md](api/README.md), [infra/README.md](infra/README.md), and
   [agent/README.md](agent/README.md). For reminders, run the Arq worker in a second
   terminal: `cd api && uv run arq app.workers.main.WorkerSettings`.

4. **Check health and logs**

   ```bash
   docker compose ps
   docker compose logs -f db redis
   ```

5. **Stop or reset**

   ```bash
   docker compose down          # stop containers, keep data
   docker compose down -v       # stop and delete local volumes (destructive)
   ```

## Environment variables

All configuration is via environment variables. `.env.example` documents every variable,
grouped by provider:

- Core, LiveKit, telephony (Exotel/Plivo)
- FAQ embeddings (local model, pgvector thresholds)
- Sarvam (STT/TTS), Deepgram (English fallback)
- LLM, Google Calendar
- WhatsApp/Gupshup, SMS
- Postgres, Redis/Arq
- S3-compatible storage
- Sentry/Langfuse
- Clinic defaults

## Connecting from the host

```
postgresql://receptionist:<local-postgres-password>@localhost:5432/receptionist
redis://localhost:6379/0
```

Use the `POSTGRES_PASSWORD` value from your `.env`; no database credentials are
hardcoded in the application.

## Run the API

```bash
cd api
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed
uv run uvicorn app.main:app --reload --port 8000
```

OpenAPI docs are at <http://localhost:8000/docs>. The seed reads
`DEMO_STAFF_EMAIL`, `DEMO_STAFF_PASSWORD`, and `DEMO_AGENT_KEY` from `.env`; set the
password and key before running it. They are never hardcoded. See
[api/README.md](api/README.md) for endpoints, auth, slot rules, and cloud Postgres setup.

## Run the dashboard

```bash
cd dashboard
npm install
npm run dev
```

Open <http://localhost:3000> and sign in with the staff email and password from your
`.env`. The dashboard authenticates with the staff JWT and calls only the FastAPI
backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`); copy `.env.example`
to `.env.local` to override it. The API must allow the dashboard origin via
`DASHBOARD_URL` (default `http://localhost:3000`).

The dashboard includes login, a first-run setup wizard, doctor management, weekly
availability and time off, a daily appointment list with booking, rescheduling,
cancellation, and free-slot views, an FAQ knowledge base with add/edit/deactivate and
JSON/CSV upload, a Callbacks queue for failed human transfers, a Messaging page for
confirmation/reminder switches and Hindi/English templates, plus admin-only staff
management. Admins can invite
receptionists or other admins, promote or demote staff, and deactivate access. An invite
is a one-time link valid for 7 days; the recipient sets a password and is signed in
immediately. Email delivery is not connected yet, so copy the link and send it manually.
API types are generated from the OpenAPI schema:

```bash
npm run api:types   # requires the API on http://localhost:8000
```

The generated `src/lib/api-schema.d.ts` is committed, so builds do not need the API
running. Run `npm run typecheck` and `npm run build` before deploying.

If Chrome blocks local API requests with a private-network preflight error, keep the API
and dashboard on `http://localhost` origins listed in `DASHBOARD_URL`. The API enables
`allow_private_network=True` for development; this does not bypass the origin allow-list.

## Run the voice agent

```bash
cd agent
uv sync
uv run python -m src.receptionist_agent dev
```

Then open the [LiveKit Agents Playground](https://agents-playground.livekit.io/) and
start a session with agent name `ai-receptionist`. See [agent/README.md](agent/README.md)
for required keys, browser testing, and latency log fields.

## Next steps

1. Call ingestion, transcripts, evals, and dashboard analytics.
2. Post-call jobs and CRM sync.
3. Recordings, transcripts, summaries, and cost tracking after each call.
