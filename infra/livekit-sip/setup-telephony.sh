#!/usr/bin/env bash
#
# Create a LiveKit inbound SIP trunk and an individual dispatch rule that routes
# every caller into its own room and dispatches our agent worker into that room.
# The dispatch rule is scoped to the trunk created by this run.
#
# Provider-agnostic: the same LiveKit configuration works for Exotel and Plivo.
# The provider side (destination URI, DID mapping) is done in the Exotel/Plivo
# console or API. See ../../docs/telephony.md.
#
# Usage:
#   infra/livekit-sip/setup-telephony.sh [--dry-run]
#
# Reads values from the environment first, then from the repo-root .env.
#
# Required:
#   LIVEKIT_SIP_NUMBER   The DID in E.164, e.g. +918069000000
# Optional:
#   LIVEKIT_AGENT_NAME   Agent worker name (default: ai-receptionist)
#   SIP_TRUNK_NAME       LiveKit inbound trunk name (default: Exotel inbound)
#   SIP_ROOM_PREFIX      Room name prefix (default: call-)
#   SIP_DISPATCH_NAME    Dispatch rule name (default: ai-receptionist inbound)
#   SIP_KRISP_ENABLED    true/false, noise cancellation (default: true)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
STATE_FILE="${SCRIPT_DIR}/.env.telephony"

DRY_RUN=0
for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=1 ;;
    -h | --help)
      grep '^# ' "${BASH_SOURCE[0]}" | sed 's/^# //'
      exit 0
      ;;
    *)
      echo "unknown argument: ${arg}" >&2
      exit 2
      ;;
  esac
done

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

require python3

# Load repo-root .env without clobbering already-exported variables. The .env
# file is parsed instead of sourced so values with spaces or quotes are safe.
if [[ -f "${ROOT_DIR}/.env" ]]; then
  while IFS= read -r line; do
    key="${line%%=*}"
    [[ -n "${key}" && -z "${!key+x}" ]] || continue
    eval "export ${line}"
  done < <(python3 - "${ROOT_DIR}/.env" <<'PY'
import os
import shlex
import sys

path = sys.argv[1]
if os.path.exists(path):
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.isidentifier():
            continue
        value = value.strip()
        for quote in ("'", '"'):
            if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
                value = value[1:-1]
        print(f"{key}={shlex.quote(value)}")
PY
  )
fi

if [[ -z "${LIVEKIT_SIP_NUMBER:-}" ]]; then
  echo "LIVEKIT_SIP_NUMBER is required (E.164, e.g. +918069000000)." >&2
  echo "Set it in the repo-root .env or export it before running this script." >&2
  exit 1
fi

if ((DRY_RUN == 0)); then
  require lk
  if ! lk project list >/dev/null 2>&1; then
    echo "LiveKit CLI is not authenticated. Run: lk cloud auth" >&2
    exit 1
  fi
fi

AGENT_NAME="${LIVEKIT_AGENT_NAME:-ai-receptionist}"
TRUNK_NAME="${SIP_TRUNK_NAME:-Exotel inbound}"
ROOM_PREFIX="${SIP_ROOM_PREFIX:-call-}"
DISPATCH_NAME="${SIP_DISPATCH_NAME:-${AGENT_NAME} inbound}"
KRISP_ENABLED="${SIP_KRISP_ENABLED:-true}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

export LIVEKIT_SIP_NUMBER AGENT_NAME TRUNK_NAME ROOM_PREFIX DISPATCH_NAME KRISP_ENABLED
export TRUNK_JSON="${TMP_DIR}/inbound-trunk.json"
export DISPATCH_JSON="${TMP_DIR}/dispatch-rule.json"

python3 - <<'PY'
import json
import os

krisp = os.environ["KRISP_ENABLED"].lower() in {"1", "true", "yes", "on"}

with open(os.environ["TRUNK_JSON"], "w", encoding="utf-8") as fh:
    json.dump(
        {
            "trunk": {
                "name": os.environ["TRUNK_NAME"],
                "numbers": [os.environ["LIVEKIT_SIP_NUMBER"]],
                "krisp_enabled": krisp,
            }
        },
        fh,
        indent=2,
    )
    fh.write("\n")

with open(os.environ["DISPATCH_JSON"], "w", encoding="utf-8") as fh:
    json.dump(
        {
            "dispatch_rule": {
                "name": os.environ["DISPATCH_NAME"],
                "rule": {
                    "dispatch_rule_individual": {
                        "room_prefix": os.environ["ROOM_PREFIX"],
                    }
                },
                "room_config": {
                    "agents": [{"agent_name": os.environ["AGENT_NAME"]}],
                },
            }
        },
        fh,
        indent=2,
    )
    fh.write("\n")
PY

echo "== inbound trunk =="
cat "${TRUNK_JSON}"
echo "== dispatch rule =="
cat "${DISPATCH_JSON}"

if ((DRY_RUN == 1)); then
  echo
  echo "dry run: nothing created. Re-run without --dry-run to apply."
  exit 0
fi

lookup_id() {
  # Reads JSON on stdin. $1: name to match, $2: comma-separated id keys to try.
  python3 -c '
import json
import sys

name, keys = sys.argv[1], sys.argv[2].split(",")
data = json.load(sys.stdin)


def walk(node):
    if isinstance(node, dict):
        if node.get("name") == name:
            for key in keys:
                if node.get(key):
                    return node[key]
        for value in node.values():
            found = walk(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = walk(value)
            if found:
                return found
    return None


print(walk(data) or "")
' "$1" "$2"
}

echo
echo "creating inbound trunk '${TRUNK_NAME}' for ${LIVEKIT_SIP_NUMBER} ..."
lk sip inbound create "${TRUNK_JSON}"

TRUNK_ID="$(lk sip inbound list --json | lookup_id "${TRUNK_NAME}" "sip_trunk_id,sipTrunkId,id")"
if [[ -z "${TRUNK_ID}" ]]; then
  echo "could not resolve the inbound trunk id; run 'lk sip inbound list --json'" >&2
  exit 1
fi
echo "trunk id: ${TRUNK_ID}"

echo
echo "creating dispatch rule '${DISPATCH_NAME}' (agent: ${AGENT_NAME}, trunk: ${TRUNK_ID}) ..."
python3 - "${DISPATCH_JSON}" "${TRUNK_ID}" <<'PY'
import json
import sys

path, trunk_id = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    data = json.load(fh)
data["dispatch_rule"]["trunk_ids"] = [trunk_id]
with open(path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PY
lk sip dispatch create "${DISPATCH_JSON}"

RULE_ID="$(lk sip dispatch list --json | lookup_id "${DISPATCH_NAME}" "sip_dispatch_rule_id,sipDispatchRuleId,id")"
if [[ -z "${RULE_ID}" ]]; then
  echo "could not resolve the dispatch rule id; run 'lk sip dispatch list --json'" >&2
  exit 1
fi
echo "dispatch rule id: ${RULE_ID}"

umask 077
cat >"${STATE_FILE}" <<EOF
# Generated by infra/livekit-sip/setup-telephony.sh. Do not commit.
LIVEKIT_SIP_TRUNK_ID=${TRUNK_ID}
LIVEKIT_SIP_DISPATCH_RULE_ID=${RULE_ID}
LIVEKIT_SIP_NUMBER=${LIVEKIT_SIP_NUMBER}
LIVEKIT_AGENT_NAME=${AGENT_NAME}
EOF

echo
echo "saved ids to ${STATE_FILE}"
echo "next: start the agent worker, then dial ${LIVEKIT_SIP_NUMBER} from a phone."
