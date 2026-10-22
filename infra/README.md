# Infra

Dockerfiles, Postgres init, AWS deployment, and telephony setup.

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

## AWS Mumbai (ECS Fargate)

The production stack is Terraform in [`aws/terraform`](aws/terraform). It creates the
VPC, ALB, ECS services, RDS Postgres + pgvector, ElastiCache Redis, S3 recordings,
Secrets Manager values, and active-call autoscaling for the agent.

- Deployment runbook: [`../docs/deployment.md`](../docs/deployment.md)
- RDS migration: [`../docs/rds-migration.md`](../docs/rds-migration.md)
- Build/push helper: [`aws/deploy.sh`](aws/deploy.sh)
- Active-call metric sidecar: [`aws/agent-metrics/`](aws/agent-metrics)

The agent sidecar reads `GET :8081/worker`, publishes `ActiveCalls` to
`AIReceptionist/Agent` via CloudWatch EMF, and ECS target tracking keeps average active
calls per task at `agent_target_calls_per_task`. The worker's own admission control uses
`AGENT_MAX_ACTIVE_CALLS`, which must stay above the scaling target.

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
