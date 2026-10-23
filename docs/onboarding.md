# Clinic onboarding

This is the hand-off checklist for a new clinic. Work through it in order. The clinic
admin should be present for the demo at the end.

## 1. Before the session

Collect from the clinic:

- Legal/clinic name, timezone, address, phone, and front-desk number
- Doctors, specialties, languages, consultation fees, and weekly working hours
- Time off, holidays, and slot length
- Top 30-50 caller questions and approved answers
- Whether WhatsApp, SMS, or both should send confirmations and reminders
- The clinic's DPDP/privacy contact and recording-retention policy
- The phone number that will receive calls, and the provider (Exotel or Plivo)

Confirm the deployment is healthy before the clinic joins:

```bash
curl -fsS "https://api.clinic.example.com/health"
curl -fsS "https://app.clinic.example.com/login" >/dev/null
```

See [`deployment.md`](deployment.md) for infrastructure and [`telephony.md`](telephony.md)
for the LiveKit SIP setup.

## 2. Sign in and create the clinic profile

1. Sign in at `https://app.clinic.example.com` with the seeded admin account.
2. Open **Clinic setup**.
3. Set the clinic name, timezone (`Asia/Kolkata` for India), address, phone, email, and
   **front-desk number**.
4. Save.

The front-desk number is where `transfer_to_human` dials. If it is blank, transfers fail
and the agent takes a callback instead. The number must be reachable from the LiveKit
outbound SIP trunk.

5. Open **Staff** and invite the receptionist/admin users. Invitations are one-time links
   valid for 7 days. Email delivery is not connected, so copy the link and send it
   manually.

## 3. Add doctors, availability, and time off

1. Open **Doctors** and add each doctor: name, specialization, languages, fee, and
   whether they are active.
2. Open **Availability** and add weekly rules per doctor: weekday, start, end, and slot
   length (for example 15 or 20 minutes).
3. Add **Time off** for leave, holidays, or blocked hours.
4. Open **Appointments** and book a test appointment. Confirm it appears in the correct
   slot and that overlapping slots are rejected.

### Calendar connection

The current build uses the clinic calendar stored in Postgres as the source of truth.
Doctors, availability rules, time off, and appointments are managed in the dashboard.
There is no two-way Google Calendar sync in this build; the `GOOGLE_*` environment
variables are reserved placeholders and are not read by the appointment tools. Do not
tell a clinic that Google Calendar is connected.

If the clinic needs Google Calendar, treat it as a separate integration project: OAuth
consent, calendar selection, busy-time import, and conflict handling all need to be built
and tested before go-live.

## 4. Load the FAQ knowledge base

1. Open **FAQs**.
2. Add individual FAQs or use **Upload**.
3. JSON format:

   ```json
   [
     {"question": "What are the clinic timings?", "answer": "We are open Monday to Saturday, 9 AM to 6 PM."},
     {"question": "Do you accept insurance?", "answer": "Please call the front desk; insurance varies by plan."}
   ]
   ```

   An object with a `faqs` list is also accepted. CSV needs a header row with
   `question,answer`.

4. Keep answers short and factual. Do not put medical advice, diagnoses, or unapproved
   price promises in the FAQ.
5. Deactivate old answers instead of leaving conflicting duplicates.
6. Ask the clinic to test 10 real caller questions. Use the **FAQs** page to fix gaps.
7. If a question has no confident answer, the agent offers a callback. That is the correct
   behavior; do not force an answer by lowering the confidence threshold blindly.

For bulk loading from the repo, use `api/scripts/ingest_faqs.py` with the clinic id.
See [`faq.md`](faq.md).

## 5. Configure messaging

1. Set the provider credentials in the deployment secrets/environment:
   `WHATSAPP_PROVIDER`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, or
   `SMS_PROVIDER`, `EXOTEL_*`/`PLIVO_*`.
2. For local or staging without provider credentials, use
   `WHATSAPP_PROVIDER=fake` and `SMS_PROVIDER=fake`. Messages are logged, not sent.
3. Open **Messaging** in the dashboard and enable the channels the clinic wants.
4. Review the Hindi and English confirmation and reminder templates. Clinic-specific
   wording and approved WhatsApp template names must match the provider account.
5. Book a test appointment and send a confirmation. Confirm it arrives on a real phone.
6. Confirm the 24-hour and 2-hour reminder jobs are running (`arq` worker healthy).

Do not enable WhatsApp reminders in production until the templates are approved by Meta.
See [`messaging.md`](messaging.md).

## 6. Connect the phone number

1. Add the LiveKit inbound trunk and individual dispatch rule with
   `infra/livekit-sip/setup-telephony.sh` or the console steps in
   [`telephony.md`](telephony.md). Use the `.india.sip.livekit.cloud` endpoint.
