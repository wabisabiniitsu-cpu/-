#!/usr/bin/env bash
# PreToolUse hook (matcher: Agent)
# 秘書がAgentツールで担当を呼ぶ直前に、依頼内容をpendingキューに積む。
# description の先頭に「[担当名] ...」の形式でタグを付ける運用を前提とする。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PENDING="$DIR/pending.jsonl"
LOCK="$DIR/.lock"

input="$(cat)"

description="$(echo "$input" | jq -r '.tool_input.description // ""')"
subagent_type="$(echo "$input" | jq -r '.tool_input.subagent_type // ""')"

if [[ "$description" =~ ^\[([^]]+)\] ]]; then
  role="${BASH_REMATCH[1]}"
else
  role="$subagent_type"
fi

ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
line="$(jq -nc --arg role "$role" --arg description "$description" --arg ts "$ts" \
  '{role: $role, description: $description, ts: $ts}')"

{
  flock -x 200
  echo "$line" >> "$PENDING"
} 200>"$LOCK"

exit 0
