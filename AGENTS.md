# AI Receptionist System

A voice AI receptionist for clinics. It answers phone calls 24x7 in Hindi and English, books appointments, sends confirmations (WhatsApp/SMS), and reports on every call.

## Architecture

```
Caller -> PSTN -> Exotel/Plivo -> SIP trunk -> LiveKit SIP -> LiveKit Room
   -> Agent worker (Python): VAD -> STT -> LLM (tools) -> TTS
   -> Tools: calendar, FAQ RAG, transfer to human, WhatsApp/SMS, CRM/Sheets
   -> Post-call queue: recording, transcript, summary, evals, cost
   -> Postgres -> Analytics dashboard
```

Inbound telephony is LiveKit SIP: one inbound trunk per DID plus an individual dispatch
rule that routes each caller to its own room and dispatches the agent via
`room_config.agents[].agent_name` (must equal `LIVEKIT_AGENT_NAME`). Setup scripts and the
runbook are in `/infra/livekit-sip` and `docs/telephony.md`. Use the region-pinned
`.india.sip.livekit.cloud` endpoint for Indian numbers.

## Tech stack

- Agent: Python 3.11+, LiveKit Agents (cascaded pipeline, NOT speech-to-speech)
- STT/TTS: Sarvam AI (Hindi + English); Deepgram as English fallback
- VAD / turn detection: Silero VAD + LiveKit turn detector
- LLM: fast tool-calling model, configurable via env (`LLM_MODEL`)
- Backend: FastAPI + SQLAlchemy 2 (async) + Alembic
- DB: PostgreSQL + pgvector (FAQ RAG); cloud via `DATABASE_URL` (Supabase/Neon)
- FAQ embeddings: `fastembed` local ONNX model (`EMBEDDING_MODEL`, 384d) + pgvector HNSW;
  chosen over a hosted embeddings API to keep retrieval under 300 ms and FAQ text in-region.
- Auth: staff email/password -> JWT; voice agent -> `X-Service-Key`
- Queue: Redis + Arq (post-call jobs)
- Storage: S3-compatible (recordings), use Cloudflare R2 or S3 Mumbai
- Messaging: WhatsApp Business API (Meta Cloud API or Gupshup), SMS via Exotel/Plivo
- Dashboard: Next.js + Tailwind + Recharts
- Observability: Langfuse (LLM traces), Sentry, structured JSON logs
- Infra: Docker Compose locally; AWS ap-south-1 (Mumbai) for deployment

## Repo layout

```
/agent       LiveKit agent worker (voice pipeline, tools, prompts)
/api         FastAPI backend (appointments, calls, webhooks, dashboard API)
## Architecture

```
Caller -> PSTN -> Exotel/Plivo -> SIP trunk -> LiveKit SIP -> LiveKit Room
   -> Agent worker (Python): VAD -> STT -> LLM (tools) -> TTS
