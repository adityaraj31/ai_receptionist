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
SARVAM_API_KEY=...
LLM_API_KEY=...
LLM_MODEL=gpt-4.1-mini
# Optional for OpenAI-compatible providers:
# LLM_BASE_URL=https://...
```

Set `SARVAM_LANGUAGE=hi-IN` or `en-IN` to choose the TTS voice language. The LLM mirrors
the caller's language (Hindi, English, or Hinglish) in its replies.

## Run

```bash
cd agent
uv sync
uv run python src/receptionist_agent.py dev
```

The worker registers with LiveKit under the agent name `ai-receptionist` (configurable via
`LIVEKIT_AGENT_NAME`). The Python CLI prints a deprecation warning for `dev` mode; it
still works. If you have the LiveKit CLI installed, `lk agent dev` is the newer path.

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
| `session_started` | room, models, TTS language |
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
- No tools (calendar, FAQ, transfer, WhatsApp) are wired yet. This slice only proves the
  voice pipeline and greeting.
