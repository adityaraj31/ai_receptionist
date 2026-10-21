# Post-call processing

When a LiveKit room closes, the agent submits one finalize request and the API queues the
recording/transcript/summary work. The call never depends on these jobs succeeding.

## Flow

```
Agent shutdown
  -> stop optional LiveKit egress recording
  -> POST /api/v1/agent/calls (X-Service-Key)
     -> calls + transcripts + call_events
     -> Arq process_call
        -> copy recording into the clinic prefix in S3
        -> summarize transcript + classify outcome (LLM, heuristic fallback)
        -> compute STT/LLM/TTS/telephony cost
        -> Arq evaluate_call
           -> correctness, politeness, missed handoffs in evaluations
```

The finalize endpoint is idempotent per `(clinic_id, livekit_room_name)`. A call that is
already `processing` or `completed` is not written again. A retry while the call is
`pending` or `failed` replaces its transcript and resets the post-call state.

## Finalize request

```http
POST /api/v1/agent/calls
X-Service-Key: <clinic service key>

{
  "room_name": "call-...",
  "started_at": "2026-10-21T09:00:00+00:00",
  "ended_at": "2026-10-21T09:02:00+00:00",
  "from_number": "+919000000001",
  "to_number": "+919000000002",
  "language": "hi-IN",
  "transcript": [
    {"role": "user", "text": "Mujhe kal appointment chahiye"},
    {"role": "assistant", "text": "Kal 10 baje slot available hai."}
  ],
  "recording": {
    "url": "s3://bucket/recordings/call-....ogg",
    "bucket": "bucket",
    "key": "recordings/call-....ogg",
    "egress_id": "EG_..."
  },
  "usage": {
    "stt_audio_seconds": 120,
    "llm_prompt_tokens": 1000,
    "llm_completion_tokens": 200,
    "tts_characters": 300
  }
}
```

`recording` is optional. Usage counters are accumulated from LiveKit metrics. Times must
include a timezone and `ended_at` must not precede `started_at`.

## Jobs

The Arq worker must be running for any post-call work:

```bash
cd api
uv run arq app.workers.main.WorkerSettings
```

| Job | Purpose |
| --- | --- |
| `process_call` | Recording storage, summary/outcome, cost, `calls` update |
| `evaluate_call` | Correctness/politeness scores and missed-handoff list |
| `send_appointment_reminder` | Existing 24h/2h reminders |

`process_call` is retried up to 3 times. Terminal failures are recorded in
`calls.post_call_error` / `calls.evaluation_error` and emitted as `call_events`. An empty
transcript is still summarized as `dropped`, but evaluation is marked `skipped`.

## Summary and outcome

The API calls an OpenAI-compatible chat-completions endpoint with
`LLM_API_KEY`, `LLM_MODEL`, and optional `LLM_BASE_URL`. The model must return JSON:

- `summary`: two short sentences.
- `outcome`: `booked`, `enquiry`, `transferred`, or `dropped`.

If the LLM is not configured or returns invalid JSON, the job uses a deterministic
heuristic summary/outcome so the call is still recorded. LLM errors are stored in the
`post_call_completed` event payload.

The evaluation job stores one row per metric in `evaluations`:

- `correctness` and `politeness`: 0-1, higher is better.
- `missed_handoffs`: count of missed required handoffs, lower is better; the reasons are
  in `details.items`.

## Recording storage

Recording is opt-in with `RECORDING_ENABLED=true`. The agent starts a LiveKit
audio-only room-composite egress to S3 and stops it during shutdown. Required variables:

```dotenv
RECORDING_ENABLED=true
RECORDING_PREFIX=recordings
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_REGION=ap-south-1
# Optional for R2/MinIO and public playback:
S3_ENDPOINT_URL=
S3_PUBLIC_BASE_URL=
S3_FORCE_PATH_STYLE=false
```

The egress writes an `.ogg` file under the configured prefix. `process_call` copies it to
`recordings/{clinic_id}/{call_id}.ogg` (the canonical key) and stores
`calls.recording_url` / `calls.recording_meta`. If S3 is missing or a copy fails, the
original egress URL is kept and `recording_meta.storage_error` explains why. A recording
larger than `RECORDING_MAX_BYTES` is rejected.

Use a private bucket and serve playback through short-lived signed URLs. Do not put
recordings on a public bucket: call audio is health data under India's DPDP.

## Cost

`process_call` computes cost from `usage_metrics` and the call duration. Rates are
env-driven and default to zero so no provider-specific price is baked into the code:

```dotenv
STT_COST_PER_MINUTE=0
LLM_INPUT_COST_PER_1M_TOKENS=0
LLM_OUTPUT_COST_PER_1M_TOKENS=0
TTS_COST_PER_1M_CHARACTERS=0
TELEPHONY_COST_PER_MINUTE=0
COST_CURRENCY=INR
```

The total is stored in `calls.cost`; per-provider amounts, rates, and usage are stored in
`calls.cost_breakdown`.

## Local testing

The API tests cover the finalize endpoint, idempotency, storage fallback, cost math, and
evaluation rows:

```bash
cd api
uv run pytest -q tests/test_post_call.py tests/test_call_costs.py
```

The agent tests cover usage collection, finalize retry, and recording opt-out:

```bash
cd agent
uv run pytest -q tests/test_call_lifecycle.py
```

Without S3 or an LLM key, the flow still completes: the original recording URL is kept
and the heuristic summary is used. Enable `POST_CALL_JOBS_ENABLED=true` (the default) and
make sure Redis and the Arq worker are running.
