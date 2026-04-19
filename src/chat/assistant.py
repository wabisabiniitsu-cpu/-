"""対話型 Q&A: Claude が最新レポートを参照してマーケター視点で答える。"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from anthropic import Anthropic
from rich.console import Console
from rich.markdown import Markdown

from ..config import ClaudeConfig


_SYSTEM_PROMPT = """あなたはハリナビ (https://www.harinavi.jp/) 専属のシニアグロースマーケターです。
ユーザー (社内マーケ担当) からの質問に、提供された直近の GA4 / Search Console 指標を根拠に
日本語で答えてください。

- 数値を答えるときは必ず元データのフィールドを引用する (例: 「直近 7 日の PV は X, 前期比 Y%」)
- データに無い項目については推測せず、「データに含まれていない」と明示する
- 改善提案は必ず「根拠となる数値」+「具体的アクション」+「想定効果」をセットにする
- 要点は先に結論から述べ、必要に応じて箇条書き・表で整理する
"""


def _as_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [_as_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _as_dict(v) for k, v in obj.items()}
    return obj


def _context_block(report_payload: dict[str, Any]) -> str:
    return (
        "以下が直近レポートの元データです (JSON):\n"
        "```json\n"
        + json.dumps(_as_dict(report_payload), ensure_ascii=False, indent=2)
        + "\n```"
    )


def chat_loop(
    client: Anthropic,
    claude_cfg: ClaudeConfig,
    report_payload: dict[str, Any],
) -> None:
    """ターミナル上でマーケターチャットを開く。"""
    console = Console()
    console.rule("[bold]ハリナビ マーケ AI アシスタント")
    console.print(
        "直近レポートを読み込みました。質問を入力してください (Ctrl+D / `exit` で終了)\n"
    )

    # system プロンプト + レポートコンテキストをキャッシュ対象にする。
    # 質問のたびに同じプレフィックスが再送されるのでキャッシュが効く。
    system = [
        {"type": "text", "text": _SYSTEM_PROMPT},
        {
            "type": "text",
            "text": _context_block(report_payload),
            "cache_control": {"type": "ephemeral"},
        },
    ]

    history: list[dict[str, Any]] = []

    while True:
        try:
            question = console.input("[bold cyan]あなた >[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n終了します。")
            return
        if not question:
            continue
        if question.lower() in {"exit", "quit", ":q"}:
            console.print("終了します。")
            return

        history.append({"role": "user", "content": question})

        with client.messages.stream(
            model=claude_cfg.model,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            output_config={"effort": claude_cfg.effort},
            system=system,
            messages=history,
        ) as stream:
            final = stream.get_final_message()

        text = "\n".join(
            b.text for b in final.content if getattr(b, "type", None) == "text"
        ).strip()
        history.append({"role": "assistant", "content": final.content})

        console.print()
        console.print(Markdown(text))
        console.print()
