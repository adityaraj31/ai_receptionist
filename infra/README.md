# Infra

Dockerfiles, Postgres init, and deployment configs.

The local `docker-compose.yml` lives at the repository root so `docker compose up -d`
works from the project directory. It mounts `infra/postgres/init.sql` to enable the
`vector` extension on first start.

Module Dockerfiles will be added here once the modules exist:

- `docker/api.Dockerfile`
- `docker/agent.Dockerfile`
- `docker/dashboard.Dockerfile`
