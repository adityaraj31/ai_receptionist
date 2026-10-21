# Telephony: connect an Exotel or Plivo number to LiveKit SIP

How to route real phone calls (PSTN) into a LiveKit room and have the AI receptionist
answer them. Provider-agnostic LiveKit config is the same for Exotel and Plivo; only the
provider console/API steps differ.

Verified against the LiveKit telephony docs (October 2026):
[inbound trunk](https://docs.livekit.io/telephony/accepting-calls/inbound-trunk.md),
[dispatch rule](https://docs.livekit.io/telephony/accepting-calls/dispatch-rule.md),
[Plivo quickstart](https://docs.livekit.io/telephony/start/providers/plivo.md),
[region pinning](https://docs.livekit.io/telephony/features/region-pinning.md),
[testing](https://docs.livekit.io/telephony/testing.md). Re-check these before changing
config; telephony APIs move.

## Call flow

```
Caller dials DID
  -> Exotel / Plivo PSTN
  -> trunk "destination URI" points at your LiveKit SIP endpoint
  -> LiveKit SIP matches the inbound trunk (phone number)
  -> dispatch rule picks the room and dispatches the agent
  -> caller joins the room as a SIP participant
  -> our agent worker (agent_name=ai-receptionist) joins the same room
  -> VAD -> Sarvam STT -> LLM tools -> Sarvam TTS
```

Two long-lived LiveKit objects make this work:

- **Inbound trunk** — accepts INVITEs for a given DID and can restrict auth by digest
  username/password or `allowed_addresses`. One trunk per phone number.
- **Dispatch rule** — decides the room name and which agent to dispatch. We use an
  **individual** rule so every caller gets their own room (`call-<random>`).

The agent worker registers with `LIVEKIT_AGENT_NAME` (default `ai-receptionist`), set on
`@server.rtc_session(agent_name=...)` in `agent/src/receptionist_agent.py`. Because the name
is set, the worker accepts jobs only when it is **explicitly dispatched**, so the dispatch
rule must include `room_config.agents[].agent_name` — otherwise calls ring and nobody answers.

## Prerequisites

- LiveKit Cloud project with Telephony enabled (SIP is included on Cloud, no extra deploy).
- [LiveKit CLI](https://docs.livekit.io/reference/developer-tools/livekit-cli/) (`lk`)
  installed and authenticated: `lk cloud auth`.
- An Exotel or Plivo account with KYC complete (India), a purchased DID in E.164, and API
  credentials.
- The agent worker running locally or deployed, with Sarvam + LLM keys set.

```bash
# install the CLI (macOS)
brew install livekit-cli
# or Linux
curl -sSL https://get.livekit.io/cli | bash

lk cloud auth
lk project list --json   # note ProjectId, e.g. p_vjnxecm0tjk
```

## Step 1 - find your LiveKit SIP endpoint

Your SIP URI is `sip:<project-id-without-p_>.sip.livekit.cloud`. It is also on
**Project settings** in the LiveKit Cloud dashboard.

- Global endpoint: `<subdomain>.sip.livekit.cloud`
- India region-pinned endpoint: `<subdomain>.india.sip.livekit.cloud`

Use the India endpoint for Indian DIDs. Region pinning is **required** for Plivo India
numbers and calls to/from India, and keeps media in-country for DPDP.

## Step 2 - create the LiveKit inbound trunk and dispatch rule

Easiest path is the script, which builds both objects from your environment:

```bash
# add to the repo-root .env
LIVEKIT_SIP_NUMBER=+918069000000

infra/livekit-sip/setup-telephony.sh --dry-run   # print the JSON first
infra/livekit-sip/setup-telephony.sh             # create trunk + dispatch rule
```

It writes the created ids to `infra/livekit-sip/.env.telephony` (git-ignored). Remove
everything with `infra/livekit-sip/teardown-telephony.sh`.

Manual equivalent (CLI):

```bash
lk sip inbound create infra/livekit-sip/inbound-trunk.plivo.json   # or .exotel.json
lk sip dispatch create infra/livekit-sip/dispatch-rule.individual.json
lk sip inbound list --json
lk sip dispatch list --json
```

The dashboard JSON editor uses the same files **without** the `trunk`/`dispatch_rule`
wrapper. For example, the inbound trunk body is:

```json
{
  "name": "Plivo inbound",
  "numbers": ["+918069000000"],
  "krisp_enabled": true
}
```

> The file-based `lk sip inbound create` command needs the `{"trunk": {...}}` wrapper, so
> the script generates that form. The templates in `infra/livekit-sip/` are dashboard shape.

Notes:

- `numbers` must be the E.164 DID. Leave it empty only for wildcard trunks, which then
  require digest auth or `allowed_addresses` (the latter needs LiveKit support to enable).
- `krisp_enabled` adds noise cancellation for cleaner STT.
- Dispatch rule `room_prefix: "call-"` gives each caller a fresh room. Individual rules
  include the caller's number in the room name before the random suffix; if that PII in
  room names is a concern, switch to the "route by ID" callee pattern in the dispatch rule
  docs.
- To scope the rule to one trunk, add `"trunk_ids": ["<trunk-id>"]`. The setup script does
  this automatically after creating the trunk. Omitting it makes the rule match **all**
  inbound trunks, which silently breaks isolation once you add a second DID.
- `room_config.agents[].agent_name` must equal `LIVEKIT_AGENT_NAME` (default
  `ai-receptionist`). A mismatch leaves the caller in the room with no agent.

## Step 3a - configure Exotel

Exotel trunk setup is account-specific; the API lives at `https://api.in.exotel.com`
(India) and uses HTTP basic auth with your API key/token. `trunk_name` is alphanumeric +
underscores, max 16 chars. Replace `${API_KEY}`, `${API_TOKEN}`, `${ACCOUNT_SID}`.

1. **Create the trunk**

   ```bash
   curl -s -X POST "https://${API_KEY}:${API_TOKEN}@api.in.exotel.com/v2/accounts/${ACCOUNT_SID}/trunks" \
     -H "Content-Type: application/json" \
     -d '{
       "trunk_name": "livekit_inbound",
       "nso_code": "ANY-ANY",
       "domain_name": "'"${ACCOUNT_SID}"'.pstn.exotel.com"
     }'
   ```

   Save `trunk_sid` from the response.

2. **Map the DID to the trunk**

   ```bash
   curl -s -X POST "https://${API_KEY}:${API_TOKEN}@api.in.exotel.com/v2/accounts/${ACCOUNT_SID}/trunks/${TRUNK_SID}/phone-numbers" \
     -H "Content-Type: application/json" \
     -d '{"phone_number": "+91XXXXXXXXXX"}'
   ```

3. **Point inbound calls at LiveKit** (destination URI, inbound only)

   ```bash
   curl -s -X POST "https://${API_KEY}:${API_TOKEN}@api.in.exotel.com/v2/accounts/${ACCOUNT_SID}/trunks/${TRUNK_SID}/destination-uris" \
     -H "Content-Type: application/json" \
     -d '{
       "destinations": [
         { "destination": "<subdomain>.india.sip.livekit.cloud:5061;transport=tls" }
       ]
     }'
   ```

   Use TLS `:443`/`:5061` where available; Exotel's India SIP edge is
   `in.voip.exotel.com:5070` (TCP) and `in.voip.exotel.com:443` (TLS) for signaling **from**
   LiveKit (outbound). Use the exact host/port Exotel assigns to your account.

4. **Route the DID to the trunk with a Flow.** In the Exotel Flow builder add a Connect
   applet with **Dial whom** set to `sip:<trunk_sid>` (the trunk SID with a `sip:` prefix,
   not a full URI), then map your Exophone to that flow.

5. **Auth.** Prefer SIP digest credentials (create via
   `POST .../trunks/${TRUNK_SID}/credentials` with `user_name`/`password`); Exotel challenges
   with a nonce. Put the same credentials on the LiveKit inbound trunk with
   `--auth-user`/`--auth-pass` (or `auth_username`/`auth_password` in the JSON) if you
   enable digest. IP allowlisting (`.../whitelisted-ips`) takes one static IP per call with
   `mask: 32` and has **no CIDR support**, so it does not suit LiveKit Cloud's shared
   egress — use digest instead.

   > Exotel can also provision the FQDN mapping for you: email the LiveKit SIP FQDN and
   > your mobile DID to `hello@exotel.com`. Confirm the current signaling and media IP
   > ranges before tightening firewalls; Exotel's network/firewall page is the source of
   > truth and changes.

## Step 3b - configure Plivo (Zentrunk)

API at `https://api.plivo.com/v1/Account/$PLIVO_AUTH_ID` (basic auth). Console path:
**SIP Trunking -> Inbound Trunks**.

1. **Create an origination URI** pointing at LiveKit, including the transport:

   ```bash
   curl -s "https://api.plivo.com/v1/Account/$PLIVO_AUTH_ID/Zentrunk/URI/" \
     -u "$PLIVO_AUTH_ID:$PLIVO_AUTH_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{
       "name": "LiveKit SIP endpoint",
       "uri": "<subdomain>.india.sip.livekit.cloud;transport=tcp"
     }'
   ```

   Save `uri_uuid`. Use `;transport=tls` for secure trunking.

2. **Create the inbound trunk** with that URI as primary:

   ```bash
   curl -s "https://api.plivo.com/v1/Account/$PLIVO_AUTH_ID/Zentrunk/Trunk/" \
     -u "$PLIVO_AUTH_ID:$PLIVO_AUTH_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{
       "name": "My LiveKit inbound trunk",
       "trunk_direction": "inbound",
       "primary_uri_uuid": "<uri_uuid>"
     }'
   ```

   Save `trunk_id`.

3. **Connect the phone number** by setting its `app_id` to the trunk id:

   ```bash
   curl -s "https://api.plivo.com/v1/Account/$PLIVO_AUTH_ID/Number/918069000000/" \
     -u "$PLIVO_AUTH_ID:$PLIVO_AUTH_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"app_id": "<trunk_id>"}'
   ```

   In the console: **Phone Numbers -> Purchased Numbers -> Application Type: SIP Trunk ->
   Trunk**.

4. **Region pinning is mandatory for India.** If the number is Indian or you dial Indian
   numbers, use the `.india.sip.livekit.cloud` endpoint and enable region pinning in the
   LiveKit project. Calls fail to connect otherwise.

## Step 4 - run the agent worker

The dispatch rule sends calls to `agent_name=ai-receptionist`, so the worker must be up and
registered under that name:

```bash
cd agent
uv sync
uv run python -m src.receptionist_agent dev
```

`LIVEKIT_AGENT_NAME` (default `ai-receptionist`) must equal the dispatch rule's
`agent_name`. `dev` mode connects to the project in your `.env`. For a persistent worker,
deploy it (LiveKit Cloud agents or your own host) and register the same name.

## Step 5 - test with a real phone call

1. Dial the DID from any phone (mobile or landline).
2. The Exotel/Plivo edge INVITEs LiveKit; LiveKit creates room `call-<random>` and adds the
   caller as a SIP participant.
3. The agent answers with the AI disclosure + recording-consent greeting, then handles the
   call. Try a booking: give a name, date, and time, and confirm the read-back.

Verify the plumbing:

```bash
lk room list                                  # expect call-<random>
lk room participants list call-<random>       # SIP participant + agent
lk room participants get --room call-<random> <SIP_PARTICIPANT_ID>
```

Expected SIP participant attributes:

| Attribute | Expected value |
| --- | --- |
| `kind` | `SIP` |
| `sip.trunkPhoneNumber` | your DID |
| `sip.phoneNumber` | caller's number (absent if `hide_phone_number` is set) |
| `sip.trunkID` | trunk id from Step 2 |
| `sip.ruleID` | dispatch rule id from Step 2 |
| `sip.callID` / `sip.callIDFull` | present; use to correlate provider logs |

Also check the agent worker logs (JSON on stdout): a `session_started` event with the room
name, `config_source`, and `tools`, plus per-turn `turn_latency`. In LiveKit Cloud, open
**Telephony -> Call logs** and the **Sessions** view for the same call.

### Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| Rings, agent never answers | Dispatch rule missing `room_config.agents[].agent_name`, or it doesn't match `LIVEKIT_AGENT_NAME`; or the worker isn't running/registered |
| 403 from provider | Digest credentials don't match between Exotel/Plivo and the LiveKit trunk, or IP ACL is interfering |
| 486 Busy Here | `ringing_timeout` expired — no participant joined to subscribe to the caller |
| Connects but no audio | Media (RTP) blocked, or transport mismatch (`udp`/`tcp`/`tls`); check provider CDR and open the media ranges |
| One-way audio | Firewall allowing signaling but not RTP; verify both directions |
| No room created | Inbound trunk `numbers` doesn't match the DID, or no dispatch rule matches the trunk |
| 503 on outbound | Wrong trunk `address` / inline `hostname` |

Provider logs first (`cx.plivo.com/logs`, Exotel trunk logs, Exotel Flow logs), then the
LiveKit **Telephony** dashboard. Use `sip.callID` to line them up. Full list of codes:
[SIP troubleshooting](https://docs.livekit.io/reference/telephony/troubleshooting.md).

## Step 6 - human transfer to the front desk

The `transfer_to_human` tool dials the clinic front desk into the **caller's existing
room** with `CreateSIPParticipant(wait_until_answered=true)`. The caller stays in the room,
so if the front desk does not answer the agent can still take a message.

1. Set the number in the dashboard: **Clinic setup -> Front desk number**. The agent loads
   it from `GET /api/v1/agent/clinic-config`. `TRANSFER_NUMBER` in `.env` is only a
   fallback for local runs.
2. Create an outbound trunk (once per provider). Example for Plivo:

   ```bash
   lk sip outbound create \
     --name "Clinic front desk outbound" \
     --address "<trunk>.zt.plivo.com" \
     --numbers "$LIVEKIT_SIP_NUMBER" \
     --destination-country IN \
     --transport tls \
     --auth-user "$PLIVO_SIP_USERNAME" \
     --auth-pass "$PLIVO_SIP_PASSWORD"
   ```

   For Exotel, use the outbound edge (`in.voip.exotel.com`, port 5070 TCP or 443 TLS) and
   the digest credentials from Step 3a. The trunk `numbers` list must include the caller ID
   you want the clinic to see; `LIVEKIT_SIP_NUMBER` is sent as `sip_number`.
3. Put the returned trunk id in `.env` as `LIVEKIT_SIP_OUTBOUND_TRUNK` and restart the
   agent worker.
4. Tune `TRANSFER_RING_TIMEOUT_SECONDS` (default 20). When the ring window expires, the
   agent says the front desk is unavailable, takes the caller's name, number, and message,
   and creates a callback task through `POST /api/v1/agent/callbacks`.

Transfer flow:

```
caller + agent in call-<random>
  -> agent says "please hold"
  -> CreateSIPParticipant(front desk, wait_until_answered, ringing_timeout)
  -> answered: front desk joins the same room; agent disables its mic/speaker
  -> caller and front desk talk until either hangs up, then the room closes
  -> no answer: agent re-enables audio and takes a callback
```

The agent triggers a transfer on emergencies, explicit human requests, billing/insurance
questions, repeated frustration, and after two failed attempts to understand. The dashboard
**Callbacks** page lists fallback tasks (`pending`, `contacted`, `done`).

> Warm transfer needs an outbound trunk. LiveKit Phone Numbers are inbound-only, so the
> front desk leg must go through Exotel/Plivo. Cold transfer via SIP REFER is not used
> because it cannot fall back when the destination does not answer.

## Outbound calls (not implemented)

Appointment reminders use WhatsApp/SMS, not outbound voice calls; see
[`messaging.md`](messaging.md). If outbound calling is added later, it can reuse the
outbound trunk from Step 6:

- Exotel edge (digest): `in.voip.exotel.com:5070` TCP or `:443` TLS, with the trunk
  credentials created in Step 3a.
- Set `destination_country: "IN"` so outbound calls originate from India.
- Keep a consent flag before dialing: DPDP + TRAI rules mean no outbound calling without
  recorded consent.

LiveKit Phone Numbers support inbound only, so outbound always needs Exotel/Plivo.

## Compliance notes (India)

- Use the region-pinned `.india` endpoint and `destination_country: "in"` to keep signaling
  and media in-country.
- Room names from individual dispatch rules contain the caller's number (PII) and are
  logged by LiveKit; prefer the callee "route by ID" pattern or a direct rule if you need
  to avoid that.
- Mask phone numbers in logs and dashboards where possible; see the DPDP section in
  `AGENTS.md`.

## Files

| Path | Purpose |
| --- | --- |
| `infra/livekit-sip/setup-telephony.sh` | create inbound trunk + dispatch rule from env |
| `infra/livekit-sip/teardown-telephony.sh` | delete them using the saved ids |
| `infra/livekit-sip/inbound-trunk.exotel.json` | Exotel inbound trunk (dashboard JSON) |
| `infra/livekit-sip/inbound-trunk.plivo.json` | Plivo inbound trunk (dashboard JSON) |
| `infra/livekit-sip/dispatch-rule.individual.json` | individual dispatch rule + agent dispatch |
| `agent/src/receptionist_agent.py` | worker; `agent_name` must match the dispatch rule |
