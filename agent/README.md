# Agent

LiveKit Agents worker for the AI Receptionist. Cascaded pipeline:

```
Silero VAD -> Sarvam STT (auto language) -> OpenAI-compatible LLM -> Sarvam TTS
```

Verified against `livekit-agents` and `livekit-plugins-sarvam` **1.8.8** (October 2026).
The worker uses the current `AgentServer` / `@server.rtc_session` API, not the deprecated
`WorkerOptions` entrypoint style.

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- LiveKit project (Cloud or self-hosted)
- Sarvam API key
- OpenAI or OpenAI-compatible LLM API key

## Environment

The worker loads `agent/.env` first, then the repository-root `.env` (OS environment
variables always win). From the repo root:

```bash
cp .env.example .env
```

`dev` mode will exit early with a clear message if any required key is missing.

Minimum values for this slice:

```dotenv
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
LIVEKIT_AGENT_NAME=ai-receptionist
# Outbound trunk used to dial the clinic front desk for transfers:
LIVEKIT_SIP_OUTBOUND_TRUNK=...
LIVEKIT_SIP_NUMBER=+918069000000
SARVAM_API_KEY=...
LLM_API_KEY=...
LLM_MODEL=gpt-4.1-mini
# Optional for OpenAI-compatible providers:
# LLM_BASE_URL=https://...
# Calendar tools (optional: agent falls back to DB/env config without them):
AGENT_API_URL=http://localhost:8000
AGENT_API_KEY=...  # falls back to DEMO_AGENT_KEY
```

Set `SARVAM_LANGUAGE=hi-IN` or `en-IN` to choose the TTS voice language. The LLM mirrors
the caller's language (Hindi, English, or Hinglish) in its replies.

## Clinic config and prompt

The system prompt lives in [`prompts.py`](prompts.py). Clinic-specific values are
not hardcoded in the prompt: `build_system_prompt(ClinicConfig)` injects them at runtime.

Clinic config is resolved at the start of every call in this order:

1. `GET {AGENT_API_URL}/api/v1/agent/clinic-config` with the `X-Service-Key` header
   (`AGENT_API_KEY`, falling back to `DEMO_AGENT_KEY`). This is the source for doctor IDs
   and availability used by the calendar tools.
2. Postgres directly, if `DATABASE_URL` is set and the API is unreachable.
3. `CLINIC_*` environment values below.

Set `CLINIC_ID` to a clinic UUID to pin one clinic; leave it empty for the first active
clinic. When the API is used, non-clinic fields the API does not store (fees, emergency
number) still come from the environment fallback.

The schema is managed by Alembic in [`../api/alembic`](../api/alembic). Apply the
migration and seed demo data from the repository root:

```bash
cd api
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed  # optional demo clinic/doctors/availability
```

The agent reads:

- `clinics` - name, timezone, address, phone, `front_desk_number`.
- `doctors` - doctor name and specialization (`is_active` filters rows).
- `availability_rules` - weekly windows (`weekday`, `start_time`, `end_time`); these
  produce the doctor days/hours and clinic open hours in the prompt.

## Tools

[`agent_tools.py`](agent_tools.py) exposes the function tools to the LLM. HTTP tools call
the FastAPI backend through [`api_client.py`](api_client.py) using the clinic-scoped
service key, so the agent never writes to Postgres directly.

| Tool | API call / action |
| --- | --- |
| `check_availability(date, doctor)` | `GET /api/v1/doctors/{id}/free-slots?date=` |
| `book_appointment(patient_name, phone, doctor, datetime, language)` | `POST /api/v1/appointments` |
| `reschedule_appointment(appointment_id, datetime)` | `PATCH /api/v1/appointments/{id}/reschedule` |
| `cancel_appointment(appointment_id)` | `POST /api/v1/appointments/{id}/cancel` |
| `search_faq(question)` | `POST /api/v1/agent/faq/search` |
| `transfer_to_human(reason)` | dials `front_desk_number` into the room via SIP |
| `create_callback(name, phone, reason, message)` | `POST /api/v1/agent/callbacks` |
| `send_confirmation(channel, appointment_id)` | `POST /api/v1/agent/appointments/{id}/confirmation` |

`date` is `YYYY-MM-DD`; `datetime` is clinic-local `YYYY-MM-DDTHH:MM`. The tools match the
requested time against the computed free slots and let the database exclusion constraint
be the final double-booking guard.

## Human transfer

`transfer_to_human` uses [`transfer.py`](transfer.py) to dial the front desk into the
caller's room with `CreateSIPParticipant(wait_until_answered=true)`. The number comes from
`clinics.front_desk_number` (dashboard **Clinic setup**), with `TRANSFER_NUMBER` as a local
fallback. The agent disables its own mic/speaker once the front desk answers. If the ring
window (`TRANSFER_RING_TIMEOUT_SECONDS`, default 20) expires, the tool returns `ok=false`
and the prompt tells the LLM to take a message and call `create_callback`. Warm transfer
needs an outbound SIP trunk; see [`../docs/telephony.md`](../docs/telephony.md).

Tool results are short JSON. Every failure returns `{"ok": false, "reason", "say"}`, where
`say` is a one-line spoken fallback, so a slow or down API never leaves the caller in
silence. A missing `AGENT_API_KEY`/`DEMO_AGENT_KEY` is logged as `agent_api_key_missing`
and the tools degrade to the fallback lines.

