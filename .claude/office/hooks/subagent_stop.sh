#!/usr/bin/env bash
# SubagentStop hook
# 該当 agent_id を active から取り除く（idempotent。何度呼ばれても安全）。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$DIR/state.json"
LOCK="$DIR/.lock"

input="$(cat)"
agent_id="$(echo "$input" | jq -r '.agent_id // ""')"

{
  flock -x 200

  if [[ -f "$STATE" ]]; then
    current="$(cat "$STATE")"
    updated="$(echo "$current" | jq --arg agent_id "$agent_id" \
      '.active = [.active[] | select(.agent_id != $agent_id)]')"
    echo "$updated" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
  fi
} 200>"$LOCK"

exit 0
