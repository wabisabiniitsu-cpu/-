"""Jinja2 でレポートを Markdown / HTML に整形する。"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


_TEMPLATES_DIR = Path(__file__).parent / "templates"

_COMPARISON_LABELS = {
    "day_over_day": "前日比",
    "week_over_week": "前週比",
    "month_over_month": "前月比",
}


def _fmt_value(label: str, value: float | int) -> str:
    if label in ("直帰率", "CVR", "CTR"):
        return f"{value * 100:.2f}%"
    if label == "平均順位":
        return f"{value:.1f}"
    if label == "平均セッション時間":
        return f"{value:.1f}s"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return f"{int(value):,}"


def _fmt_change(label: str, change: float, change_pct: float) -> str:
    if label == "平均順位":
        # 順位は小さいほどよい → 符号を反転して表示
        arrow = "↑" if change < 0 else ("↓" if change > 0 else "→")
        return f"{arrow} {change:+.1f}"
    arrow = "↑" if change_pct > 0 else ("↓" if change_pct < 0 else "→")
    return f"{arrow} {change_pct * 100:+.1f}%"


def _as_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [_as_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _as_dict(v) for k, v in obj.items()}
    return obj


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["fmt"] = _fmt_value
    env.globals["fmt_change"] = _fmt_change
    return env


def render(
    site: dict,
    period: dict,
    comparison: str,
    ga4_current: Any,
    ga4_previous: Any,
    gsc_current: Any,
    gsc_previous: Any,
    deltas_ga4: list[Any],
    deltas_gsc: list[Any],
    top_pages: list[Any],
    channels: list[Any],
    top_queries: list[Any],
    rising_queries: list[Any],
    alerts: list[Any],
    insights_markdown: str,
    claude_model: str,
) -> tuple[str, str]:
    env = _env()
    ctx = {
        "site": site,
        "period": period,
        "comparison_label": _COMPARISON_LABELS.get(comparison, comparison),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ga4_current": _as_dict(ga4_current),
        "ga4_previous": _as_dict(ga4_previous),
        "gsc_current": _as_dict(gsc_current),
        "gsc_previous": _as_dict(gsc_previous),
        "deltas_ga4": _as_dict(deltas_ga4),
        "deltas_gsc": _as_dict(deltas_gsc),
        "top_pages": _as_dict(top_pages),
        "channels": _as_dict(channels),
        "top_queries": _as_dict(top_queries),
        "rising_queries": _as_dict(rising_queries),
        "alerts": _as_dict(alerts),
        "insights_markdown": insights_markdown,
        "claude_model": claude_model,
    }
    md = env.get_template("daily.md.j2").render(**ctx)
    html = env.get_template("daily.html.j2").render(**ctx)
    return md, html


def save(output_dir: str | Path, tag: str, markdown: str, html: str) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / f"{tag}.md"
    html_path = out / f"{tag}.html"
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return md_path, html_path
