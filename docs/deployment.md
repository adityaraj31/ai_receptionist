# Deploy to AWS Mumbai (ECS Fargate)

Production topology for the receptionist. Everything runs in `ap-south-1` (Mumbai)
unless a provider requires otherwise.

```
Route 53 / external DNS
  -> ALB (public subnets, HTTPS)
     -> api service         (FastAPI, Cloud Map: api.<project>.local:8000)
     -> dashboard service   (Next.js, port 3000)
  -> ECS Fargate
     -> arq worker          (post-call jobs, reminders)
     -> agent worker(s)     (LiveKit worker, HTTP 8081)
        + metrics sidecar   (EMF -> CloudWatch ActiveCalls)
  -> RDS Postgres 16 + pgvector (private subnets)
  -> ElastiCache Redis 7 (TLS, private subnets)
  -> S3 recordings bucket (private, encrypted, lifecycle expiry)
```

Terraform lives in [`../infra/aws/terraform`](../infra/aws/terraform). Dockerfiles are in
[`../infra/docker`](../infra/docker). The build/push helper is
[`../infra/aws/deploy.sh`](../infra/aws/deploy.sh).

The API and Arq worker use the ECS task role for S3 reads, writes, and presigned
downloads. Only the agent receives the static egress access key, because LiveKit egress
uploads the recording from outside the task.

## Why ECS

A single VM is cheaper for a demo, but the agent has to add capacity when concurrent
calls rise. ECS gives us a service-level desired count, health checks, rolling deploys,
and Application Auto Scaling. The agent's admission control and autoscaling policy both
use **active calls**, not CPU:

- `AgentServer` reports `active_jobs` on `GET :8081/worker`.
- The metrics sidecar samples that endpoint every 15 s and emits `ActiveCalls` through
  CloudWatch Embedded Metric Format (EMF).
- ECS target tracking keeps **average active calls per task** at
  `agent_target_calls_per_task` (default 6).
- `AGENT_MAX_ACTIVE_CALLS` (default 8) caps each task. Keep it above the scaling target
  so new calls can still arrive and trigger scale-out.

The worker load function is also active-call based when `AGENT_MAX_ACTIVE_CALLS` is set,
so the default CPU load heuristic does not mark a task full before the autoscaler sees
the call volume.

## Prerequisites

- AWS account with permissions for VPC, ECS, ECR, RDS, ElastiCache, S3, IAM, ALB,
  CloudWatch, Secrets Manager, and Application Auto Scaling.
- Terraform 1.9+ and AWS provider credentials (`AWS_PROFILE` or role).
- Docker with Buildx.
- AWS CLI v2.
- Two DNS names, for example `api.clinic.example.com` and `app.clinic.example.com`.
- An ACM certificate in `ap-south-1` covering both names. HTTP-only is possible for a
  smoke test but is not acceptable for real caller data.
- LiveKit, Sarvam, and LLM API keys.
- A strong `agent_api_key`. It must equal `DEMO_AGENT_KEY` when seeding the database.

## 1. Configure Terraform

```bash
cd infra/aws/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars. Never commit it.
```

Set at minimum:

- `api_hostname`, `dashboard_hostname`, and `acm_certificate_arn`
- `agent_api_key`, `demo_staff_password`
- `livekit_url`, `livekit_api_key`, `livekit_api_secret`
- `sarvam_api_key`, `llm_api_key`
- `agent_target_calls_per_task` and `agent_max_count` after load testing

For shared state, copy [`backend.tf.example`](../infra/aws/terraform/backend.tf.example)
to `backend.tf`, create the bucket/table, and run `terraform init -migrate-state`. Never
commit state or `.tfvars` files.

## 2. Create the ECR repositories first

The first full apply cannot start healthy ECS tasks until images exist. Create only the
repositories first:

```bash
terraform init
terraform apply -target='aws_ecr_repository.app'
```

Then load the public API URL into the environment for the dashboard build:

```bash
export NEXT_PUBLIC_API_URL="https://api.clinic.example.com"
```

## 3. Build and push images

```bash
AWS_REGION=ap-south-1 IMAGE_TAG="$(git rev-parse --short HEAD)" \
  ../deploy.sh
```

The script builds `linux/amd64` images for:

