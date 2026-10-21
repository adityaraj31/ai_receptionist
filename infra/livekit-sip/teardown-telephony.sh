#!/usr/bin/env bash
#
# Delete the LiveKit inbound trunk and dispatch rule created by
# setup-telephony.sh. Reads ids from infra/livekit-sip/.env.telephony, or takes
# them as arguments.
#
# Usage:
#   infra/livekit-sip/teardown-telephony.sh [TRUNK_ID] [DISPATCH_RULE_ID]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="${SCRIPT_DIR}/.env.telephony"

TRUNK_ID="${1:-}"
RULE_ID="${2:-}"

if [[ -z "${TRUNK_ID}" || -z "${RULE_ID}" ]]; then
  if [[ -f "${STATE_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${STATE_FILE}"
  fi
  TRUNK_ID="${TRUNK_ID:-${LIVEKIT_SIP_TRUNK_ID:-}}"
  RULE_ID="${RULE_ID:-${LIVEKIT_SIP_DISPATCH_RULE_ID:-}}"
fi

command -v lk >/dev/null 2>&1 || {
  echo "missing required command: lk" >&2
  exit 1
}

if [[ -n "${RULE_ID}" ]]; then
  echo "deleting dispatch rule ${RULE_ID} ..."
  lk sip dispatch delete "${RULE_ID}"
else
  echo "no dispatch rule id; run 'lk sip dispatch list --json' to find it." >&2
fi

if [[ -n "${TRUNK_ID}" ]]; then
  echo "deleting inbound trunk ${TRUNK_ID} ..."
  lk sip inbound delete "${TRUNK_ID}"
else
  echo "no inbound trunk id; run 'lk sip inbound list --json' to find it." >&2
fi

rm -f "${STATE_FILE}"
echo "teardown complete."
