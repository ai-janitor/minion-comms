#!/usr/bin/env bash
set -euo pipefail

# poll.sh — block until an agent has unread messages in minion-comms.
#
# Usage: poll.sh <agent-name> [--interval <seconds>] [--timeout <seconds>]
#
# Exits 0 when unread messages are found.
# Exits 1 on timeout (if --timeout is set).
# Exits 2 on usage error.
#
# Used by minion-swarm daemons to detect incoming work without
# coupling to the minion-comms DB schema.

AGENT_NAME="${1:?Usage: poll.sh <agent-name> [--interval <seconds>] [--timeout <seconds>]}"
shift

INTERVAL=5
TIMEOUT=0  # 0 = no timeout (poll forever)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval) INTERVAL="$2"; shift 2 ;;
    --timeout)  TIMEOUT="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

DB_PATH="${MINION_COMMS_DB_PATH:-${HOME}/.minion-comms/messages.db}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "Error: DB not found at $DB_PATH" >&2
  exit 2
fi

elapsed=0

while true; do
  # Count unread direct messages
  direct=$(sqlite3 "$DB_PATH" \
    "SELECT COUNT(*) FROM messages WHERE to_agent = '${AGENT_NAME}' AND read_flag = 0;" \
    2>/dev/null || echo 0)

  # Count unread broadcast messages
  broadcast=$(sqlite3 "$DB_PATH" \
    "SELECT COUNT(*) FROM messages
     WHERE to_agent = 'all' AND from_agent != '${AGENT_NAME}'
     AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = '${AGENT_NAME}');" \
    2>/dev/null || echo 0)

  total=$(( direct + broadcast ))

  if [[ "$total" -gt 0 ]]; then
    echo "$total"
    exit 0
  fi

  if [[ "$TIMEOUT" -gt 0 && "$elapsed" -ge "$TIMEOUT" ]]; then
    exit 1
  fi

  sleep "$INTERVAL"
  elapsed=$(( elapsed + INTERVAL ))
done