| Image | Context | Purpose |
| --- | --- | --- |
| `ai-receptionist/api` | `api/` | API and Arq worker |
| `ai-receptionist/agent` | `agent/` | LiveKit voice worker |
| `ai-receptionist/dashboard` | `dashboard/` | Next.js standalone server |
| `ai-receptionist/agent-metrics` | `infra/aws/agent-metrics/` | Active-call EMF sidecar |

`NEXT_PUBLIC_API_URL` is baked into the dashboard at build time. Rebuild the dashboard if
the API hostname changes.

## 4. Apply the stack

```bash
terraform apply -var="image_tag=$(git rev-parse --short HEAD)"
```

Terraform creates the VPC, NAT gateway, ALB, RDS, Redis, S3, secrets, ECS services, and
the agent autoscaling policy. Point DNS at the `alb_dns_name` output, or set
`route53_zone_id` to let Terraform create alias records.

## 5. Run migrations and seed

The API task definition already has the database URL secret. Run one-off tasks in the
private subnets using the outputs:

```bash
CLUSTER="$(terraform output -raw ecs_cluster_name)"
TASK_DEF="$(terraform output -raw api_task_definition_arn)"
SUBNETS="$(terraform output -json private_subnet_ids | jq -r 'join(",")')"
SG="$(terraform output -raw app_security_group_id)"

aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEF" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'
```

Run the seed once (demo data only; skip it for a real clinic):

```bash
# Repeat aws ecs run-task with:
# "command":["python","-m","scripts.seed"]
```

The seed uses `DEMO_STAFF_EMAIL`, `DEMO_STAFF_PASSWORD`, and `DEMO_AGENT_KEY` from the
container secrets. The agent uses the same key as `AGENT_API_KEY`.

## 6. Connect the phone number

Create the LiveKit inbound trunk and dispatch rule with the runbook in
[`telephony.md`](telephony.md). The dispatch rule must send
`room_config.agents[].agent_name = ai-receptionist`; that value must match
`LIVEKIT_AGENT_NAME` in Terraform.

Then dial the DID and verify:

- LiveKit room appears and the agent joins.
- Greeting includes AI disclosure and recording consent.
- A booking appears in the dashboard and the caller reads back name/date/time.
- `ActiveCalls` appears in CloudWatch under `AIReceptionist/Agent`.
- The agent service scales out when concurrent calls exceed the target.

## 7. Load test before real traffic

Run from a machine that can reach LiveKit Cloud, not from inside the VPC:

```bash
cd agent
uv run python scripts/load_test_calls.py --calls 10 --duration 30
```

This smoke test measures room creation, dispatch, greeting TTS, and first-audio latency.
For a full STT/LLM/tool test, pass a real caller recording:

```bash
uv run python scripts/load_test_calls.py \
  --calls 25 \
  --duration 45 \
  --start-interval 2 \
  --audio /tmp/caller-booking.wav \
  --output /tmp/load-test.json
```

WAV must be 16-bit PCM mono/stereo. Start below `agent_max_count`; watch ECS desired
count, `ActiveCalls` average, first-audio p95, and error rate. Tune
`agent_target_calls_per_task`, CPU/memory, and `AGENT_MAX_ACTIVE_CALLS` from measured
results. A 2 vCPU / 4 GB task at 6 calls is a starting point, not a guaranteed capacity.

## Operations

- **Logs:** CloudWatch groups `/ecs/ai-receptionist-prod/{api,worker,dashboard,agent,agent-metrics}`.
- **Secrets:** `ai-receptionist/prod/app` (JSON) and
  `ai-receptionist/prod/database-url`. Update provider keys in Terraform or Secrets
  Manager, then redeploy the service.
- **Metrics:** `ActiveCalls` and `WorkerLoadPercent` in `AIReceptionist/Agent`, plus
  ECS/Container Insights metrics.
- **Rollback:** `terraform apply -var="image_tag=<previous-tag>"`. ECS circuit breakers
  roll back failed deployments.
- **Recording retention:** S3 lifecycle expires `recordings/` after
  `recording_retention_days` (default 90). Change it to match the clinic's DPDP policy.
- **Database:** see [`rds-migration.md`](rds-migration.md) for moving existing
  Supabase/Neon data into this RDS instance.

## Cost notes

The NAT gateway, ALB, RDS, ElastiCache, and at least one always-on agent task dominate
the bill. Keep `agent_min_count = 1` so the first call is answered immediately; scaling
to zero would make the first caller wait for a cold task.
