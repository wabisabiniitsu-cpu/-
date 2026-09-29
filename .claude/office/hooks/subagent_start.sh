#!/usr/bin/env bash
# SubagentStart hook
# pendingキューの先頭（FIFO）を取り出し、その担当を active に追加する。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PENDING="$DIR/pending.jsonl"
STATE="$DIR/state.json"
LOCK="$DIR/.lock"

input="$(cat)"
agent_id="$(echo "$input" | jq -r '.agent_id // ""')"
agent_type="$(echo "$input" | jq -r '.agent_type // ""')"

{
  flock -x 200

  entry='{}'
  if [[ -f "$PENDING" && -s "$PENDING" ]]; then
    entry="$(head -n 1 "$PENDING")"
    tail -n +2 "$PENDING" > "$PENDING.tmp" && mv "$PENDING.tmp" "$PENDING"
  fi

  role="$(echo "$entry" | jq -r '.role // empty')"
  description="$(echo "$entry" | jq -r '.description // empty')"
  [[ -z "$role" ]] && role="$agent_type"

  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  if [[ -f "$STATE" ]]; then
    current="$(cat "$STATE")"
  else
    current='{"roles":["秘書","営業担当","記事担当","リサーチ担当","マーケター","レビュー担当"],"active":[]}'
  fi

  updated="$(echo "$current" | jq \
    --arg agent_id "$agent_id" \
    --arg role "$role" \
    --arg description "$description" \
    --arg started_at "$ts" \
    '.active += [{agent_id: $agent_id, role: $role, description: $description, started_at: $started_at}]')"

  echo "$updated" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
} 200>"$LOCK"

exit 0