2. Ensure the dispatch rule has
   `room_config.agents[].agent_name = ai-receptionist` and that it matches
   `LIVEKIT_AGENT_NAME`.
3. Point the Exotel/Plivo number at the LiveKit SIP endpoint.
4. Dial the number from a mobile. Verify:
   - the agent answers promptly
   - the greeting discloses AI and asks recording consent
   - the caller can speak in Hindi, English, and Hinglish
   - the call appears in the dashboard after it ends

## 7. Consent, recording, and DPDP

Recording is **opt-in**. The greeting asks the caller whether the call may be recorded;
the agent starts egress only after the caller clearly agrees. If the caller declines or
the answer is unclear, the call continues without recording. Do not change the greeting
to imply that recording is mandatory.

Checklist:

- [ ] The AI disclosure is in the first greeting.
- [ ] Recording consent is asked once, and recording does not start without a clear yes.
- [ ] `RECORDING_ENABLED` matches the clinic's contract and consent policy.
- [ ] Recording retention matches the clinic's DPDP notice. The default S3 lifecycle is
      90 days; update `recording_retention_days` if the clinic requires a different period.
- [ ] Phone numbers are masked in logs/dashboards wherever practical.
- [ ] Only clinic staff with a need to know can access transcripts and recordings.
- [ ] The clinic has a privacy notice covering purpose, retention, data location, and
      grievance contact.
- [ ] All production data (managed database, object storage, Redis, backups, logs) stays
      in an India region.
- [ ] The clinic knows the agent does not give medical advice or diagnoses; emergencies
      are transferred to a human or the emergency number.
- [ ] The clinic has a deletion/retention request process for patient data.
- [ ] Provider DPAs (LiveKit, Sarvam, LLM, WhatsApp/SMS, hosting provider) are on file.

If the clinic does not consent to recording, set `RECORDING_ENABLED=false` for that
deployment. Do not leave egress enabled "just in case."

## 8. Demo script

Run this on a speakerphone with the clinic admin listening. Use a test appointment and
cancel it afterward.

1. **Answer and disclosure**
   - Dial the clinic number.
   - Expected: the agent greets in Hindi/English, says it is an AI, asks recording
     consent, and asks how it can help.
   - Say "Haan, record kar sakte hain" and confirm the agent does not claim recording if
     consent was declined in a second test.

2. **Book an appointment**
   - "Mujhe kal subah Dr. Asha Rao ke saath appointment chahiye."
   - Give a name and a test phone number.
   - Expected: the agent checks availability, offers a real slot, reads back name, phone,
     date, time, and doctor, then books only after confirmation.
   - Verify the appointment in the dashboard.

3. **FAQ**
   - "Clinic ka address kya hai?" and "Do you accept walk-ins?"
   - Expected: a short answer from the configured clinic data or FAQ. If unknown, the
     agent offers a callback instead of inventing an answer.

4. **Reschedule or cancel**
   - "Mera appointment reschedule karna hai."
   - Give the appointment reference from the booking.
   - Expected: the agent checks a real free slot and confirms the change.

5. **Human transfer**
   - "Mujhe billing ke baare mein baat karni hai" or "Connect me to a human."
   - Expected: the agent dials the front desk. If the front desk does not answer within
     the ring timeout, it takes a callback and the task appears in **Callbacks**.

6. **Emergency**
   - "Chest pain ho raha hai."
   - Expected: the agent does not diagnose. It transfers to a human or tells the caller to
     call the emergency number, depending on the configured clinic behavior.

7. **After the call**
   - Open **Calls** and the call detail page.
   - Check transcript, summary, outcome, language, evaluations, and (if consented)
     recording playback.
   - Send a confirmation from the appointment and verify receipt.

## 9. Go-live checklist

- [ ] Real number tested from at least two carriers/mobile networks.
- [ ] Hindi, English, and Hinglish test calls pass.
- [ ] Booking, reschedule, cancel, FAQ, transfer, callback, and confirmation tested.
- [ ] Front-desk transfer answered by a human.
- [ ] Callback queue visible to staff.
- [ ] WhatsApp/SMS confirmation and reminders received on a real phone.
- [ ] Analytics shows calls, conversion, transfer rate, and latency.
- [ ] Recording playback works for a consented call.
- [ ] No recording exists for a declined-consent call.
- [ ] Staff accounts and roles are correct; demo credentials are removed.
- [ ] Autoscaling, alerts, and logs are enabled; on-call owner is named.
- [ ] Clinic knows how to change hours, doctors, FAQs, and messaging templates.
- [ ] Clinic has the support escalation path for a dropped call or wrong booking.
