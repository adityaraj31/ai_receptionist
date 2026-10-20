# AI Receptionist

A voice AI receptionist for clinics. It answers calls 24x7 in Hindi and English, books
appointments, sends confirmations (WhatsApp/SMS), and reports on every call.

See [AGENTS.md](AGENTS.md) for architecture, conventions, and the working agreement.

## Repository layout

```
/agent       LiveKit agent worker (voice pipeline, tools, prompts)
/api         FastAPI backend (appointments, calls, webhooks, dashboard API)
/dashboard   Next.js analytics dashboard
/infra       Dockerfiles, Postgres init, deploy configs
/evals       Transcript evaluation scripts and test conversations
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
   an agent service key. The agent loads clinic config from Postgres and falls back to
   `CLINIC_*` env values only when the database is unavailable or has no active clinic.
   See [api/README.md](api/README.md), [infra/README.md](infra/README.md), and
   [agent/README.md](agent/README.md).

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

Open <http://localhost:3000> and sign in with the demo staff credentials. The dashboard
authenticates with the staff JWT and lets you manage doctors, weekly availability, time
off, free slots, and appointments. It calls the API at `NEXT_PUBLIC_API_URL`, which
defaults to `http://localhost:8000`; copy `.env.example` to `.env.local` to override it.
The API must allow the dashboard origin via `DASHBOARD_URL` (default
`http://localhost:3000`). Use `npm run typecheck` and `npm run build` before deploying.

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

1. Wire the agent tools to the API (slots, booking, reschedule, cancel).
2. Call ingestion, transcripts, evals, and dashboard analytics.
3. FAQ RAG with pgvector, WhatsApp/SMS confirmations, and post-call jobs.
4. Recordings, transcripts, summaries, and cost tracking after each call.
