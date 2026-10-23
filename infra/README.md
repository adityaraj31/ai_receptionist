# Infra

Dockerfiles, Postgres init, telephony setup, and an optional metrics sidecar.

## Local stack

The local `docker-compose.yml` lives at the repository root so `docker compose up -d`
works from the project directory. It starts Postgres/pgvector and Redis by default.

To run the application containers too:

```bash
docker compose --profile app up -d --build
docker compose --profile app logs -f api agent dashboard arq
```

The app profile uses `.env` and exposes API `:8000`, dashboard `:3000`, and the agent
worker HTTP endpoint `:8081`. Build definitions are in [`docker/`](docker):

- [`docker/api.Dockerfile`](docker/api.Dockerfile) - API, also used for the Arq worker
- [`docker/agent.Dockerfile`](docker/agent.Dockerfile) - LiveKit voice worker
- [`docker/dashboard.Dockerfile`](docker/dashboard.Dockerfile) - Next.js standalone

The dashboard bakes `NEXT_PUBLIC_API_URL` at build time. Rebuild when the public API URL
changes.

## Database schema

The application schema is managed by Alembic in [`../api/alembic`](../api/alembic).
Do not add ad-hoc SQL migrations. From the repository root:

```bash
cd api
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed   # optional demo data
```

The first migration creates:

- `clinics`, `staff_users`, `agent_api_keys`
- `doctors`, `availability_rules`, `time_off`
- `patients`, `appointments`
- `calls`, `transcripts`, `call_events`, `evaluations`

It also enables `btree_gist` for appointment/time-off exclusion constraints and
`vector` (pgvector) for FAQ retrieval.

To apply schema changes against a cloud database, set `DATABASE_URL` in `.env` and run
the same `uv run alembic upgrade head` command.

## Deployment

Build the images in [`docker/`](docker) and run them on a container host or
orchestrator. The reference single-host deployment is the root
[`docker-compose.yml`](../docker-compose.yml) `app` profile. See
[`../docs/deployment.md`](../docs/deployment.md) for the full runbook and
[`../docs/postgres-migration.md`](../docs/postgres-migration.md) for moving to managed
Postgres.

The application needs Postgres 16 + pgvector, Redis, an S3-compatible recordings bucket,
and TLS in front of the API and dashboard.

## Optional active-call metric sidecar

[`aws/agent-metrics/`](aws/agent-metrics) reads `GET :8081/worker` and publishes
`ActiveCalls` through CloudWatch EMF. It is optional; use it only when the container
platform scales on a custom active-call metric. Keep `AGENT_MAX_ACTIVE_CALLS` above the
scaling target so the worker admits calls up to the intended capacity.

Load test against a deployed worker:

```bash
cd agent
uv run python scripts/load_test_calls.py --calls 10 --duration 30
```

## Telephony (LiveKit SIP)

Scripts to connect an Exotel or Plivo number to LiveKit SIP live in
[`livekit-sip/`](livekit-sip). See [`../docs/telephony.md`](../docs/telephony.md) for the
full runbook.

```bash
infra/livekit-sip/setup-telephony.sh --dry-run   # print config
infra/livekit-sip/setup-telephony.sh             # create trunk + dispatch rule
infra/livekit-sip/teardown-telephony.sh          # remove them
```
