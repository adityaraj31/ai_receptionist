# Confirmations and reminders

Patient messages go through one API interface, `MessagingService`, with adapters for
WhatsApp and SMS. Clinic staff control channels and wording from **Messaging** in the
dashboard; the settings are stored in `clinic_messaging_settings`.

## Providers

| Channel | Provider | Env |
| --- | --- | --- |
| WhatsApp | Meta Cloud API | `WHATSAPP_PROVIDER=meta`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` |
| WhatsApp | Gupshup | `WHATSAPP_PROVIDER=gupshup`, `GUPSHUP_API_KEY`, `GUPSHUP_SOURCE_NUMBER`, `GUPSHUP_APP_NAME` |
| SMS | Exotel | `SMS_PROVIDER=exotel`, `EXOTEL_SID`, `EXOTEL_API_KEY`, `EXOTEL_API_TOKEN`, `EXOTEL_CALLER_ID` |
| SMS | Plivo | `SMS_PROVIDER=plivo`, `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN`, `PLIVO_NUMBER` |
| WhatsApp/SMS | Fake (local only) | `WHATSAPP_PROVIDER=fake`, `SMS_PROVIDER=fake` |

Use `WHATSAPP_PROVIDER=none` or `SMS_PROVIDER=none` to disable a channel. Provider
failures are logged in `message_logs` and never break a booking. The agent only says a
confirmation was sent when the provider accepted it.

For local end-to-end testing without provider credentials, set both providers to `fake`:

```dotenv
WHATSAPP_PROVIDER=fake
SMS_PROVIDER=fake
```

The fake adapter makes no network call. It writes the rendered message to the API/worker
log with a masked recipient and records a successful `message_logs` row with provider
`fake_whatsapp` or `fake_sms`. Restart the API and Arq worker after changing the env.
Never enable this in production.

With the API running, `api/scripts/test_messaging.py` sends a test message for the most
recent booked appointment in the demo clinic:

```bash
cd api
uv run python -m scripts.test_messaging confirmation
uv run python -m scripts.test_messaging confirmation --channel sms
uv run python -m scripts.test_messaging reminder --reminder-kind reminder_2h
```

Pass `--appointment-id <uuid>` to target a specific appointment. The confirmation path
calls the real agent API; the reminder path executes the same job function used by Arq and
prints its result. The script prints the latest `message_logs` status and provider.

## Confirmations

After a booking, the agent can call `send_confirmation(channel, appointment_id)`. The API
checks that the channel is enabled for the clinic, picks the caller's language
(`appointments.language`, falling back to the clinic default), renders the template, and
sends it.

## Reminders

Booking or rescheduling enqueues two Arq jobs at `starts_at - 24h` and `starts_at - 2h`.
Each job stores the appointment start it was scheduled for, skips if the appointment was
cancelled or moved, checks the clinic switches, and uses `reminder_channel`. A sent
reminder is idempotent for that start time.

The worker uses the same package and environment as the API:

```bash
cd api
uv run arq app.workers.main.WorkerSettings
```

The job function is `send_appointment_reminder`. The API enqueues only when
`REMINDER_JOBS_ENABLED=true`; the worker checks the per-clinic switches at send time.

## Templates

Templates support `{patient_name}`, `{doctor_name}`, `{clinic_name}`, `{clinic_phone}`,
and `{appointment_time}`. Unknown variables are rejected when staff save the settings.
Hindi and English versions are stored separately for confirmations, 24-hour reminders,
and 2-hour reminders.

WhatsApp reminders are business-initiated messages outside the 24-hour customer service
window. Meta and Gupshup require a pre-approved template for those in production; the
current adapter sends the rendered text, so use SMS for reminders or add the approved
template wiring before relying on WhatsApp reminders with real numbers.