/dashboard   Next.js analytics dashboard
/infra       Dockerfiles, docker-compose, deploy configs, LiveKit SIP setup scripts
/evals       Transcript evaluation scripts and test conversations
/docs        Architecture notes, runbooks
```

## Conventions

- Python: type hints everywhere, `ruff` for lint/format, `pytest` for tests, `uv` or `pip-tools` for deps.
- Config via environment variables only. Never hardcode keys. Keep `.env.example` updated.
- Every external call (STT, LLM, TTS, calendar, WhatsApp) must have timeouts and error handling. A call must never go silent.
- Log a structured event for each call stage into `call_events` with timestamps (used for latency analysis).
- Clinic config (name, doctors, availability) is loaded from Postgres (`clinics`, `doctors`, `availability_rules`); `CLINIC_*` env values are a local fallback only.
- Schema changes go through Alembic in `/api/alembic`; do not add ad-hoc SQL migrations.
- Every staff query must be scoped by the `clinic_id` from the JWT. The voice agent must use its clinic-scoped service key.
- Appointment writes must check computed free slots and rely on the database exclusion constraint as the final double-booking guard.
- Before using LiveKit, Sarvam or any SDK, check the current official docs. APIs change; do not rely on memory.

## Voice agent rules

- Latency target: under ~1 second from end of caller speech to start of agent speech. Stream at every stage.
- Support interruptions (barge-in). Stop TTS immediately when the caller speaks.
- Keep spoken replies short (1-2 sentences). This is a phone call, not a chat.
- Greet with an AI disclosure and ask for recording consent at the start of every call.
- Detect language (Hindi / English / Hinglish) and reply in the caller's language.
- Confirm critical details by reading them back: name, date, time, phone number.
- Transfer to a human on: medical emergency keywords, caller requests a human, 2 failed attempts to understand, or repeated frustration.
- The agent must never give medical advice or diagnoses. It only handles scheduling, clinic info and message-taking.

## Tools the agent exposes

- `check_availability(date, doctor)`
- `book_appointment(patient_name, phone, doctor, datetime)`
- `reschedule_appointment(appointment_id, datetime)` / `cancel_appointment(appointment_id)`
- `search_faq(query)` (RAG over clinic timings, fees, doctors, location, services, policies)
- `transfer_to_human(reason)` (warm SIP dial to the clinic front desk; fallback `create_callback`)
- `create_callback(name, phone, reason, message)` (callback task when transfer fails)
- `send_confirmation(channel, appointment_id)` (WhatsApp or SMS)
- `save_lead(name, phone, notes)` (CRM or Sheets)

Tool outputs must be short and structured so the LLM can answer in one sentence.
`search_faq` calls `POST /api/v1/agent/faq/search` (service key), which embeds the query
locally and returns the closest active FAQ trimmed to two sentences. If nothing clears the
confidence threshold it returns `found=false`, and the agent offers a callback. Staff manage
the knowledge base from the dashboard's FAQs page (add/edit/deactivate, JSON/CSV upload);
`api/scripts/ingest_faqs.py` bulk-loads the seed corpus. Retrieval must stay under 300 ms
p95 in the eval (`evals/run_faq_eval.py`); see `docs/faq.md`.

`transfer_to_human` dials the clinic front desk into the caller's room with
`CreateSIPParticipant(wait_until_answered=true)` (`agent/transfer.py`). The number comes from
`clinics.front_desk_number` (dashboard **Clinic setup**), with `TRANSFER_NUMBER` as a local
fallback. If the front desk does not answer within `TRANSFER_RING_TIMEOUT_SECONDS`, the agent
takes a message and calls `create_callback`, which writes `callback_tasks` through
`POST /api/v1/agent/callbacks`. Transfers trigger on emergencies, explicit human requests,
billing/insurance questions, repeated frustration, and two failed attempts to understand.
Warm transfer needs a LiveKit **outbound** SIP trunk (`LIVEKIT_SIP_OUTBOUND_TRUNK`); see
`docs/telephony.md`.

Calendar tools are implemented in `/agent` (`agent_tools.py` + `api_client.py`). They call
`/api` with the `X-Service-Key` header (`AGENT_API_URL` / `AGENT_API_KEY`, falling back to
`DEMO_AGENT_KEY`) and never write appointments directly to Postgres. At call start the agent
loads doctors/availability from `GET /api/v1/agent/clinic-config` (service key); Postgres
and `CLINIC_*` env are fallbacks. On any tool failure the agent returns `ok=false` plus a
short `say` line so the call never goes silent.

## Data model (core tables)

`clinics` (with `front_desk_number`), `staff_users`, `staff_invitations`, `agent_api_keys`, `doctors`, `availability_rules`, `time_off`, `patients`, `appointments` (clinic-scoped, with overlap exclusion), `faq_chunks` (clinic-scoped, vector(384), HNSW cosine index), `callback_tasks` (clinic-scoped follow-ups), `calls` (id, from_number, duration, language, recording_url, cost, status), `transcripts`, `call_events`, `evaluations`.

Free slots = weekly availability minus time off minus non-cancelled appointments. Appointments must align to generated slots; a GiST exclusion constraint blocks overlapping bookings even under concurrent requests.

## Compliance (India)

- Health data falls under DPDP: encrypt at rest, restrict access, define retention, keep data in India.
- Mask phone numbers in logs and dashboards where possible.
- Respect TRAI rules for number series and outbound calling. Do not build outbound calling without a consent flag.
- Keep HIPAA awareness in mind for international clinics.

## Working agreement for the AI assistant

1. Plan first, then build. Propose a short plan before writing code for any new module.
2. Work in small vertical slices. Each slice must run and have at least one test or a manual test script.
3. Do not add dependencies without saying why.
4. After each slice, update this file or `/docs` if conventions or architecture changed.
5. Ask before making irreversible changes (schema drops, deleting files).

## Milestones

- Week 1: Phone -> STT -> LLM -> TTS working, calendar booking, Hindi + English.
- Week 2: FAQ RAG (done: local embeddings, pgvector, staff UI, eval), human transfer
  (done: warm SIP transfer + callback fallback), WhatsApp/SMS confirmations, reminders, CRM sync.
- Week 3: Recording, transcripts, evals, analytics dashboard, concurrency tests, demo and pricing.