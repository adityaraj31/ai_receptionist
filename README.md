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

The local infrastructure (Postgres + pgvector, Redis) is ready to use, and the first
agent slice is implemented in [`/agent`](agent/README.md). Other modules are not
scaffolded yet.

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
   as-is. Never commit `.env`.

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

   The output should list the `vector` extension.

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
postgresql://receptionist:receptionist_dev_password@localhost:5432/receptionist
redis://localhost:6379/0
```

Change the defaults in `.env` before using anything beyond local development.

## Run the voice agent

```bash
cd agent
uv sync
uv run python src/receptionist_agent.py dev
```

Then open the [LiveKit Agents Playground](https://agents-playground.livekit.io/) and
start a session with agent name `ai-receptionist`. See [agent/README.md](agent/README.md)
for required keys, browser testing, and latency log fields.

## Next steps

1. Agent tools: calendar booking, FAQ, human transfer.
2. API slice: appointments, calls, webhooks, dashboard endpoints.
3. Dashboard slice: call list, transcripts, analytics.
4. FAQ RAG, WhatsApp/SMS, post-call jobs and evals.
