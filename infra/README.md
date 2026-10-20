# Infra

Dockerfiles, Postgres init, and deployment configs.

The local `docker-compose.yml` lives at the repository root so `docker compose up -d`
works from the project directory. It mounts `infra/postgres/init.sql` (pgvector) into
the Postgres entrypoint.

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

It also enables `btree_gist` for the appointment and time-off exclusion constraints
and `vector` (pgvector) for future FAQ retrieval.

To apply schema changes against a cloud database, set `DATABASE_URL` in `.env` and run
the same `uv run alembic upgrade head` command.

## Module Dockerfiles

Module Dockerfiles will be added here once deployment is wired:

- `docker/api.Dockerfile`
- `docker/agent.Dockerfile`
- `docker/dashboard.Dockerfile`
