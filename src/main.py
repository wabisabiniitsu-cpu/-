"""CLI エントリ: report / run-daily / chat サブコマンド。"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from anthropic import Anthropic
from rich.console import Console

from .chat.assistant import chat_loop
from .config import load_config
from .english_chat.app import english_chat_loop
from .pipeline import load_latest_payload, run_daily


def _parse_date(s: str | None) -> date:
    if not s:
        return date.today() - timedelta(days=1)
    return datetime.strptime(s, "%Y-%m-%d").date()


def cmd_report(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    client = Anthropic(api_key=cfg.env["ANTHROPIC_API_KEY"] or None)
    end = _parse_date(args.date)
    result = run_daily(cfg, end, client, send_email=False)
    Console().print_json(data=result)
    return 0


def cmd_run_daily(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    client = Anthropic(api_key=cfg.env["ANTHROPIC_API_KEY"] or None)
    end = _parse_date(args.date)
    result = run_daily(cfg, end, client, send_email=not args.no_email)
    Path(cfg.report.output_dir).mkdir(parents=True, exist_ok=True)
    log_path = Path(cfg.report.output_dir) / "run.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
    Console().print_json(data=result)
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    client = Anthropic(api_key=cfg.env["ANTHROPIC_API_KEY"] or None)
    payload = load_latest_payload(cfg)
    chat_loop(client, cfg.claude, payload)
    return 0


def cmd_english_chat(args: argparse.Namespace) -> int:
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            cfg = load_config(args.config)
            api_key = cfg.env.get("ANTHROPIC_API_KEY")
        except Exception:
            pass
    client = Anthropic(api_key=api_key or None)
    english_chat_loop(client)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="harinavi-marketing",
        description="ハリナビ マーケティング分析ツール",
    )
    p.add_argument(
        "-c", "--config", default="config.yaml", help="config.yaml のパス"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("report", help="レポートを生成して保存する (メール送信なし)")
    s.add_argument("--date", help="基準日 YYYY-MM-DD (省略時は昨日)")
    s.set_defaults(func=cmd_report)

    s = sub.add_parser(
        "run-daily", help="日次実行: 収集・分析・レポ生成・メール送信まで"
    )
    s.add_argument("--date", help="基準日 YYYY-MM-DD (省略時は昨日)")
    s.add_argument(
        "--no-email", action="store_true", help="メール送信をスキップする"
    )
    s.set_defaults(func=cmd_run_daily)

    s = sub.add_parser("chat", help="最新レポートを元に対話型で質問する")
    s.set_defaults(func=cmd_chat)

    s = sub.add_parser("english-chat", help="英会話練習アプリ: Claudeと英語で会話して文法を学ぶ")
    s.set_defaults(func=cmd_english_chat)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
