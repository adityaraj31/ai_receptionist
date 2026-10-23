# Deploy with Docker

The application runs as four containers behind Postgres, Redis, and S3-compatible
storage. For a small clinic, Docker Compose on one VM is enough. For multiple hosts,
run the same images on a container platform and keep the external services managed.

```
Internet
  -> reverse proxy (TLS)
     -> dashboard :3000
     -> API :8000
  -> LiveKit Cloud (SIP + rooms)
     -> agent worker :8081
  -> API / Arq worker
     -> Postgres + pgvector
     -> Redis
     -> S3-compatible recordings bucket
```

The API, Arq worker, dashboard, and agent all use the images in
[`../infra/docker`](../infra/docker). The root [`docker-compose.yml`](../docker-compose.yml)
starts Postgres and Redis by default and runs the application with the `app` profile.

## What production needs

- A Linux VM or container host. Start with 4 vCPU / 8 GB for API, dashboard, worker, and
  one busy agent process; measure before sizing.
- Docker Engine 24+ with Compose v2.
- A domain and TLS certificate for the dashboard and API.
- Network access to LiveKit Cloud, Sarvam, the LLM provider, and the WhatsApp/SMS
  provider.
- Postgres 16 with `pgvector` and `btree_gist`. The Compose file includes this database.
- Redis 7 for Arq jobs and reminders.
- An S3-compatible bucket for recordings. Keep it private and encrypted.
- Provider keys for LiveKit, Sarvam, LLM, and messaging.

## 1. Configure the environment

```bash
cp .env.example .env
```

Set at least:

- `SECRET_KEY` (generate a long random value)
- `POSTGRES_PASSWORD`
- `DATABASE_URL` only when using an external Postgres instance
- `REDIS_URL` only when using an external Redis instance
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_AGENT_NAME`
- `SARVAM_API_KEY`, `LLM_API_KEY`
- `AGENT_API_KEY`, which must match `DEMO_AGENT_KEY` when seeding
- `NEXT_PUBLIC_API_URL`, for example `https://api.clinic.example.com`
- `S3_*` recording settings and `RECORDING_ENABLED`
- WhatsApp/SMS provider settings

Never commit `.env`. The Compose app profile overrides `DATABASE_URL` and `REDIS_URL`
to use the bundled `db` and `redis` services. For managed Postgres and Redis, add a
Compose override that removes those two `environment` entries, or run the API/worker
containers with the managed URLs directly.

## 2. Build and start

```bash
docker compose --profile app up -d --build
docker compose --profile app logs -f api agent dashboard arq
```

The dashboard's `NEXT_PUBLIC_API_URL` is baked in at build time. Rebuild the dashboard
when the public API URL changes.

## 3. Run migrations and seed

```bash
docker compose --profile app run --rm api alembic upgrade head
docker compose --profile app run --rm api python -m scripts.seed
```

The seed is demo data only. Skip it for a real clinic, or change the demo credentials
before the first login.

## 4. Put a reverse proxy in front

Terminate TLS at Caddy, nginx, or the platform load balancer. Do not expose the agent
metrics port or the database publicly. Example Caddy config:

```caddyfile
api.clinic.example.com {
    reverse_proxy 127.0.0.1:8000
}

app.clinic.example.com {
    reverse_proxy 127.0.0.1:3000
}
```

Allow inbound traffic only on `80/443`, and restrict SSH to the operator network. The
agent worker connects outbound to LiveKit for job dispatch; port `8081` is only for
health and metrics and should not be public. See [`telephony.md`](telephony.md).

## 5. Verify

```bash
curl -fsS https://api.clinic.example.com/health
curl -fsSI https://app.clinic.example.com/login
```

Then dial the clinic number and confirm:

- the agent joins the LiveKit room
- the greeting includes the AI disclosure and recording consent
- a booking appears in the dashboard with the correct name, date, and time
- the caller is transferred to the front desk when they ask for a human
- a recording is created only after clear consent

## Operations

- **Logs:** `docker compose logs -f api agent dashboard arq`
- **Restart one service:** `docker compose --profile app restart api`
- **Update:** pull the new code, run `docker compose --profile app build`, then
  `docker compose --profile app up -d`, then run Alembic.
- **Rollback:** check out the previous commit, rebuild, and start again. Keep the
  previous database backup until the new version has been verified.
- **Backups:** run `pg_dump` on a schedule, encrypt the dump, and test a restore
  monthly. Keep backups in India for DPDP compliance.
- **Recording retention:** apply an object-storage lifecycle rule that matches the
  clinic's consent and retention policy.
- **Scaling:** one host can run one agent container. For more concurrency, run more
  agent containers on more hosts and set `AGENT_MAX_ACTIVE_CALLS` so each worker
  admits calls up to its measured capacity. LiveKit distributes jobs across connected
  workers.
- **Load testing:** use `agent/scripts/load_test_calls.py` before increasing traffic.
  Watch first-audio latency and active calls, not CPU alone.

## Security checklist

- TLS everywhere; no plain HTTP for the dashboard or API.
- Secrets only in the environment or a secret manager, never in the image or repo.
- Private Postgres, Redis, and recording bucket; no public database port.
- Separate clinic API keys and staff accounts.
- Recording consent enforced by the tool, not just the prompt.
- Backups encrypted and access limited to the operator.
