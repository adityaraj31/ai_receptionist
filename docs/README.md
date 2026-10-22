# Docs

Architecture notes and runbooks for the AI Receptionist live here.

- [../AGENTS.md](../AGENTS.md) - architecture, conventions, and working agreement.
- [../README.md](../README.md) - local setup.
- [deployment.md](deployment.md) - ECS Fargate deploy in `ap-south-1`, autoscaling, and operations.
- [onboarding.md](onboarding.md) - clinic hand-off, FAQ/calendar setup, consent/DPDP, demo script.
- [rds-migration.md](rds-migration.md) - move Supabase/Neon data to RDS `ap-south-1`.
- [telephony.md](telephony.md) - connect an Exotel/Plivo number to LiveKit SIP.
- [faq.md](faq.md) - FAQ knowledge base, local embeddings, ingestion, and retrieval eval.
- [messaging.md](messaging.md) - confirmations, reminders, providers, and templates.
- [post-call.md](post-call.md) - recording, transcript, summary, evals, and cost.

Planned notes:

- `architecture.md` - call flow, latency budget, failure modes.
- `data-model.md` - tables, retention, and DPDP considerations.
- `runbook.md` - on-call checks and provider outages.
