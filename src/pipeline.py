"""日次の `収集 → 分析 → レポート生成` パイプライン。CLI / chat の両方から呼ばれる。"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from .analyzer.insights import InsightResult, build_payload, generate_insights
from .analyzer.metrics import (
    check_alerts,
    comparison_window,
    compute_ga4_deltas,
    compute_gsc_deltas,
)
from .collectors.ga4 import GA4Collector, GA4Metrics
from .collectors.search_console import SearchConsoleCollector
from .config import Config
from .report import generator as report_gen
from .storage.db import MetricsDB


def _as_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [_as_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _as_dict(v) for k, v in obj.items()}
    return obj


def collect_all(cfg: Config, end: date) -> dict[str, Any]:
    """GA4 と Search Console から現期/前期の指標を取得してまとめて返す。"""
    cur_start, cur_end, prev_start, prev_end = comparison_window(end, cfg.report.comparison)

    ga4 = GA4Collector(cfg.site.ga4_property_id, cfg.conversion_events)
    ga4_current = ga4.fetch_summary(cur_start, cur_end)
    ga4_previous = ga4.fetch_summary(prev_start, prev_end)
    top_pages = ga4.fetch_top_pages(cur_start, cur_end, limit=10)
    channels = ga4.fetch_channels(cur_start, cur_end)

    gsc_current = None
    gsc_previous = None
    top_queries = []
    rising_queries = []
    try:
        gsc = SearchConsoleCollector(cfg.search_console.site_url)
        gsc_report = gsc.fetch_report(cur_start, cur_end)
        gsc_current = gsc_report.totals
        gsc_previous = gsc.fetch_totals(prev_start, prev_end)
        top_queries = gsc_report.top_queries
        rising_queries = gsc_report.rising_queries
    except Exception as e:  # noqa: BLE001
        # Search Console は権限設定不備で初回失敗しやすい → レポート継続
        print(f"[warn] Search Console の取得に失敗しました: {e}")

    return {
        "window": {
            "current": (cur_start, cur_end),
            "previous": (prev_start, prev_end),
        },
        "ga4_current": ga4_current,
        "ga4_previous": ga4_previous,
        "top_pages": top_pages,
        "channels": channels,
        "gsc_current": gsc_current,
        "gsc_previous": gsc_previous,
        "top_queries": top_queries,
        "rising_queries": rising_queries,
    }


def persist(cfg: Config, bundle: dict[str, Any]) -> None:
    db = MetricsDB(Path(cfg.report.output_dir).parent / "data" / "metrics.db")
    try:
        db.save_ga4(bundle["ga4_current"])
        db.save_ga4(bundle["ga4_previous"])
        if bundle["gsc_current"] is not None:
            db.save_gsc(bundle["gsc_current"])
        if bundle["gsc_previous"] is not None:
            db.save_gsc(bundle["gsc_previous"])
    finally:
        db.close()


def build_report_payload(cfg: Config, bundle: dict[str, Any]) -> dict[str, Any]:
    ga4_current: GA4Metrics = bundle["ga4_current"]
    ga4_previous: GA4Metrics = bundle["ga4_previous"]
    deltas_ga4 = compute_ga4_deltas(ga4_current, ga4_previous)
    deltas_gsc = (
        compute_gsc_deltas(bundle["gsc_current"], bundle["gsc_previous"])
        if bundle["gsc_current"] and bundle["gsc_previous"]
        else []
    )
    alerts = check_alerts(
        ga4_current,
        ga4_previous,
        bundle["gsc_current"],
        bundle["gsc_previous"],
        cfg.thresholds,
    )

    cur_start, cur_end = bundle["window"]["current"]
    prev_start, prev_end = bundle["window"]["previous"]
    period = {
        "start": cur_start.isoformat(),
        "end": cur_end.isoformat(),
        "previous_start": prev_start.isoformat(),
        "previous_end": prev_end.isoformat(),
    }

    insight_payload = build_payload(
        site_name=cfg.site.name,
        site_url=cfg.site.url,
        comparison=cfg.report.comparison,
        period=period,
        ga4_current=_as_dict(ga4_current),
        ga4_previous=_as_dict(ga4_previous),
        gsc_current=_as_dict(bundle["gsc_current"]),
        gsc_previous=_as_dict(bundle["gsc_previous"]),
        deltas_ga4=_as_dict(deltas_ga4),
        deltas_gsc=_as_dict(deltas_gsc),
        top_pages=_as_dict(bundle["top_pages"]),
        channels=_as_dict(bundle["channels"]),
        top_queries=_as_dict(bundle["top_queries"]),
        rising_queries=_as_dict(bundle["rising_queries"]),
        alerts=[asdict(a) for a in alerts],
    )

    return {
        "period": period,
        "deltas_ga4": deltas_ga4,
        "deltas_gsc": deltas_gsc,
        "alerts": alerts,
        "insight_payload": insight_payload,
    }


def run_daily(
    cfg: Config,
    end: date,
    anthropic_client: Anthropic,
    send_email: bool = False,
) -> dict[str, Any]:
    """1 日分のレポートを生成しファイル保存。email=True でメール送信もする。"""
    bundle = collect_all(cfg, end)
    persist(cfg, bundle)

    built = build_report_payload(cfg, bundle)
    insight: InsightResult = generate_insights(
        anthropic_client, cfg.claude, built["insight_payload"]
    )

    site = {"name": cfg.site.name, "url": cfg.site.url}
    md, html = report_gen.render(
        site=site,
        period=built["period"],
        comparison=cfg.report.comparison,
        ga4_current=bundle["ga4_current"],
        ga4_previous=bundle["ga4_previous"],
        gsc_current=bundle["gsc_current"],
        gsc_previous=bundle["gsc_previous"],
        deltas_ga4=built["deltas_ga4"],
        deltas_gsc=built["deltas_gsc"],
        top_pages=bundle["top_pages"],
        channels=bundle["channels"],
        top_queries=bundle["top_queries"],
        rising_queries=bundle["rising_queries"],
        alerts=built["alerts"],
        insights_markdown=insight.markdown,
        claude_model=insight.model,
    )

    cur_end: date = bundle["window"]["current"][1]
    tag = f"harinavi-{cur_end.isoformat()}"
    md_path, html_path = report_gen.save(cfg.report.output_dir, tag, md, html)

    result = {
        "md_path": str(md_path),
        "html_path": str(html_path),
        "insight": {
            "model": insight.model,
            "input_tokens": insight.input_tokens,
            "output_tokens": insight.output_tokens,
            "cache_read_tokens": insight.cache_read_tokens,
        },
        "tag": tag,
        "end": cur_end.isoformat(),
    }

    if send_email:
        from .notifier.email import send_report

        subject = f"[ハリナビ] マーケティングレポート {cur_end.isoformat()}"
        send_report(
            recipients=cfg.report.recipients,
            subject=subject,
            html_body=html,
            markdown_body=md,
            smtp=cfg.env,
            attachments=[md_path, html_path],
        )
        result["emailed_to"] = cfg.report.recipients

    # 最新ペイロードを chat から参照できるように保存
    latest = Path(cfg.report.output_dir) / "latest.json"
    latest.write_text(
        json.dumps(_as_dict(built["insight_payload"]), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result["latest_json"] = str(latest)
    result["generated_at"] = datetime.now().isoformat(timespec="seconds")
    return result


def load_latest_payload(cfg: Config) -> dict[str, Any]:
    path = Path(cfg.report.output_dir) / "latest.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} が見つかりません。`python -m src.main report` を先に実行してください。"
        )
    return json.loads(path.read_text(encoding="utf-8"))