Environment fallback values:

```dotenv
CLINIC_NAME=Aarogya Clinic
CLINIC_TIMEZONE=Asia/Kolkata
CLINIC_ADDRESS=
CLINIC_PHONE=
CLINIC_FEES=General consultation: INR 500
CLINIC_EMERGENCY_NUMBER=108
CLINIC_DOCTORS='[{"name":"Dr. Asha Rao","specialty":"General Physician","days":"Mon, Wed, Fri","hours":"10:00-13:00"}]'
CLINIC_TIMINGS='{"Monday":"09:00-18:00","Saturday":"09:00-14:00","Sunday":"Closed"}'
```

`CLINIC_DOCTORS` is a JSON list; each item can be a name or an object with `name`,
`specialty`, `days`, and `hours`. `CLINIC_TIMINGS` is a JSON object mapping weekday to
hours. If doctors or timings are missing, the prompt tells the model not to invent them.

Example evaluation conversations are in [`../evals/conversations.yaml`](../evals/conversations.yaml).

## Run

```bash
cd agent
uv sync
uv run python -m src.receptionist_agent dev
```

The worker registers with LiveKit under the agent name `ai-receptionist` (configurable via
`LIVEKIT_AGENT_NAME`). Use `python -m src.receptionist_agent` rather than
`python src/receptionist_agent.py` so the root-level `prompts.py` is importable. The Python
CLI prints a deprecation warning for `dev` mode; it still works. If you have the LiveKit
CLI installed, `lk agent dev` is the newer path.

## Test in the browser

1. Start the worker in `dev` mode as above and leave it running.
2. Open the [LiveKit Agents Playground](https://agents-playground.livekit.io/) or the
   **Agent Console** in your LiveKit Cloud project.
3. Use the same `LIVEKIT_URL`, API key, and secret as the worker.
4. Start a session with agent name `ai-receptionist`.
5. Allow microphone access and speak in Hindi, English, or Hinglish.

The greeting is deterministic (does not wait for the LLM): it discloses that the caller is
speaking to an AI, mentions recording, asks for consent, and offers Hindi or English.

## Latency logs

Each log line is JSON on stdout. One `turn_latency` event is emitted per assistant turn:

```json
{"ts":"...","event":"turn_latency","e2e_ms":812.4,"stt_transcription_ms":190.2,"end_of_turn_ms":110.0,"llm_ttft_ms":240.1,"llm_first_sentence_ms":310.5,"tts_ttfb_ms":271.6,"playback_ms":0.5,"interrupted":false}
```

Per-provider events are also logged:

| Event | Key fields |
| --- | --- |
| `stt_metrics` | `audio_ms`, `duration_ms`, `streamed` |
| `llm_metrics` | `ttft_ms`, `duration_ms`, token counts, `tokens_per_second` |
| `tts_metrics` | `ttfb_ms`, `duration_ms`, `audio_ms`, `characters` |
| `turn_latency` | `e2e_ms` plus the per-stage breakdown above |
| `session_started` | room, models, TTS language, `config_source`, `tools` |
| `clinic_config_api_error` / `clinic_config_db_error` | fallback reason |
| `agent_api_key_missing` | tools will use spoken fallbacks |
| `stt_error` / `llm_error` / `tts_error` | provider error details |

`e2e_ms` approximates `stt_transcription + end_of_turn + llm_ttft + tts_ttfb`. Use the
breakdown to see which provider is causing delay.

## Troubleshooting

### Sarvam 402 / no credits

If logs show `stt_error` or `tts_error` with `insufficient_quota_error` or
`No credits available`, the Sarvam account has no credits. Add credits or switch
`SARVAM_API_KEY` to a funded account, then restart the worker. This looks like a generic
`STTError` in LiveKit's telemetry warning until the new provider-error logs are inspected.

## Checks

```bash
cd agent
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Notes

- Silero VAD is loaded once per job process in `prewarm`.
- Sarvam STT uses `language="unknown"` for automatic Hindi/English detection. Override
  with `SARVAM_STT_LANGUAGE` if needed.
- `SARVAM_TTS_MODEL` defaults to `bulbul:v3` with speaker `shubh`; keep the speaker
  compatible with the model.
- The TTS voice language is `SARVAM_LANGUAGE` (default `hi-IN`). The LLM still mirrors the
  caller, so English is spoken with the Hindi voice unless you set `SARVAM_LANGUAGE=en-IN`.
  Per-turn TTS language switching is not implemented yet.
- Sarvam's current docs recommend `STTRealtime` with server-side turn detection for new
  builds. This slice intentionally uses the legacy streaming `STT` with Silero VAD because
  the requested pipeline requires Silero VAD; revisit this before production.
- Calendar, FAQ, human transfer, callback, and confirmation tools are wired. Arq sends
  24h/2h reminders from the API; CRM sync is not yet.
- At shutdown the agent submits the transcript, per-provider usage counters, and optional
  recording metadata to `/api/v1/agent/calls`. Post-call summary/cost/evaluation jobs are
  documented in [`../docs/post-call.md`](../docs/post-call.md).
- Recording is opt-in: set `RECORDING_ENABLED=true` plus the S3 values. The agent starts a
  LiveKit audio-only egress only after `set_recording_consent` receives a clear yes, and
  stops/polls it at shutdown. A refusal or unclear answer keeps the call unrecorded.
