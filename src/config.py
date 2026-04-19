"""設定ローダー。config.yaml と環境変数を読み込む。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class SiteConfig:
    name: str
    url: str
    measurement_id: str
    ga4_property_id: str


@dataclass
class SearchConsoleConfig:
    site_url: str


@dataclass
class ReportConfig:
    recipients: list[str]
    output_dir: str
    comparison: str


@dataclass
class Thresholds:
    bounce_rate_warning: float
    conversion_rate_warning: float
    uu_drop_pct: float


@dataclass
class ClaudeConfig:
    model: str
    effort: str


@dataclass
class Config:
    site: SiteConfig
    search_console: SearchConsoleConfig
    conversion_events: list[str]
    report: ReportConfig
    thresholds: Thresholds
    claude: ClaudeConfig
    env: dict[str, str] = field(default_factory=dict)


def load_config(path: str | Path = "config.yaml") -> Config:
    load_dotenv()
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"{cfg_path} が見つかりません。config.yaml.example をコピーして作成してください。"
        )
    with cfg_path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    return Config(
        site=SiteConfig(**raw["site"]),
        search_console=SearchConsoleConfig(**raw["search_console"]),
        conversion_events=list(raw.get("conversion_events", [])),
        report=ReportConfig(**raw["report"]),
        thresholds=Thresholds(**raw["thresholds"]),
        claude=ClaudeConfig(**raw["claude"]),
        env={
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
            "GOOGLE_APPLICATION_CREDENTIALS": os.environ.get(
                "GOOGLE_APPLICATION_CREDENTIALS", ""
            ),
            "SMTP_HOST": os.environ.get("SMTP_HOST", ""),
            "SMTP_PORT": os.environ.get("SMTP_PORT", "587"),
            "SMTP_USER": os.environ.get("SMTP_USER", ""),
            "SMTP_PASSWORD": os.environ.get("SMTP_PASSWORD", ""),
            "SMTP_FROM": os.environ.get("SMTP_FROM", ""),
        },
    )
