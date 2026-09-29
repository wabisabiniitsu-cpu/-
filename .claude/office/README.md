# AI社員オフィス可視化

`.claude/agents/` の各担当を、アイソメトリックのオフィス画面上でリアルタイムに可視化するツールです。
秘書（Claude Codeのメインセッション）がAgentツールで担当を呼び出すと、対応する机が光ります。

## 仕組み

- `hooks/pretooluse_agent.sh`（PreToolUse, matcher: Agent）
  Agentツール実行前に、依頼内容を `pending.jsonl` に積む
- `hooks/subagent_start.sh`（SubagentStart）
  `pending.jsonl` の先頭を取り出し、`state.json` の `active` に追加する
- `hooks/subagent_stop.sh`（SubagentStop）
  該当エージェントを `active` から取り除く
- `index.html`
  `state.json` を1秒ごとにポーリングし、稼働中の担当の机を光らせる

LLM呼び出しは発生しません（hookはすべてシェルスクリプト + jq）。

## 担当タグの付け方（秘書向け）

Agentツールを呼ぶとき、`description` の先頭に `[担当名]` を付けること。
（`.claude/agents/*.md` はこの環境のAgentツールでは直接は呼び出せないため、
実際には `general-purpose` などの汎用エージェントに役割ファイルを読ませて動かしている。
その際も description の先頭タグだけは付けること。）

```
description: "[営業担当] 美容鍼サロンへの営業リスト作成"
```

タグの担当名は `state.json` の `roles`（秘書・営業担当・リサーチ担当・マーケター・レビュー担当）
のいずれかに合わせる。タグがない場合は `subagent_type`（claude, general-purpose 等）がそのまま
role として表示される。

## ローカルで見る方法

このリポジトリをクローンして Claude Code CLI をローカルで動かしている場合、
このディレクトリで簡易サーバーを起動してブラウザで開く。

```bash
cd .claude/office
python3 -m http.server 8765
# ブラウザで http://localhost:8765 を開く
```

**注意**：claude.ai のクラウドセッション（このリモート環境）上では、
コンテナのファイルシステムに外部のブラウザから直接アクセスする手段がないため、
このページをその場でライブ表示することはできません。ローカルのClaude Code CLIで
このプロジェクトを動かしているときにのみ、リアルタイムに机が光る様子を見られます。
