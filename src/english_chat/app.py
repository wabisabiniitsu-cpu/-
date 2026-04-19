"""英会話練習アプリ: Claude を会話相手に英語を練習し、日本語で文法解説を受ける。"""
from __future__ import annotations

from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import box

console = Console()

TOPICS = {
    "1": ("自己紹介", "Let's practice introducing yourself in English! Tell me about yourself."),
    "2": ("レストランで注文", "You're at an English-speaking restaurant. I'll be your server. What would you like to order?"),
    "3": ("道を聞く・案内する", "You need directions in a foreign city. I'll play a local. Where would you like to go?"),
    "4": ("ショッピング", "You're shopping at an English store. I'll be the shop assistant. What are you looking for?"),
    "5": ("天気・日常会話", "Let's have a casual chat about the weather and daily life, just like with a new friend!"),
    "6": ("仕事・職場", "Let's talk about work! Tell me about your job or practice job interview questions."),
    "7": ("旅行・観光", "You're a tourist in an English-speaking country. Let's explore together!"),
    "0": ("自由会話", "Let's have a free conversation in English! Talk about anything you like."),
}

_SYSTEM = """\
You are a friendly and encouraging English conversation teacher helping a Japanese learner practice English.

Your response MUST always follow this exact format — two clearly separated sections:

---
💬 **English Response**

[Write your natural English reply here. Keep it friendly and conversational. If the learner made an error, gently model the correct phrasing in your response without making them feel bad.]

---
📝 **日本語フィードバック**

**✅ 良かった点:**
[What the learner did well, in Japanese. Be specific and encouraging.]

**📌 文法・表現のポイント:**
[Grammar corrections and explanations in Japanese. Use simple, clear Japanese. Format each point as:
• 間違い: "..." → 正しくは: "..."
　　理由: [easy Japanese explanation]
If there are no mistakes, write「問題なし！自然な英語でした」]

**💡 もっと自然な言い方:**
[Optional: Suggest a more native-sounding alternative or useful phrase, in Japanese with English example]

**🔤 今日の表現メモ:**
[Pick 1–2 key vocabulary or phrases from this exchange. Format:
• [English word/phrase] = [Japanese meaning] (例: "[example sentence]")]
---

Rules:
- ALWAYS respond with BOTH sections, every single turn.
- Keep English responses warm, short, and natural — like a real conversation.
- Grammar explanations must be in plain Japanese that a beginner can understand.
- Never make the learner feel embarrassed. Always be positive and supportive.
- If the learner writes in Japanese, gently remind them to try in English, and give them a hint.
"""


def _show_welcome() -> None:
    console.print()
    console.print(Panel(
        "[bold yellow]🇺🇸 英会話練習アプリ 🇬🇧[/bold yellow]\n\n"
        "[white]Claudeと英語で会話しながら、文法も日本語で学べます！\n"
        "間違えても大丈夫。どんどん話しましょう！[/white]",
        border_style="yellow",
        padding=(1, 4),
    ))
    console.print()


def _show_commands() -> None:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="cyan")
    table.add_column(style="white")
    table.add_row("!topic", "話題を変える")
    table.add_row("!help", "使い方を表示")
    table.add_row("!hint", "英語のヒントをもらう")
    table.add_row("exit / quit", "終了")
    console.print(Panel(table, title="[bold]コマンド一覧[/bold]", border_style="dim", padding=(0, 1)))
    console.print()


def _choose_topic() -> tuple[str, str]:
    console.print("[bold cyan]話題を選んでください:[/bold cyan]")
    for key, (name, _) in TOPICS.items():
        console.print(f"  [cyan]{key}[/cyan]  {name}")
    console.print()
    choice = Prompt.ask("番号を入力", choices=list(TOPICS.keys()), default="0")
    name, starter = TOPICS[choice]
    console.print(f"\n[green]「{name}」を選びました！[/green]\n")
    return name, starter


def _hint_prompt(topic_starter: str) -> str:
    return (
        f"The learner wants a hint. The current topic context is: {topic_starter}\n"
        "Give them a very simple English sentence they could use right now, "
        "with Japanese translation. Keep it encouraging and brief."
    )


def english_chat_loop(client: Anthropic) -> None:
    _show_welcome()
    _show_commands()

    topic_name, topic_starter = _choose_topic()

    system = [{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}]
    history: list[dict] = []

    # AIから先に話しかける
    console.print("[dim]Claudeが話しかけています...[/dim]")
    opener_messages = [{"role": "user", "content": f"[SYSTEM: Start the conversation about the topic: {topic_starter}. Say a short, friendly opening sentence in English to the learner, then give the Japanese feedback section as usual.]"}]
    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system,
        messages=opener_messages,
    ) as stream:
        opener_text = stream.get_final_message()

    opener = "\n".join(
        b.text for b in opener_text.content if getattr(b, "type", None) == "text"
    ).strip()

    console.print()
    console.print(Panel(opener, title="[bold green]Claude[/bold green]", border_style="green", padding=(1, 2)))
    console.print()

    history.append({"role": "user", "content": opener_messages[0]["content"]})
    history.append({"role": "assistant", "content": opener_text.content})

    while True:
        try:
            user_input = console.input("[bold cyan]あなた (英語で入力) >[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]お疲れ様でした！また練習しましょう！[/yellow]")
            return

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", ":q"}:
            console.print("[yellow]お疲れ様でした！また練習しましょう！[/yellow]")
            return

        if user_input == "!help":
            _show_commands()
            continue

        if user_input == "!topic":
            topic_name, topic_starter = _choose_topic()
            history = []
            console.print("[dim]Claudeが話しかけています...[/dim]")
            opener_messages = [{"role": "user", "content": f"[SYSTEM: New topic selected. Start fresh: {topic_starter}]"}]
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system,
                messages=opener_messages,
            ) as stream:
                opener_text = stream.get_final_message()
            opener = "\n".join(
                b.text for b in opener_text.content if getattr(b, "type", None) == "text"
            ).strip()
            console.print()
            console.print(Panel(opener, title="[bold green]Claude[/bold green]", border_style="green", padding=(1, 2)))
            console.print()
            history.append({"role": "user", "content": opener_messages[0]["content"]})
            history.append({"role": "assistant", "content": opener_text.content})
            continue

        if user_input == "!hint":
            hint_content = _hint_prompt(topic_starter)
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": hint_content}],
            ) as stream:
                hint_msg = stream.get_final_message()
            hint_text = "\n".join(
                b.text for b in hint_msg.content if getattr(b, "type", None) == "text"
            ).strip()
            console.print()
            console.print(Panel(hint_text, title="[bold magenta]💡 ヒント[/bold magenta]", border_style="magenta", padding=(1, 2)))
            console.print()
            continue

        history.append({"role": "user", "content": user_input})

        console.print("[dim]Claudeが考えています...[/dim]")
        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=history,
        ) as stream:
            response_msg = stream.get_final_message()

        response_text = "\n".join(
            b.text for b in response_msg.content if getattr(b, "type", None) == "text"
        ).strip()

        history.append({"role": "assistant", "content": response_msg.content})

        console.print()
        console.print(Panel(
            response_text,
            title="[bold green]Claude[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))
        console.print()
